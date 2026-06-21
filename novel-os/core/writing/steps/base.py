"""写作流水线步骤基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.writing.context import ChapterContext


@dataclass
class StepResult:
    """单步执行结果。"""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    skip_subsequent: bool = False
    """为 True 时，后续步骤（如 HookEngineer → DialogueTuner）可跳过。"""


@dataclass
class StepFailure(Exception):
    """步骤执行失败。"""

    step_name: str
    reason: str
    correction_hint: str = ""
    retryable: bool = True


class PipelineStep(ABC):
    """流水线步骤抽象基类。

    每个 Agent 调用（Director/Writer/Polish 等）封装为一个 Step，
    实现统一的 execute 接口，便于编排、测试和替换。
    """

    name: str = ""

    @abstractmethod
    def execute(self, ctx: ChapterContext) -> StepResult:
        """执行本步骤。

        Args:
            ctx: 章节上下文，包含大纲、人设、前章摘要等。

        Returns:
            StepResult，其中 content 为本步骤产出的文本。

        Raises:
            StepFailure: 当步骤无法产出有效内容时抛出。
        """
        ...

    def fallback(self, ctx: ChapterContext, failure: StepFailure) -> str | None:
        """失败时的回退策略。

        默认返回 correction_hint，子类可覆盖以实现更智能的修正。

        Returns:
            修正指令字符串（注入下次重试的 corrections），或 None（完全失败）。
        """
        return failure.correction_hint or None
