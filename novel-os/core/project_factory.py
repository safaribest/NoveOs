"""项目工厂：根据洞察生成的大纲创建可直接写作的 Novel-OS 项目。"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import yaml

from core.config_loader import BookConfig, get_novel_base_path
from core.llm_settings_client import LLMSettingsClient
from core.state_manager import StateManager
from core.fanqie_course import load_fanqie_rules
from core.writing.prompts import map_genre_to_course_key

logger = logging.getLogger("novel-os.project_factory")

DEFAULT_BASE_PATH = get_novel_base_path()


class ProjectFactoryError(Exception):
    """项目创建错误。"""


def _make_project_id(title: str) -> str:
    """根据标题生成安全的项目 ID（可用作目录名）。"""
    # 移除 Windows / Linux 非法字符
    safe = re.sub(r'[<>:"/\\|?*]', "", title)
    safe = safe.strip().replace(" ", "_")
    if not safe:
        safe = "project"
    # 避免目录名过长
    safe = safe[:60]
    suffix = uuid.uuid4().hex[:8]
    return f"{safe}_{suffix}"


def _get_active_llm_config() -> dict[str, Any]:
    """读取当前默认 LLM Provider 配置，用于初始化 book.yaml。"""
    try:
        client = LLMSettingsClient()
        provider_name = client.config.get("default_provider", "")
        provider = client.config.get("providers", {}).get(provider_name, {})
        if not provider:
            return {}

        from core.llm_settings_client import DEFAULT_PROVIDER_PRESETS

        provider_type = provider.get("type", "custom")
        preset = DEFAULT_PROVIDER_PRESETS.get(provider_type, {})
        return {
            "model": provider.get("model") or preset.get("model", "deepseek-chat"),
            "api_key": provider.get("api_key", ""),
            "api_base": provider.get("base_url") or preset.get("base_url", "https://api.deepseek.com/v1"),
            "temperature": float(provider.get("temperature", 0.8)),
            "max_tokens": int(provider.get("max_tokens", 4096)),
            "timeout": int(provider.get("timeout", 120)),
            "reasoning_effort": "high",
            "thinking_enabled": False,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取 LLM 配置失败，将使用空配置: %s", exc)
        return {}


class ProjectFactory:
    """根据大纲创建项目。"""

    def __init__(self, base_path: Path | str | None = None):
        self.base_path = Path(base_path or DEFAULT_BASE_PATH)

    def create_from_outline(
        self,
        title: str,
        outline: dict[str, Any],
        category_id: str | None = None,
        chapters_target: int | None = None,
        words_per_chapter: int | None = None,
    ) -> dict[str, Any]:
        """创建项目并返回 project_id / title。

        当调用方显式传入 chapters_target / words_per_chapter 时，严格使用用户输入值；
        仅当未传入时，才回退到 outline 自带值或按 outline 长度推导。
        """
        project_id = _make_project_id(title)
        project_dir = self.base_path / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        genre = outline.get("genre", "") or "都市"
        platform = outline.get("platform", "") or "起点"

        # 用户显式输入优先；未提供时按 outline 自身字段，再按实际章节列表长度兜底
        outline_chapters = len(outline.get("outline", []))
        effective_chapters_target = (
            chapters_target
            if chapters_target is not None
            else int(outline.get("chapters_target", outline_chapters) or outline_chapters)
        )
        effective_words_per_chapter = (
            words_per_chapter
            if words_per_chapter is not None
            else int(outline.get("words_per_chapter", 2200) or 2200)
        )
        total_words_target = effective_chapters_target * effective_words_per_chapter

        # 将最终生效值写回 outline，确保 book_data.py 和 world_state.db 保持一致
        outline["chapters_target"] = effective_chapters_target
        outline["words_per_chapter"] = effective_words_per_chapter

        # 1. book.yaml
        book_yaml_path = project_dir / "book.yaml"
        self._write_book_yaml(
            book_yaml_path,
            title=title,
            genre=genre,
            platform=platform,
            project_dir=project_dir,
            chapters_target=effective_chapters_target,
            words_per_chapter=effective_words_per_chapter,
            total_words_target=total_words_target,
        )

        # 2. book_data.py（安全序列化，避免代码注入）
        book_data_path = project_dir / "book_data.py"
        self._write_book_data_py(book_data_path, outline)

        # 3. world_state.db
        db_path = project_dir / "world_state.db"
        self._init_world_state(
            db_path,
            project_id=project_id,
            title=title,
            genre=genre,
            platform=platform,
            project_dir=project_dir,
            outline=outline,
        )

        # 4. 注册到 orchestrator（延迟导入避免循环依赖）
        from api.main import orchestrator

        book_config = BookConfig.from_yaml(book_yaml_path)
        orchestrator.register_project(project_id, book_config)

        logger.info("项目创建成功: %s (%s)", title, project_id)
        return {
            "project_id": project_id,
            "title": title,
            "base_path": str(project_dir),
            "env_file": str(project_dir / ".env"),
            "note": "book.yaml 中的 api_key 已使用 ${OPENAI_API_KEY} 占位，运行前请 source 项目目录下的 .env 文件或设置环境变量",
        }

    def _write_book_yaml(
        self,
        path: Path,
        title: str,
        genre: str,
        platform: str,
        project_dir: Path,
        chapters_target: int,
        words_per_chapter: int,
        total_words_target: int,
    ) -> None:
        llm_cfg = _get_active_llm_config()
        api_key = llm_cfg.get("api_key", "")
        # book.yaml 不直接保存真实 api_key，使用环境变量占位
        llm_cfg["api_key"] = "${OPENAI_API_KEY}"

        genre_key = map_genre_to_course_key(genre)
        try:
            emotion_ratio = load_fanqie_rules().get_emotion_ratio(genre_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("加载情绪配比失败，使用默认值: %s", exc)
            emotion_ratio = {"shuang": 0.35, "tian": 0.25, "ping": 0.25, "nue": 0.15}

        config = {
            "project": title,
            "platform": platform,
            "genre": genre,
            "target_tier": "A",
            "total_words_target": total_words_target,
            "chapters_target": chapters_target,
            "words_per_chapter": words_per_chapter,
            "base_path": str(project_dir),
            "output_dir": "chapters",
            "plugin_id": "",
            "fanqie_course_profile": {
                "genre_key": genre_key,
                "emotion_ratio": emotion_ratio,
                "active_rules": ["opening", "chapter_beat", "dialogue", "pacing"],
            },
            "agent_query": {},
            "writing": {
                "tolerance": int(words_per_chapter * 0.1),
                "max_retries": 3,
                "batch_size": 5,
            },
            "llm": llm_cfg,
            "llm_fallback": {},
            "author_persona": {},
            "outer_crew": {
                "enabled": False,
                "inspection_interval": 10,
                "auto_apply": False,
            },
            "exploration_mode": {
                "enabled": False,
                "until_chapter": 5,
                "max_retries": 2,
            },
        }
        path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")

        # 将真实 api_key 写入项目级 .env 文件（不被提交，运行前可 source）
        if api_key:
            env_path = project_dir / ".env"
            env_path.write_text(f"OPENAI_API_KEY={api_key}\n", encoding="utf-8")

    def _write_book_data_py(self, path: Path, outline: dict[str, Any]) -> None:
        """生成 book_data.py，使用 json.loads 包裹静态数据，避免代码注入。"""
        payload = {
            "title": outline.get("topic_title", ""),
            "hook": outline.get("topic_hook", ""),
            "genre": outline.get("genre", ""),
            "platform": outline.get("platform", ""),
            "chapters_target": outline.get("chapters_target", 200),
            "words_per_chapter": outline.get("words_per_chapter", 2200),
            "summary": outline.get("summary", ""),
            "volumes": outline.get("volumes", []),
            "outline": outline.get("outline", []),
            "characters": outline.get("characters", []),
            "debts": outline.get("debts", []),
            "foreshadowing": outline.get("foreshadowing", []),
            "rules": outline.get("rules", []),
            "skills": outline.get("skills", []),
        }
        json_text = json.dumps(payload, ensure_ascii=False, indent=2)
        content = f"\"\"\"由 Novel-OS 洞察模块自动生成的大纲数据。\"\"\"\n\nimport json\n\nOUTLINE = json.loads(r'''\n{json_text}\n''')\n"
        path.write_text(content, encoding="utf-8")

    def _init_world_state(
        self,
        db_path: Path,
        project_id: str,
        title: str,
        genre: str,
        platform: str,
        project_dir: Path,
        outline: dict[str, Any],
    ) -> None:
        state = StateManager(db_path, project_id)
        chapters_target = int(outline.get("chapters_target", 200) or 200)

        # 初始化项目元信息 + schema
        state.init_project(
            project_id=project_id,
            name=title,
            genre=genre,
            platform=platform,
            base_path=str(project_dir),
            total_chapters=chapters_target,
        )
        # 初始化品类 DNA
        state.init_genre_dna(genre)

        with sqlite3.connect(str(db_path)) as conn:
            # 写入章节大纲
            for ch in outline.get("outline", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO outline
                    (project_id, chapter, arc, core_event, face_slap_target, face_slap_method,
                     husband_moment, chapter_hook, emotion_ratio, skill_unlocked,
                     questions, reveal_at, beat_pattern)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        int(ch.get("chapter", 0)),
                        ch.get("arc", ""),
                        ch.get("core_event", ""),
                        ch.get("face_slap_target", ""),
                        ch.get("face_slap_method", ""),
                        ch.get("husband_moment", ""),
                        ch.get("chapter_hook", ""),
                        ch.get("emotion_ratio", "5:3:2"),
                        ch.get("skill_unlocked", ""),
                        json.dumps(ch.get("questions", []), ensure_ascii=False),
                        ch.get("reveal_at"),
                        json.dumps(ch.get("beat_pattern", {}), ensure_ascii=False),
                    ),
                )

            # 写入角色初始状态
            for c in outline.get("characters", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO character_states
                    (project_id, chapter, character_name, location, emotional_state,
                     known_secrets, unknown_secrets, abilities_active, abilities_locked,
                     dialog_fingerprint, body_language, physical_description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        0,
                        c.get("name", "未命名"),
                        "",
                        "",
                        json.dumps([], ensure_ascii=False),
                        json.dumps([], ensure_ascii=False),
                        json.dumps(c.get("tags", []) or [], ensure_ascii=False),
                        json.dumps([], ensure_ascii=False),
                        c.get("brief", ""),
                        "",
                        c.get("arc", ""),
                    ),
                )

            # 写入债务
            for d in outline.get("debts", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO debts
                    (project_id, debt_id, type, content, bury_chapter, collect_chapter, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        d.get("debt_id", f"d_{uuid.uuid4().hex[:6]}"),
                        d.get("type", "债务"),
                        d.get("content", ""),
                        int(d.get("bury_chapter", 1)),
                        int(d.get("collect_chapter", 1)) if d.get("collect_chapter") is not None else None,
                        "active",
                    ),
                )

            # 写入伏笔
            for f in outline.get("foreshadowing", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO foreshadowing
                    (project_id, fs_id, bury_chapter, content, collect_chapter, type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        f.get("debt_id", f"f_{uuid.uuid4().hex[:6]}"),
                        int(f.get("bury_chapter", 1)),
                        f.get("content", ""),
                        int(f.get("collect_chapter", 1)) if f.get("collect_chapter") is not None else None,
                        f.get("type", "伏笔"),
                        "active",
                    ),
                )

            # 写入世界观规则
            for rule in outline.get("rules", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO consistency_rules
                    (project_id, rule_type, rule_content, enforcement_level)
                    VALUES (?, ?, ?, ?)
                    """,
                    (project_id, "world_lock", rule, "hard"),
                )

            # 写入技能树
            for sk in outline.get("skills", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO skill_tree
                    (project_id, skill_name, unlock_chapter, description, used_chapters)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        sk.get("name", "未命名技能"),
                        int(sk.get("chapter", 1)),
                        sk.get("description", ""),
                        json.dumps(sk.get("used_chapters", []), ensure_ascii=False),
                    ),
                )

            conn.commit()
