"""外层回路数据模型 —— AuditRecord / AssetChange / IterationRound 等。

Loop Engineering 外层回路的核心数据结构：
- 每个审计记录 (AuditRecord) 对接 ChapterValidator + StyleRuleEngine
- 每条提案 (AssetChange) 精确描述 from→to
- 每轮迭代 (IterationRound) 完整可追溯
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 单章审计记录
# ═══════════════════════════════════════════════════════════════
@dataclass
class AuditRecord:
    """单章完整审计数据，聚合 ChapterValidator + StyleRuleEngine + 统计指纹。"""

    chapter_num: int
    word_count: int = 0
    ta_density: float = 0.0
    ta_count: int = 0

    # StyleRuleEngine.score() 输出
    rule_score_total: float = 0.0
    rule_score_breakdown: dict[str, float] = field(default_factory=dict)
    rule_issue_count: int = 0

    # ChapterValidator.validate() 输出
    validator_verdict: str = "PASS"          # PASS / WARN / BLOCK
    validator_issues: list[dict] = field(default_factory=list)
    blocked: bool = False

    # 禁用词命中
    banned_hits: dict[str, list[str]] = field(default_factory=dict)
    banned_total: int = 0

    # 统计指纹
    burstiness: float = 0.0
    perplexity: float = 0.0
    sentence_length_cv: float = 0.0
    overall_human_score: float = 0.0

    # StyleCritic 开销
    style_critic_issues: int = 0
    style_critic_original_score: float = 0.0
    style_critic_revised_score: float = 0.0

    # 对话 / 句长
    dialogue_ratio: float = 0.0
    avg_sentence_length: float = 0.0
    avg_para_length: float = 0.0

    # IWR / 平台
    iwr_score: float = 0.0
    platform_score: float = 0.0
    platform_grade: str = ""

    # 特定AI指纹
    not_x_but_y_count: int = 0
    xiang_count: int = 0
    emotion_label_count: int = 0
    cn_number_density: float = 0.0
    precise_number_count: int = 0
    sudden_count: int = 0
    ending_hook: bool = False
    sensory_count: int = 0

    # 番茄课程指标
    fanqie_opening_hook: bool = False
    fanqie_opening_hook_position: int = 0
    fanqie_climax_count: int = 0
    fanqie_ending_hook: bool = False
    fanqie_emotion_ratio: dict[str, float] = field(default_factory=dict)
    fanqie_course_score: float = 0.0

    # 扩展元数据
    retry_count: int = 0
    pipeline_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典（用于 LLM analysis 和存储）。"""
        return {
            "chapter_num": self.chapter_num,
            "word_count": self.word_count,
            "ta_density": round(self.ta_density, 4),
            "ta_count": self.ta_count,
            "rule_score_total": self.rule_score_total,
            "rule_score_breakdown": self.rule_score_breakdown,
            "rule_issue_count": self.rule_issue_count,
            "validator_verdict": self.validator_verdict,
            "validator_issues_count": len(self.validator_issues),
            "blocked": self.blocked,
            "banned_hits": {k: len(v) for k, v in self.banned_hits.items()},
            "banned_total": self.banned_total,
            "burstiness": round(self.burstiness, 4),
            "perplexity": round(self.perplexity, 4),
            "sentence_length_cv": round(self.sentence_length_cv, 4),
            "overall_human_score": round(self.overall_human_score, 4),
            "style_critic_issues": self.style_critic_issues,
            "style_critic_original_score": self.style_critic_original_score,
            "style_critic_revised_score": self.style_critic_revised_score,
            "dialogue_ratio": round(self.dialogue_ratio, 4),
            "avg_sentence_length": round(self.avg_sentence_length, 1),
            "avg_para_length": round(self.avg_para_length, 1),
            "iwr_score": round(self.iwr_score, 1),
            "platform_score": self.platform_score,
            "platform_grade": self.platform_grade,
            "not_x_but_y_count": self.not_x_but_y_count,
            "xiang_count": self.xiang_count,
            "emotion_label_count": self.emotion_label_count,
            "cn_number_density": self.cn_number_density,
            "precise_number_count": self.precise_number_count,
            "sudden_count": self.sudden_count,
            "ending_hook": self.ending_hook,
            "sensory_count": self.sensory_count,
            "fanqie_opening_hook": self.fanqie_opening_hook,
            "fanqie_opening_hook_position": self.fanqie_opening_hook_position,
            "fanqie_climax_count": self.fanqie_climax_count,
            "fanqie_ending_hook": self.fanqie_ending_hook,
            "fanqie_emotion_ratio": self.fanqie_emotion_ratio,
            "fanqie_course_score": round(self.fanqie_course_score, 4),
            "retry_count": self.retry_count,
            "pipeline_time_ms": self.pipeline_time_ms,
        }


# ═══════════════════════════════════════════════════════════════
# 资产变更提案
# ═══════════════════════════════════════════════════════════════
@dataclass
class AssetChange:
    """单条规则变更提案。"""

    asset_path: str              # 如 "THRESHOLDS.max_ta_density"
    asset_type: str              # "threshold" | "wordlist_add" | "wordlist_remove" | "prompt_template" | "skill_file" | "config"
    current_value: Any           # 当前值
    proposed_value: Any          # 提案值
    rationale: str               # 变更理由
    evidence_ids: list[str] = field(default_factory=list)  # 关联的分析发现ID
    risk: str = "low"            # "low" | "medium" | "high"
    risk_detail: str = ""        # 古德哈特风险具体说明
    test_hypothesis: str = ""    # 预期效果
    approved: bool | None = None # None=待审批, True=批准, False=拒绝
    approved_by: str = ""
    approved_at: str = ""

    def summary(self) -> str:
        """一行摘要，用于审批界面。"""
        return (
            f"[{self.asset_type}] {self.asset_path}: "
            f"{self.current_value} → {self.proposed_value}"
        )


# ═══════════════════════════════════════════════════════════════
# 分析发现
# ═══════════════════════════════════════════════════════════════
@dataclass
class AnalysisFinding:
    """Analyzer Agent 产出的一条模式发现。"""

    finding_id: str              # 唯一ID
    category: str                # "threshold_miscalibration" | "blind_spot" | "false_positive" | "correlation" | "other"
    description: str
    affected_assets: list[str]   # 关联的资产路径列表
    confidence: float            # 0-1 置信度
    evidence: str                # 支撑数据描述
    recommendation: str          # 初步建议（供 Proposer 使用）
    severity: str = "medium"     # "low" | "medium" | "high"


# ═══════════════════════════════════════════════════════════════
# 对比报告
# ═══════════════════════════════════════════════════════════════
@dataclass
class MetricComparison:
    """单指标 before/after 对比。"""

    metric_name: str
    before_avg: float
    after_avg: float
    delta: float                  # after - before（负值=改善）
    delta_pct: float              # 变化百分比
    direction: str                # "improved" | "worsened" | "unchanged"
    goodhart_warning: str = ""    # 若恶化则填充说明


@dataclass
class ComparisonReport:
    """整轮对比报告。"""

    round_num: int
    metrics: list[MetricComparison]
    summary: str                  # 人类可读摘要
    goodhart_alerts: list[str]    # 古德哈特预警列表
    proposal_accuracy: dict[str, bool]  # 提案ID → 预期是否达成
    overall_verdict: str          # "improved" | "unchanged" | "worsened"
    fanqie_summary: str = ""      # 番茄课程指标摘要


# ═══════════════════════════════════════════════════════════════
# 迭代轮次
# ═══════════════════════════════════════════════════════════════
@dataclass
class IterationRound:
    """一轮完整迭代记录。"""

    round_num: int
    started_at: str = ""
    finished_at: str = ""
    snapshot_id: str = ""

    # 分析阶段
    findings: list[AnalysisFinding] = field(default_factory=list)

    # 提案阶段
    proposals: list[AssetChange] = field(default_factory=list)
    approved_count: int = 0
    rejected_count: int = 0

    # 测试阶段
    audit_before: list[AuditRecord] = field(default_factory=list)
    audit_after: list[AuditRecord] = field(default_factory=list)

    # 对比阶段
    comparison: ComparisonReport | None = None

    # 收敛判定
    convergence_status: str = ""   # "converged" | "continuing" | "blocked"
    convergence_detail: str = ""

    # 花费
    total_tokens: int = 0
    total_llm_calls: int = 0

    def to_summary(self) -> dict[str, Any]:
        return {
            "round": self.round_num,
            "findings": len(self.findings),
            "proposals": len(self.proposals),
            "approved": self.approved_count,
            "rejected": self.rejected_count,
            "convergence": self.convergence_status,
            "tokens": self.total_tokens,
            "before_avg_score": round(
                sum(r.rule_score_total for r in self.audit_before) / max(len(self.audit_before), 1), 3
            ) if self.audit_before else 0,
            "after_avg_score": round(
                sum(r.rule_score_total for r in self.audit_after) / max(len(self.audit_after), 1), 3
            ) if self.audit_after else 0,
        }


# ═══════════════════════════════════════════════════════════════
# 审计批次
# ═══════════════════════════════════════════════════════════════
@dataclass
class AuditBatch:
    """一次测试运行的审计数据集合。"""

    source: str = ""              # "before" | "after" | "baseline"
    records: list[AuditRecord] = field(default_factory=list)
    run_id: str = ""
    run_at: str = ""

    @property
    def avg_rule_score(self) -> float:
        if not self.records:
            return 0.0
        return sum(r.rule_score_total for r in self.records) / len(self.records)

    @property
    def block_count(self) -> int:
        return sum(1 for r in self.records if r.blocked)

    @property
    def pass_rate(self) -> float:
        if not self.records:
            return 0.0
        return sum(1 for r in self.records if r.validator_verdict == "PASS") / len(self.records)
