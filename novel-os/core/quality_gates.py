"""Novel-OS 质量门 —— 自动拦截和修复不符合硬指标的章节。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class GateResult:
    """质量门审计结果。"""
    passed: bool
    level: str  # "PASS" | "WARN" | "BLOCKING"
    reasons: list[str]
    metrics: dict[str, Any] | None = None


class QualityGates:
    """核心审计与拦截逻辑。

    阻断条件（BLOCKING）:
    - 字数 < 4050 或 > 4950
    - 红线词 > 0
    - 禁用词 > 3
    - 他字密度 > 15%
    """

    def __init__(
        self,
        min_words: int = 4050,
        max_words: int = 4950,
        max_redline: int = 0,
        max_forbidden: int = 3,
        max_ta_density: float = 0.15,
    ) -> None:
        self.min_words = min_words
        self.max_words = max_words
        self.max_redline = max_redline
        self.max_forbidden = max_forbidden
        self.max_ta_density = max_ta_density

    def audit(self, chapter_content: str, audit_report: dict[str, Any]) -> GateResult:
        """基于 audit_report 判定 BLOCKING / WARN / PASS。

        audit_report 预期字段:
        - word_count: int
        - ta_density: float (他字密度，0.0~1.0)
        - redline_words: list[str] (触发的红线词)
        - forbidden_words: list[str] (触发的禁用词)
        - broken_sentences: list[str] (句式破坏示例)
        - extra: dict (插件自定义指标)
        """
        reasons: list[str] = []
        word_count = audit_report.get("word_count", 0)
        ta_density = audit_report.get("ta_density", 0.0)
        redline = audit_report.get("redline_words", [])
        forbidden = audit_report.get("forbidden_words", [])
        broken = audit_report.get("broken_sentences", [])

        # BLOCKING 判定
        if word_count < self.min_words:
            reasons.append(f"字数不足: {word_count} < {self.min_words}")
        if word_count > self.max_words:
            reasons.append(f"字数超标: {word_count} > {self.max_words}")
        if len(redline) > self.max_redline:
            reasons.append(f"红线词: {redline}")
        if len(forbidden) > self.max_forbidden:
            reasons.append(f"禁用词超限: {forbidden} ({len(forbidden)} 个)")
        if ta_density > self.max_ta_density:
            reasons.append(f"他字密度超标: {ta_density:.2%} > {self.max_ta_density:.0%}")

        # WARN 判定（ softer 条件）
        warns: list[str] = []
        if broken:
            warns.append(f"句式破坏: {len(broken)} 处")
        if word_count > self.max_words * 0.95 and word_count <= self.max_words:
            warns.append(f"字数接近上限: {word_count}")

        if reasons:
            return GateResult(
                passed=False,
                level="BLOCKING",
                reasons=reasons,
                metrics=audit_report,
            )
        if warns:
            return GateResult(
                passed=True,
                level="WARN",
                reasons=warns,
                metrics=audit_report,
            )
        return GateResult(
            passed=True,
            level="PASS",
            reasons=[],
            metrics=audit_report,
        )

    def truncate_if_needed(self, content: str, max_chars: int = 4950) -> str:
        """在句子边界截断超长章节。

        优先在段落边界截断，其次在句子边界（。！？…），避免切断词语。
        """
        if len(content) <= max_chars:
            return content

        # 尝试在段落边界截断
        truncated = content[:max_chars]
        last_para = truncated.rfind("\n\n")
        if last_para > max_chars * 0.8:
            return truncated[:last_para] + "\n\n[本章因超字数截断，续见下章]"

        # 尝试在句子边界截断
        for delim in ("。」", "。", "！", "？", "…"):
            pos = truncated.rfind(delim)
            if pos > max_chars * 0.8:
                return truncated[: pos + 1] + "\n\n[本章因超字数截断，续见下章]"

        # 兜底：硬截断（尽可能不切断字）
        return truncated.rstrip() + "\n\n[本章因超字数截断，续见下章]"

    def should_retry(
        self, gate_result: GateResult, attempt: int, max_retries: int = 3
    ) -> bool:
        """判定当前失败是否应该触发重试。"""
        if gate_result.level != "BLOCKING":
            return False
        return attempt < max_retries

    def build_retry_prompt(self, original_prompt: str, gate_result: GateResult) -> str:
        """将审计失败原因注入下一轮 Prompt，指导模型修复。

        返回新的完整 prompt。
        """
        if gate_result.level == "PASS":
            return original_prompt

        injection = "\n\n===== 质量门审计反馈（请针对以下问题修复） =====\n"
        injection += f"级别: {gate_result.level}\n"
        for r in gate_result.reasons:
            injection += f"- {r}\n"

        if gate_result.metrics:
            wc = gate_result.metrics.get("word_count")
            if wc is not None:
                injection += f"当前字数: {wc}\n"

        injection += (
            "\n修复要求:\n"
            "1. 严格满足上述指标后再输出。\n"
            "2. 不要简单删除内容，应保持情节连贯性。\n"
            "3. 如果是字数问题，可通过扩充场景描写或对话细节来调整。\n"
            "===== 反馈结束 =====\n"
        )

        return original_prompt + injection
