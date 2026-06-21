"""OuterLoopRunner —— 外层回路主编排器。

编排完整的7步骤回路:
  Step 1: 测试集运行 (TestRunner)
  Step 2: 分析 (Analyzer)
  Step 3: 提案 (Proposer)
  Step 4: 人类审批 (ApprovalNode)
  Step 5: 应用变更 (RuleWriter)
  Step 6: 验证测试 (TestRunner again)
  Step 7: 对比 + 收敛判定 (Comparer + ConvergenceDetector)

用法:
  python -m core.outer_loop.runner --chapters-dir <dir> --rounds 5
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from core.outer_loop.analyzer import Analyzer
from core.outer_loop.approval import TerminalApproval
from core.outer_loop.comparer import Comparer
from core.outer_loop.convergence import ConvergenceDetector
from core.outer_loop.models import AnalysisFinding, AssetChange, AuditBatch, IterationRound
from core.outer_loop.proposer import Proposer
from core.outer_loop.rule_auditor import RuleAuditor
from core.outer_loop.rule_reader import RuleReader
from core.outer_loop.rule_writer import RuleWriter
from core.outer_loop.test_runner import TestRunner

logger = logging.getLogger("novel-os.outer_loop.runner")

# 日志目录
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "reports" / "outer_loop"


class OuterLoopRunner:
    """外层回路主编排器。"""

    def __init__(
        self,
        chapters_dir: str | Path,
        llm=None,
        book_config_path: str = "",
        max_rounds: int = 5,
        auto_approve: bool = False,
        chapter_range: tuple[int, int] | None = None,
    ) -> None:
        self.chapters_dir = Path(chapters_dir)
        self.llm = llm
        self.book_config_path = book_config_path
        self.max_rounds = max_rounds
        self.auto_approve = auto_approve
        self.chapter_range = chapter_range

        # 组件
        self.reader = RuleReader()
        self.writer = RuleWriter()
        self.runner = TestRunner(chapters_dir, book_config_path=book_config_path)
        self.analyzer = Analyzer(llm)
        self.proposer = Proposer(llm)
        self.comparer = Comparer()
        self.convergence = ConvergenceDetector(max_stable_rounds=3, rule_reader=self.reader)
        self.approval = TerminalApproval() if not auto_approve else None

        # 状态
        self.rounds: list[IterationRound] = []
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════════════════
    # 主循环
    # ═══════════════════════════════════════════════════════
    def run(self) -> dict[str, Any]:
        """执行完整外层回路，返回最终报告。"""
        print("\n" + "=" * 60)
        print("  Novel-OS 外层回路：去AI味规则自动优化")
        print(f"  测试集: {self.chapters_dir}")
        print(f"  最大轮数: {self.max_rounds}")
        print(f"  模式: {'自动审批(测试模式)' if self.auto_approve else '人工审批'}")
        print("=" * 60)

        # ── Round 0: 基线 ──
        print("\n[Round 0] 建立基线...")
        baseline_batch = self._run_tests("baseline")
        self._print_batch_summary(baseline_batch, "基线")

        # ── 迭代循环 ──
        for round_num in range(1, self.max_rounds + 1):
            rnd = IterationRound(round_num=round_num)
            rnd.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rnd.audit_before = baseline_batch.records

            print(f"\n{'='*60}")
            print(f"  Round {round_num}/{self.max_rounds}")
            print(f"{'='*60}")

            # STEP 2: 分析
            print("\n[Step 2] 分析审计数据...")
            findings = self.analyzer.analyze(baseline_batch)
            rnd.findings = findings
            print(f"  发现 {len(findings)} 条模式")
            for f in findings[:5]:
                print(f"    - [{f.category}] {f.description[:100]}...")

            if not findings:
                print("  ✅ 无新发现，回路提前收敛")
                rnd.convergence_status = "converged"
                self.rounds.append(rnd)
                break

            # STEP 2.5: 规则自检 (RuleAuditor)
            print("\n[Step 2.5] 规则自检（参考文本反测）...")
            auditor = RuleAuditor(genre=getattr(self, '_genre', '玄幻'))
            ra_findings, rule_health = auditor.audit(baseline_batch.records)
            if ra_findings:
                print(f"  发现 {len(ra_findings)} 条规则级问题")
                for f in ra_findings[:5]:
                    sev = {'high':'🔴','medium':'🟡','low':'🔵'}.get(f.severity,'')
                    print(f"    {sev} [{f.category}] {f.description[:100]}...")
                # 合并到 findings 中
                findings.extend(ra_findings)
                rnd.findings = findings

            # STEP 3: 提案
            print("\n[Step 3] 生成变更提案...")
            proposals = self.proposer.propose(findings)
            rnd.proposals = proposals
            print(f"  生成 {len(proposals)} 条提案")
            for p in proposals:
                print(f"    - {p.summary()}")

            if not proposals:
                print("  ✅ 无变更提案，回路提前收敛")
                rnd.convergence_status = "converged"
                self.rounds.append(rnd)
                break

            # STEP 4: 审批
            print("\n[Step 4] 等待审批...")
            if self.auto_approve:
                # 自动审批：低风险全部通过
                approved = [p for p in proposals if p.risk != "high"]
                for p in approved:
                    p.approved = True
                print(f"  自动审批: {len(approved)}/{len(proposals)} 批准 (跳过高风险)")
                rejected = [p for p in proposals if p.risk == "high"]
                if rejected:
                    print(f"  跳过高风险提案: {[p.asset_path for p in rejected]}")
            else:
                # 人工审批
                approved = self.approval.present(findings, proposals, round_num)

            rnd.approved_count = len(approved)
            rnd.rejected_count = len(proposals) - len(approved)

            if not approved:
                print("  ⚠️ 本轮无批准的提案，跳过执行")
                rnd.convergence_status = "blocked"
                self.rounds.append(rnd)
                continue

            # STEP 5: 应用变更
            print("\n[Step 5] 应用变更...")
            snapshot_id = self.writer.apply_all(
                approved,
                snapshot_label=f"round_{round_num}",
            )
            rnd.snapshot_id = snapshot_id
            print(f"  快照: {snapshot_id}")

            # ★ 修复（2026-06-20）：应用变更后必须清空 RuleReader 缓存，
            # 否则下一轮 _record_round 读取的还是旧值，ConvergenceDetector
            # 永远看不到参数变化。
            self.reader.invalidate_cache()

            # STEP 6: 验证测试（静态审计）
            print("\n[Step 6] 验证测试...")
            after_batch = self._run_tests("after")
            rnd.audit_after = after_batch.records
            self._print_batch_summary(after_batch, f"Round {round_num} 验证")

            # ★ STEP 6.5: 抽样重写验证（修复 UNCHANGED 死锁）
            # 静态审计只读旧 .md，规则改了但章节没重写 → 指标必然 UNCHANGED。
            # 抽 1 章用新规则实跑内层流水线，用真章节验证规则效果。
            sample_report = self._sample_rewrite_verify(
                baseline_batch, after_batch, round_num
            )
            if sample_report:
                rnd.metadata = rnd.metadata or {}
                rnd.metadata["sample_rewrite"] = sample_report

            # STEP 7: 对比 + 收敛
            print("\n[Step 7] 对比报告 + 收敛判定...")
            comparison = self.comparer.compare(baseline_batch, after_batch, approved)
            comparison.round_num = round_num
            rnd.comparison = comparison

            # 打印对比摘要
            print(f"  {comparison.summary}")

            # 收敛判定
            conv_result = self.convergence.check(rnd, comparison)
            rnd.convergence_status = conv_result["status"]
            rnd.convergence_detail = conv_result["reason"]
            print(f"  收敛判定: {conv_result['status']} — {conv_result['reason']}")

            # 保存 Markdown 报告
            report_md = self.comparer.render_markdown(comparison)
            self._save_report(report_md, round_num)

            # 记录本轮
            rnd.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.rounds.append(rnd)

            # 收敛?
            if conv_result["converged"]:
                print(f"\n{'='*60}")
                print(f"  🎉 回路收敛！共 {round_num} 轮")
                print(f"{'='*60}")
                break

            # 将 after 作为下一轮 baseline
            baseline_batch = after_batch
            self.reader.invalidate_cache()

        # ── 最终报告 ──
        return self._final_report()

    # ═══════════════════════════════════════════════════════
    # 内部
    # ═══════════════════════════════════════════════════════
    def _run_tests(self, source: str) -> AuditBatch:
        """运行测试集。"""
        batch = self.runner.run(self.chapter_range)
        batch.source = source
        return batch

    @staticmethod
    def _print_batch_summary(batch: AuditBatch, label: str) -> None:
        """打印批次摘要。"""
        records = [r for r in batch.records if r.validator_verdict != "ERROR"]
        if not records:
            print(f"  {label}: 无有效记录")
            return
        print(f"  {label}: {len(records)}章, "
              f"avg_score={batch.avg_rule_score:.3f}, "
              f"BLOCK={batch.block_count}, "
              f"pass_rate={batch.pass_rate:.0%}")

    def _save_report(self, md_content: str, round_num: int) -> None:
        """保存 Markdown 对比报告。"""
        fp = OUTPUT_DIR / f"comparison_r{round_num:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        fp.write_text(md_content, encoding="utf-8")

    def _sample_rewrite_verify(
        self,
        baseline_batch: AuditBatch,
        after_batch: AuditBatch,
        round_num: int,
    ) -> dict[str, Any]:
        """抽样重写验证（修复 UNCHANGED 死锁）。

        静态审计只读旧 .md，规则改了但章节文本没变 → 文本统计指标必然 UNCHANGED。
        本方法抽 1 章用 LLM 做一次 StyleCritic 修订（用新规则），对比修订前后指标，
        验证规则改动对"修订行为"的真实影响。

        成本：约 3K tokens/章（仅 StyleCritic 修订，不跑完整流水线）。
        若 llm 不可用则跳过（保持 0 tokens 兼容）。
        """
        if not self.llm:
            return {"skipped": True, "reason": "llm 不可用"}

        # 选第 1 个有效章节
        valid = [r for r in after_batch.records if r.validator_verdict != "ERROR"]
        if not valid:
            return {"skipped": True, "reason": "无有效章节"}
        sample = valid[0]

        try:
            from core.writing.style_rule_engine import StyleRuleEngine
            from pathlib import Path
            import re as _re

            # 读取该章节原文
            ch_files = list(self.chapters_dir.glob("*.md")) + list(self.chapters_dir.glob("*.txt"))
            ch_path = None
            for fp in ch_files:
                if str(sample.chapter_num) in fp.stem or f"{sample.chapter_num:03d}" in fp.stem:
                    ch_path = fp
                    break
            if not ch_path:
                return {"skipped": True, "reason": f"未找到第 {sample.chapter_num} 章文件"}

            original = ch_path.read_text(encoding="utf-8")
            engine = StyleRuleEngine()

            # 用新规则对原文评分
            before_score = engine.score(original)

            # 调 LLM 做一次 StyleCritic 修订（system prompt 用新规则）
            system = (
                "你是 StyleCritic。用最新去AI味规则修订下列章节文本。"
                "只改写有AI味的句子，保留情节、对话、钩子不变。"
                "输出修订后的完整正文。"
            )
            revised = self.llm.call(system, original[:6000], temperature=0.3, max_tokens=4000)

            # 用新规则对修订稿评分
            after_score = engine.score(revised)

            report = {
                "chapter_num": sample.chapter_num,
                "before_rule_score": round(before_score, 4),
                "after_rule_score": round(after_score, 4),
                "improvement": round(before_score - after_score, 4),
                "tokens_used": len(original) // 3 + len(revised) // 3,
            }
            print(f"  [Step 6.5] 抽样重写验证: 第{sample.chapter_num}章 "
                  f"rule_score {before_score:.3f} → {after_score:.3f} "
                  f"(改善 {before_score - after_score:+.3f})")
            return report
        except Exception as exc:
            print(f"  [Step 6.5] 抽样重写验证失败: {exc}")
            return {"skipped": True, "reason": str(exc)}

    def _final_report(self) -> dict[str, Any]:
        """生成最终汇总报告。"""
        total_rounds = len(self.rounds)
        last = self.rounds[-1] if self.rounds else None

        summary = {
            "total_rounds": total_rounds,
            "converged": last.convergence_status == "converged" if last else False,
            "final_status": last.convergence_status if last else "no_rounds",
            "rounds": [r.to_summary() for r in self.rounds],
            "total_proposals": sum(r.approved_count for r in self.rounds),
            "snapshots": self.writer.list_snapshots(),
        }

        # 保存
        fp = OUTPUT_DIR / f"final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        fp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n最终报告已保存: {fp}")

        # 收敛报告
        conv_md = self.convergence.convergence_report()
        conv_fp = OUTPUT_DIR / f"convergence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        conv_fp.write_text(conv_md, encoding="utf-8")

        return summary


# ═══════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════
def main():
    """CLI 入口: python -m core.outer_loop.runner"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Novel-OS 外层回路：去AI味规则自动优化引擎",
    )
    parser.add_argument(
        "--chapters-dir",
        required=True,
        help="测试章节目录（如 books/<项目>/chapters/）",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=5,
        help="最大迭代轮数 (默认: 5)",
    )
    parser.add_argument(
        "--chapter-range",
        type=str,
        default="",
        help="测试章节范围，如 '1-10' (默认: 自动发现全部)",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="自动审批模式（低风险提案自动通过，仅用于测试）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细日志",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # 解析章节范围
    chapter_range = None
    if args.chapter_range:
        parts = args.chapter_range.split("-")
        if len(parts) == 2:
            chapter_range = (int(parts[0]), int(parts[1]))

    # LLM 客户端（可选，从环境获取）
    llm = None
    try:
        from core.llm_client import LLMClient
        llm = LLMClient()
        logger.info("LLM 客户端已就绪，深度分析模式")
    except Exception:
        logger.warning("LLM 客户端不可用，仅使用代码级分析")

    runner = OuterLoopRunner(
        chapters_dir=args.chapters_dir,
        llm=llm,
        max_rounds=args.rounds,
        auto_approve=args.auto_approve,
        chapter_range=chapter_range,
    )

    result = runner.run()

    print("\n" + "=" * 60)
    print(f"  完成: {result['total_rounds']} 轮, "
          f"{'✅ 收敛' if result['converged'] else '⚠️ 未收敛'}")
    print("=" * 60)

    return 0 if result["converged"] else 1


if __name__ == "__main__":
    sys.exit(main())
