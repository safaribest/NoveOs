"""外层回路测试脚本 —— 在1-5章上运行 Analyze → Propose，不修改规则。

用法: python -X utf8 run_outer_loop_test.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# 确保 novel-os 在 path 中
sys.path.insert(0, str(Path(__file__).parent))

from core.outer_loop.rule_reader import RuleReader
from core.outer_loop.test_runner import TestRunner
from core.outer_loop.analyzer import Analyzer
from core.outer_loop.proposer import Proposer
from core.outer_loop.comparer import Comparer

CHAPTERS_DIR = "e:/1/NoveOs-master/NoveOs-master/books/修仙模拟器：我的未来被诡异污染了_54a4cced/chapters"
OUTPUT_DIR = Path(__file__).parent.parent / "reports" / "outer_loop"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 70)
    print("  外层回路测试 —— 修仙模拟器 1-5章")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # ── 1. 当前规则快照 ──
    print("\n" + "─" * 70)
    print("  [1/4] 读取当前规则")
    print("─" * 70)
    reader = RuleReader()
    snapshot = reader.read_all()
    for key, val in snapshot.items():
        if isinstance(val, list):
            print(f"  {key}: {len(val)} 项 → {val[:5]}{'...' if len(val) > 5 else ''}")
        else:
            print(f"  {key}: {val}")

    # ── 2. 测试集运行 ──
    print("\n" + "─" * 70)
    print("  [2/4] 静态审计 1-5章")
    print("─" * 70)
    runner = TestRunner(CHAPTERS_DIR)
    batch = runner.run(chapter_range=(1, 5))

    # 导出审计 JSON
    audit_path = runner.export_audit_json(batch, str(OUTPUT_DIR))

    # 打印每章摘要
    records = [r for r in batch.records if r.validator_verdict != "ERROR"]
    print(f"\n  {'章':<6} {'字数':<8} {'AI味分':<10} {'他密度':<8} {'突发性':<8} {'困惑度':<8} {'判決':<8}")
    print(f"  {'-'*6} {'-'*8} {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for r in records:
        verdict_emoji = {"PASS": "✅", "WARN": "⚠️", "BLOCK": "🔴"}.get(r.validator_verdict, "❓")
        print(f"  {r.chapter_num:<6} {r.word_count:<8} {r.rule_score_total:<10.3f} "
              f"{r.ta_density:<8.1%} {r.burstiness:<8.3f} {r.perplexity:<8.3f} "
              f"{verdict_emoji} {r.validator_verdict}")

    print(f"\n  批次摘要: avg_score={batch.avg_rule_score:.3f}, "
          f"BLOCK={batch.block_count}, pass_rate={batch.pass_rate:.0%}")

    # ── 3. 分析 ──
    print("\n" + "─" * 70)
    print("  [3/4] Analyzer 分析（代码级，0 tokens）")
    print("─" * 70)
    analyzer = Analyzer(llm=None)  # 纯代码分析，不花LLM钱
    findings = analyzer.analyze(batch)

    if not findings:
        print("  ✅ 无发现 —— 当前规则在测试集上表现良好")
    else:
        for f in findings:
            sev = {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(f.severity, "⚪")
            cat_map = {
                "threshold_miscalibration": "阈值失配",
                "blind_spot": "盲区",
                "false_positive": "误报",
                "correlation": "参数冲突",
            }
            cat_cn = cat_map.get(f.category, f.category)
            print(f"\n  {sev} [{cat_cn}] {f.description}")
            print(f"      置信度: {f.confidence:.0%} | 影响: {', '.join(f.affected_assets[:3])}")
            print(f"      建议: {f.recommendation[:150]}")

    # ── 4. 提案 ──
    print("\n" + "─" * 70)
    print("  [4/4] Proposer 生成提案（代码级，0 tokens）")
    print("─" * 70)
    proposer = Proposer(llm=None)  # 纯代码提案，不花LLM钱
    proposals = proposer.propose(findings)

    if not proposals:
        print("  ✅ 无提案 —— 当前规则已是最优")
    else:
        for i, p in enumerate(proposals, 1):
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(p.risk, "⚪")
            print(f"\n  提案 {i}: {risk_emoji} [{p.asset_type}] {p.asset_path}")
            print(f"    理由: {p.rationale[:200]}")
            print(f"    当前: {p.current_value} → 提案: {p.proposed_value}")
            print(f"    风险: {p.risk} — {p.risk_detail}")
            if p.test_hypothesis:
                print(f"    预期: {p.test_hypothesis[:150]}")

    # ── 保存完整报告 ──
    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "chapters": "1-5",
        "rule_snapshot": {k: v for k, v in snapshot.items() if not isinstance(v, list)},
        "rule_snapshot_wordlists": {k: {"count": len(v), "sample": v[:5]} for k, v in snapshot.items() if isinstance(v, list)},
        "audit_summary": {
            "avg_rule_score": batch.avg_rule_score,
            "block_count": batch.block_count,
            "pass_rate": batch.pass_rate,
            "per_chapter": [r.to_dict() for r in batch.records],
        },
        "findings": [
            {
                "id": f.finding_id,
                "category": f.category,
                "description": f.description,
                "confidence": f.confidence,
                "affected_assets": f.affected_assets,
                "recommendation": f.recommendation,
                "severity": f.severity,
            }
            for f in findings
        ],
        "proposals": [
            {
                "asset_path": p.asset_path,
                "asset_type": p.asset_type,
                "current_value": str(p.current_value),
                "proposed_value": str(p.proposed_value),
                "rationale": p.rationale,
                "risk": p.risk,
                "risk_detail": p.risk_detail,
                "test_hypothesis": p.test_hypothesis,
            }
            for p in proposals
        ],
    }
    report_path = OUTPUT_DIR / f"test_1_5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  完整报告: {report_path}")
    print(f"  审计数据: {audit_path}")
    print(f"\n  总LLM消耗: 0 tokens ($0.00) —— 纯代码分析")

    return 0


if __name__ == "__main__":
    sys.exit(main())
