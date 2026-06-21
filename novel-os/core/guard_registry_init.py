"""Guard Registry 初始化 —— 注册所有 Guard 并创建带 Registry 的 ChapterValidator。

ChapterValidator 负责硬指标校验（字数、他字密度、禁用词等）。
GuardRegistry 负责插件化扩展校验（连续性、幻觉、节奏、文风一致性等）。
两者在 ChapterValidator.validate() 中合并输出。
"""
from __future__ import annotations

from core.chapter_validator import ChapterValidator
from core.guards.causality_guard import CausalityGuard
from core.guards.continuity_guard import ContinuityGuard
from core.guards.hallucination_guard import HallucinationGuard
from core.guards.pacing_guard import PacingGuard
from core.guards.quality_gate_guard import QualityGateGuard
from core.guards.reader_pull_guard import ReaderPullGuard
from core.guards.registry import GuardRegistry
from core.guards.voice_consistency_guard import VoiceConsistencyGuard
from core.quality_gates import QualityGates

# 全局单例
_validator: ChapterValidator | None = None


def get_registry() -> ChapterValidator:
    """获取带 GuardRegistry 的 ChapterValidator 单例。"""
    global _validator
    if _validator is None:
        registry = GuardRegistry()
        # 注册所有 Guard（按优先级排序）
        registry.register(QualityGateGuard(QualityGates()))
        registry.register(ContinuityGuard())
        registry.register(CausalityGuard())
        registry.register(HallucinationGuard())
        registry.register(PacingGuard())
        registry.register(ReaderPullGuard())
        registry.register(VoiceConsistencyGuard())
        _validator = ChapterValidator(guard_registry=registry)
    return _validator


def reset_registry() -> None:
    """重置单例（主要用于测试）。"""
    global _validator
    _validator = None
