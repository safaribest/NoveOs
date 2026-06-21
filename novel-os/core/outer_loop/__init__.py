"""Outer Loop —— 去AI味规则自动优化引擎。

Loop Engineering 外层回路实现:
  - 测试集运行 → 分析 → 提案 → 审批 → 应用 → 验证 → 收敛判定

Usage:
  from core.outer_loop import OuterLoopRunner
  runner = OuterLoopRunner(chapters_dir="books/project/chapters")
  runner.run()

CLI:
  python -m core.outer_loop.runner --chapters-dir books/project/chapters --rounds 5
"""

from core.outer_loop.runner import OuterLoopRunner
from core.outer_loop.models import (
    AssetChange,
    AnalysisFinding,
    AuditBatch,
    AuditRecord,
    ComparisonReport,
    IterationRound,
)
from core.outer_loop.rule_reader import RuleReader
from core.outer_loop.rule_writer import RuleWriter
from core.outer_loop.test_runner import TestRunner
from core.outer_loop.analyzer import Analyzer
from core.outer_loop.proposer import Proposer
from core.outer_loop.comparer import Comparer
from core.outer_loop.convergence import ConvergenceDetector
from core.outer_loop.approval import TerminalApproval, JSONApproval

__all__ = [
    "OuterLoopRunner",
    "AssetChange",
    "AnalysisFinding",
    "AuditBatch",
    "AuditRecord",
    "ComparisonReport",
    "IterationRound",
    "RuleReader",
    "RuleWriter",
    "TestRunner",
    "Analyzer",
    "Proposer",
    "Comparer",
    "ConvergenceDetector",
    "TerminalApproval",
    "JSONApproval",
]
