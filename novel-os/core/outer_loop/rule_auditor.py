"""RuleAuditor —— 用参考文本反向验证规则的合理性。

核心逻辑：
1. 加载参考文本（人类爆款网文）
2. 对参考文本运行全部检测器
3. 对比检测结果：测试章 vs 参考文本
4. 标记可疑规则（在参考文本上也大量触发 = 可能在惩罚人类写作）
5. 发现测试文本独有的异常维度（真正需要关注的AI味）
6. 生成规则健康度报告
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.outer_loop.models import AnalysisFinding, AuditRecord

logger = logging.getLogger("novel-os.outer_loop.rule_auditor")

# 参考文本目录
REFERENCE_DIR = Path(__file__).parent.parent.parent.parent / "data_utf8"


@dataclass
class RuleHealth:
    """单条规则的健康度评估。"""

    rule_name: str
    test_trigger_rate: float      # 测试章节触发率 (0-1)
    ref_trigger_rate: float       # 参考文本触发率 (0-1)
    ratio: float                  # test/ref 比率 (>1 = 测试更多)
    verdict: str                  # "safe" | "suspicious" | "genuine_signal" | "needs_data"
    recommendation: str
    severity: str = "low"


@dataclass
class RuleAuditReport:
    """规则审计报告。"""

    reference_texts: list[str]
    reference_chunks: int
    findings: list[AnalysisFinding]
    rule_health: list[RuleHealth]
    summary: str


class RuleAuditor:
    """规则审计器 —— 用人类爆款网文反测检测器。"""

    # 要审计的检测维度及其提取方法
    AUDIT_RULES = [
        "not_x_but_y",
        "xiang_metaphor",
        "emotion_label",
        "sudden_count",
        "cn_number_density",
        "precise_number",
        "ending_hook",
        "avg_sentence_length",
        "sentence_length_cv",
        "burstiness",
        "perplexity",
        "sensory_count",
    ]

    def __init__(self, genre: str = "玄幻") -> None:
        self.genre = genre
        self._ref_cache: dict[str, list[dict]] = {}

    def audit(
        self,
        test_batch: list[AuditRecord],
        make_id=None,
    ) -> tuple[list[AnalysisFinding], list[RuleHealth]]:
        """主入口：审计规则健康度。

        Returns:
            findings: 关于规则本身的新发现
            health: 每条规则的健康度评估
        """
        if make_id is None:
            fid_counter = [0]
            def make_id():
                fid_counter[0] += 1
                return "RA{:03d}".format(fid_counter[0])

        # 1. 加载参考文本并运行检测
        ref_records = self._load_reference_texts()

        # 2. 逐条规则对比
        health: list[RuleHealth] = []
        findings: list[AnalysisFinding] = []

        for rule_name in self.AUDIT_RULES:
            h = self._audit_rule(rule_name, test_batch, ref_records)
            health.append(h)

            # 生成发现
            if h.verdict == "suspicious":
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="rule_false_positive",
                    description=(
                        "规则'{}'在参考文本上触发率{:.0%}，测试章{:.0%}，ratio={:.1f}。"
                        "该规则可能在惩罚正常的人类写作特征。"
                    ).format(rule_name, h.ref_trigger_rate, h.test_trigger_rate, h.ratio),
                    affected_assets=[rule_name],
                    confidence=0.75 if h.ratio < 2.0 else 0.50,
                    evidence=(
                        "ref_rate={:.3f}, test_rate={:.3f}, ratio={:.1f}"
                    ).format(h.ref_trigger_rate, h.test_trigger_rate, h.ratio),
                    recommendation=h.recommendation,
                    severity=h.severity,
                ))
            elif h.verdict == "genuine_signal":
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="rule_effective",
                    description=(
                        "规则'{}'在测试章上触发率{:.0%}远超参考文本{:.0%}(ratio={:.1f}x)，"
                        "这是真正的AI味差异，应保持并可能收紧。"
                    ).format(rule_name, h.test_trigger_rate, h.ref_trigger_rate, h.ratio),
                    affected_assets=[rule_name],
                    confidence=0.80,
                    evidence=("ratio={:.1f}x").format(h.ratio),
                    recommendation="保持当前规则，可考虑收紧阈值",
                    severity="low",
                ))

        # 3. 分布对比发现
        dist_findings = self._audit_distributions(test_batch, ref_records, make_id)
        findings.extend(dist_findings)

        return findings, health

    # ── 参考文本加载 ──
    def _load_reference_texts(self) -> list[AuditRecord]:
        """加载对应品类的参考文本并跑审计。"""
        genre_dir = REFERENCE_DIR / self.genre
        if not genre_dir.exists():
            logger.warning("参考文本目录不存在: %s", genre_dir)
            return []

        records: list[AuditRecord] = []
        for txt_file in sorted(genre_dir.glob("*.txt"))[:2]:  # 最多2本
            try:
                text = txt_file.read_text(encoding="utf-8")
                # 取前50000字作为样本（约20章的量）
                sample = text[:50000]
                # 按2000字切块
                chunks = [sample[i:i+2200] for i in range(0, len(sample), 2200)]
                for ci, chunk in enumerate(chunks[:20]):  # 最多20块
                    if len(chunk) < 500:
                        continue
                    rec = self._audit_text(chunk, ci + 1)
                    records.append(rec)
                logger.info("加载参考文本 %s: %d chunks", txt_file.stem, len(chunks[:20]))
            except Exception as exc:
                logger.warning("加载参考文本失败 %s: %s", txt_file.name, exc)

        return records

    def _audit_text(self, text: str, chunk_id: int) -> AuditRecord:
        """对一段文本运行完整审计。"""
        record = AuditRecord(chapter_num=chunk_id)

        cn_chars = re.findall(r"[一-鿿]", text)
        record.word_count = len(cn_chars)

        ta_count = text.count("他") + text.count("她") + text.count("它")
        record.ta_density = ta_count / max(record.word_count, 1)

        # StyleRuleEngine
        from core.writing.style_rule_engine import StyleRuleEngine
        engine = StyleRuleEngine()
        score_result = engine.score(text)
        record.rule_score_total = score_result["score"]["total"]
        record.rule_score_breakdown = score_result["score"]
        record.not_x_but_y_count = score_result["breakdown"].get("not_x_but_y", 0)
        record.xiang_count = score_result["breakdown"].get("xiang", 0)
        record.emotion_label_count = score_result["breakdown"].get("emotion_label", 0)
        record.precise_number_count = score_result["breakdown"].get("precise_number", 0)
        record.cn_number_density = score_result.get("cn_number_density", 0)
        record.sudden_count = len(re.findall(r"突然", text))

        # 句长
        sentences = [s for s in re.split(r"[。！？…]+", text) if s.strip()]
        sent_lens = [len(re.findall(r"[一-鿿]", s)) for s in sentences if re.findall(r"[一-鿿]", s)]
        record.avg_sentence_length = round(sum(sent_lens) / max(len(sent_lens), 1), 1) if sent_lens else 0

        # 统计指纹
        from core.statistical_fingerprint_optimizer import StatisticalFingerprintOptimizer
        optimizer = StatisticalFingerprintOptimizer()
        fingerprint = optimizer.compute_metrics(text)
        record.burstiness = fingerprint.burstiness_score
        record.perplexity = fingerprint.perplexity_score
        record.sentence_length_cv = fingerprint.sentence_length_cv

        # 章末钩子
        tail = text[-200:]
        record.ending_hook = bool(re.search(r"[？?]|正要|就要|刚要|即将|不知道|不明白|然而|可是|但$", tail))

        # 感官
        record.sensory_count = len(re.findall(
            r"(闻到|听见|触到|摸到|冰凉|温热|粗糙|滑腻|刺痛|麻木"
            r"|气味|声音|温度|触感|舌尖|鼻腔|耳膜|皮肤|指尖传来)",
            text,
        ))

        # 禁用词
        from core.chapter_validator import BANNED_PATTERNS
        for cat in ["禁用词", "AI万能结尾", "模板比喻", "标志性AI表情"]:
            pat_words = BANNED_PATTERNS.get(cat, [])
            hits = [w for w in pat_words if w in text]
            if hits:
                record.banned_hits[cat] = hits
        record.banned_total = sum(len(v) for v in record.banned_hits.values())

        return record

    # ── 规则审计 ──
    def _audit_rule(
        self,
        rule_name: str,
        test_batch: list[AuditRecord],
        ref_records: list[AuditRecord],
    ) -> RuleHealth:
        """对单条规则进行健康度评估。"""
        # 提取指标
        test_vals = [getattr(r, rule_name, 0) for r in test_batch if r.validator_verdict != "ERROR"]
        ref_vals = [getattr(r, rule_name, 0) for r in ref_records]

        if not test_vals or not ref_vals:
            return RuleHealth(
                rule_name=rule_name,
                test_trigger_rate=0, ref_trigger_rate=0, ratio=0,
                verdict="needs_data",
                recommendation="数据不足，无法评估",
            )

        # 触发率（非零值比例）
        test_trigger = sum(1 for v in test_vals if v > 0) / len(test_vals) if test_vals else 0
        ref_trigger = sum(1 for v in ref_vals if v > 0) / len(ref_vals) if ref_vals else 0

        # 对于数值型指标，比较均值
        test_avg = sum(test_vals) / len(test_vals)
        ref_avg = sum(ref_vals) / len(ref_vals) if ref_vals else 0

        if ref_avg > 0:
            ratio = test_avg / ref_avg
        elif test_avg > 0:
            ratio = float("inf")
        else:
            ratio = 1.0

        # 判定
        if ref_trigger > 0.3 and test_trigger > 0.3:
            # 双方都高触发 → 可疑（规则可能在检测正常特征）
            verdict = "suspicious"
            severity = "high" if ref_trigger > 0.5 else "medium"
            recommendation = (
                "参考文本触发率{:.0%}，建议降权或禁用此规则，或改为仅标记不扣分"
            ).format(ref_trigger)
        elif ratio > 3.0:
            # 测试远高于参考 → 真正的AI信号
            verdict = "genuine_signal"
            severity = "low"
            recommendation = "测试章远高于参考({:.1f}x)，这是有效的AI检测维度".format(ratio)
        elif ref_trigger < 0.1 and test_trigger < 0.1:
            # 双方都低 → 规则可能无意义
            verdict = "suspicious"
            severity = "low"
            recommendation = "双方触发率都极低，此规则可能无效，建议考虑移除"
        else:
            verdict = "safe"
            severity = "low"
            recommendation = "规则表现正常"

        return RuleHealth(
            rule_name=rule_name,
            test_trigger_rate=round(test_trigger, 3),
            ref_trigger_rate=round(ref_trigger, 3),
            ratio=round(ratio, 2) if ratio != float("inf") else 999,
            verdict=verdict,
            recommendation=recommendation,
            severity=severity,
        )

    # ── 分布对比 ──
    def _audit_distributions(
        self,
        test_batch: list[AuditRecord],
        ref_records: list[AuditRecord],
        make_id,
    ) -> list[AnalysisFinding]:
        """对比测试文本和参考文本的统计分布差异。"""
        findings: list[AnalysisFinding] = []

        if not ref_records:
            return findings

        # 句长方差对比
        test_cv = [r.sentence_length_cv for r in test_batch if r.sentence_length_cv > 0]
        ref_cv = [r.sentence_length_cv for r in ref_records if r.sentence_length_cv > 0]
        if test_cv and ref_cv:
            test_cv_avg = sum(test_cv) / len(test_cv)
            ref_cv_avg = sum(ref_cv) / len(ref_cv)
            if abs(test_cv_avg - ref_cv_avg) > 0.15:
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="distribution_mismatch",
                    description=(
                        "句长变异系数：测试章{:.3f} vs 参考{:.3f}，差异{:.3f}。"
                        "{}"
                    ).format(test_cv_avg, ref_cv_avg, abs(test_cv_avg - ref_cv_avg),
                             "测试章句长更均匀→疑似AI" if test_cv_avg < ref_cv_avg else "测试章句长变化更大"),
                    affected_assets=["sentence_length检测维度"],
                    confidence=0.65,
                    evidence="test_cv={:.3f}, ref_cv={:.3f}".format(test_cv_avg, ref_cv_avg),
                    recommendation="如果测试CV显著低于参考，说明句式过于均匀，需要增加句长变化",
                    severity="medium",
                ))

        return findings

    def render_report(self, health: list[RuleHealth]) -> str:
        """生成人类可读的规则健康度报告。"""
        lines = [
            "# 规则健康度审计报告",
            "",
            "## 方法论",
            "用《{}》品类的人类爆款网文作为参考文本，反向验证每条检测规则的合理性。".format(self.genre),
            "如果一条规则在参考文本上大量触发 → 该规则可能在惩罚正常的人类写作特征。",
            "如果一条规则在测试章上触发远高于参考 → 该规则检测到了真正的AI模式差异。",
            "",
            "## 规则健康度",
            "",
            "| 规则 | 测试触发率 | 参考触发率 | 比率 | 判定 |",
            "|------|-----------|-----------|------|------|",
        ]

        for h in health:
            verdict_emoji = {
                "suspicious": "⚠️ 可疑",
                "genuine_signal": "✅ 有效",
                "safe": "➖ 正常",
                "needs_data": "❓ 数据不足",
            }.get(h.verdict, "?")
            lines.append("| {} | {:.0%} | {:.0%} | {:.1f}x | {} |".format(
                h.rule_name, h.test_trigger_rate, h.ref_trigger_rate, h.ratio, verdict_emoji))

        suspicious = [h for h in health if h.verdict == "suspicious"]
        if suspicious:
            lines.append("")
            lines.append("## ⚠️ 建议处理的可疑规则")
            for h in suspicious:
                lines.append("- **{}**: {}".format(h.rule_name, h.recommendation))

        return "\n".join(lines)
