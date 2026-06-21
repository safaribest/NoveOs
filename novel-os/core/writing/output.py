"""写作流水线输出模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class WriteResult:
    """单章写作结果。"""

    chapter_num: int
    success: bool
    final_content: str
    word_count: int
    gate_level: str  # "PASS" / "WARN" / "BLOCKING"
    attempts: int
    saved_path: Path | None = None
    audit_report: dict[str, Any] = field(default_factory=dict)
