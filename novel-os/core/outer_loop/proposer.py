"""Proposer Agent —— 将分析发现转化为可执行的规则变更提案。

职责:
1. 读入 AnalysisFinding 列表 + 当前规则快照
2. 为每条发现生成具体的 AssetChange 提案
3. 评估每条提案的古德哈特风险
4. 输出提案列表供人类审批
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from core.outer_loop.assets_index import ASSET_REGISTRY, ASSETS_BY_KEY
from core.outer_loop.models import AnalysisFinding, AssetChange
from core.outer_loop.rule_reader import RuleReader

logger = logging.getLogger("novel-os.outer_loop.proposer")


class Proposer:
    """提案生成器。"""

    def __init__(self, llm=None) -> None:
        self._llm = llm
        self._reader = RuleReader()

    def propose(self, findings: list[AnalysisFinding]) -> list[AssetChange]:
        """将分析发现转化为规则变更提案。"""
        proposals: list[AssetChange] = []

        for finding in findings:
            try:
                p = self._finding_to_proposal(finding)
                if p:
                    proposals.append(p)
            except Exception as exc:
                logger.warning("[Proposer] 提案生成失败 for %s: %s", finding.finding_id, exc)

        # 去重：如果两条提案修改同一个参数，保留置信度高的
        proposals = self._deduplicate(proposals)

        # LLM 补充提案（对复杂情况）
        if self._llm:
            try:
                llm_proposals = self._llm_propose(findings, proposals)
                proposals.extend(llm_proposals)
            except Exception as exc:
                logger.warning("[Proposer] LLM 提案失败: %s", exc)

        # ── 安全校验 ──
        proposals = self._validate_direction(proposals)
        proposals = self._validate_types(proposals)
        proposals = self._escalate_risk(proposals)

        return proposals

    # ── 安全校验 1: 方向校验 ──
    def _validate_direction(self, proposals: list[AssetChange]) -> list[AssetChange]:
        """检测提案是否逆转了之前的变更方向，标记为高风险。

        通过读 rule_overrides.json 判断：
        - 若当前值已被外层回路修改过（≠代码默认值），且提案方向相反 → 高风险
        """
        from core.outer_loop.rule_config import DEFAULTS, load_overrides
        overrides = load_overrides()

        for p in proposals:
            # 找到对应的 config key
            config_key = self._asset_to_config_key(p.asset_path)
            if not config_key:
                continue

            default_val = DEFAULTS.get(config_key)
            override_val = overrides.get(config_key)
            if default_val is None or override_val is None:
                continue

            # 判断方向：当前 override 相对于 default 是增大还是减小
            if isinstance(default_val, (int, float)) and isinstance(override_val, (int, float)):
                prev_direction = 'up' if override_val > default_val else 'down'
                curr_direction = 'up' if p.proposed_value > override_val else 'down' if p.proposed_value < override_val else 'same'

                # 提案方向与上一轮相反
                if prev_direction != 'same' and curr_direction != 'same' and prev_direction != curr_direction:
                    p.risk = 'high'
                    p.risk_detail = (
                        'DIRECTION_REVERSAL: 上一轮已从 {} 调整到 {} ({}), '
                        '本轮提案 {} → {} ({}) 方向相反'
                    ).format(default_val, override_val, prev_direction,
                             override_val, p.proposed_value, curr_direction)
                    logger.warning('[Proposer] 方向校验拦截: %s', p.summary())

                # 提案回到默认值附近 → 中等风险
                if curr_direction != 'same' and abs(p.proposed_value - default_val) < abs(override_val - default_val) * 0.3:
                    p.risk = max(p.risk, 'medium') if p.risk else 'medium'
                    if not p.risk_detail:
                        p.risk_detail = '提案接近代码默认值，可能抵消之前优化'

        return proposals

    # ── 安全校验 2: 类型校验 ──
    def _validate_types(self, proposals: list[AssetChange]) -> list[AssetChange]:
        """校验 proposed_value 类型是否匹配资产预期类型。"""
        from core.outer_loop.assets_index import ASSETS_BY_KEY

        for p in proposals:
            asset_key = p.asset_path.split('.')[-1]
            # Try to find the asset definition
            asset = ASSETS_BY_KEY.get(asset_key)
            if not asset:
                continue

            constraints = asset.constraints
            if not constraints:
                continue

            expected_type = constraints.get('type', '')
            actual = p.proposed_value

            type_ok = True
            if expected_type == 'int' and not isinstance(actual, int):
                # 尝试转换
                if isinstance(actual, float) and actual == int(actual):
                    p.proposed_value = int(actual)
                else:
                    type_ok = False
            elif expected_type == 'float' and isinstance(actual, int):
                p.proposed_value = float(actual)
            elif expected_type == 'str' and not isinstance(actual, str):
                type_ok = False

            if not type_ok:
                p.risk = 'high'
                p.risk_detail = 'TYPE_MISMATCH: expected {}, got {} (value={})'.format(
                    expected_type, type(actual).__name__, actual)
                logger.warning('[Proposer] 类型校验拦截: %s', p.summary())

        return proposals

    # ── 安全校验 3: 风险升级 ──
    def _escalate_risk(self, proposals: list[AssetChange]) -> list[AssetChange]:
        """对高危类型的资产变更自动升级风险等级。"""
        for p in proposals:
            # wordlist 变更（增删词条）→ 至少 medium
            if p.asset_type in ('wordlist_add', 'wordlist_remove'):
                if p.risk == 'low':
                    p.risk = 'medium'
                    p.risk_detail = '词表修改需要人工确认 (原风险: low → medium)'

            # prompt_template / skill_file 变更 → 高风险
            if p.asset_type in ('prompt_template', 'skill_file'):
                p.risk = 'high'
                p.risk_detail = 'prompt/skill文件修改必须人工审核'

            # 变化幅度 >50% 且原风险不是 high → 升级
            if isinstance(p.current_value, (int, float)) and isinstance(p.proposed_value, (int, float)):
                if p.current_value != 0:
                    change = abs(p.proposed_value - p.current_value) / abs(p.current_value)
                    if change > 0.5 and p.risk != 'high':
                        p.risk = 'high'
                        p.risk_detail = 'HIGH_AMPLITUDE: 变化{:.0%}, 自动升级为高风险'.format(change)

        return proposals

    # ── 辅助 ──
    @staticmethod
    def _asset_to_config_key(asset_path: str) -> str | None:
        """将 asset_path 映射到 rule_config key。"""
        mapping = {
            'THRESHOLDS.max_ta_density': 'THRESHOLDS.max_ta_density',
            'THRESHOLDS.precise_number_threshold': 'THRESHOLDS.precise_number_threshold',
            'THRESHOLDS.suspense_ending_min': 'THRESHOLDS.suspense_ending_min',
            'THRESHOLDS.dialogue_ratio_min': 'THRESHOLDS.dialogue_ratio_min',
            'THRESHOLDS.dialogue_ratio_max': 'THRESHOLDS.dialogue_ratio_max',
            'THRESHOLDS.max_forbidden_patterns': 'THRESHOLDS.max_forbidden_patterns',
            'THRESHOLDS.max_sudden_count': 'THRESHOLDS.max_sudden_count',
            'THRESHOLDS.min_burstiness': 'THRESHOLDS.min_burstiness',
            'THRESHOLDS.max_perplexity': 'THRESHOLDS.max_perplexity',
            'StyleRuleEngine.max_not_x_but_y': 'StyleRuleEngine.max_not_x_but_y',
            'StyleRuleEngine.max_xiang': 'StyleRuleEngine.max_xiang',
            'StyleRuleEngine.max_cn_numbers': 'StyleRuleEngine.max_cn_numbers',
            'StyleRuleEngine.max_repetition': 'StyleRuleEngine.max_repetition',
            'ChapterGoal.max_rule_score': 'ChapterGoal.max_rule_score',
            'ChapterGoal.max_cn_number_density': 'ChapterGoal.max_cn_number_density',
        }
        for path_hint, config_key in mapping.items():
            if path_hint in asset_path:
                return config_key
        return None

    def _finding_to_proposal(self, finding: AnalysisFinding) -> AssetChange | None:
        """将单条发现转化为提案。"""
        cat = finding.category

        if cat == "threshold_miscalibration" or cat.startswith("fanqie_"):
            return self._propose_threshold_change(finding)
        elif cat == "blind_spot":
            return self._propose_blind_spot_fix(finding)
        elif cat == "false_positive":
            return self._propose_false_positive_fix(finding)
        elif cat == "correlation":
            return self._propose_correlation_fix(finding)
        else:
            return self._propose_generic(finding)

    def _propose_threshold_change(self, finding: AnalysisFinding) -> AssetChange | None:
        """阈值失调 → 调整阈值。"""
        for asset_key in finding.affected_assets:
            asset = ASSETS_BY_KEY.get(asset_key)
            if not asset:
                continue
            if asset.asset_type != "threshold":
                continue

            current = self._reader.read_one(asset_key)
            if current is None:
                continue

            # 从 recommendation 中提取建议值
            proposed = self._extract_value_from_recommendation(
                finding.recommendation, current, asset
            )

            constraints = asset.constraints
            risk = self._assess_risk(asset_key, current, proposed)

            return AssetChange(
                asset_path=asset.path,
                asset_type=asset.asset_type,
                current_value=current,
                proposed_value=proposed,
                rationale=f"[{finding.finding_id}] {finding.description}",
                evidence_ids=[finding.finding_id],
                risk=risk["level"],
                risk_detail=risk["detail"],
                test_hypothesis=(
                    f"修改后预期效果: {finding.recommendation}"
                ),
            )

        return None

    def _propose_blind_spot_fix(self, finding: AnalysisFinding) -> AssetChange | None:
        """盲区发现 → 收紧阈值或新增检测。"""
        # 盲区通常需要收紧阈值
        for asset_key in finding.affected_assets:
            asset = ASSETS_BY_KEY.get(asset_key)
            if not asset:
                continue

            current = self._reader.read_one(asset_key)
            if current is None:
                continue

            if asset.asset_type == "threshold":
                # 盲区 → 收紧（降低上限或提高下限）
                if "max_" in asset_key or asset_key.endswith("_max"):
                    proposed = current * 0.7  # 收紧30%
                else:
                    proposed = current * 1.3  # 提高下限30%

                # 夹到约束范围
                constraints = asset.constraints
                if "min" in constraints:
                    proposed = max(proposed, constraints["min"])
                if "max" in constraints:
                    proposed = min(proposed, constraints["max"])

                risk = self._assess_risk(asset_key, current, proposed)

                return AssetChange(
                    asset_path=asset.path,
                    asset_type=asset.asset_type,
                    current_value=current,
                    proposed_value=proposed,
                    rationale=f"[{finding.finding_id}] {finding.description}",
                    evidence_ids=[finding.finding_id],
                    risk=risk["level"],
                    risk_detail=risk["detail"],
                    test_hypothesis=f"收紧{asset_key}以覆盖盲区",
                )

        return None

    def _propose_false_positive_fix(self, finding: AnalysisFinding) -> AssetChange | None:
        """误报 → 从禁用列表移除或放宽阈值。"""
        # 从描述中提取要移除的词
        word_match = re.search(r"'([^']+)'", finding.description)
        if not word_match:
            return None
        word = word_match.group(1)

        return AssetChange(
            asset_path="BANNED_PATTERNS.禁用词",
            asset_type="wordlist_remove",
            current_value=f"列表中包含 '{word}'",
            proposed_value=word,
            rationale=f"[{finding.finding_id}] {finding.description}",
            evidence_ids=[finding.finding_id],
            risk="low",
            risk_detail=f"移除'{word}'可能导致漏检，但当前误报率过高",
            test_hypothesis=f"移除'{word}'后WARN减少，且不引入新的AI味",
        )

    def _propose_correlation_fix(self, finding: AnalysisFinding) -> AssetChange | None:
        """参数冲突 → 通常需要放宽某一个。"""
        # 简化处理：取第一个 affected_asset
        if not finding.affected_assets:
            return None

        asset_key = finding.affected_assets[0]
        asset = ASSETS_BY_KEY.get(asset_key)
        if not asset:
            return None

        current = self._reader.read_one(asset_key)
        if current is None:
            return None

        # 放宽20%
        if "max_" in asset_key:
            proposed = current * 1.2
        else:
            proposed = current * 0.8

        constraints = asset.constraints
        if "min" in constraints:
            proposed = max(proposed, constraints["min"])
        if "max" in constraints:
            proposed = min(proposed, constraints["max"])

        return AssetChange(
            asset_path=asset.path,
            asset_type=asset.asset_type,
            current_value=current,
            proposed_value=proposed,
            rationale=f"[{finding.finding_id}] {finding.description}",
            evidence_ids=[finding.finding_id],
            risk="medium",
            risk_detail="放宽阈值可能引入新问题，建议只改一个参数观察效果",
            test_hypothesis=f"放宽{asset_key}以解决参数冲突",
        )

    def _propose_generic(self, finding: AnalysisFinding) -> AssetChange | None:
        """通用提案（LLM级别发现或自定义类别）。"""
        if not finding.affected_assets:
            return None

        asset_key = finding.affected_assets[0]
        asset = ASSETS_BY_KEY.get(asset_key)
        if not asset:
            return None

        current = self._reader.read_one(asset_key)

        return AssetChange(
            asset_path=asset.path,
            asset_type=asset.asset_type,
            current_value=current,
            proposed_value=current,  # 需LLM辅助确定
            rationale=f"[{finding.finding_id}] {finding.description}",
            evidence_ids=[finding.finding_id],
            risk="medium",
            risk_detail="通用提案，需人工确认具体参数值",
            test_hypothesis=finding.recommendation,
        )

    # ── 辅助 ──
    def _extract_value_from_recommendation(
        self, recommendation: str, current: Any, asset: AssetDef
    ) -> Any:
        """从推荐文字中提取数值（如 '上调到 0.055'）。"""
        # 尝试匹配数值
        for pat in [r"(\d+\.?\d*)%", r"(\d+\.?\d*)"]:
            match = re.search(pat, recommendation)
            if match:
                val = float(match.group(1))
                # 如果是百分比且当前值在 0-1 范围，除以100
                if "%" in match.group(0) and isinstance(current, float) and 0 <= current <= 1:
                    val = val / 100
                # 夹到约束
                constraints = asset.constraints
                if "min" in constraints:
                    val = max(val, constraints["min"])
                if "max" in constraints:
                    val = min(val, constraints["max"])
                if constraints.get("type") == "int":
                    val = int(val)
                return val

        # 未找到数值，返回当前值
        return current

    def _assess_risk(self, asset_key: str, current: Any, proposed: Any) -> dict:
        """评估古德哈特风险。"""
        # 变化幅度
        if isinstance(current, (int, float)) and isinstance(proposed, (int, float)):
            if current == 0:
                change_pct = 1.0 if proposed != 0 else 0
            else:
                change_pct = abs(proposed - current) / abs(current)
        else:
            change_pct = 0

        if change_pct > 0.5:
            level = "high"
            detail = f"变化幅度 {change_pct:.0%}，可能产生意外副作用"
        elif change_pct > 0.2:
            level = "medium"
            detail = f"变化幅度 {change_pct:.0%}，建议观察一轮后再继续调整"
        else:
            level = "low"
            detail = f"微调，变化 {change_pct:.0%}"

        # 特殊风险
        if asset_key == "max_ta_density" and isinstance(proposed, float) and proposed > 0.08:
            level = "high"
            detail = "他字密度 >8% 在网文中显著偏高，放宽到此可能漏检大量AI味"

        return {"level": level, "detail": detail}

    @staticmethod
    def _deduplicate(proposals: list[AssetChange]) -> list[AssetChange]:
        """去重：同资产多条提案只保留置信度来源最多的。"""
        seen: dict[str, AssetChange] = {}
        for p in proposals:
            if p.asset_path in seen:
                # 保留 evidence_ids 更多的
                if len(p.evidence_ids) > len(seen[p.asset_path].evidence_ids):
                    seen[p.asset_path] = p
            else:
                seen[p.asset_path] = p
        return list(seen.values())

    # ── LLM 补充 ──
    def _llm_propose(
        self,
        findings: list[AnalysisFinding],
        existing_proposals: list[AssetChange],
    ) -> list[AssetChange]:
        """让 LLM 对复杂情况生成额外提案。"""
        if not self._llm:
            return []

        existing_paths = {p.asset_path for p in existing_proposals}
        findings_text = json.dumps(
            [
                {"id": f.finding_id, "cat": f.category, "desc": f.description,
                 "rec": f.recommendation, "assets": f.affected_assets}
                for f in findings
            ],
            ensure_ascii=False,
            indent=2,
        )

        system = (
            "你是规则优化提案器。对于以下分析发现，如果代码生成器未能覆盖某个方面，"
            "请生成额外的规则变更提案。只输出JSON。\n"
            '{"proposals": [{"asset_key": "...", "from": ..., "to": ..., '
            '"rationale": "...", "risk": "low|medium|high"}]}'
        )
        user = (
            f"【分析发现】\n{findings_text}\n\n"
            f"【已有提案覆盖的资产】\n{existing_paths}\n\n"
            f"【可用资产列表】\n{[a.key for a in ASSET_REGISTRY]}\n\n"
            "请检查发现中是否有未被提案覆盖的关键问题，生成补充提案。"
        )

        try:
            raw = self._llm.call_for_agent(
                "outer_loop_proposer",
                system,
                user,
                temperature=0.1,
                max_tokens=1500,
            )
            data = self._parse_json(raw)
            proposals = []
            for item in data.get("proposals", []):
                asset_key = item.get("asset_key", "")
                asset = ASSETS_BY_KEY.get(asset_key)
                if not asset:
                    continue
                proposals.append(AssetChange(
                    asset_path=asset.path,
                    asset_type=asset.asset_type,
                    current_value=item.get("from"),
                    proposed_value=item.get("to"),
                    rationale=item.get("rationale", "[LLM补充提案]"),
                    risk=item.get("risk", "medium"),
                    test_hypothesis=item.get("rationale", ""),
                ))
            return proposals
        except Exception as exc:
            logger.warning("[Proposer] LLM 提案失败: %s", exc)
            return []

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
        return json.loads(text)
