"""Comparer —— before/after 对比报告生成器。

职责:
1. 对比两批审计数据 (before vs after)
2. 逐指标计算改善/恶化
3. 检测古德哈特预警（某指标改善但另一指标恶化）
4. 验证每条提案的预期是否达成
5. 生成人类可读的 ComparisonReport
"""

from __future__ import annotations

import logging
from typing import Any

from core.outer_loop.models import (
    AssetChange,
    AuditBatch,
    AuditRecord,
    ComparisonReport,
    MetricComparison,
)

logger = logging.getLogger("novel-os.outer_loop.comparer")


class Comparer:
    """对比报告生成器。"""

    # 对比指标列表（AuditRecord.to_dict() 中的 key → 显示名 → 方向）
    COMPARE_METRICS: dict[str, dict] = {
        "rule_score_total":       {"label": "AI味综合评分",     "lower_is_better": True},
        "ta_density":             {"label": "他字密度",          "lower_is_better": True},
        "banned_total":           {"label": "禁用词命中数",      "lower_is_better": True},
        "burstiness":             {"label": "突发性(burstiness)","lower_is_better": False},
        "perplexity":             {"label": "困惑度(perplexity)", "lower_is_better": False},
        "overall_human_score":    {"label": "人类写作评分",      "lower_is_better": False},
        "not_x_but_y_count":      {"label": "'不是X是Y'次数",    "lower_is_better": True},
        "xiang_count":            {"label": "'像…'比喻次数",     "lower_is_better": True},
        "emotion_label_count":    {"label": "情绪标签次数",      "lower_is_better": True},
        "cn_number_density":      {"label": "中文数词密度",      "lower_is_better": True},
        "precise_number_count":   {"label": "精确数字次数",      "lower_is_better": True},
        "sudden_count":           {"label": "'突然'出现次数",    "lower_is_better": True},
        "dialogue_ratio":         {"label": "对话占比",          "lower_is_better": None},  # 看是否在范围内
        "avg_sentence_length":    {"label": "平均句长",          "lower_is_better": None},  # 看是否在范围内
        "avg_para_length":        {"label": "平均段长",          "lower_is_better": None},  # 看是否在范围内
        "iwr_score":              {"label": "IWR悬念分",         "lower_is_better": False},
        "sensory_count":          {"label": "感官描写次数",      "lower_is_better": False},
        "style_critic_issues":    {"label": "StyleCritic问题数", "lower_is_better": True},
        "validator_issues_count": {"label": "Validator问题数",   "lower_is_better": True},
        "fanqie_opening_hook":      {"label": "番茄开篇钩子",     "lower_is_better": False},
        "fanqie_ending_hook":       {"label": "番茄章末钩子",     "lower_is_better": False},
        "fanqie_climax_count":      {"label": "番茄爽点密度",     "lower_is_better": None},
        "fanqie_course_score":      {"label": "番茄课程综合评分", "lower_is_better": False},
    }

    def compare(
        self,
        before: AuditBatch,
        after: AuditBatch,
        proposals: list[AssetChange] | None = None,
    ) -> ComparisonReport:
        """生成完整对比报告。"""
        records_before = [r for r in before.records if r.validator_verdict != "ERROR"]
        records_after = [r for r in after.records if r.validator_verdict != "ERROR"]

        comparisons: list[MetricComparison] = []
        goodhart_alerts: list[str] = []

        for metric_key, cfg in self.COMPARE_METRICS.items():
            before_vals = [getattr(r, metric_key, 0) for r in records_before if metric_key in r.to_dict()]
            after_vals = [getattr(r, metric_key, 0) for r in records_after if metric_key in r.to_dict()]

            if not before_vals or not after_vals:
                continue

            before_avg = sum(before_vals) / len(before_vals)
            after_avg = sum(after_vals) / len(after_vals)
            delta = after_avg - before_avg

            if before_avg == 0:
                delta_pct = 0 if delta == 0 else float("inf")
            else:
                delta_pct = delta / abs(before_avg)

            # 判定方向
            direction = self._judge_direction(delta, cfg.get("lower_is_better"))

            mc = MetricComparison(
                metric_name=metric_key,
                before_avg=round(before_avg, 4),
                after_avg=round(after_avg, 4),
                delta=round(delta, 4),
                delta_pct=round(delta_pct, 4),
                direction=direction,
            )

            # 古德哈特预警：lower_is_better=True 的指标如果 after > before
            if direction == "worsened" and cfg.get("lower_is_better") in (True, False):
                if delta_pct > 0.10:  # 恶化超10%
                    mc.goodhart_warning = (
                        f"{cfg['label']} 恶化 {delta_pct:.0%} "
                        f"({before_avg:.3f} → {after_avg:.3f})"
                    )
                    goodhart_alerts.append(mc.goodhart_warning)

            comparisons.append(mc)

        # 验证提案预期
        proposal_accuracy: dict[str, bool] = {}
        if proposals:
            for p in proposals:
                proposal_accuracy[p.asset_path] = self._verify_proposal(p, comparisons)

        # 总体判定
        improved = sum(1 for c in comparisons if c.direction == "improved")
        worsened = sum(1 for c in comparisons if c.direction == "worsened")
        unchanged = sum(1 for c in comparisons if c.direction == "unchanged")

        if improved > worsened and len(goodhart_alerts) == 0:
            verdict = "improved"
        elif len(goodhart_alerts) > 0:
            verdict = "worsened"
        else:
            verdict = "unchanged"

        summary = (
            f"本轮对比: {improved}项改善, {worsened}项恶化, {unchanged}项持平。"
            f"平均AI味评分: {before.avg_rule_score:.3f} → {after.avg_rule_score:.3f}。"
            + (f" ⚠️ 古德哈特预警: {'; '.join(goodhart_alerts[:3])}" if goodhart_alerts else "")
        )

        fanqie_summary = self._fanqie_summary(records_before, records_after)

        return ComparisonReport(
            round_num=0,  # 由 runner 注入
            metrics=comparisons,
            summary=summary,
            goodhart_alerts=goodhart_alerts,
            proposal_accuracy=proposal_accuracy,
            overall_verdict=verdict,
            fanqie_summary=fanqie_summary,
        )

    @staticmethod
    def _judge_direction(delta: float, lower_is_better: bool | None) -> str:
        """判断指标变化方向。"""
        if abs(delta) < 0.001:
            return "unchanged"
        if lower_is_better is True:
            return "improved" if delta < 0 else "worsened"
        elif lower_is_better is False:
            return "improved" if delta > 0 else "worsened"
        else:
            return "unchanged"  # 无方向性判断

    @staticmethod
    def _fanqie_summary(
        before_records: list[AuditRecord], after_records: list[AuditRecord]
    ) -> str:
        """生成番茄课程指标摘要。"""

        def _avg_bool(records: list[AuditRecord], attr: str) -> float:
            if not records:
                return 0.0
            return sum(1 for r in records if getattr(r, attr, False)) / len(records)

        def _avg_num(records: list[AuditRecord], attr: str) -> float:
            if not records:
                return 0.0
            return sum(getattr(r, attr, 0) for r in records) / len(records)

        return (
            f"番茄课程: 开篇钩子 {_avg_bool(before_records, 'fanqie_opening_hook'):.0%} → "
            f"{_avg_bool(after_records, 'fanqie_opening_hook'):.0%}, "
            f"章末钩子 {_avg_bool(before_records, 'fanqie_ending_hook'):.0%} → "
            f"{_avg_bool(after_records, 'fanqie_ending_hook'):.0%}, "
            f"爽点密度 {_avg_num(before_records, 'fanqie_climax_count'):.2f} → "
            f"{_avg_num(after_records, 'fanqie_climax_count'):.2f}, "
            f"综合评分 {_avg_num(before_records, 'fanqie_course_score'):.3f} → "
            f"{_avg_num(after_records, 'fanqie_course_score'):.3f}"
        )

    def _verify_proposal(
        self, proposal: AssetChange, comparisons: list[MetricComparison]
    ) -> bool:
        """验证单条提案预期是否达成。"""
        # 简单启发式：检查关联的资产路径是否对应了改善的指标
        path = proposal.asset_path.lower()

        mapping = {
            "max_ta_density": "ta_density",
            "min_burstiness": "burstiness",
            "max_perplexity": "perplexity",
            "max_sudden_count": "sudden_count",
            "max_not_x_but_y": "not_x_but_y_count",
            "max_xiang": "xiang_count",
            "max_cn_numbers": "cn_number_density",
            "sensory_min_per_500": "sensory_count",
        }

        for asset_hint, metric_key in mapping.items():
            if asset_hint in path:
                for c in comparisons:
                    if c.metric_name == metric_key:
                        return c.direction == "improved"
        return True  # 无法验证的默认为达成

    # ── Markdown 报告生成 ──
    def render_markdown(self, report: ComparisonReport) -> str:
        """渲染为人类可读的 Markdown 报告。"""
        lines = [
            f"# 规则优化对比报告 — 第 {report.round_num} 轮",
            "",
            f"**总体判定**: {report.overall_verdict.upper()}",
            "",
            report.summary,
            "",
            "---",
            "",
            "## 逐指标对比",
            "",
            "| 指标 | 改前 | 改后 | 变化 | 方向 |",
            "|------|------|------|------|------|",
        ]

        for mc in report.metrics:
            emoji = {"improved": "✅", "worsened": "❌", "unchanged": "➖"}[mc.direction]
            label = self.COMPARE_METRICS.get(mc.metric_name, {}).get("label", mc.metric_name)
            lines.append(
                f"| {label} | {mc.before_avg} | {mc.after_avg} | "
                f"{mc.delta_pct:+.1%} | {emoji} {mc.direction} |"
            )

        if report.goodhart_alerts:
            lines.append("")
            lines.append("## ⚠️ 古德哈特预警")
            for alert in report.goodhart_alerts:
                lines.append(f"- {alert}")

        if report.proposal_accuracy:
            lines.append("")
            lines.append("## 提案验证")
            for path, ok in report.proposal_accuracy.items():
                lines.append(f"- {'✅' if ok else '❌'} {path}")

        if report.fanqie_summary:
            lines.append("")
            lines.append("## 番茄课程指标摘要")
            lines.append(report.fanqie_summary)

        return "\n".join(lines)
