"""配置加载 —— 从 book.yaml 解析为类型安全的数据结构。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AgentLLMConfig:
    """单个 Agent 的 LLM 覆盖配置。"""

    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass
class WritingConfig:
    """写作行为配置。"""

    words_per_chapter: int = 4500
    tolerance: int = 450
    max_retries: int = 3
    batch_size: int = 5


@dataclass
class BookConfig:
    """book.yaml 的完整配置对象。

    替代现有的字典式访问，提供类型安全和 IDE 自动补全。
    """

    project: str = ""
    platform: str = ""
    genre: str = ""
    target_tier: str = "A+"
    total_words_target: int = 800000
    chapters_target: int = 240
    words_per_chapter: int = 4500
    base_path: Path = field(default_factory=lambda: Path("."))
    output_dir: str = "chapters"
    plugin_id: str = ""

    writing: WritingConfig = field(default_factory=WritingConfig)

    # LLM 配置
    llm_model: str = "deepseek-ai/DeepSeek-V3"
    llm_api_key: str = ""
    llm_api_base: str = "https://api.siliconflow.cn/v1"
    llm_temperature: float = 1.0
    llm_max_tokens: int = 12000
    llm_timeout: int = 180

    # Agent 专属 LLM 配置
    agent_llm: dict[str, AgentLLMConfig] = field(default_factory=dict)

    # 外层 Crew 配置
    outer_crew_enabled: bool = True

    @classmethod
    def from_yaml(cls, path: Path) -> "BookConfig":
        """从 YAML 文件加载，支持环境变量替换 ${VAR}。"""
        text = path.read_text(encoding="utf-8")
        # 简单环境变量替换
        text = os.path.expandvars(text)
        data = yaml.safe_load(text)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "BookConfig":
        writing_data = data.get("writing", {})
        llm_data = data.get("llm", {})
        agent_data = data.get("agent_query", {})

        return cls(
            project=data.get("project", ""),
            platform=data.get("platform", ""),
            genre=data.get("genre", ""),
            target_tier=data.get("target_tier", "A+"),
            total_words_target=data.get("total_words_target", 800000),
            chapters_target=data.get("chapters_target", 240),
            words_per_chapter=data.get("words_per_chapter", 4500),
            base_path=Path(data.get("base_path", ".")),
            output_dir=data.get("output_dir", "chapters"),
            plugin_id=data.get("plugin_id", ""),
            writing=WritingConfig(
                words_per_chapter=writing_data.get("words_per_chapter", 4500),
                tolerance=writing_data.get("tolerance", 450),
                max_retries=writing_data.get("max_retries", 3),
                batch_size=writing_data.get("batch_size", 5),
            ),
            llm_model=llm_data.get("model", "deepseek-ai/DeepSeek-V3"),
            llm_api_key=llm_data.get("api_key", ""),
            llm_api_base=llm_data.get("api_base", "https://api.siliconflow.cn/v1"),
            llm_temperature=llm_data.get("temperature", 1.0),
            llm_max_tokens=llm_data.get("max_tokens", 12000),
            llm_timeout=llm_data.get("timeout", 180),
            outer_crew_enabled=data.get("outer_crew", {}).get("enabled", True),
        )

    @property
    def words_tolerance(self) -> int:
        return self.writing.tolerance
