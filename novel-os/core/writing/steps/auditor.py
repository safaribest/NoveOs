"""Auditor Step —— 结构审计 + LLM 深度审计。"""
from __future__ import annotations

import json
import logging
import re

from core.content.metrics import count_chinese_chars
from core.iwr_analyzer import analyze_chapter
from core.platform_scorer import score_platform_adaptation, compute_genre_dna_match
from core.writing.context import ChapterContext
from core.writing.prompts import get_agent_llm_params, log_full_prompt
from core.writing.steps.base import PipelineStep, StepFailure, StepResult

logger = logging.getLogger("novel-os.steps.auditor")


class AuditorStep(PipelineStep):
    """结构审计 + LLM 深度审计。

    原 batch_writer._call_auditor / _structural_audit / _build_auditor_* 的迁移版本。
    """

    name = "Auditor"

    def execute(self, ctx: ChapterContext) -> StepResult:
        # Auditor 不修改正文，只返回审计报告
        content = ctx.get_correction("__previous_content__")
        if not content:
            raise StepFailure(
                step_name=self.name,
                reason="Auditor 需要前置内容，但 __previous_content__ 未设置",
                retryable=False,
            )

        report = self._structural_audit(ctx, content)

        # LLM 深度审计
        if ctx.book_config.llm.get("auditor_enabled", True):
            try:
                system = self._build_auditor_system_prompt(ctx)
                user = self._build_auditor_user_prompt(ctx, content, report)
                temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "auditor", 0.0, 2000)
                log_full_prompt("auditor", ctx.chapter_num, system, user, project_id=ctx.project_id)
                
                # ★ 使用 call_with_reasoning 获取 reasoning_content（如有）
                llm_report_text = ""
                reasoning_content = None
                if hasattr(ctx.llm, "call_with_reasoning"):
                    resp = ctx.llm.call_with_reasoning(
                        system, user, temperature=temp, max_tokens=max_tok
                    )
                    llm_report_text = resp.content
                    reasoning_content = resp.reasoning_content
                else:
                    llm_report_text = ctx.llm.call_for_agent(
                        "auditor", system, user, temperature=temp, max_tokens=max_tok
                    )
                
                # 尝试解析 JSON
                llm_report = None
                if isinstance(llm_report_text, str):
                    try:
                        llm_report = json.loads(llm_report_text)
                    except json.JSONDecodeError:
                        # 尝试从文本中提取 JSON
                        try:
                            if "```json" in llm_report_text:
                                llm_report_text = llm_report_text.split("```json")[1].split("```")[0].strip()
                            elif "```" in llm_report_text:
                                llm_report_text = llm_report_text.split("```")[1].split("```")[0].strip()
                            llm_report = json.loads(llm_report_text)
                        except Exception:
                            logger.warning("Auditor 返回内容 JSON 解析失败，使用原始文本")
                            llm_report = {"raw_text": llm_report_text[:1000]}
                
                if isinstance(llm_report, dict):
                    report["llm_audit"] = llm_report
                    # ★ 将 reasoning_content 中的逻辑跳跃记录到 audit_report（写作灵感）
                    if reasoning_content:
                        report["llm_reasoning"] = reasoning_content[:2000]  # 限制长度
                        # 提取可能的逻辑跳跃/创意洞察
                        insights = self._extract_reasoning_insights(reasoning_content)
                        if insights:
                            report["reasoning_insights"] = insights
                            logger.info("第 %d 章 Auditor reasoning 提取 %d 条洞察", ctx.chapter_num, len(insights))
                    if any(
                        v.get("score", 10) < 5
                        for v in llm_report.values()
                        if isinstance(v, dict) and "score" in v
                    ):
                        report["llm_flagged"] = True
                logger.info("第 %d 章 LLM深度审计完成", ctx.chapter_num)
            except Exception as exc:
                logger.warning("第 %d 章 LLM深度审计失败（回退到结构审计）: %s", ctx.chapter_num, exc)

        return StepResult(content=content, metadata={"agent": "Auditor", "audit_report": report})

    def _structural_audit(self, ctx: ChapterContext, content: str) -> dict:
        """结构审计（RAG 分析驱动）。"""
        text = content
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        word_count = len(chinese_chars)
        ta_count = text.count("他") + text.count("她") + text.count("它")
        ta_density = ta_count / max(word_count, 1)
        forbidden_words = ["然而", "不得不说", "众所周知", "突然", "竟然", "原来",
                           "与此同时", "紧接着", "果不其然"]
        found_forbidden = [w for w in forbidden_words if w in text]

        metrics = analyze_chapter(text)
        history = ctx.state.list_chapters()
        hist_word_counts = [h.get("word_count", 0) or 0 for h in history if h.get("word_count")]
        platform = score_platform_adaptation(metrics, hist_word_counts)
        genre_dna = ctx.state.get_genre_dna()
        dna_match = compute_genre_dna_match(metrics, genre_dna)

        return {
            "word_count": word_count,
            "ta_density": ta_density,
            "redline_words": [],
            "forbidden_words": found_forbidden,
            "broken_sentences": [],
            "extra": {
                "iwr_score": metrics["iwr_score"],
                "questions_count": metrics["questions_count"],
                "answers_count": metrics["answers_count"],
                "hook_ending": metrics["hook_ending"],
                "sentence_length": metrics["sentence_length"],
                "dialogue_ratio": metrics["dialogue_ratio"],
                "oscillations": metrics["oscillations"],
                "platform_score": platform.get("platform_score", 0),
                "platform_grade": platform.get("platform_grade", "C"),
                "platform_breakdown": platform.get("breakdown", {}),
                "genre_dna_match": dna_match,
            },
        }

    @staticmethod
    def _extract_reasoning_insights(reasoning_content: str) -> list[str]:
        """从 reasoning_content 中提取写作洞察/逻辑跳跃点。"""
        insights = []
        # 提取以 "注意"、"发现"、"但是"、"然而"、"有趣的是" 开头的句子
        patterns = [
            r"注意[到，].*?[。！]",
            r"发现.*?[。！]",
            r"但[是，].*?[。！]",
            r"然而.*?[。！]",
            r"有趣[的是，].*?[。！]",
            r"值得.*?[。！]",
            r"可能.*?[。！]",
            r"建议.*?[。！]",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, reasoning_content)
            for m in matches[:3]:  # 每种类型最多取3条
                if len(m) > 10 and len(m) < 200:
                    insights.append(m)
        # 去重并限制总数
        seen = set()
        unique_insights = []
        for insight in insights:
            if insight not in seen:
                seen.add(insight)
                unique_insights.append(insight)
                if len(unique_insights) >= 5:
                    break
        return unique_insights

    def _build_auditor_system_prompt(self, ctx: ChapterContext) -> str:
        query = ctx.book_config.agent_query.get("auditor", {})
        role = query.get("role", "小说审计师")
        goal = query.get("goal", "审计字数、他字密度、禁用词、年代一致性、IWR、平台适配度")
        return (
            f"你是 {role}。你的目标是：{goal}。\n\n"
            "你需要从以下5个维度对章节进行深度审计，每个维度给出1-10分的评分和具体点评。\n"
            "如果发现问题，必须指出具体位置和修改建议。\n\n"
            "返回严格JSON格式，不要有任何额外文字：\n"
            "{\n"
            '  "dialogue_rhythm": {"score": 1-10, "comment": "对话节奏点评", "issues": ["具体问题1", ...]},\n'
            '  "scene_causality": {"score": 1-10, "comment": "场景因果自洽性", "issues": []},\n'
            '  "character_arc": {"score": 1-10, "comment": "角色弧光进展", "issues": []},\n'
            '  "info_density": {"score": 1-10, "comment": "信息密度评估", "issues": []},\n'
            '  "hook_strength": {"score": 1-10, "comment": "钩子强度", "issues": []},\n'
            '  "overall_comment": "总体评价和优先修改建议"\n'
            "}"
        )

    def _build_auditor_user_prompt(self, ctx: ChapterContext, content: str, report: dict) -> str:
        target = ctx.word_target
        tol = ctx.word_tolerance
        parts = [
            f"【任务】深度审计第{ctx.chapter_num}章。",
            f"【字数标准】目标 {target}±{tol} 字。",
            "【结构审计结果】",
            f"- 字数: {report.get('word_count', 0)}",
            f"- IWR: {report.get('extra', {}).get('iwr_score', 0)}",
            f"- 平台分: {report.get('extra', {}).get('platform_score', 0)} ({report.get('extra', {}).get('platform_grade', '')})",
            f"- DNA匹配: {report.get('extra', {}).get('genre_dna_match', 0)}",
            f"- 他字密度: {report.get('ta_density', 0):.2%}",
            f"- 对话占比: {report.get('extra', {}).get('dialogue_ratio', 0):.1%}",
            f"- 句长: {report.get('extra', {}).get('sentence_length', 0)}",
            "",
            "【待审计正文（前8000字）】",
            content[:8000],
        ]
        return "\n".join(parts)
