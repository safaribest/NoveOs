"""StyleCritic Step —— 多 Agent 风格审查与修订。

通过三个 Specialist Critic（Pattern / Repetition / Voice）并行审查章节，
汇总问题后交给 Reviser 做最小化修改，从而降低 AI 味。
"""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from core.content.metrics import count_chinese_chars
from core.writing.context import ChapterContext
from core.writing.prompts import get_agent_llm_params, log_full_prompt
from core.writing.steps.base import PipelineStep, StepFailure, StepResult
from core.writing.style_rule_engine import StyleIssue, StyleRuleEngine

logger = logging.getLogger("novel-os.steps.style_critic")


class _StyleIssue:
    """单条风格问题。"""

    def __init__(self, critic: str, type_: str, text: str, suggestion: str) -> None:
        self.critic = critic
        self.type = type_
        self.text = text
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, str]:
        return {
            "critic": self.critic,
            "type": self.type,
            "text": self.text,
            "suggestion": self.suggestion,
        }


class _BaseCritic:
    """风格审查员基类。"""

    name = ""

    def __init__(self, llm, project_id: str, chapter_num: int, temperature: float, max_tokens: int) -> None:
        self.llm = llm
        self.project_id = project_id
        self.chapter_num = chapter_num
        self.temperature = temperature
        self.max_tokens = max_tokens

    def check(self, content: str) -> list[_StyleIssue]:
        raise NotImplementedError

    def _call(self, system: str, user: str, agent_name: str) -> str:
        log_full_prompt(agent_name, self.chapter_num, system, user, project_id=self.project_id)
        return self.llm.call_for_agent(
            agent_name,
            system,
            user,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        # 允许模型输出被 markdown 代码块包裹
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
        return json.loads(text)


class _PatternCritic(_BaseCritic):
    """模式审查员：盯着禁用句式和 AI 指纹。"""

    name = "PatternCritic"

    def check(self, content: str) -> list[_StyleIssue]:
        system = (
            "你是 PatternCritic，专门识别中文网文中的 AI 句式指纹。"
            "只输出 JSON，不要解释。"
        )
        user = (
            "请审查以下章节，找出以下问题（每类最多 5 条，优先最严重）：\n"
            "1. '不是X，是Y' 类对比句式（如：不是A，是B / 不是……而是……）\n"
            "2. '像……' 类比喻，尤其是公共库存比喻（像刀、像蛇、像铁板、像离弦的箭）\n"
            "3. 系统面板标记：【】、宿主、面板、属性点、经验条、冷却时间、侵蚀度百分比等\n"
            "4. 情绪标签：恐惧、绝望、愤怒、悲伤、焦虑等直接写出的情绪词\n"
            "5. 精确数字铺陈环境：0.5毫米、45%湿度、47赫兹等无剧情必要的参数\n\n"
            "输出格式：\n"
            "{\"issues\": [{\"type\": \"not_x_but_y\", \"text\": \"原文片段\", \"suggestion\": \"修改建议\"}, ...]}\n\n"
            f"【章节正文】\n{content}\n"
        )
        raw = self._call(system, user, "style_pattern_critic")
        try:
            data = self._parse_json(raw)
        except Exception as exc:
            logger.warning("[StyleCritic] PatternCritic JSON 解析失败: %s", exc)
            return []
        return [
            _StyleIssue(self.name, item.get("type", ""), item.get("text", ""), item.get("suggestion", ""))
            for item in data.get("issues", [])
            if item.get("text")
        ]


class _RepetitionCritic(_BaseCritic):
    """重复审查员：盯着复读意象和同质开头。"""

    name = "RepetitionCritic"

    def check(self, content: str) -> list[_StyleIssue]:
        # 先本地统计高频意象，帮助 LLM 聚焦
        keywords = ["虎口", "旧疤", "黑丝", "识海", "倒影", "污染", "裂缝", "铜锈味", "铁锈味", "透明液体"]
        counts = {kw: len(re.findall(kw, content)) for kw in keywords}
        top = sorted(counts.items(), key=lambda x: -x[1])[:5]
        top_str = ", ".join(f"{kw}:{c}" for kw, c in top if c > 0)

        system = (
            "你是 RepetitionCritic，专门识别章节内的重复意象和机械开头。"
            "只输出 JSON，不要解释。"
        )
        user = (
            "请审查以下章节，找出以下问题（每类最多 5 条）：\n"
            "1. 同一意象反复出现（如虎口、旧疤、黑丝、识海、倒影、污染、裂缝、铜锈味等）\n"
            "2. 段落开头高度重复（如连续多段以'秦命把/秦命看/秦命站/秦命没'开头）\n"
            "3. 同一场景反复用同一种身体反应入口（如每段都写'虎口旧疤'）\n\n"
            "输出格式：\n"
            "{\"issues\": [{\"type\": \"repeated_image\", \"text\": \"原文片段\", \"suggestion\": \"修改建议\"}, ...]}\n\n"
            f"【本地高频意象统计】{top_str}\n\n"
            f"【章节正文】\n{content}\n"
        )
        raw = self._call(system, user, "style_repetition_critic")
        try:
            data = self._parse_json(raw)
        except Exception as exc:
            logger.warning("[StyleCritic] RepetitionCritic JSON 解析失败: %s", exc)
            return []
        return [
            _StyleIssue(self.name, item.get("type", ""), item.get("text", ""), item.get("suggestion", ""))
            for item in data.get("issues", [])
            if item.get("text")
        ]


class _VoiceCritic(_BaseCritic):
    """声线审查员：盯着段落节奏和对话。"""

    name = "VoiceCritic"

    def check(self, content: str) -> list[_StyleIssue]:
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        lengths = [len(re.findall(r"[\u4e00-\u9fff]", p)) for p in paragraphs]
        avg = sum(lengths) / max(len(lengths), 1)
        short_ratio = sum(1 for x in lengths if x <= 10) / max(len(lengths), 1)

        system = (
            "你是 VoiceCritic，专门审查中文网文的段落节奏和人物声线。"
            "只输出 JSON，不要解释。"
        )
        user = (
            "请审查以下章节，找出以下问题（每类最多 5 条）：\n"
            "1. 段落过度碎片化（大量 10 字以下短段）或过度均匀\n"
            "2. 对话标签单一（通篇用'说/道'，或过度使用'低语/沉声道/冷声道'）\n"
            "3. 人物台词没有个性，所有人说话像一个作者\n"
            "4. 叙述句被不必要的句号切得太碎\n\n"
            "输出格式：\n"
            "{\"issues\": [{\"type\": \"fragmented\", \"text\": \"原文片段\", \"suggestion\": \"修改建议\"}, ...]}\n\n"
            f"【本地统计】段落数 {len(paragraphs)}，平均段长 {avg:.1f} 字，"
            f"≤10字段落占比 {short_ratio*100:.1f}%\n\n"
            f"【章节正文】\n{content}\n"
        )
        raw = self._call(system, user, "style_voice_critic")
        try:
            data = self._parse_json(raw)
        except Exception as exc:
            logger.warning("[StyleCritic] VoiceCritic JSON 解析失败: %s", exc)
            return []
        return [
            _StyleIssue(self.name, item.get("type", ""), item.get("text", ""), item.get("suggestion", ""))
            for item in data.get("issues", [])
            if item.get("text")
        ]


class StyleCriticStep(PipelineStep):
    """多 Agent 风格审查步骤。"""

    name = "StyleCritic"

    def execute(self, ctx: ChapterContext) -> StepResult:
        content = ctx.get_correction("__previous_content__") or ""
        if not content:
            logger.warning("[StyleCritic] 未获取到前置内容，跳过")
            return StepResult(content="", metadata={"skipped": True})

        word_count = count_chinese_chars(content)
        if word_count < 200:
            return StepResult(content=content, metadata={"skipped": "too_short"})

        engine = StyleRuleEngine()
        original_score = engine.score(content)
        logger.info("[StyleCritic] 第 %d 章 原稿规则评分: %.3f", ctx.chapter_num, original_score["score"]["total"])

        # 先自动修复能硬规则修复的问题（如系统面板括号）
        content, hard_issues = engine.fix(content)

        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "style_critic", 0.3, 4000)
        critics = [
            _PatternCritic(ctx.llm, ctx.project_id, ctx.chapter_num, temp, max_tok),
            _RepetitionCritic(ctx.llm, ctx.project_id, ctx.chapter_num, temp, max_tok),
            _VoiceCritic(ctx.llm, ctx.project_id, ctx.chapter_num, temp, max_tok),
        ]

        # 多 Agent 并行审查
        all_issues: list[StyleIssue | _StyleIssue] = []
        all_issues.extend(self._convert_rule_issues(hard_issues))
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(c.check, content): c.name for c in critics}
            for future in futures:
                critic_name = futures[future]
                try:
                    issues = future.result(timeout=120)
                    logger.info("[StyleCritic] %s 发现 %d 个问题", critic_name, len(issues))
                    all_issues.extend(issues)
                except Exception as exc:
                    logger.warning("[StyleCritic] %s 执行失败: %s", critic_name, exc)

        if not all_issues:
            logger.info("[StyleCritic] 第 %d 章 未发现风格问题，跳过修订", ctx.chapter_num)
            return StepResult(
                content=content,
                metadata={"issues": 0, "original_score": original_score},
            )

        # 汇总问题，调用 Reviser
        issue_text = json.dumps(
            [issue.to_dict() if hasattr(issue, "to_dict") else {"rule": issue.rule, "type": issue.type, "text": issue.text, "suggestion": issue.suggestion}
             for issue in all_issues],
            ensure_ascii=False,
            indent=2,
        )
        revised = self._revise(ctx, content, issue_text)

        # 修订后再次运行硬规则引擎，确保没有漏网之鱼
        revised, remaining = engine.fix(revised)
        revised_score = engine.score(revised)
        logger.info("[StyleCritic] 第 %d 章 修改稿规则评分: %.3f", ctx.chapter_num, revised_score["score"]["total"])

        # Judge：如果修改稿评分没有明显变好，或字数暴跌，保留原稿
        final_content = self._judge(content, revised, original_score, revised_score, ctx)

        # ★ 修复（2026-06-20）：收集 issue 类型频率，持久化到文件，
        # 供 build_scene_writer_dna 反哺高频模式（P2-⑤ 初稿去AI味前置）。
        issue_types: dict[str, int] = {}
        for issue in all_issues:
            itype = getattr(issue, "type", "") or getattr(issue, "rule", "unknown")
            issue_types[itype] = issue_types.get(itype, 0) + 1
        self._persist_issue_patterns(ctx.chapter_num, issue_types)

        return StepResult(
            content=final_content,
            metadata={
                "issues": len(all_issues),
                "original_score": original_score["score"]["total"],
                "revised_score": revised_score["score"]["total"],
                "issue_breakdown": {
                    "RuleEngine": len(hard_issues),
                    "PatternCritic": sum(1 for i in all_issues if getattr(i, "critic", "") == "PatternCritic"),
                    "RepetitionCritic": sum(1 for i in all_issues if getattr(i, "critic", "") == "RepetitionCritic"),
                    "VoiceCritic": sum(1 for i in all_issues if getattr(i, "critic", "") == "VoiceCritic"),
                },
                "issue_types": issue_types,
            },
        )

    @staticmethod
    def _persist_issue_patterns(chapter_num: int, issue_types: dict[str, int]) -> None:
        """将本轮 issue 类型频率追加到累积文件，供 SceneWriter DNA 反哺。"""
        import json as _json
        from pathlib import Path as _Path

        patterns_file = _Path(".style_critic_patterns.json")
        data: dict[str, Any] = {}
        if patterns_file.exists():
            try:
                data = _json.loads(patterns_file.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        # 累积每类 issue 的总次数和涉及章节数
        cumulative = data.get("cumulative", {})
        for itype, count in issue_types.items():
            entry = cumulative.get(itype, {"total": 0, "chapters": 0})
            entry["total"] += count
            entry["chapters"] += 1
            cumulative[itype] = entry
        data["cumulative"] = cumulative
        data["last_chapter"] = chapter_num
        data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            patterns_file.write_text(
                _json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("[StyleCritic] 持久化 issue 模式失败: %s", exc)

    @staticmethod
    def _convert_rule_issues(hard_issues: list[StyleIssue]) -> list[_StyleIssue]:
        return [
            _StyleIssue(
                critic="RuleEngine",
                type_=i.type,
                text=i.text,
                suggestion=i.suggestion,
            )
            for i in hard_issues
        ]

    def _judge(
        self,
        original: str,
        revised: str,
        original_score: dict,
        revised_score: dict,
        ctx: ChapterContext,
    ) -> str:
        """Judge：修改稿必须评分更好、字数不过度流失、不能丢失钩子。

        若首轮修订未达标，启用严格 reviser 做一次降级尝试。
        """
        orig_total = original_score["score"]["total"]
        rev_total = revised_score["score"]["total"]
        orig_wc = count_chinese_chars(original)
        rev_wc = count_chinese_chars(revised)
        engine = StyleRuleEngine()

        # 边界：丢失章末钩子直接回退
        if engine.has_ending_hook(original) and not engine.has_ending_hook(revised):
            logger.warning(
                "[StyleCritic] 第 %d 章 修改稿丢失章末钩子，保留原稿",
                ctx.chapter_num,
            )
            return original

        # 字数流失超过 15% 视为异常
        if rev_wc < orig_wc * 0.85:
            logger.warning(
                "[StyleCritic] 第 %d 章 修改稿字数流失过多(%d -> %d)，保留原稿",
                ctx.chapter_num, orig_wc, rev_wc,
            )
            return original

        # 评分明显改善，直接采用
        if rev_total < orig_total - 0.05:
            logger.info(
                "[StyleCritic] 第 %d 章 采用修改稿(%.3f -> %.3f)",
                ctx.chapter_num, orig_total, rev_total,
            )
            return revised

        # 评分未明显改善 —— Loop Engineering 失败降级：启用严格 reviser 再试一次
        logger.info(
            "[StyleCritic] 第 %d 章 首轮修改稿评分未明显改善(%.3f -> %.3f)，启用严格 reviser",
            ctx.chapter_num, orig_total, rev_total,
        )
        strict_revised = self._strict_revise(ctx, original)
        strict_revised, _ = engine.fix(strict_revised)
        strict_score = engine.score(strict_revised)
        strict_total = strict_score["score"]["total"]
        strict_wc = count_chinese_chars(strict_revised)
        logger.info(
            "[StyleCritic] 第 %d 章 严格 reviser 评分: %.3f",
            ctx.chapter_num, strict_total,
        )

        if (
            strict_total < orig_total - 0.05
            and strict_wc >= orig_wc * 0.85
            and (not engine.has_ending_hook(original) or engine.has_ending_hook(strict_revised))
        ):
            logger.info(
                "[StyleCritic] 第 %d 章 采用严格修改稿(%.3f -> %.3f)",
                ctx.chapter_num, orig_total, strict_total,
            )
            return strict_revised

        logger.info(
            "[StyleCritic] 第 %d 章 严格修改稿仍未改善，保留原稿",
            ctx.chapter_num,
        )
        return original

    def _revise(self, ctx: ChapterContext, content: str, issue_text: str) -> str:
        system = (
            "你是 StyleReviser。你的任务是根据风格审查员反馈，对章节做最小化修改。"
            "要求：\n"
            "1. 只修改风格问题（句式、重复、节奏、对话声线），不改动情节、人设、核心事件。\n"
            "2. 保持中文字数接近原文，不要大幅扩写或删减。\n"
            "3. 严禁引入新的 AI 指纹：不要新增'不是X，是Y'、系统面板词、情绪标签、公共库存比喻。\n"
            "4. 段落之间保留空行，不要输出任何说明、JSON、自检表。\n"
            "5. 直接输出修改后的完整正文。"
        )
        user = (
            f"【章节正文】\n{content}\n\n"
            f"【审查员发现的问题】\n{issue_text}\n\n"
            "请输出修改后的完整正文。"
        )
        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "style_reviser", 0.4, 12000)
        log_full_prompt("style_reviser", ctx.chapter_num, system, user, project_id=ctx.project_id)
        try:
            revised = ctx.llm.call_for_agent(
                "style_reviser",
                system,
                user,
                temperature=temp,
                max_tokens=max_tok,
            )
        except Exception as exc:
            logger.warning("[StyleCritic] Reviser 调用失败，返回原文: %s", exc)
            return content
        return revised.strip()

    def _strict_revise(self, ctx: ChapterContext, content: str) -> str:
        """Loop Engineering 失败降级：更严格的 reviser，只聚焦最顽固的 AI 味。"""
        engine = StyleRuleEngine()
        issues = engine.detect(content)
        # 只保留最严重的 5 条
        top_issues = issues[:5]
        issue_text = json.dumps(
            [{"rule": i.rule, "type": i.type, "text": i.text, "suggestion": i.suggestion} for i in top_issues],
            ensure_ascii=False,
            indent=2,
        )
        system = (
            "你是 StrictStyleReviser（严格去 AI 味修订师）。\n"
            "本轮只处理最顽固的 AI 指纹，不做广泛润色。\n"
            "必须遵守：\n"
            "1. 删除所有'不是X，是Y'句式。\n"
            "2. 删除或替换所有'像…'比喻，最多保留 3 处。\n"
            "3. 删除系统面板词：宿主、面板、属性点、经验条、冷却时间、侵蚀度百分比。\n"
            "4. 删除情绪标签词，改为身体反应。\n"
            "5. 删除精确数字铺陈（如0.5毫米/47赫兹），改为体感。\n"
            "6. 不改动情节、人物、核心事件。\n"
            "7. 保持字数接近原文。\n"
            "8. 保留章末悬念钩子。\n"
            "9. 只输出正文，不要说明、JSON、自检表。"
        )
        user = (
            f"【章节正文】\n{content}\n\n"
            f"【必须处理的问题（Top 5）】\n{issue_text}\n\n"
            "请输出修改后的完整正文。"
        )
        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "style_reviser", 0.2, 12000)
        log_full_prompt("strict_style_reviser", ctx.chapter_num, system, user, project_id=ctx.project_id)
        try:
            revised = ctx.llm.call_for_agent(
                "style_reviser",
                system,
                user,
                temperature=temp,
                max_tokens=max_tok,
            )
        except Exception as exc:
            logger.warning("[StyleCritic] Strict reviser 调用失败，返回原文: %s", exc)
            return content
        return revised.strip()
