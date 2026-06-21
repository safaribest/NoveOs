"""Guard注册表单元测试。"""
from __future__ import annotations

import pytest

from core.guards.registry import GuardRegistry
from core.guards.base import BaseGuard, GuardResult
from core.guards.quality_gate_guard import QualityGateGuard
from core.guards.continuity_guard import ContinuityGuard
from core.quality_gates import QualityGates


class DummyGuard(BaseGuard):
    """测试用Guard。"""
    guard_id = "dummy"
    description = "dummy guard"
    default_level = "PASS"

    def run(self, content: str, context: dict) -> GuardResult:
        return GuardResult(guard_id=self.guard_id, level="PASS", message="ok")


class BlockingGuard(BaseGuard):
    """总是BLOCKING的测试Guard。"""
    guard_id = "blocking"
    description = "blocking guard"
    default_level = "BLOCKING"

    def run(self, content: str, context: dict) -> GuardResult:
        return GuardResult(guard_id=self.guard_id, level="BLOCKING", message="blocked")


class TestGuardRegistry:
    """测试GuardRegistry的注册、执行、校准。"""

    @pytest.fixture
    def registry(self) -> GuardRegistry:
        return GuardRegistry()

    def test_register_and_list(self, registry: GuardRegistry) -> None:
        """注册后能在列表中看到。"""
        registry.register(DummyGuard())
        guards = registry.list_guards()
        assert len(guards) == 1
        assert guards[0]["guard_id"] == "dummy"

    def test_unregister(self, registry: GuardRegistry) -> None:
        """注销后列表为空。"""
        registry.register(DummyGuard())
        registry.unregister("dummy")
        assert len(registry.list_guards()) == 0

    def test_run_all_pass(self, registry: GuardRegistry) -> None:
        """所有Guard通过。"""
        registry.register(DummyGuard())
        results = registry.run_all("text", {})
        assert len(results) == 1
        assert results[0].level == "PASS"

    def test_run_all_blocking_stop(self, registry: GuardRegistry) -> None:
        """BLOCKING时停止后续检查。"""
        registry.register(BlockingGuard())
        registry.register(DummyGuard())
        results = registry.run_all("text", {}, stop_on_blocking=True)
        assert len(results) == 1  # 第二个Guard被跳过
        assert results[0].level == "BLOCKING"

    def test_run_all_blocking_continue(self, registry: GuardRegistry) -> None:
        """BLOCKING时不停止，继续检查。"""
        registry.register(BlockingGuard())
        registry.register(DummyGuard())
        results = registry.run_all("text", {}, stop_on_blocking=False)
        assert len(results) == 2

    def test_run_level_filter(self, registry: GuardRegistry) -> None:
        """按级别过滤执行。"""
        registry.register(DummyGuard())  # PASS级别
        registry.register(BlockingGuard())  # BLOCKING级别
        results = registry.run_level("text", {}, target_level="BLOCKING")
        assert len(results) == 1
        assert results[0].guard_id == "blocking"

    def test_stats(self, registry: GuardRegistry) -> None:
        """统计命中次数。"""
        registry.register(DummyGuard())
        registry.run_all("text", {})
        # 通过record手动记录一次命中
        registry.record("dummy", "WARN")
        stats = registry._stats["dummy"]
        assert stats["total"] == 2  # run_all 1次 + record 1次
        assert stats["hits"] == 1

    def test_calibrate(self, registry: GuardRegistry) -> None:
        """校准循环。"""
        registry.register(QualityGateGuard(QualityGates()))
        # 模拟100次检查，0次命中（命中率0% < 10%阈值）
        for _ in range(100):
            registry.record("quality_gate", "PASS")
        adj = registry.calibrate_all(threshold=0.1)
        assert "quality_gate" in adj
        assert "tighten" in adj["quality_gate"]

    def test_continuity_guard_no_state(self, registry: GuardRegistry) -> None:
        """ContinuityGuard无state时跳过。"""
        registry.register(ContinuityGuard())
        results = registry.run_all("text", {"chapter_num": 1})
        assert results[0].level == "PASS"
        assert "跳过" in results[0].message

    def test_duplicate_register(self, registry: GuardRegistry) -> None:
        """重复注册应覆盖。"""
        registry.register(DummyGuard())
        registry.register(DummyGuard())
        assert len(registry.list_guards()) == 1
