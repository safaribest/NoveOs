"""校验链 —— 按顺序执行多个 Validator。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.content.metrics import count_chinese_chars
from core.validation.models import (
    ValidationContext,
    ValidationIssue,
    ValidationResult,
)


class Validator:
    """校验器接口。"""

    name: str = ""

    def validate(self, content: str, ctx: ValidationContext) -> ValidationResult:
        raise NotImplementedError


class ValidationChain:
    """校验链：组合多个 Validator，按优先级合并结果。

    执行策略：
    1. 所有 Validator 都执行（不短路）
    2. 收集全部 issues
    3. 按最高 severity 定 verdict：BLOCK > WARN > PASS
    4. 返回合并后的 ValidationResult
    """

    def __init__(self, validators: list[Validator] | None = None) -> None:
        self._validators = validators or []

    def add(self, validator: Validator) -> "ValidationChain":
        self._validators.append(validator)
        return self

    def validate(self, content: str, ctx: ValidationContext) -> ValidationResult:
        all_issues: list[ValidationIssue] = []
        all_metrics: dict[str, Any] = {}
        auto_fix: str | None = None

        for v in self._validators:
            result = v.validate(content, ctx)
            all_issues.extend(result.issues)
            all_metrics.update(result.metrics)
            if result.auto_fix_text:
                auto_fix = result.auto_fix_text
                content = auto_fix  # 链式自动修复：后续 validator 基于修复后文本

        # 判定 verdict
        if any(i.level == "BLOCK" for i in all_issues):
            verdict = "BLOCK"
        elif any(i.level == "WARN" for i in all_issues):
            verdict = "WARN"
        else:
            verdict = "PASS"

        return ValidationResult(
            verdict=verdict,
            issues=all_issues,
            metrics=all_metrics,
            auto_fix_text=auto_fix,
        )
