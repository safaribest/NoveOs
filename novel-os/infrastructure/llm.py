"""LLM 服务抽象 —— 替代 llm_client.py，更薄、更易 Mock。"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("novel-os.llm")


@dataclass
class LLMConfig:
    """LLM 调用配置。"""

    model: str = "deepseek-v4-pro"
    api_key: str = ""
    api_base: str = "https://api.deepseek.com/v1"
    temperature: float = 0.7
    max_tokens: int = 8000
    timeout: int = 300
    reasoning_effort: str = "high"
    thinking_enabled: bool = False


class LLMService(ABC):
    """LLM 服务抽象。

    职责：只负责发送请求和接收响应。
    不负责：Prompt 构建、重试逻辑、Token 统计（这些在 Step 或 infrastructure 层处理）。
    """

    @abstractmethod
    def complete(self, system: str, user: str, config: LLMConfig | None = None) -> str:
        """发送 completion 请求，返回文本响应。

        Args:
            system: system prompt
            user: user prompt
            config: 本次调用的覆盖配置（如 temperature），为 None 时使用默认

        Returns:
            LLM 返回的文本内容（已去除多余空白）

        Raises:
            LLMError: 调用失败时抛出
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """检查服务是否可用。"""
        ...


class LLMError(Exception):
    """LLM 调用异常。"""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class LiteLLMService(LLMService):
    """基于 LiteLLM 的实现。"""

    def __init__(self, default_config: LLMConfig) -> None:
        self._default = default_config
        try:
            from litellm import completion

            self._completion = completion
        except ImportError:
            raise RuntimeError("litellm 未安装，请执行: pip install litellm")

    def complete(self, system: str, user: str, config: LLMConfig | None = None) -> str:
        cfg = config or self._default
        try:
            resp = self._completion(
                model=cfg.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                api_key=cfg.api_key or None,
                api_base=cfg.api_base or None,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                timeout=cfg.timeout,
            )
            content = resp.choices[0].message.content or ""
            return content.strip()
        except Exception as exc:
            logger.error("LLM 调用失败: %s", exc)
            raise LLMError(str(exc), retryable=True)

    def health_check(self) -> bool:
        try:
            self.complete("You are a test assistant.", "Say 'ok' only.")
            return True
        except Exception:
            return False
