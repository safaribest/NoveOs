"""LLM Provider 配置管理与统一调用客户端（面向前端设置页）。

注意：此模块不替代 core.llm_client（写作流水线仍使用后者）。
它只为前端提供：
1. 读写 novel-os/config/llm.yaml
2. 测试 Provider 连通性
3. 统一调用任意已配置 Provider
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import yaml
from openai import AsyncOpenAI, OpenAI

logger = logging.getLogger("novel-os.llm_settings")

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "llm.yaml"

DEFAULT_PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-v4-pro",
    },
    "deepseek_thinking": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-v4-pro",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-latest",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
        "model": "glm-5.2",
    },
}


class LLMProviderError(Exception):
    """LLM Provider 配置错误。"""


class LLMSettingsClient:
    """LLM Provider 配置客户端。"""

    def __init__(self, config_path: Path | str | None = None):
        self.config_path = Path(config_path or DEFAULT_CONFIG_PATH)
        self._config: dict[str, Any] | None = None

    def _load_config(self) -> dict[str, Any]:
        """加载 LLM 配置文件。"""
        if not self.config_path.exists():
            logger.warning("LLM 配置文件不存在: %s", self.config_path)
            return {"default_provider": "", "providers": {}}

        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise LLMProviderError(f"YAML 解析失败: {exc}") from exc

        return {
            "default_provider": config.get("default_provider", ""),
            "providers": config.get("providers", {}),
        }

    @property
    def config(self) -> dict[str, Any]:
        """当前配置（带缓存）。"""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def reload(self) -> None:
        """重新加载配置。"""
        self._config = None

    def _get_provider_config(self, provider_name: str | None = None) -> dict[str, Any]:
        """获取指定 provider 的配置，未指定则使用默认。"""
        name = provider_name or self.config.get("default_provider", "")
        if not name:
            raise LLMProviderError("未指定 provider，且没有设置默认 provider")

        provider = self.config.get("providers", {}).get(name)
        if not provider:
            raise LLMProviderError(f"Provider 未配置: {name}")

        provider_type = provider.get("type", "custom")
        preset = DEFAULT_PROVIDER_PRESETS.get(provider_type, {})

        def _expand_env(val: Any) -> Any:
            """展开字符串中的 ${VAR} 或 $VAR 环境变量引用。"""
            if not isinstance(val, str):
                return val
            # Windows 也兼容 Unix 风格 ${VAR}
            import re
            def _repl(m: re.Match) -> str:
                var_name = m.group(1) or m.group(2)
                return os.environ.get(var_name, m.group(0))
            return re.sub(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)', _repl, val)

        return {
            "name": name,
            "api_key": _expand_env(provider.get("api_key", "")),
            "base_url": provider.get("base_url") or preset.get("base_url", ""),
            "model": provider.get("model") or preset.get("model", ""),
            "temperature": provider.get("temperature", 0.8),
            "max_tokens": provider.get("max_tokens", 4096),
            "timeout": provider.get("timeout", 120),
            "thinking_enabled": provider.get("thinking_enabled", False),
            "reasoning_effort": provider.get("reasoning_effort", "high"),
        }

    def get_sync_client(self, provider_name: str | None = None) -> OpenAI:
        """获取同步 OpenAI 客户端。"""
        cfg = self._get_provider_config(provider_name)
        if not cfg["api_key"]:
            raise LLMProviderError("API Key 不能为空")
        return OpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            timeout=cfg["timeout"],
        )

    def get_async_client(self, provider_name: str | None = None) -> AsyncOpenAI:
        """获取异步 OpenAI 客户端。"""
        cfg = self._get_provider_config(provider_name)
        if not cfg["api_key"]:
            raise LLMProviderError("API Key 不能为空")
        return AsyncOpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            timeout=cfg["timeout"],
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        provider_name: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """同步聊天调用。"""
        cfg = self._get_provider_config(provider_name)
        client = self.get_sync_client(provider_name)
        call_kwargs = {
            "model": cfg["model"],
            "messages": messages,  # type: ignore[arg-type]
            "temperature": kwargs.get("temperature", cfg["temperature"]),
            "max_tokens": kwargs.get("max_tokens", cfg["max_tokens"]),
        }
        # DeepSeek thinking 模式支持
        if cfg.get("thinking_enabled") and cfg["model"].startswith("deepseek-v4"):
            call_kwargs["extra_body"] = {
                "thinking": {"type": "enabled"},
                "reasoning_effort": cfg.get("reasoning_effort", "high"),
            }
        return client.chat.completions.create(**call_kwargs)

    async def achat(
        self,
        messages: list[dict[str, str]],
        provider_name: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """异步聊天调用。"""
        cfg = self._get_provider_config(provider_name)
        client = self.get_async_client(provider_name)
        call_kwargs = {
            "model": cfg["model"],
            "messages": messages,  # type: ignore[arg-type]
            "temperature": kwargs.get("temperature", cfg["temperature"]),
            "max_tokens": kwargs.get("max_tokens", cfg["max_tokens"]),
        }
        # DeepSeek thinking 模式支持
        if cfg.get("thinking_enabled") and cfg["model"].startswith("deepseek-v4"):
            call_kwargs["extra_body"] = {
                "thinking": {"type": "enabled"},
                "reasoning_effort": cfg.get("reasoning_effort", "high"),
            }
        return await client.chat.completions.create(**call_kwargs)

    def test_connection(self, provider_name: str | None = None) -> dict[str, Any]:
        """测试 provider 连通性。"""
        start = time.time()
        try:
            client = self.get_sync_client(provider_name)
            response = client.chat.completions.create(
                model=self._get_provider_config(provider_name)["model"],
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            latency = round((time.time() - start) * 1000, 2)
            return {
                "success": True,
                "message": "连接成功",
                "latency_ms": latency,
                "model": response.model,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 连接测试失败: %s", exc)
            return {
                "success": False,
                "message": f"连接失败: {exc}",
            }

    async def atest_connection(self, provider_name: str | None = None) -> dict[str, Any]:
        """异步测试 provider 连通性。"""
        start = time.time()
        try:
            client = self.get_async_client(provider_name)
            response = await client.chat.completions.create(
                model=self._get_provider_config(provider_name)["model"],
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            latency = round((time.time() - start) * 1000, 2)
            return {
                "success": True,
                "message": "连接成功",
                "latency_ms": latency,
                "model": response.model,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 连接测试失败: %s", exc)
            return {
                "success": False,
                "message": f"连接失败: {exc}",
            }


def load_llm_settings(config_path: Path | str | None = None) -> dict[str, Any]:
    """加载 LLM 设置（供 router 使用）。"""
    client = LLMSettingsClient(config_path)
    config = client.config
    # 确保 agent_providers 字段存在
    if "agent_providers" not in config:
        config["agent_providers"] = {}
    return config


def save_llm_settings(
    settings: dict[str, Any],
    config_path: Path | str | None = None,
) -> None:
    """保存 LLM 设置（供 router 使用）。"""
    path = Path(config_path or DEFAULT_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, allow_unicode=True, sort_keys=False)


def get_agent_providers(config_path: Path | str | None = None) -> dict[str, str]:
    """获取 Agent → Provider 映射。"""
    settings = load_llm_settings(config_path)
    return settings.get("agent_providers", {})


def save_agent_providers(
    agent_providers: dict[str, str],
    config_path: Path | str | None = None,
) -> None:
    """保存 Agent → Provider 映射。"""
    path = Path(config_path or DEFAULT_CONFIG_PATH)
    settings = load_llm_settings(path) if path.exists() else {"default_provider": "", "providers": {}}
    settings["agent_providers"] = agent_providers
    save_llm_settings(settings, path)
