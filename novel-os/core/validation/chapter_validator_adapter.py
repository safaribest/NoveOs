"""将现有的 ChapterValidator 包装为新接口。"""
from __future__ import annotations

from typing import Any

from core.chapter_validator import ChapterValidator
from core.validation.chain import Validator
from core.validation.models import ValidationContext, ValidationIssue, ValidationResult


class ChapterValidatorAdapter(Validator):
    """将现有的 ChapterValidator 包装为新 Validator 接口。"""

    name = "ChapterValidator"

    def __init__(self, chapter_validator_instance: ChapterValidator) -> None:
        self._inner = chapter_validator_instance

    def validate(self, content: str, ctx: ValidationContext) -> ValidationResult:
        """调用现有的 ChapterValidator，然后转换结果格式。"""
        context: dict[str, Any] = {
            "chapter_num": ctx.chapter_num,
            "state_manager": ctx.state_manager,
        }
        if ctx.outline:
            context["core_event"] = ctx.outline.core_event

        result = self._inner.validate(content, context)

        # 转换 result 为新的 ValidationResult 格式
        issues = [
            ValidationIssue(
                level=issue.level,
                category=issue.category,
                message=issue.message,
                detail=self._normalize_detail(issue.detail),
            )
            for issue in result.issues
        ]

        return ValidationResult(
            verdict=result.verdict,
            issues=issues,
            metrics=result.metrics,
            auto_fix_text=result.auto_fix_text or None,
        )

    @staticmethod
    def _normalize_detail(detail: Any) -> dict[str, Any]:
        """将旧的任意 detail 转换为新的 dict 格式。"""
        if detail is None:
            return {}
        if isinstance(detail, dict):
            return dict(detail)
        return {"value": detail}
