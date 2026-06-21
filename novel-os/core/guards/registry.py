"""Guard Registry —— 门禁注册表与编排器。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from core.guards.base import BaseGuard, GuardResult

logger = logging.getLogger("novel-os.guard_registry")

GuardLevel = str  # "BLOCKING" | "WARN" | "PASS" | "INFO"

LEVEL_PRIORITY: dict[str, int] = {
    "BLOCKING": 0,
    "WARN": 1,
    "PASS": 2,
    "INFO": 3,
}


@dataclass
class GuardRegistry:
    """门禁注册表：统一管理所有 Guard 的注册、执行与校准。"""

    _guards: dict[str, BaseGuard] = field(default_factory=dict)
    _stats: dict[str, dict[str, int]] = field(default_factory=dict)

    def register(self, guard: BaseGuard) -> None:
        """注册一个 Guard。"""
        if not guard.guard_id:
            raise ValueError("Guard.guard_id 不能为空")
        self._guards[guard.guard_id] = guard
        self._stats.setdefault(guard.guard_id, {"hits": 0, "total": 0})
        logger.info("Guard 已注册: %s", guard.guard_id)

    def unregister(self, guard_id: str) -> None:
        """注销 Guard。"""
        self._guards.pop(guard_id, None)
        self._stats.pop(guard_id, None)

    def run_all(
        self,
        content: str,
        context: dict[str, Any],
        stop_on_blocking: bool = True,
    ) -> list[GuardResult]:
        """顺序执行所有已注册的 Guard。

        Args:
            content: 待检查文本。
            context: 运行时上下文。
            stop_on_blocking: 遇到 BLOCKING 是否停止后续检查。

        Returns:
            所有 Guard 的检查结果列表（按注册顺序）。
        """
        results: list[GuardResult] = []
        for guard_id, guard in self._guards.items():
            try:
                result = guard.run(content, context)
                self._stats[guard_id]["total"] += 1
                if result.level != "PASS":
                    self._stats[guard_id]["hits"] += 1
                results.append(result)
                if stop_on_blocking and result.level == "BLOCKING":
                    logger.warning("Guard %s BLOCKING，停止后续检查", guard_id)
                    break
            except Exception:
                logger.exception("Guard %s 执行异常", guard_id)
                results.append(
                    GuardResult(
                        guard_id=guard_id,
                        level="BLOCKING",
                        message=f"Guard {guard_id} 内部错误",
                    )
                )
                if stop_on_blocking:
                    break
        return results

    def run_level(
        self,
        content: str,
        context: dict[str, Any],
        target_level: str = "BLOCKING",
    ) -> list[GuardResult]:
        """仅执行指定级别的 Guard（用于分级门禁）。"""
        results: list[GuardResult] = []
        for guard_id, guard in self._guards.items():
            if guard.default_level != target_level:
                continue
            try:
                result = guard.run(content, context)
                self._stats[guard_id]["total"] += 1
                if result.level != "PASS":
                    self._stats[guard_id]["hits"] += 1
                results.append(result)
            except Exception:
                logger.exception("Guard %s 执行异常", guard_id)
                results.append(
                    GuardResult(
                        guard_id=guard_id,
                        level="BLOCKING",
                        message=f"Guard {guard_id} 内部错误",
                    )
                )
        return results

    def calibrate_all(self, threshold: float = 0.1) -> dict[str, dict[str, Any]]:
        """对所有 Guard 执行校准循环。

        命中率低于 threshold 的 Guard 会触发 calibrate()。

        Returns:
            每个 Guard 的校准结果。
        """
        adjustments: dict[str, dict[str, Any]] = {}
        for guard_id, stats in self._stats.items():
            total = stats["total"]
            if total == 0:
                continue
            hit_rate = stats["hits"] / total
            if hit_rate < threshold:
                guard = self._guards.get(guard_id)
                if guard:
                    adj = guard.calibrate(stats["hits"], total)
                    adjustments[guard_id] = adj
                    logger.info(
                        "Guard %s 校准: 命中率 %.2f%% < %.0f%%, 调整=%s",
                        guard_id,
                        hit_rate * 100,
                        threshold * 100,
                        adj,
                    )
        return adjustments

    def record(self, guard_id: str, level: str) -> None:
        """记录外部执行的 Guard 结果（用于校准统计）。"""
        if guard_id not in self._stats:
            return
        self._stats[guard_id]["total"] += 1
        if level != "PASS":
            self._stats[guard_id]["hits"] += 1

    def list_guards(self) -> list[dict[str, str]]:
        """列出所有已注册的 Guard。"""
        return [
            {"guard_id": g.guard_id, "description": g.description, "default_level": g.default_level}
            for g in self._guards.values()
        ]
