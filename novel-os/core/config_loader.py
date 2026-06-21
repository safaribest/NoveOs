"""Novel-OS 配置加载器 —— 解析 book.yaml 为强类型 BookConfig。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


import re


def _normalize_path(value: str) -> Path:
    r"""规范化路径：在 Windows 上将 Unix 风格绝对路径 /x/... 转换为 X:\...。"""
    value = value.strip()
    if os.name == "nt":
        # 匹配 /c/... 或 /C/... 等单盘符绝对路径
        m = re.match(r"^/([a-zA-Z])/(.*)$", value)
        if m:
            value = f"{m.group(1).upper()}:/" + m.group(2)
    return Path(value).resolve()


def get_novel_base_path() -> Path:
    """获取 Novel-OS 项目根目录（环境变量 NOVEL_BASE_PATH，默认 D:/noveos/books）。"""
    return _normalize_path(os.environ.get("NOVEL_BASE_PATH", "D:/noveos/books"))


def _expand_env(value: str) -> str:
    """跨平台环境变量展开，支持 ${VAR}、$VAR 和 %VAR%（Windows）。"""
    # 1. Windows 原生 %VAR%
    expanded = os.path.expandvars(value)
    # 2. Unix 风格 ${VAR} 和 $VAR
    def _repl(m: re.Match) -> str:
        var_name = m.group(1) or m.group(2)
        return os.environ.get(var_name, m.group(0))
    expanded = re.sub(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)', _repl, expanded)
    return expanded

def _resolve_llm(llm_cfg: dict[str, Any]) -> dict[str, Any]:
    """对 llm 配置中的所有字符串字段做环境变量展开。"""
    if not llm_cfg:
        return llm_cfg
    resolved = dict(llm_cfg)
    for key in ("model", "api_key", "api_base", "reasoning_effort"):
        if key in resolved and isinstance(resolved[key], str):
            expanded = _expand_env(resolved[key])
            if "$" not in expanded and "%" not in expanded:
                resolved[key] = expanded
    # bool / int 字段不做展开
    return resolved


@dataclass
class BookConfig:
    """单本小说的全局配置，由 book.yaml 反序列化而来。"""

    # 项目元信息
    project: str
    platform: str
    genre: str
    target_tier: str
    total_words_target: int
    chapters_target: int
    words_per_chapter: int
    base_path: Path
    output_dir: str
    # 兼容层：旧版 book.yaml 可能包含 crewai_db_path，解析时忽略
    v8_dir: str | None = None

    # Agent 查询配置
    agent_query: dict[str, dict[str, str]] = field(default_factory=dict)

    # 写作参数
    writing: dict[str, Any] = field(default_factory=dict)

    # LLM 配置
    llm: dict[str, Any] = field(default_factory=dict)

    # Fallback LLM 配置（主Provider失败时自动切换）
    llm_fallback: dict[str, Any] = field(default_factory=dict)

    # 作者人格注入
    author_persona: dict[str, Any] = field(default_factory=dict)

    # 外层 CrewAI 配置
    outer_crew: dict[str, Any] = field(default_factory=dict)

    # 探索模式配置（前N章轻量验证）
    exploration_mode: dict[str, Any] = field(default_factory=dict)

    # 插件 ID
    plugin_id: str = ""

    # Agent 专属 LLM 配置（新增：支持按 Agent 配置不同模型）
    agent_llm: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def _load_dotenv(cls, base_path: Path) -> None:
        """加载项目目录下的 .env 文件到环境变量（如果存在）。"""
        env_path = base_path / ".env"
        if not env_path.exists():
            return
        try:
            with env_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key:
                        os.environ[key] = value
        except Exception:  # noqa: BLE001
            pass

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "BookConfig":
        """从 book.yaml 文件加载配置。

        Args:
            yaml_path: book.yaml 的本地路径。

        Raises:
            FileNotFoundError: yaml_path 不存在。
            ValueError: 环境变量未设置或 YAML 结构缺失关键字段。
        """
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"book.yaml 不存在: {yaml_path}")

        raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

        # 必需字段校验（crewai_db_path 已废弃，不再强制要求）
        required = ["project", "platform", "genre", "base_path"]
        missing = [k for k in required if k not in raw]
        if missing:
            raise ValueError(f"book.yaml 缺少必需字段: {missing}")

        # 解析路径并展开环境变量
        base_path = cls._resolve_path(raw["base_path"], "NOVEL_BASE_PATH")

        # 加载项目级 .env（让 ${OPENAI_API_KEY} 等占位符能展开）
        cls._load_dotenv(base_path)
        # 重新展开一次，确保 .env 中设置的变量生效
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

        # 解析 agent_llm 配置（新增）
        agent_llm_raw = raw.get("agent_llm", {})
        agent_llm: dict[str, dict[str, Any]] = {}
        for agent_name, agent_cfg in agent_llm_raw.items():
            if isinstance(agent_cfg, dict):
                agent_llm[agent_name] = _resolve_llm(agent_cfg)

        return cls(
            project=raw["project"],
            platform=raw["platform"],
            genre=raw["genre"],
            target_tier=raw.get("target_tier", "A"),
            total_words_target=raw.get("total_words_target", 0),
            chapters_target=raw.get("chapters_target", 0),
            words_per_chapter=raw.get("words_per_chapter", 4500),
            base_path=base_path,
            output_dir=raw.get("output_dir", "chapters"),
            v8_dir=raw.get("v8_dir"),
            agent_query=raw.get("agent_query", {}),
            writing=raw.get("writing", {}),
            llm=_resolve_llm(raw.get("llm", {})),
            llm_fallback=_resolve_llm(raw.get("llm_fallback", {})),
            author_persona=raw.get("author_persona", {}),
            outer_crew=raw.get("outer_crew", {}),
            exploration_mode=raw.get("exploration_mode", {}),
            plugin_id=raw.get("plugin_id", ""),
            agent_llm=agent_llm,
        )

    @staticmethod
    def _resolve_path(value: str, env_hint: str) -> Path:
        """展开环境变量并返回 Path；若展开后仍含 '$' 或 '%' 说明变量未定义。"""
        expanded = _expand_env(value)
        if "$" in expanded or "%" in expanded:
            raise ValueError(
                f"路径中的环境变量未设置: {value!r}。"
                f"请确保 {env_hint} 等环境变量已导出。"
            )
        return _normalize_path(expanded)

    @property
    def words_tolerance(self) -> int:
        """单章字数容差，默认 10%。"""
        return self.writing.get("tolerance", int(self.words_per_chapter * 0.1))

    @property
    def max_retries(self) -> int:
        """质量门拦截后的最大重试次数。"""
        return self.writing.get("max_retries", 3)

    @property
    def batch_size(self) -> int:
        """批量写作时每批连续写的章节数。"""
        return self.writing.get("batch_size", 5)

    def to_dict(self) -> dict[str, Any]:
        """将 BookConfig 导出为 dict，供 StateManager.init_project 等使用。"""
        return {
            "project": self.project,
            "platform": self.platform,
            "genre": self.genre,
            "target_tier": self.target_tier,
            "total_words_target": self.total_words_target,
            "chapters_target": self.chapters_target,
            "words_per_chapter": self.words_per_chapter,
            "base_path": str(self.base_path),

            "output_dir": self.output_dir,
            "v8_dir": self.v8_dir,
            "agent_query": self.agent_query,
            "writing": self.writing,
            "llm": self.llm,
            "author_persona": self.author_persona,
            "exploration_mode": self.exploration_mode,
            "plugin_id": self.plugin_id,
            "agent_llm": self.agent_llm,
        }

    def update_fields(
        self,
        *,
        project: str | None = None,
        genre: str | None = None,
        platform: str | None = None,
        chapters_target: int | None = None,
        words_per_chapter: int | None = None,
        total_words_target: int | None = None,
    ) -> "BookConfig":
        """更新指定字段，同步修改 book.yaml 并返回新的 BookConfig。

        通过正则只修改目标字段，保留 YAML 中的其他内容（如环境变量占位符）。
        """
        yaml_path = self.base_path / "book.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"book.yaml 不存在: {yaml_path}")

        text = yaml_path.read_text(encoding="utf-8")

        def _replace_field(name: str, value: Any) -> None:
            nonlocal text
            if value is None:
                return
            # 支持 xxx: value 或 xxx: 'value' 或 xxx: "value"
            pattern = rf"^(\s*{re.escape(name)}\s*:\s*).*$"
            replacement = rf"\g<1>{value}"
            new_text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
            if count == 0:
                # 字段不存在时追加到文件末尾
                new_text = text.rstrip() + f"\n{name}: {value}\n"
            text = new_text

        _replace_field("project", project)
        _replace_field("genre", genre)
        _replace_field("platform", platform)
        _replace_field("chapters_target", chapters_target)
        _replace_field("words_per_chapter", words_per_chapter)
        _replace_field("total_words_target", total_words_target)

        yaml_path.write_text(text, encoding="utf-8")

        # 重新加载以返回最新配置
        return BookConfig.from_yaml(yaml_path)
