"""Fake LLM 服务 —— 用于测试，不消耗真实 API Token。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from infrastructure.llm import LLMConfig, LLMService, LLMError


@dataclass
class FakeLLMService(LLMService):
    """可编程的 Fake LLM，用于单元测试和集成测试。

    使用方式：
        fake = FakeLLMService()
        fake.when(system_contains="Director").then_return("【标题】第1章：测试标题\n核心事件：...")
        fake.when(user_contains="钩子").then_return("优化后的正文...")

        pipeline = WritingPipeline(llm=fake)
        result = pipeline.execute(ctx)
    """

    _responses: list[tuple[dict[str, Any], str]] = field(default_factory=list)
    _default_response: str = "（这是 Fake LLM 的默认返回）"
    _call_log: list[tuple[str, str]] = field(default_factory=list)

    def when(self, **conditions: Any) -> "_ResponseBuilder":
        """注册匹配条件。"""
        return _ResponseBuilder(self, conditions)

    def complete(self, system: str, user: str, config: LLMConfig | None = None) -> str:
        self._call_log.append((system[:50], user[:50]))

        for conditions, response in self._responses:
            if self._matches(system, user, conditions):
                return response

        return self._default_response

    def health_check(self) -> bool:
        return True

    def get_call_count(self) -> int:
        return len(self._call_log)

    def assert_called_with(self, **conditions: Any) -> None:
        """断言某次调用匹配条件。"""
        for sys_prompt, user_prompt in self._call_log:
            if self._matches(sys_prompt, user_prompt, conditions):
                return
        raise AssertionError(f"未找到匹配 {conditions} 的调用。调用记录: {self._call_log}")

    @staticmethod
    def _matches(system: str, user: str, conditions: dict[str, Any]) -> bool:
        for key, value in conditions.items():
            if key == "system_contains" and value not in system:
                return False
            if key == "user_contains" and value not in user:
                return False
            if key == "system_regex" and not __import__("re").search(value, system):
                return False
        return True


@dataclass
class _ResponseBuilder:
    _fake: FakeLLMService
    _conditions: dict[str, Any]

    def then_return(self, text: str) -> None:
        self._fake._responses.append((self._conditions, text))
