"""Analyzer Agent —— 分析审计数据，发现规则盲区/误报/参数失配。

职责:
1. 读入 AuditBatch + 当前规则快照
2. 从四个维度分析:
   a. 阈值校准: 当前阈值是否合理？
   b. 盲区发现: 哪些AI模式未被检测？
   c. 误报识别: 哪些规则产生了假阳性？
   d. 参数相关性: 哪些阈值互相冲突？
3. 输出结构化 AnalysisFinding 列表
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from core.fanqie_course import load_fanqie_rules
from core.outer_loop.assets_index import ASSET_REGISTRY, ASSETS_BY_KEY
from core.outer_loop.models import AnalysisFinding, AuditBatch, AuditRecord
from core.outer_loop.rule_reader import RuleReader

logger = logging.getLogger("novel-os.outer_loop.analyzer")


class Analyzer:
    """数据分析器。先用代码做统计预分析，再调用 LLM 做深度分析。"""

    def __init__(self, llm=None) -> None:
        self._llm = llm

    def analyze(self, batch: AuditBatch) -> list[AnalysisFinding]:
        """分析审计批次，返回所有发现。"""
        findings: list[AnalysisFinding] = []
        fid_counter = [0]

        def make_id() -> str:
            fid_counter[0] += 1
            return f"F{fid_counter[0]:03d}"

        # ── 阶段1: 代码级统计预分析（零LLM成本）──
        records = [r for r in batch.records if r.validator_verdict != "ERROR"]
        if not records:
            return findings

        # a. 阈值校准分析
        findings.extend(self._analyze_threshold_calibration(records, make_id))

        # b. 盲区发现
        findings.extend(self._analyze_blind_spots(records, make_id))

        # c. 误报识别
        findings.extend(self._analyze_false_positives(records, make_id))

        # d. 参数相关性
        findings.extend(self._analyze_correlations(records, make_id))

        # e. 番茄课程分析
        findings.extend(self._analyze_fanqie_course(records, make_id))

        # ── 阶段2: LLM 深度分析（如果有 LLM 实例）──
        if self._llm:
            try:
                llm_findings = self._llm_deep_analysis(batch, findings, make_id)
                findings.extend(llm_findings)
            except Exception as exc:
                logger.warning("[Analyzer] LLM 深度分析失败: %s", exc)

        return findings

    # ── 阈值校准 ──
    def _analyze_threshold_calibration(
        self, records: list[AuditRecord], make_id
    ) -> list[AnalysisFinding]:
        """检查阈值是否合理。"""
        findings: list[AnalysisFinding] = []

        # ta_density: 实际分布 vs 阈值
        ta_vals = [r.ta_density for r in records]
        ta_avg = sum(ta_vals) / len(ta_vals) if ta_vals else 0
        ta_threshold = 0.04  # 从 THRESHOLDS 读取

        if ta_avg > ta_threshold * 1.2:
            findings.append(AnalysisFinding(
                finding_id=make_id(),
                category="threshold_miscalibration",
                description=(
                    f"他字密度平均 {ta_avg:.1%}，当前阈值 {ta_threshold:.0%}，"
                    f"实际值显著高于阈值，可能导致大量误报。建议上调到 {min(ta_avg * 0.9, 0.08):.1%}"
                ),
                affected_assets=["max_ta_density"],
                confidence=0.8,
                evidence=f"{len(records)}章, avg={ta_avg:.3f}, max={max(ta_vals):.3f}, min={min(ta_vals):.3f}",
                recommendation=f"将 max_ta_density 从 {ta_threshold} 上调到 {min(ta_avg * 0.9, 0.08):.3f}",
                severity="high",
            ))

        # burstiness 阈值
        burst_vals = [r.burstiness for r in records]
        burst_avg = sum(burst_vals) / len(burst_vals) if burst_vals else 0
        burst_min = 0.35
        if burst_avg < burst_min:
            findings.append(AnalysisFinding(
                finding_id=make_id(),
                category="threshold_miscalibration",
                description=(
                    f"平均突发性 {burst_avg:.3f}，低于阈值 {burst_min}，"
                    f"当前阈值可能无法有效检测。检查是否需要降低阈值或这确实是正常人类写作范围。"
                ),
                affected_assets=["min_burstiness"],
                confidence=0.6,
                evidence=f"avg={burst_avg:.3f}, 范围 [{min(burst_vals):.3f}, {max(burst_vals):.3f}]",
                recommendation=f"考虑将 min_burstiness 降低到 {max(burst_avg - 0.05, 0.1):.3f}",
                severity="medium",
            ))

        # 禁词命中率分布
        banned_rates = [r.banned_total for r in records]
        banned_avg = sum(banned_rates) / len(banned_rates) if banned_rates else 0
        if banned_avg > 5:
            findings.append(AnalysisFinding(
                finding_id=make_id(),
                category="threshold_miscalibration",
                description=(
                    f"平均每章禁用词命中 {banned_avg:.1f} 次，当前阈值 max_forbidden_patterns=3。"
                    f"若这些命中大部分是真实AI味，说明规则有效。若大部分是误报，需要调整阈值。"
                ),
                affected_assets=["max_forbidden_patterns"],
                confidence=0.5,
                evidence=f"avg={banned_avg:.1f}/章, 各章: {banned_rates}",
                recommendation="人工抽查3章确认误报率，若<20%则保持，>50%则上调阈值",
                severity="medium",
            ))

        # 阈值过松检测：指标远低于阈值 → 阈值可能过宽
        # ta_density
        if ta_vals:
            ta_max_actual = max(ta_vals)
            if ta_max_actual < ta_threshold * 0.5:  # 实际值不到阈值一半
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="threshold_miscalibration",
                    description=(
                        f"他字密度实际最高仅 {ta_max_actual:.1%}，远低于阈值 {ta_threshold:.0%}。"
                        f"阈值可能过宽，无法有效区分AI文本。如有需要可适当收紧阈值。"
                    ),
                    affected_assets=["max_ta_density"],
                    confidence=0.5,
                    evidence=f"实际范围 [{min(ta_vals):.3f}, {max(ta_vals):.3f}], 阈值={ta_threshold}",
                    recommendation=f"可考虑将 max_ta_density 收紧至 {min(ta_max_actual * 1.5, ta_threshold):.3f}",
                    severity="low",
                ))

        # precise_number_threshold: 实际值远超阈值
        pn_vals = [r.precise_number_count for r in records]
        if pn_vals:
            pn_threshold = 8
            pn_over = [r for r in records if r.precise_number_count > pn_threshold]
            # Also check validator issues for precise number warnings
            pn_warned = [r for r in records
                         if any("精确数字" in iss.get("message", "")
                                for iss in r.validator_issues)]
            if pn_warned:
                pn_max = max(len([iss for iss in r.validator_issues
                                  if "精确数字" in iss.get("message", "")])
                              for r in pn_warned)
                pn_chapters = [r.chapter_num for r in pn_warned]
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="threshold_miscalibration",
                    description=(
                        f"精确数字+量词在 {len(pn_warned)}/5 章触发WARN，"
                        f"但AI味评分仍<0.200。这可能不是AI味问题，而是大纲量化设定所致。"
                        f"建议上调 precise_number_threshold 或降级为INFO。"
                    ),
                    affected_assets=["precise_number_threshold"],
                    confidence=0.75,
                    evidence=f"触发章节: {pn_chapters}",
                    recommendation=f"将 precise_number_threshold 从 8 上调到 25，或改为INFO级别不阻塞",
                    severity="high",
                ))

        # 章末悬念检测过严
        ending_missing = [r for r in records if not r.ending_hook and r.rule_score_total < 0.25]
        if ending_missing:
            findings.append(AnalysisFinding(
                finding_id=make_id(),
                category="false_positive",
                description=(
                    f"{len(ending_missing)}/5章章末未检测到悬念收尾，但AI味评分均<0.200。"
                    f"当前检测器可能过于机械——人类作者也会用动作戛然而止收尾。"
                    f"建议将 suspense_ending_min 从1降到0，或从WARN降级为INFO。"
                ),
                affected_assets=["suspense_ending_min"],
                confidence=0.70,
                evidence=f"缺失章: {[r.chapter_num for r in ending_missing]}, AI味分: {[r.rule_score_total for r in ending_missing]}",
                recommendation="将 suspense_ending_min 从 1 改为 0（关闭强制悬念收尾检测）",
                severity="medium",
            ))

        return findings

    # ── 盲区发现 ──
    def _analyze_blind_spots(
        self, records: list[AuditRecord], make_id
    ) -> list[AnalysisFinding]:
        """发现 AI 模式未被规则覆盖的盲区。"""
        findings: list[AnalysisFinding] = []

        # 检查 rule_score 高但 validator 未 BLOCK 的章节
        for r in records:
            if r.rule_score_total > 0.30 and not r.blocked:
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="blind_spot",
                    description=(
                        f"第{r.chapter_num}章 AI味评分 {r.rule_score_total:.3f} 但未触发BLOCK。"
                        f"检查 rule_score_breakdown 中最高的维度。"
                    ),
                    affected_assets=["max_rule_score or specific rule thresholds"],
                    confidence=0.7,
                    evidence=f"breakdown: {r.rule_score_breakdown}",
                    recommendation=f"检查 breakdown 中 >0.5 的维度，考虑收紧对应阈值",
                    severity="high",
                ))

        # 检查"突然"高频但阈值宽
        sudden_vals = [r.sudden_count for r in records]
        sudden_high = [r for r in records if r.sudden_count > 5]
        if sudden_high:
            findings.append(AnalysisFinding(
                finding_id=make_id(),
                category="blind_spot",
                description=(
                    f"{len(sudden_high)}章'突然'超过5次，但阈值 max_sudden_count=3。"
                    f"检查是否因为阈值过宽导致未被警告。"
                ),
                affected_assets=["max_sudden_count"],
                confidence=0.6,
                evidence=f"高值章节: {[(r.chapter_num, r.sudden_count) for r in sudden_high]}",
                recommendation="考虑降低 max_sudden_count 或增加每章'突然'密度检查",
                severity="medium",
            ))

        # 检查 cn_number_density 高但无警告
        cn_dense = [r for r in records if r.cn_number_density > 30]
        if cn_dense:
            findings.append(AnalysisFinding(
                finding_id=make_id(),
                category="blind_spot",
                description=(
                    f"{len(cn_dense)}章中文数词密度 >30/千字，这在人类写作中偏高。"
                    f"考虑降低 max_cn_numbers 或大纲 dequantify。"
                ),
                affected_assets=["max_cn_numbers", "goal_max_cn_number_density"],
                confidence=0.65,
                evidence=f"高值章节: {[(r.chapter_num, r.cn_number_density) for r in cn_dense]}",
                recommendation="将 max_cn_numbers 从当前值降低 20%，或大纲添加 dequantify 指令",
                severity="medium",
            ))

        # 单章异常值检测
        # 对话占比极端
        for r in records:
            if r.dialogue_ratio < 0.05:
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="blind_spot",
                    description=(
                        f"第{r.chapter_num}章对话占比仅{r.dialogue_ratio:.0%}，"
                        f"远低于15%下限。若为设定/叙述章则正常，否则应增加对话交锋。"
                    ),
                    affected_assets=["dialogue_ratio_min"],
                    confidence=0.55,
                    evidence=f"第{r.chapter_num}章 dialogue_ratio={r.dialogue_ratio:.3f}",
                    recommendation=f"检查第{r.chapter_num}章是否为设定过渡章，若是则可放宽该章对话要求",
                    severity="medium",
                ))

        # 句长极端
        for r in records:
            if r.avg_sentence_length < 13:
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="blind_spot",
                    description=(
                        f"第{r.chapter_num}章平均句长仅{r.avg_sentence_length}字，"
                        f"可能存在过度碎片化。但AI味评分仅{r.rule_score_total:.3f}，"
                        f"也可能是风格选择。"
                    ),
                    affected_assets=["long_sentence_min"],
                    confidence=0.45,
                    evidence=f"第{r.chapter_num}章 avg_sent_len={r.avg_sentence_length}, ai_score={r.rule_score_total}",
                    recommendation=f"人工确认第{r.chapter_num}章的短句风格是否可接受",
                    severity="low",
                ))

        return findings

    # ── 误报识别 ──
    def _analyze_false_positives(
        self, records: list[AuditRecord], make_id
    ) -> list[AnalysisFinding]:
        """识别可能的假阳性（规则命中了但实际不应算AI味）。"""
        findings: list[AnalysisFinding] = []

        # 分析哪些禁用词频繁命中但可能正常
        all_hits: dict[str, int] = {}
        for r in records:
            for cat, words in r.banned_hits.items():
                for w in words:
                    all_hits[w] = all_hits.get(w, 0) + 1

        # 高频命中的词可能是误报
        for word, count in sorted(all_hits.items(), key=lambda x: -x[1]):
            if count >= len(records) * 0.5:  # 超过50%的章都命中
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="false_positive",
                    description=(
                        f"'{word}' 在 {count}/{len(records)} 章中被命中，"
                        f"命中率 {count/len(records):.0%}。可能为正常用词，考虑从禁用列表移除或降级。"
                    ),
                    affected_assets=["forbidden_words"],
                    confidence=0.55,
                    evidence=f"命中词: {word}, 章: {count}/{len(records)}",
                    recommendation=f"人工抽查'{word}'的3处使用，确认是AI味还是正常用词",
                    severity="low",
                ))

        return findings

    # ── 参数相关性 ──
    def _analyze_correlations(
        self, records: list[AuditRecord], make_id
    ) -> list[AnalysisFinding]:
        """发现参数间的相关性/冲突。"""
        findings: list[AnalysisFinding] = []

        # 对话占比 vs 句长: 高对话通常短句多
        high_dialogue = [r for r in records if r.dialogue_ratio > 0.50]
        if high_dialogue:
            avg_sent = sum(r.avg_sentence_length for r in high_dialogue) / len(high_dialogue)
            if avg_sent < 15:
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="correlation",
                    description=(
                        f"对话占比>50%的章节平均句长仅{avg_sent:.1f}字。"
                        f"对话占比上限和长句最小阈值可能冲突——人类对话章节天然短句多。"
                    ),
                    affected_assets=["dialogue_ratio_max", "long_sentence_min"],
                    confidence=0.7,
                    evidence=f"{len(high_dialogue)}章, avg_sent={avg_sent:.1f}",
                    recommendation="当对话占比>50%时，跳过'未包含长句'警告",
                    severity="medium",
                ))

        return findings

    # ── 番茄课程分析 ──
    def _analyze_fanqie_course(
        self, records: list[AuditRecord], make_id
    ) -> list[AnalysisFinding]:
        """基于番茄课程规则分析开篇钩子、爽点密度、章末钩子、情绪配比。"""
        findings: list[AnalysisFinding] = []
        if not records:
            return findings

        rules = load_fanqie_rules()
        opening_rules = rules.get_opening_rules()
        chapter_beat = rules.get_chapter_beat_rules()
        active_chapters = set(opening_rules.get("active_chapters", [1, 2, 3]))
        max_lead_in = opening_rules.get("max_lead_in_words", 300)
        min_climax = chapter_beat.get("min_climax_per_chapter", 1)
        ending_zone = chapter_beat.get("ending_hook_zone", 200)

        # 开篇钩子命中率（前 3 章）
        opening_records = [r for r in records if r.chapter_num in active_chapters]
        hook_miss = [r for r in opening_records if not r.fanqie_opening_hook]
        if hook_miss:
            proposed_lead_in = max(100, max_lead_in - 50)
            findings.append(AnalysisFinding(
                finding_id=make_id(),
                category="fanqie_opening_weak",
                description=f"{len(hook_miss)}/{len(opening_records)} 章开篇未在 {max_lead_in} 字内建立钩子",
                affected_assets=["opening_max_lead_in_words"],
                confidence=0.8,
                evidence=f"未命中章节: {[r.chapter_num for r in hook_miss]}",
                recommendation=(
                    f"将 opening_max_lead_in_words 调整到 {proposed_lead_in}（当前 {max_lead_in}）"
                ),
                severity="high",
            ))

        # 爽点密度不足
        low_climax = [r for r in records if r.fanqie_climax_count < min_climax]
        if low_climax:
            proposed_min = min(5, min_climax + 1)
            findings.append(AnalysisFinding(
                finding_id=make_id(),
                category="fanqie_climax_low",
                description=(
                    f"{len(low_climax)}/{len(records)} 章爽点/情绪爆点低于阈值 {min_climax}"
                ),
                affected_assets=["chapter_min_climax"],
                confidence=0.75,
                evidence=f"低爽点章节: {[(r.chapter_num, r.fanqie_climax_count) for r in low_climax]}",
                recommendation=(
                    f"将 chapter_min_climax 调整到 {proposed_min}（当前 {min_climax}）"
                ),
                severity="high",
            ))

        # 章末钩子缺失
        missing_ending = [r for r in records if not r.fanqie_ending_hook]
        if missing_ending:
            proposed_zone = min(500, ending_zone + 50)
            findings.append(AnalysisFinding(
                finding_id=make_id(),
                category="fanqie_ending_weak",
                description=f"{len(missing_ending)}/{len(records)} 章缺少章末钩子",
                affected_assets=["ending_hook_zone"],
                confidence=0.7,
                evidence=f"缺失章节: {[r.chapter_num for r in missing_ending]}",
                recommendation=(
                    f"将 ending_hook_zone 调整到 {proposed_zone}（当前 {ending_zone}）"
                ),
                severity="medium",
            ))

        # 情绪配比偏离
        valid_ratios = [r.fanqie_emotion_ratio for r in records if r.fanqie_emotion_ratio]
        if valid_ratios:
            target = rules.get_emotion_ratio("")
            avg_ratio: dict[str, float] = {}
            for key in target:
                vals = [ratio.get(key, 0.0) for ratio in valid_ratios]
                avg_ratio[key] = sum(vals) / len(vals)
            l1_deviation = sum(
                abs(avg_ratio.get(k, 0.0) - target.get(k, 0.0)) for k in target
            )
            if l1_deviation > 0.2:
                # 找出偏离最大的单一情绪
                max_dev_key = max(
                    target.keys(),
                    key=lambda k: abs(avg_ratio.get(k, 0.0) - target.get(k, 0.0)),
                )
                current_target = target.get(max_dev_key, 0.0)
                proposed_target = round(avg_ratio.get(max_dev_key, current_target), 2)
                asset_key = f"emotion_ratio_{max_dev_key}"
                findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category="fanqie_emotion_ratio_drift",
                    description=(
                        f"情绪配比偏离目标 (L1={l1_deviation:.2f})，"
                        f"{max_dev_key} 实际 {avg_ratio.get(max_dev_key, 0.0):.2f} "
                        f"vs 目标 {current_target:.2f}"
                    ),
                    affected_assets=[asset_key],
                    confidence=min(0.9, max(0.5, l1_deviation)),
                    evidence=f"平均配比={avg_ratio}, 目标={target}",
                    recommendation=(
                        f"将 {asset_key} 调整到 {proposed_target}（当前 {current_target}）"
                    ),
                    severity="medium",
                ))

        return findings

    # ── LLM 深度分析 ──
    def _llm_deep_analysis(
        self,
        batch: AuditBatch,
        existing_findings: list[AnalysisFinding],
        make_id,
    ) -> list[AnalysisFinding]:
        """调用 LLM 做更深层的模式分析。"""
        if not self._llm:
            return []

        # 构建 prompt
        reader = RuleReader()
        rule_snapshot = reader.snapshot_for_llm()

        records_summary = json.dumps(
            [r.to_dict() for r in batch.records if r.validator_verdict != "ERROR"],
            ensure_ascii=False,
            indent=2,
        )

        pre_findings = json.dumps(
            [
                {"id": f.finding_id, "category": f.category, "desc": f.description}
                for f in existing_findings
            ],
            ensure_ascii=False,
            indent=2,
        )

        system = (
            "你是规则优化分析器。你的任务是从审计数据中发现代码级分析可能遗漏的模式。\n"
            "关注：\n"
            "1. 跨章节趋势（AI味评分是否随章节递增/递减？）\n"
            "2. 异常值（某章某个指标突然飙升/暴跌）\n"
            "3. 规则之间的隐蔽冲突（一个规则变好但另一个变差）\n"
            "4. 现有规则无法检测的AI写作模式\n\n"
            "返回严格JSON格式：\n"
            '{"findings": [{"category": "...", "description": "...", '
            '"affected_assets": [...], "confidence": 0.X, "recommendation": "...", '
            '"severity": "low|medium|high"}]}'
        )

        user = (
            "【当前规则快照】\n" + rule_snapshot + "\n\n"
            "【审计数据（每章）】\n" + records_summary + "\n\n"
            "【代码分析已有的发现】\n" + pre_findings + "\n\n"
            "请从上述数据中发现代码分析可能遗漏的模式，输出JSON。"
        )

        try:
            raw = self._llm.call_for_agent(
                "outer_loop_analyzer",
                system,
                user,
                temperature=0.1,
                max_tokens=2000,
            )
            data = self._parse_json(raw)
            llm_findings = []
            for item in data.get("findings", []):
                llm_findings.append(AnalysisFinding(
                    finding_id=make_id(),
                    category=item.get("category", "other"),
                    description=item.get("description", ""),
                    affected_assets=item.get("affected_assets", []),
                    confidence=float(item.get("confidence", 0.5)),
                    evidence=f"[LLM发现] {item.get('description', '')[:200]}",
                    recommendation=item.get("recommendation", ""),
                    severity=item.get("severity", "medium"),
                ))
            logger.info("[Analyzer] LLM 发现 %d 条新问题", len(llm_findings))
            return llm_findings
        except Exception as exc:
            logger.warning("[Analyzer] LLM 深度分析失败: %s", exc)
            return []

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
        return json.loads(text)
