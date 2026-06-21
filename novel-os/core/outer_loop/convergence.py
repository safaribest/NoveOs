"""ConvergenceDetector —— 收敛判定。

条件:
1. 超过90%的阈值参数连续3轮变动 < 1%
2. 本轮无新的BLOCKING发现
3. 古德哈特预警数 = 0
"""

from __future__ import annotations

import logging
from typing import Any

from core.outer_loop.models import (
    AssetChange,
    ComparisonReport,
    IterationRound,
)

logger = logging.getLogger("novel-os.outer_loop.convergence")

# 被监测收敛的参数（key → 变动容忍度 %）
WATCHED_PARAMS = [
    "max_ta_density", "max_forbidden_patterns", "max_sudden_count",
    "min_burstiness", "max_perplexity", "max_not_x_but_y",
    "max_xiang", "max_cn_numbers", "precise_number_threshold",
    "dialogue_ratio_min", "dialogue_ratio_max",
    "goal_max_rule_score", "goal_max_cn_number_density",
]


class ConvergenceDetector:
    """收敛检测器。

    修复说明（2026-06-20）：
    原实现只记录"已批准提案"中的参数变更，导致批准率低时历史数据稀疏，
    永远报"历史轮次不足"无法判断收敛。现改为：每轮都记录全部 WATCHED_PARAMS
    的当前值快照（通过 RuleReader 读取），不论是否批准、是否变更。
    """

    def __init__(
        self,
        max_stable_rounds: int = 3,
        param_change_tolerance: float = 0.01,
        rule_reader: Any = None,
    ) -> None:
        self.max_stable_rounds = max_stable_rounds
        self.param_change_tolerance = param_change_tolerance
        self._history: list[dict[str, Any]] = []  # 多轮参数历史
        self._rule_reader = rule_reader  # 用于读取全量参数当前值

    def check(
        self,
        current_round: IterationRound,
        comparison: ComparisonReport,
    ) -> dict[str, Any]:
        """返回收敛判定结果。"""
        # 0. 记录本轮参数（全量快照，而非仅批准项）
        self._record_round(current_round)

        # 1. 古德哈特检查
        if comparison.goodhart_alerts:
            return {
                "converged": False,
                "status": "continuing",
                "reason": f"古德哈特预警: {len(comparison.goodhart_alerts)} 条",
                "detail": comparison.goodhart_alerts[:3],
                "stable_rounds": 0,
            }

        # 2. 参数稳定性检查（需要至少 max_stable_rounds 轮历史）
        if len(self._history) < self.max_stable_rounds:
            return {
                "converged": False,
                "status": "continuing",
                "reason": f"历史轮次不足 ({len(self._history)}/{self.max_stable_rounds})",
                "detail": "",
                "stable_rounds": len(self._history),
            }

        # 3. 检查 WATCHED_PARAMS 中 >90% 的参数是否连续N轮变动 < tolerance
        stable_count = 0
        unstable_params: list[str] = []

        for param in WATCHED_PARAMS:
            values = self._get_param_history(param)
            if len(values) < self.max_stable_rounds:
                # 该参数历史不足，按"未稳定"计
                unstable_params.append(f"{param}=历史不足")
                continue

            recent = values[-self.max_stable_rounds:]
            # ★ 修复（2026-06-20）：处理前值为0的边界情况
            # 原代码 if recent[i-1] != 0 会过滤掉前值为0的迭代，
            # 当所有前值都是0时 max() 会因空迭代报 ValueError
            changes = []
            for i in range(1, len(recent)):
                prev = recent[i - 1]
                if prev == 0:
                    # 前值为0：如果当前也是0则无变动，否则视为100%变动
                    changes.append(0.0 if recent[i] == 0 else 1.0)
                else:
                    changes.append(abs(recent[i] - prev) / max(abs(prev), 0.001))
            max_change = max(changes) if changes else 0.0

            if max_change < self.param_change_tolerance:
                stable_count += 1
            else:
                unstable_params.append(f"{param}={max_change:.1%}")

        stable_ratio = stable_count / max(len(WATCHED_PARAMS), 1)

        if stable_ratio >= 0.90:
            return {
                "converged": True,
                "status": "converged",
                "reason": f"参数稳定性达标: {stable_count}/{len(WATCHED_PARAMS)} ({stable_ratio:.0%})",
                "detail": f"不稳定参数: {unstable_params}" if unstable_params else "全部参数稳定",
                "stable_rounds": self.max_stable_rounds,
            }

        return {
            "converged": False,
            "status": "continuing",
            "reason": f"参数稳定性不足: {stable_count}/{len(WATCHED_PARAMS)} ({stable_ratio:.0%})",
            "detail": f"不稳定参数: {unstable_params[:5]}",
            "stable_rounds": 0,
        }

    def _record_round(self, round_data: IterationRound) -> None:
        """记录本轮参数快照（全量当前值，而非仅批准项变更）。

        修复说明：原实现只从已批准提案提取参数变更，批准率低时历史稀疏。
        现改为：优先用 rule_reader 读取全部 WATCHED_PARAMS 的当前值；
        若 rule_reader 不可用，则回退到从提案提取（兼容旧调用方）。
        """
        params: dict[str, Any] = {}

        # 优先路径：用 rule_reader 读取全量当前值
        if self._rule_reader is not None:
            try:
                all_values = self._rule_reader.read_all_current_values()
                for param in WATCHED_PARAMS:
                    if param in all_values:
                        val = all_values[param]
                        if isinstance(val, (int, float)):
                            params[param] = float(val)
            except Exception as exc:
                logger.warning("rule_reader 读取全量参数失败: %s，回退到提案提取", exc)

        # 回退路径：从已批准提案提取（兼容旧调用方）
        if not params:
            for p in round_data.proposals:
                if p.approved:
                    key = p.asset_path.split(".")[-1]
                    if key in WATCHED_PARAMS:
                        params[key] = p.proposed_value

        self._history.append({
            "round": round_data.round_num,
            "params": params,
            "proposals_count": len(round_data.proposals),
            "approved_count": round_data.approved_count,
        })

    def _get_param_history(self, param: str) -> list[float]:
        """获取指定参数在各轮中的值序列。"""
        values: list[float] = []
        for h in self._history:
            if param in h["params"]:
                val = h["params"][param]
                if isinstance(val, (int, float)):
                    values.append(float(val))
        return values

    def reset(self) -> None:
        """重置历史（新书启动时）。"""
        self._history.clear()

    def convergence_report(self) -> str:
        """生成收敛报告。"""
        if not self._history:
            return "无收敛历史数据。"

        lines = [
            "# 收敛报告",
            "",
            f"## 历史 ({len(self._history)} 轮)",
            "",
        ]

        for h in self._history:
            lines.append(f"### 第 {h['round']} 轮")
            lines.append(f"- 提案: {h['proposals_count']} 条, 批准: {h['approved_count']} 条")
            if h["params"]:
                lines.append("- 参数变更:")
                for k, v in h["params"].items():
                    lines.append(f"  - {k}: → {v}")
            lines.append("")

        # 参数趋势
        lines.append("## 参数收敛趋势")
        for param in WATCHED_PARAMS:
            vals = self._get_param_history(param)
            if len(vals) >= 2:
                trend = "→".join(f"{v:.4f}" for v in vals[-5:])
                lines.append(f"- {param}: {trend}")

        return "\n".join(lines)
