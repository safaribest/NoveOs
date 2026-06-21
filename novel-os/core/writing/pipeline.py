"""写作流水线编排 —— 替代 batch_writer.py 的核心逻辑。"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from core.chapter_validator import ChapterValidator, ValidationIssue, ValidationResult
from core.content.metrics import count_chinese_chars
from core.event_bus import AGENT_CALL_COMPLETE, AGENT_CALL_START, EventBus
from core.post_write_validator import PostWriteValidator
from core.writing.context import ChapterContext
from core.writing.output import WriteResult
from core.writing.loop_controller import ChapterGoal, LoopController
from core.writing.steps.base import PipelineStep, StepFailure, StepResult
from core.writing.steps.auditor import AuditorStep
from core.writing.steps.beat_planner import BeatPlannerStep
from core.writing.steps.dialogue_tuner import DialogueTunerStep
from core.writing.steps.director import DirectorStep
from core.writing.steps.expander import ExpanderStep
from core.writing.steps.hook_engineer import HookEngineerStep
from core.writing.steps.polish import PolishStep
from core.writing.steps.scene_writer import SceneWriterStep
from core.writing.steps.spot_fix import SpotFixStep
from core.writing.steps.style_critic import StyleCriticStep
from core.writing.steps.style_retrieval import StyleRetrievalStep

logger = logging.getLogger("novel-os.pipeline")


@dataclass
class PipelineConfig:
    """流水线行为配置。"""

    max_retries: int = 3
    enable_polish: bool = True  # DeepSeek v4-pro 对 Polish 稳定，默认开启
    polish_interval: int = 3  # 每 N 章润色一次
    enable_anti_detect: bool = False  # 反检测改写器默认关闭，避免为骗检测器而制造 AI 味
    skip_hook_if_in_range: bool = False  # ★ 改 False（2026-06-20）：字数达标 ≠ 钩子达标
    skip_dialogue_if_in_range: bool = True  # HookEngineer 后字数达标时跳过 DialogueTuner


class WritingPipeline:
    """10 阶写作流水线编排器。

    职责：
    1. 按顺序执行 Steps
    2. 管理重试逻辑（字数不足 → Expander，结构问题 → 修正回退）
    3. 协调条件跳过（字数达标时跳过 Hook/Dialogue）
    4. 触发校验和反检测改写
    5. 产出最终的 WriteResult

    不直接操作：
    - 文件保存（委托 BatchWriter）
    - 数据库更新（委托 BatchWriter）
    - LLM 调用细节（委托各 Step）
    """

    def __init__(
        self,
        steps: list[PipelineStep] | None = None,
        validator: ChapterValidator | None = None,
        config: PipelineConfig | None = None,
        event_bus: EventBus | None = None,
        project_id: str = "",
        book_config: Any = None,
    ) -> None:
        self._steps = steps if steps is not None else self._default_steps()
        self._validator = validator
        self._cfg = config or PipelineConfig()
        self._step_map: dict[str, PipelineStep] = {s.name: s for s in self._steps}
        self._post_validator = PostWriteValidator()
        self._expander = ExpanderStep()
        self._spot_fix = SpotFixStep()
        self._event_bus = event_bus
        self._project_id = project_id
        # ★ 修复（2026-06-20）：ChapterGoal 从 book_config 动态计算字数目标，
        # 不再用硬编码的 1900/2600（与 book.yaml 的 4500 字标准冲突）
        if book_config is not None:
            self._loop = LoopController(ChapterGoal.from_book_config(book_config))
        else:
            self._loop = LoopController(ChapterGoal())  # 使用更新后的默认值 4050/4950

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def execute(self, ctx: ChapterContext) -> WriteResult:
        """执行完整流水线，返回 WriteResult。"""
        logger.info("=" * 60)
        logger.info("[Pipeline] 开始写作 第 %d 章", ctx.chapter_num)

        attempt = 0
        content = ""
        validation = ValidationResult(verdict="BLOCK", issues=[])
        audit_report: dict[str, Any] = {}
        chapter_title = ""

        corrections: dict[str, str] = {
            "scene_writer": "",
            "hook_engineer": "",
            "dialogue_tuner": "",
            "global": "",
        }

        while self._should_retry(validation, attempt):
            attempt += 1
            logger.info("[Pipeline] 第 %d 章 第 %d 次尝试", ctx.chapter_num, attempt)

            try:
                content = self._run_steps(ctx, corrections)
            except StepFailure as exc:
                logger.warning("[Pipeline] StepFailure: %s - %s", exc.step_name, exc.reason)
                hint = self._step_map.get(exc.step_name, exc).fallback(ctx, exc)
                if hint:
                    corrections[exc.step_name] = hint
                    continue
                break
            except Exception as exc:
                logger.exception("[Pipeline] 未处理异常: %s", exc)
                validation = ValidationResult(
                    verdict="BLOCK",
                    issues=[ValidationIssue("BLOCK", "异常", str(exc))],
                )
                break

            # PostWriteValidator 零成本预检
            post_result = self._post_validator.validate(content)
            if post_result.verdict == "SPOT_FIX":
                logger.info("[Pipeline] 第 %d 章 PostWriteValidator 命中 %d 处", ctx.chapter_num, len(post_result.issues))
                logger.info("[Pipeline] 第 %d 章 跳过 SpotFix，保留原始内容", ctx.chapter_num)

            # ChapterValidator 快速扫描
            quick_check = self._validator.validate(content, {"chapter_num": ctx.chapter_num}) if self._validator else ValidationResult(verdict="PASS", issues=[])
            polish_extra = self._validator.build_retry_feedback(quick_check) if (self._validator and quick_check.issues) else ""
            if quick_check.issues:
                content = quick_check.auto_fix_text or content
                logger.info("[Pipeline] 第 %d 章 Validator 标红 %d 处", ctx.chapter_num, len(quick_check.issues))

            # Polish（当前默认禁用）
            should_polish = self._cfg.enable_polish and ((ctx.chapter_num - 1) % self._cfg.polish_interval == 0 or bool(quick_check.issues))
            if should_polish:
                polish_step = self._step_map.get("Polish")
                if polish_step:
                    logger.info("[Pipeline] 第 %d 章 调用 Polish", ctx.chapter_num)
                    polish_key = self._agent_key(polish_step.name)
                    self._emit_agent_event(AGENT_CALL_START, ctx.chapter_num, polish_key, f"开始 {polish_step.name}")
                    pre_polish_content = content
                    try:
                        ctx.corrections["__previous_content__"] = content
                        ctx.corrections["polish"] = polish_extra
                        result = polish_step.execute(ctx)
                        polished = result.content
                        # Loop Engineering 边界护栏：Polish 不能回灌 AI 味、不能丢钩子、不能大幅丢字数
                        violations = self._loop.check_boundary(pre_polish_content, polished, "Polish")
                        if violations:
                            logger.warning(
                                "[Pipeline] 第 %d 章 Polish 触发 %d 处护栏，回退到 Polish 前:\n%s",
                                ctx.chapter_num, len(violations), "\n".join(violations)
                            )
                            content = pre_polish_content
                        else:
                            content = polished
                    except StepFailure as exc:
                        logger.warning("Polish 失败: %s", exc.reason)
                    finally:
                        self._emit_agent_event(AGENT_CALL_COMPLETE, ctx.chapter_num, polish_key, f"完成 {polish_step.name}")

            # Auditor + ChapterValidator
            auditor_step = self._step_map.get("Auditor")
            if auditor_step:
                auditor_key = self._agent_key(auditor_step.name)
                self._emit_agent_event(AGENT_CALL_START, ctx.chapter_num, auditor_key, f"开始 {auditor_step.name}")
                try:
                    ctx.corrections["__previous_content__"] = content
                    audit_result = auditor_step.execute(ctx)
                    audit_report = audit_result.metadata.get("audit_report", {})
                except Exception as exc:
                    logger.warning("Auditor 失败: %s", exc)
                finally:
                    self._emit_agent_event(AGENT_CALL_COMPLETE, ctx.chapter_num, auditor_key, f"完成 {auditor_step.name}")

            if self._validator:
                validation = self._validator.validate(content, {
                    "chapter_num": ctx.chapter_num,
                    "state_manager": ctx.state,
                    "core_event": ctx.outline.get("core_event", ""),
                })
            else:
                validation = ValidationResult(verdict="PASS", issues=[])

            # Loop Engineering: 目标达成判定 —— 即使 Validator 报 WARN，只要核心目标满足就放行
            if validation.verdict == "WARN" and self._validator:
                dialogue_ratio = validation.metrics.get("dialogue_ratio")
                if self._validator.is_goal_met(content, dialogue_ratio):
                    logger.info("[Pipeline] 第 %d 章 Validator WARN 但核心目标已达成，放行", ctx.chapter_num)
                    validation = ValidationResult(verdict="PASS", issues=[])

            # 反检测改写 + 统计指纹优化
            # 当显式传入空步骤时，跳过后置反检测改写，避免对非真实写作产物误处理
            if validation.verdict != "BLOCK" and self._steps and self._cfg.enable_anti_detect:
                from core.anti_detect_reviser import AntiDetectReviser
                ai_markers = AntiDetectReviser.compute_ai_marker_score(content)
                audit_report["ai_markers"] = ai_markers
                total_score = ai_markers.get("total", 0)
                burstiness = ai_markers.get("burstiness", 0)
                if total_score > 0.6 or burstiness < 0.4:
                    logger.warning(
                        "第 %d 章 AI 痕迹=%.2f, 突发性=%.2f，触发反检测改写",
                        ctx.chapter_num, total_score, burstiness,
                    )
                    anti_detect = AntiDetectReviser()
                    content = anti_detect.revise(content, aggressiveness=0.7)
                    if self._validator:
                        validation = self._validator.validate(content, {
                            "chapter_num": ctx.chapter_num,
                            "state_manager": ctx.state,
                            "core_event": ctx.outline.get("core_event", ""),
                        })
                    audit_report["anti_detect_applied"] = True
                    logger.info("第 %d 章 反检测改写后验证: %s", ctx.chapter_num, validation.verdict)
                else:
                    logger.info(
                        "第 %d 章 AI 痕迹=%.2f, 突发性=%.2f，无需改写",
                        ctx.chapter_num, total_score, burstiness,
                    )
            else:
                logger.info("第 %d 章 反检测改写已关闭", ctx.chapter_num)

            if validation.verdict == "BLOCK":
                block_issues = [i for i in validation.issues if i.level == "BLOCK"]
                logger.warning("ChapterValidator BLOCK: %s",
                               [i.message for i in block_issues])

                # Loop Engineering: 用失败模式指导最小化修正路径
                if self._validator:
                    dialogue_ratio = validation.metrics.get("dialogue_ratio")
                    goal_check = self._loop.check(content, dialogue_ratio)
                    if goal_check.fallback and goal_check.fallback != "full_retry":
                        fb_corr = self._fallback_corrections(goal_check.fallback)
                        corrections = self._merge_corrections(corrections, fb_corr)
                        logger.info(
                            "[Pipeline] 第 %d 章 Loop fallback=%s，注入定向修正指令",
                            ctx.chapter_num, goal_check.fallback,
                        )

                has_overlength = any("字数超标" in i.message for i in block_issues)
                has_shortage = any("字数不足" in i.message for i in block_issues)

                # 字数超标 → 截断
                if has_overlength:
                    content = self._truncate_if_overlength(ctx, content)
                    if self._validator:
                        validation = self._validator.validate(content, {"chapter_num": ctx.chapter_num})
                    if validation.verdict != "BLOCK":
                        break
                    # 截断后仍有其他阻塞问题，合并修正指令继续重试
                    corrections = self._merge_corrections(
                        corrections, self._generate_corrections(validation, audit_report)
                    )
                    logger.info(
                        "[Pipeline] 第 %d 章 截断后仍有 %d 处阻塞问题，继续重试",
                        ctx.chapter_num,
                        len([i for i in validation.issues if i.level == "BLOCK"]),
                    )
                    continue

                # 字数不足 → Expander
                if has_shortage:
                    content = self._try_expand(ctx, content, validation)
                    if self._validator:
                        validation = self._validator.validate(content, {"chapter_num": ctx.chapter_num})
                    if validation.verdict != "BLOCK":
                        break
                    # 第二次
                    short_by2 = ctx.word_min - count_chinese_chars(content)
                    if short_by2 > 0:
                        content = self._try_expand(ctx, content, None, short_by2)
                        if self._validator:
                            validation = self._validator.validate(content, {"chapter_num": ctx.chapter_num})
                        if validation.verdict != "BLOCK":
                            break
                        # 若二次扩写后字数达标但仍有其他阻塞问题，合并修正指令
                        if not any("字数不足" in i.message for i in validation.issues if i.level == "BLOCK"):
                            corrections = self._merge_corrections(
                                corrections, self._generate_corrections(validation, audit_report)
                            )
                            logger.info(
                                "[Pipeline] 第 %d 章 扩写后字数达标但仍有 %d 处阻塞问题，继续重试",
                                ctx.chapter_num,
                                len([i for i in validation.issues if i.level == "BLOCK"]),
                            )
                            continue
                        short_by3 = ctx.word_min - count_chinese_chars(content)
                        corrections = self._merge_corrections(corrections, {
                            "scene_writer": (
                                f"\n字数仍不足，当前{count_chinese_chars(content)}字，"
                                f"需再扩写{max(short_by3, 200)}字。"
                            ),
                            "hook_engineer": "",
                            "dialogue_tuner": "",
                            "global": "",
                        })
                        logger.info("[Pipeline] 第 %d 章 第二次Expander后仍不足，回退 SceneWriter", ctx.chapter_num)
                    else:
                        # 扩写后字数达标但仍有其他阻塞问题，合并修正指令继续重试
                        corrections = self._merge_corrections(
                            corrections, self._generate_corrections(validation, audit_report)
                        )
                        logger.info(
                            "[Pipeline] 第 %d 章 扩写后字数达标但仍有 %d 处阻塞问题，继续重试",
                            ctx.chapter_num,
                            len([i for i in validation.issues if i.level == "BLOCK"]),
                        )
                        continue
                else:
                    corrections = self._merge_corrections(
                        corrections, self._generate_corrections(validation, audit_report)
                    )
                    logger.info("[Pipeline] 第 %d 章 结构问题，回退修正", ctx.chapter_num)
            else:
                break

        # 最终判定
        final_wc = count_chinese_chars(content)
        if validation.verdict == "BLOCK":
            logger.error("[Pipeline] 第 %d 章 最终失败，已用尽 %d 次重试", ctx.chapter_num, attempt)
            return WriteResult(
                chapter_num=ctx.chapter_num,
                success=False,
                final_content=content,
                word_count=final_wc,
                gate_level="BLOCKING",
                attempts=attempt,
                audit_report=audit_report,
            )

        if validation.verdict == "WARN":
            logger.warning("[Pipeline] 第 %d 章 WARN: %s", ctx.chapter_num,
                           [i.message for i in validation.issues])

        logger.info("[Pipeline] 第 %d 章 完成，字数=%d", ctx.chapter_num, final_wc)
        return WriteResult(
            chapter_num=ctx.chapter_num,
            success=True,
            final_content=content,
            word_count=final_wc,
            gate_level=validation.verdict,
            attempts=attempt,
            audit_report=audit_report,
        )

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _should_retry(self, validation: ValidationResult, attempt: int) -> bool:
        return validation.verdict == "BLOCK" and attempt < self._cfg.max_retries

    @staticmethod
    def _merge_corrections(
        old: dict[str, str], new: dict[str, str]
    ) -> dict[str, str]:
        """合并修正指令，避免覆盖已累积的反馈。"""
        merged = dict(old)
        for key, value in new.items():
            if value:
                merged[key] = (merged.get(key, "") + "\n" + value).strip()
        return merged

    @staticmethod
    def _agent_key(step_name: str) -> str:
        """将 Step 类名（如 BeatPlanner）映射为前端使用的 snake_case key（如 beat_planner）。"""
        return re.sub(r"(?<!^)(?=[A-Z])", "_", step_name).lower()

    def _emit_agent_event(self, event_type: str, chapter_num: int, agent: str, detail: str = "") -> None:
        """向前端推送 Agent 调用事件。"""
        if self._event_bus:
            self._event_bus.emit(
                event_type,
                {
                    "chapter_num": chapter_num,
                    "agent": agent,
                    "detail": detail,
                    "project_id": self._project_id,
                },
            )

    def _run_steps(self, ctx: ChapterContext, corrections: dict[str, str]) -> str:
        """按顺序执行 Steps，返回最终正文。"""
        content = ""
        ctx.corrections = corrections.copy()

        for step in self._steps:
            logger.info("[Pipeline] 执行 %s", step.name)

            # 字数保护：SceneWriter 后达标 → 跳过 HookEngineer
            if step.name == "HookEngineer" and self._cfg.skip_hook_if_in_range:
                wc = count_chinese_chars(content)
                if ctx.word_min <= wc <= ctx.word_max:
                    logger.info("[Pipeline] SceneWriter 字数达标(%d)，跳过 HookEngineer", wc)
                    continue

            # 字数保护：HookEngineer 后达标 → 跳过 DialogueTuner
            if step.name == "DialogueTuner" and self._cfg.skip_dialogue_if_in_range:
                wc = count_chinese_chars(content)
                if ctx.word_min <= wc <= ctx.word_max:
                    logger.info("[Pipeline] HookEngineer 后字数达标(%d)，跳过 DialogueTuner", wc)
                    continue

            # 条件跳过：Polish 和 Auditor 不在 _run_steps 中执行
            # Polish 在 execute() 中根据 enable_polish 和间隔触发
            # Auditor 在 execute() 中始终执行（轻量审计）
            if step.name == "Polish" and not self._cfg.enable_polish:
                logger.info("[Pipeline] enable_polish=False，跳过 Polish")
                continue
            if step.name == "Auditor":
                logger.info("[Pipeline] Auditor 将在后续阶段执行，跳过 Step 链")
                continue

            agent_key = self._agent_key(step.name)
            self._emit_agent_event(AGENT_CALL_START, ctx.chapter_num, agent_key, f"开始 {step.name}")

            # 传递当前内容给需要前置内容的 Steps
            if step.name in ("HookEngineer", "DialogueTuner", "StyleCritic", "Polish", "Auditor"):
                ctx.corrections["__previous_content__"] = content

            try:
                result: StepResult = step.execute(ctx)
                content = result.content
            finally:
                self._emit_agent_event(AGENT_CALL_COMPLETE, ctx.chapter_num, agent_key, f"完成 {step.name}")

        return content

    def _truncate_if_overlength(self, ctx: ChapterContext, content: str) -> str:
        """字数超标时按完整句末截断，避免留下半截话。"""
        max_cn = ctx.word_max
        chars = list(re.finditer(r'[\u4e00-\u9fff]', content))
        if len(chars) <= max_cn:
            return content

        # 中文字数上限位置
        max_pos = chars[max_cn - 1].end()
        # 在 0.8*max_cn ~ max_cn 之间找最后一个句末标点
        lower_idx = max(0, int(max_cn * 0.8) - 1)
        lower_pos = chars[lower_idx].start()
        segment = content[lower_pos:max_pos]
        for delim in ("。」", "！』", "？』", "。", "！", "？", "…", "」", "』", "】"):
            idx = segment.rfind(delim)
            if idx != -1:
                cut = lower_pos + idx + len(delim)
                content = content[:cut].rstrip()
                logger.info("[Pipeline] 第 %d 章 在句末截断到 ~%d 中文字符", ctx.chapter_num, max_cn)
                return content

        # 回退：找段落边界
        para_idx = content.rfind("\n\n", lower_pos, max_pos)
        if para_idx != -1:
            content = content[:para_idx].rstrip()
            logger.info("[Pipeline] 第 %d 章 在段落边界截断到 ~%d 中文字符", ctx.chapter_num, max_cn)
            return content

        # 最后回退：硬截断
        content = content[:max_pos].rstrip()
        logger.info("[Pipeline] 第 %d 章 硬截断到 %d 中文字符", ctx.chapter_num, max_cn)
        return content

    def _try_expand(self, ctx: ChapterContext, content: str, validation: ValidationResult | None = None, short_by: int | None = None) -> str:
        """调用 Expander 补充字数。"""
        if short_by is None:
            short_by = ctx.word_min - (validation.metrics.get("word_count", 0) if validation else count_chinese_chars(content))
        short_by = max(short_by, 200)
        logger.info("[Pipeline] 第 %d 章 调用 Expander，缺口 %d 字", ctx.chapter_num, short_by)
        try:
            expanded = self._expander.expand(ctx, content, short_by)
            return content + "\n\n" + expanded
        except StepFailure:
            return content

    def _fallback_corrections(self, fallback: str) -> dict[str, str]:
        """Loop Engineering 失败降级策略 → 定向修正指令。"""
        base: dict[str, str] = {
            "scene_writer": "",
            "hook_engineer": "",
            "dialogue_tuner": "",
            "global": "",
        }
        if fallback == "style_critic_strict":
            base["global"] = (
                "\n【去AI味紧急修正】全文强制检查并删除：'不是X，是Y'句式、"
                "公共库存比喻（像刀/像蛇/像铁板/像离弦的箭）、系统面板词、情绪标签、"
                "精确数字铺陈。改为动作、对话、身体体感表达。"
            )
        elif fallback == "hook_engineer":
            base["hook_engineer"] = (
                "\n【钩子紧急修正】章末必须以问句、动作中断、认知缺口或环境突变收尾，"
                "禁止'主角静止+物品特写+省略号'的AI万能结尾。"
            )
        elif fallback == "outline_dequantify":
            base["global"] = (
                "\n【量化表达降级】大纲/任务卡中的'三层、七日、百年、九道'等精确层级/时间/数量，"
                "在正文中改为模糊体感表达（如'没多久''几层''许多年'），降低中文数词密度。"
            )
        elif fallback == "expander":
            base["scene_writer"] = "\n【字数补充】优先增加事件、对话或动作细节，禁止扩写环境或心理。"
        elif fallback == "truncate":
            base["global"] = "\n【字数精简】删除冗余铺陈和重复叙述，保留核心情节和钩子。"
        elif fallback == "dialogue_tuner":
            base["dialogue_tuner"] = (
                "\n【对话密度修正】对话占比偏离合理区间，调整对话与叙述比例，"
                "使对话自然嵌入情节推进。"
            )
        return base

    def _generate_corrections(self, validation: ValidationResult, audit_report: dict[str, Any]) -> dict[str, str]:
        """根据 ChapterValidator 结果生成各 Agent 的修正指令。"""
        corrections: dict[str, str] = {
            "scene_writer": "",
            "hook_engineer": "",
            "dialogue_tuner": "",
            "global": "",
        }
        extra = audit_report.get("extra", {})

        reasons = [i.message for i in validation.issues] if hasattr(validation, 'issues') else []
        for reason in reasons:
            if any(k in reason for k in ["IWR", "钩子", "悬念", "结尾", "开头"]):
                iwr = extra.get("iwr_score", 0)
                q_count = extra.get("questions_count", 0)
                corrections["hook_engineer"] += (
                    f"\n【钩子修正】当前IWR={iwr}（要求≥2.0），问题数={q_count}（要求≥3）。"
                    f"请在开头增加1个情境悬念，在结尾增加1-2个未解之谜。"
                )
            if any(k in reason for k in ["对话", "道说比", "对白"]):
                dial = extra.get("dialogue_ratio", 0)
                corrections["dialogue_tuner"] += (
                    f"\n【对话修正】当前对话占比={dial:.0%}。请调整对话密度和'道/说'比率。"
                )
            if any(k in reason for k in ["句长", "句子", "过长"]):
                sent = extra.get("sentence_length", 0)
                corrections["scene_writer"] += (
                    f"\n【句长修正】当前平均句长={sent}字。请将过长句子拆分为短句。"
                )
            if any(k in reason for k in ["他密度", "人称", "他字"]):
                ta = extra.get("ta_density", 0)
                corrections["scene_writer"] += (
                    f"\n【人称修正】当前他密度={ta:.2%}。请减少'他/她/它'的使用。"
                )
            if any(k in reason for k in ["平台", "适配", "DNA"]):
                grade = extra.get("platform_grade", "C")
                corrections["global"] += (
                    f"\n【平台适配修正】当前等级{grade}。请整体调整结构。"
                )

        # 强制术语缺失 → 注入补全指令
        missing_terms = []
        for issue in validation.issues:
            if issue.category == "术语" and issue.level in ("BLOCK", "WARN"):
                m = re.search(r"'(.+?)'", issue.message)
                if m:
                    missing_terms.append(m.group(1))
        if missing_terms:
            corrections["scene_writer"] += (
                f"\n【术语补全——绝对优先】当前正文缺失以下世界观核心术语，"
                f"必须在正文中准确出现（禁止意译或替换）：{', '.join(missing_terms)}。"
                f"请在合适场景自然嵌入这些术语，确保读者能看到准确的专有名词。"
            )
            corrections["global"] += (
                f"\n【术语铁律】本章必须包含：{', '.join(missing_terms)}。"
            )

        return corrections

    @classmethod
    def _default_steps(cls) -> list[PipelineStep]:
        """默认 8 阶 Steps。"""
        return [
            DirectorStep(),
            BeatPlannerStep(),
            StyleRetrievalStep(),
            SceneWriterStep(),
            HookEngineerStep(),
            DialogueTunerStep(),
            StyleCriticStep(),
            PolishStep(),
            AuditorStep(),
        ]
