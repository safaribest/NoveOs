"""校验域领域模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.state.models import ChapterOutline


@dataclass
class ValidationIssue:
    """单个校验问题。"""

    level: str  # "PASS" / "WARN" / "BLOCK"
    category: str  # "字数" / "他密度" / "禁用词" / "术语" / "钩子" / "对话"
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """校验结果。"""

    verdict: str  # "PASS" / "WARN" / "BLOCK"
    issues: list[ValidationIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    auto_fix_text: str | None = None  # 自动修复后的文本

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "issues": [
                {"level": i.level, "category": i.category, "message": i.message}
                for i in self.issues
            ],
            "metrics": self.metrics,
        }


@dataclass
class ValidationContext:
    """校验上下文。"""

    chapter_num: int
    word_count: int
    outline: ChapterOutline | None = None
    state_manager: Any | None = None
