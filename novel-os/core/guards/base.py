"""Guard 抽象基类 —— 所有门禁必须实现的接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class GuardResult:
    """单条门禁检查结果。"""

    guard_id: str
    level: str  # "BLOCKING" | "WARN" | "PASS" | "INFO"
    message: str
    metadata: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseGuard(ABC):
    """门禁抽象基类。

    子类必须实现:
        - guard_id: 唯一标识
        - run(content: str, context: dict) -> GuardResult
    """

    guard_id: str = ""
    description: str = ""
    default_level: str = "BLOCKING"

    @abstractmethod
    def run(self, content: str, context: dict[str, Any]) -> GuardResult:
        """执行门禁检查。

        Args:
            content: 待检查文本（章节正文）。
            context: 运行时上下文（章节号、项目配置等）。

        Returns:
            GuardResult
        """
        ...

    def calibrate(self, hits: int, total: int) -> dict[str, Any]:
        """校准循环：根据命中率调整参数。

        Args:
            hits: 触发该 guard 的次数。
            total: 总检查次数。

        Returns:
            更新后的参数字典（子类可选实现）。
        """
        return {}
