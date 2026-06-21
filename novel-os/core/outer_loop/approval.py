"""ApprovalNode —— 人类审批交互界面。

支持两种模式:
1. 终端交互模式 (TerminalApproval): 在 CLI 中逐条审批
2. JSON 模式 (JSONApproval): 输出 JSON 供其他工具读取，返回审批结果
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from core.outer_loop.models import AnalysisFinding, AssetChange

logger = logging.getLogger("novel-os.outer_loop.approval")

# 提案记录目录
PROPOSALS_DIR = Path(__file__).parent.parent.parent.parent / ".rule_proposals"


class TerminalApproval:
    """终端交互式审批。"""

    def __init__(self) -> None:
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

    def present(
        self,
        findings: list[AnalysisFinding],
        proposals: list[AssetChange],
        round_num: int = 1,
    ) -> list[AssetChange]:
        """在终端展示提案，收集用户审批，返回批准的列表。"""
        self._print_header(round_num, findings, proposals)

        approved: list[AssetChange] = []
        rejected: list[AssetChange] = []

        for i, p in enumerate(proposals, 1):
            decision = self._ask_one(i, p)
            if decision == "y":
                p.approved = True
                p.approved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                approved.append(p)
                print(f"  ✅ 批准: {p.asset_path}\n")
            elif decision == "n":
                p.approved = False
                rejected.append(p)
                print(f"  ❌ 拒绝: {p.asset_path}\n")
            elif decision.startswith("m:"):
                # 修改后批准
                new_val = decision[2:].strip()
                try:
                    if isinstance(p.current_value, int):
                        p.proposed_value = int(new_val)
                    elif isinstance(p.current_value, float):
                        p.proposed_value = float(new_val)
                    else:
                        p.proposed_value = new_val
                except ValueError:
                    pass
                p.approved = True
                p.approved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                approved.append(p)
                print(f"  ✏️ 修改后批准: {p.asset_path} → {p.proposed_value}\n")

        # 保存审批记录
        self._save_record(round_num, approved, rejected, findings)

        # 摘要
        print(f"\n{'='*60}")
        print(f"本轮审批: {len(approved)} 批准 / {len(rejected)} 拒绝 / {len(proposals)} 总计")
        if approved:
            print(f"\n已批准将应用的变更:")
            for p in approved:
                print(f"  - {p.summary()}")
        print()

        return approved

    def _ask_one(self, idx: int, proposal: AssetChange) -> str:
        """询问单条提案。"""
        risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(proposal.risk, "⚪")

        print(f"\n{'─'*50}")
        print(f"提案 {idx}: [{proposal.asset_type}] {proposal.asset_path}  {risk_emoji} {proposal.risk}")
        print(f"  理由: {proposal.rationale[:200]}")
        print(f"  当前值: {proposal.current_value}")
        print(f"  提案值: {proposal.proposed_value}")
        if proposal.risk_detail:
            print(f"  风险说明: {proposal.risk_detail}")
        if proposal.test_hypothesis:
            print(f"  预期效果: {proposal.test_hypothesis[:150]}")
        print()
        print("  [y] 批准  [n] 拒绝  [m:新值] 修改后批准  [s] 跳过剩余全部批准")

        choice = input("  > ").strip().lower()
        return choice

    def _print_header(
        self,
        round_num: int,
        findings: list[AnalysisFinding],
        proposals: list[AssetChange],
    ) -> None:
        """打印审批头部信息。"""
        print("\n" + "=" * 60)
        print(f"  去AI味规则优化 — 第 {round_num} 轮提案审批")
        print("=" * 60)
        print(f"\n📊 分析发现: {len(findings)} 条")
        for f in findings[:5]:
            sev = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(f.severity, "")
            print(f"  {sev} [{f.category}] {f.description[:120]}...")
        if len(findings) > 5:
            print(f"  ... 还有 {len(findings) - 5} 条发现")
        print(f"\n📋 变更提案: {len(proposals)} 条\n")

    def _save_record(
        self,
        round_num: int,
        approved: list[AssetChange],
        rejected: list[AssetChange],
        findings: list[AnalysisFinding],
    ) -> None:
        """保存审批记录到磁盘。"""
        record = {
            "round": round_num,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "findings": [
                {"id": f.finding_id, "category": f.category, "desc": f.description}
                for f in findings
            ],
            "approved": [
                {"path": p.asset_path, "from": str(p.current_value), "to": str(p.proposed_value)}
                for p in approved
            ],
            "rejected": [
                {"path": p.asset_path, "reason": p.rationale[:200]}
                for p in rejected
            ],
        }
        filepath = PROPOSALS_DIR / f"approval_r{round_num:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("审批记录已保存: %s", filepath)


class JSONApproval:
    """JSON 模式审批 —— 用于脚本/非交互场景。

    将提案导出为 JSON，由外部工具读取并返回审批结果。
    """

    def export(self, proposals: list[AssetChange], output_path: str | Path) -> Path:
        """导出提案为 JSON。"""
        data = {
            "proposals": [
                {
                    "index": i,
                    "asset_path": p.asset_path,
                    "asset_type": p.asset_type,
                    "current_value": p.current_value,
                    "proposed_value": p.proposed_value,
                    "rationale": p.rationale,
                    "risk": p.risk,
                    "risk_detail": p.risk_detail,
                }
                for i, p in enumerate(proposals)
            ]
        }
        fp = Path(output_path)
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return fp

    def import_decisions(
        self,
        proposals: list[AssetChange],
        decisions_path: str | Path,
    ) -> list[AssetChange]:
        """从 JSON 导入审批决定，返回批准的列表。"""
        data = json.loads(Path(decisions_path).read_text(encoding="utf-8"))
        decisions = data.get("decisions", [])

        approved: list[AssetChange] = []
        for dec in decisions:
            idx = dec.get("index", -1)
            action = dec.get("action", "reject")
            modified_value = dec.get("modified_value")

            if idx < 0 or idx >= len(proposals):
                continue

            p = proposals[idx]
            if action == "approve":
                p.approved = True
                p.approved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                approved.append(p)
            elif action == "modify" and modified_value is not None:
                p.proposed_value = modified_value
                p.approved = True
                p.approved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                approved.append(p)
            else:
                p.approved = False

        return approved
