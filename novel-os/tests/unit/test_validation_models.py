"""校验模型单元测试。"""
from __future__ import annotations

from core.validation.models import ValidationIssue, ValidationResult


def test_validation_result_verdict() -> None:
    result = ValidationResult(verdict="PASS", issues=[])
    assert result.verdict == "PASS"


def test_validation_result_to_dict() -> None:
    issue = ValidationIssue(level="WARN", category="字数", message="字数不足")
    result = ValidationResult(verdict="WARN", issues=[issue])
    d = result.to_dict()
    assert d["verdict"] == "WARN"
    assert len(d["issues"]) == 1
    assert d["issues"][0]["level"] == "WARN"


def test_validation_issue_detail_default() -> None:
    issue = ValidationIssue(level="BLOCK", category="红线词", message="命中")
    assert issue.detail == {}
