"""Quality Gates Guard —— 将现有 QualityGates 接入 Guard Registry。"""
from __future__ import annotations

from typing import Any

from core.guards.base import BaseGuard, GuardResult
from core.quality_gates import QualityGates


class QualityGateGuard(BaseGuard):
    """包装 QualityGates，提供 Guard Registry 统一接口。"""

    guard_id = "quality_gate"
    description = "质量门检查：字数、红线词、禁用词、他字密度"
    default_level = "BLOCKING"

    def __init__(self, gates: QualityGates) -> None:
        self._gates = gates

    def run(self, content: str, context: dict[str, Any]) -> GuardResult:
        audit_report = context.get("audit_report", {})
        result = self._gates.audit(content, audit_report)
        return GuardResult(
            guard_id=self.guard_id,
            level=result.level,
            message="; ".join(result.reasons) if result.reasons else "通过",
            metadata=result.metrics or {},
        )

    def calibrate(self, hits: int, total: int) -> dict[str, Any]:
        if total == 0:
            return {}
        hit_rate = hits / total
        adjustments: dict[str, Any] = {}
        if hit_rate < 0.05:
            adjustments["tighten"] = "收紧阈值（当前过于宽松）"
        elif hit_rate > 0.3:
            adjustments["loosen"] = "放宽阈值（当前过于严格）"
        return adjustments
