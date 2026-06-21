"""Guard Registry —— 插件化门禁系统。

设计约束:
    - 每个 Guard 独立注册，互不影响
    - 支持分级执行：BLOCKING / WARN / INFO
    - 支持校准循环：命中率低于阈值时自动调参
"""
from core.guards.registry import GuardRegistry, GuardResult, GuardLevel
from core.guards.base import BaseGuard

__all__ = ["GuardRegistry", "GuardResult", "GuardLevel", "BaseGuard"]
