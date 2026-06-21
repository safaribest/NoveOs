"""BeatPlanner Step —— 六段式节拍分配。"""
from __future__ import annotations

import logging

from core.writing.context import ChapterContext
from core.writing.prompts import get_agent_llm_params, log_full_prompt
from core.writing.steps.base import PipelineStep, StepFailure, StepResult

logger = logging.getLogger("novel-os.steps.beat_planner")


class BeatPlannerStep(PipelineStep):
    """将 Director 任务卡转换为弹性节拍分配表。

    原 batch_writer._call_beat_planner 的迁移版本。
    """

    name = "BeatPlanner"

    def execute(self, ctx: ChapterContext) -> StepResult:
        if ctx.beat_plan:
            logger.info("[BeatPlanner] 第 %d 章 复用已有节拍表", ctx.chapter_num)
            return StepResult(content=ctx.beat_plan, metadata={"agent": "BeatPlanner", "reused": True})

        director_prompt = ctx.director_prompt
        if not director_prompt:
            raise StepFailure(
                step_name=self.name,
                reason="Director 任务卡为空，无法生成节拍表",
                retryable=True,
            )

        system = self._build_system_prompt()
        user = self._build_user_prompt(ctx, director_prompt)

        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "beat_planner", 0.1, 3000)
        log_full_prompt("beat_planner", ctx.chapter_num, system, user, project_id=ctx.project_id)

        try:
            result = ctx.llm.call_for_agent("beat_planner", system, user, temperature=temp, max_tokens=max_tok)
        except Exception as exc:
            raise StepFailure(
                step_name=self.name,
                reason=f"LLM 调用失败: {exc}",
                retryable=True,
            )

        ctx.beat_plan = result
        logger.info("[BeatPlanner] 第 %d 章 节拍分配完成", ctx.chapter_num)
        return StepResult(content=result, metadata={"agent": "BeatPlanner"})

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "你是 BeatPlanner（节拍分配师）。\n"
            "你的任务是将导演任务卡拆解为节拍分配表，精确到每段的字数范围和核心内容。\n"
            "你只做字数分配和内容规划，不输出正文。\n"
            "\n【核心职责 - 绝对不可违背】\n"
            "1. 节拍表中必须包含至少 3-5 个对话场景节点。\n"
            "2. 对话不是点缀，是推动情节的核心手段——没有对话的节拍表是失败的。\n"
            "3. 每个对话节点必须标注：参与人物、核心冲突、预估字数。\n"
            "4. 禁止每章使用完全相同的节拍结构，必须根据本章类型灵活调整。\n"
            "5. 【情绪配比约束】每个节拍必须标注预期情绪类型（爽/甜/平/虐），\n"
            "   全章情绪配比必须符合品类目标——爽文以爽为主（≥35%），\n"
            "   甜宠以甜为主（≥50%），虐恋以虐为主（≥25%），\n"
            "   平情绪不得超过30%，连续3个节拍同情绪视为失败。"
        )

    def _build_user_prompt(self, ctx: ChapterContext, director_prompt: str) -> str:
        chapter_num = ctx.chapter_num
        target = ctx.word_target
        tol = ctx.word_tolerance
        min_w = ctx.word_min
        max_w = ctx.word_max

        BEAT_VARIATIONS = {
            0: ("起-承1-承2-转-合1-合2", "标准六段式，适合常规推进章"),
            1: ("起-转-承-转-合1-合2", "快节奏，核心冲突提前爆发，适合转折章"),
            2: ("起-承-承-承-转-合", "慢燃铺垫，适合信息量大的解密章"),
            3: ("起-对话交锋1-对话交锋2-转-合1-合2", "对话主导，适合信息释放和立场对峙章"),
            4: ("起-承-转-转-转-合", "多转折连击，适合高潮章"),
            5: ("悬念-起-承-转-合-钩子", "双重悬念框架，适合钩子章"),
        }
        variation_idx = (chapter_num - 1) % len(BEAT_VARIATIONS)
        beat_structure, beat_desc = BEAT_VARIATIONS[variation_idx]

        genre_dna = ctx.genre_dna
        dna_text = ""
        if genre_dna:
            dna_text = (
                f"\n【品类DNA基准】\n"
                f"- 平均句长: {genre_dna.get('avg_sentence_length', 'N/A')} 字\n"
                f"- 道说比: {genre_dna.get('dao_shuo_ratio', 'N/A')}\n"
                f"- 对话占比: {genre_dna.get('dialogue_ratio', 'N/A')}%"
            )

        # ★ 修复（2026-06-20）：注入番茄课程情绪配比约束
        emotion_injection = ""
        try:
            from core.writing.prompts import build_fanqie_injection
            emotion_injection = build_fanqie_injection(chapter_num, ctx.book_config.genre)
        except Exception:
            pass

        return (
            f"【任务】为第{chapter_num}章生成节拍分配表。\n"
            f"\n【本章节拍结构——必须遵循，禁止套固定六段式模板】\n"
            f"类型：{beat_desc}\n"
            f"结构：{beat_structure}\n"
            f"请按此结构分配字数和规划内容，不要机械套用起-承1-承2-转-合1-合2。\n\n"
            f"【字数要求】总字数 {min_w}~{max_w} 字（目标 {target} 字）\n"
            f"- 各段字数按结构弹性分配，没有固定比例。核心冲突段可占30-40%，铺垫段可压缩。\n"
            f"{dna_text}\n"
            f"{emotion_injection}\n"
            f"\n【情绪配比规划 - 绝对不可违背】\n"
            f"每个节拍必须标注预期情绪（爽/甜/平/虐），全章情绪分布必须符合上述品类目标。\n"
            f"禁止全章只有一种情绪，禁止连续3个节拍同为'平'情绪。\n"
            f"\n【导演任务卡】\n{director_prompt}\n"
            f"\n【对话场景规划 - 绝对不可违背】\n"
            f"六段式节拍表中必须包含至少 3-5 个对话场景节点。\n"
            f"每个对话节点必须标注：\n"
            f"1. 段名标记：在对应段名后标注【对话场景】\n"
            f"2. 参与人物（2-3人）\n"
            f"3. 核心冲突（不是闲聊，必须推进情节或揭示秘密）\n"
            f"4. 预估对话字数（确保总对话字数 ≥ {int(target * 0.25)} 字，即总字数的25%）\n"
            f"\n对话节点分布建议：\n"
            f"- 起：1个对话（引出悬念或人物关系）\n"
            f"- 承1-2：1-2个对话（铺垫升级，信息交换）\n"
            f"- 转：1个对话（核心冲突爆发，情绪对峙）\n"
            f"- 合1-2：1个对话（情绪释放或钩子铺垫）\n"
            f"\n【输出格式】\n"
            f"按六段输出，每段包含：\n"
            f"1. 段名（起/承1/承2/转/合1/合2）【对话场景】（如该段包含对话）\n"
            f"2. 字数范围\n"
            f"3. 核心内容简述（2-3句）\n"
            f"4. 对话场景规划（如有）：人物+冲突+预估字数\n"
            f"5. 必须包含的伏笔/债务/钩子（如有）\n"
            f"\n【对话字数自检】\n"
            f"输出完成后，统计所有对话节点的预估字数总和，确保 ≥ {int(target * 0.25)} 字。\n"
            f"如果不足，调整对话节点数量或单节点字数，直到达标。\n"
            f"\n禁止输出任何正文内容。"
        )
