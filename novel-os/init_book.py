#!/usr/bin/env python3
"""Novel-OS 新书初始化脚本。

从数据文件（Python 模块）中读取创作方案，一次性写入 world_state.db 的所有表。

用法:
    python init_book.py --book D:/noveos/books/新书名称/book.yaml --data D:/noveos/books/新书名称/book_data.py

book_data.py 模板见 _模板_新书配置/【模板】新书-book_data.py
"""
from __future__ import annotations

import argparse
import importlib.util
import logging
import sqlite3
import sys
from pathlib import Path

from core.config_loader import BookConfig
from core.state_manager import StateManager

logger = logging.getLogger("novel-os.init_book")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def load_data_module(data_path: str | Path):
    """动态加载用户的数据文件（Python 模块）。"""
    path = Path(data_path).resolve()
    spec = importlib.util.spec_from_file_location("book_data", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载数据文件: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["book_data"] = module
    spec.loader.exec_module(module)
    return module


def init_database(db_path: Path, project_id: str):
    """确保数据库 schema 已创建。"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # projects 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id      TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            genre           TEXT NOT NULL,
            platform        TEXT NOT NULL,
            base_path       TEXT,
            total_chapters  INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'initialized',
            current_chapter INTEGER DEFAULT 0,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # outline 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outline (
            project_id      TEXT,
            chapter         INTEGER,
            title           TEXT,
            arc             TEXT,
            core_event      TEXT,
            face_slap_target TEXT,
            face_slap_method TEXT,
            husband_moment  TEXT,
            chapter_hook    TEXT,
            emotion_ratio   TEXT,
            skill_unlocked  TEXT,
            PRIMARY KEY (project_id, chapter)
        )
    """)

    # character_states 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_states (
            project_id          TEXT NOT NULL,
            chapter             INTEGER NOT NULL,
            character_name      TEXT NOT NULL,
            location            TEXT,
            emotional_state     TEXT,
            known_secrets       TEXT,
            unknown_secrets     TEXT,
            abilities_active    TEXT,
            abilities_locked    TEXT,
            dialog_fingerprint  TEXT,
            body_language       TEXT,
            physical_description TEXT,
            PRIMARY KEY (project_id, chapter, character_name)
        )
    """)

    # debts 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debts (
            project_id      TEXT NOT NULL,
            debt_id         TEXT NOT NULL,
            type            TEXT,
            content         TEXT NOT NULL,
            bury_chapter    INTEGER NOT NULL,
            collect_chapter INTEGER,
            status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'collected', 'abandoned')),
            PRIMARY KEY (project_id, debt_id)
        )
    """)

    # foreshadowing 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS foreshadowing (
            project_id      TEXT NOT NULL,
            fs_id           TEXT NOT NULL,
            bury_chapter    INTEGER NOT NULL,
            content         TEXT NOT NULL,
            collect_chapter TEXT,
            type            TEXT,
            status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'collected', 'abandoned')),
            PRIMARY KEY (project_id, fs_id)
        )
    """)

    # consistency_rules 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS consistency_rules (
            project_id          TEXT NOT NULL,
            rule_type           TEXT NOT NULL,
            rule_content        TEXT NOT NULL,
            enforcement_level   TEXT DEFAULT 'hard' CHECK (enforcement_level IN ('hard', 'soft', 'info')),
            PRIMARY KEY (project_id, rule_type, rule_content)
        )
    """)

    # skill_tree 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_tree (
            project_id      TEXT,
            skill_name      TEXT,
            unlock_chapter  INTEGER,
            description     TEXT,
            used_chapters   TEXT,
            PRIMARY KEY (project_id, skill_name)
        )
    """)

    # chapter_history 表（注意：不要加外键约束，避免 init_project 时失败）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chapter_history (
            project_id      TEXT NOT NULL,
            chapter         INTEGER NOT NULL,
            summary         TEXT,
            word_count      INTEGER,
            mode            TEXT,
            title           TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (project_id, chapter)
        )
    """)

    # term_dict 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS term_dict (
            project_id      TEXT NOT NULL,
            term            TEXT NOT NULL,
            category        TEXT,
            first_chapter   INTEGER,
            description     TEXT,
            PRIMARY KEY (project_id, term)
        )
    """)

    conn.commit()
    conn.close()
    logger.info("数据库 schema 初始化完成: %s", db_path)


def extract_first_chapters(outline: list[dict], characters: list[dict]) -> dict[str, int]:
    """扫描大纲，提取每个角色的首次出场章节。"""
    first_map: dict[str, int] = {}
    names = {c.get("name", "") for c in characters if c.get("name")}
    for row in outline:
        ch = row.get("chapter", 0)
        text = " ".join([
            row.get("core_event", ""),
            row.get("face_slap_target", ""),
            row.get("face_slap_method", ""),
            row.get("husband_moment", ""),
            row.get("chapter_hook", ""),
        ])
        for name in names:
            if name in text and name not in first_map:
                first_map[name] = ch
    # 未在大纲中找到的角色，默认第1章出场
    for name in names:
        if name not in first_map:
            first_map[name] = 1
    return first_map


def insert_outline(conn: sqlite3.Connection, project_id: str, outline_data: list[dict]):
    if not outline_data:
        return
    cursor = conn.cursor()
    cursor.execute("DELETE FROM outline WHERE project_id=?", (project_id,))
    for row in outline_data:
        cursor.execute(
            """INSERT INTO outline (project_id, chapter, title, arc, core_event, face_slap_target,
               face_slap_method, husband_moment, chapter_hook, emotion_ratio, skill_unlocked)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                project_id,
                row.get("chapter", 0),
                row.get("title", ""),
                row.get("arc", ""),
                row.get("core_event", ""),
                row.get("face_slap_target", ""),
                row.get("face_slap_method", ""),
                row.get("husband_moment", ""),
                row.get("chapter_hook", ""),
                row.get("emotion_ratio", ""),
                row.get("skill_unlocked", ""),
            ),
        )
    logger.info("导入 outline: %d 章", len(outline_data))


def insert_characters(conn: sqlite3.Connection, project_id: str, characters: list[dict], first_chapters: dict[str, int] | None = None):
    if not characters:
        return
    cursor = conn.cursor()
    cursor.execute("DELETE FROM character_states WHERE project_id=?", (project_id,))
    for char in characters:
        name = char.get("name", "")
        first_ch = first_chapters.get(name, 1) if first_chapters else 1
        # 在首次出场章节插入角色状态
        cursor.execute(
            """INSERT INTO character_states (project_id, chapter, character_name, location,
               emotional_state, known_secrets, unknown_secrets, abilities_active,
               abilities_locked, dialog_fingerprint, body_language, physical_description)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                project_id,
                first_ch,
                name,
                char.get("location", ""),
                char.get("emotional_state", ""),
                char.get("known_secrets", ""),
                char.get("unknown_secrets", ""),
                char.get("abilities_active", ""),
                char.get("abilities_locked", ""),
                char.get("dialog_fingerprint", ""),
                char.get("body_language", ""),
                char.get("physical_description", ""),
            ),
        )
    logger.info("导入 characters: %d 人", len(characters))


def insert_debts(conn: sqlite3.Connection, project_id: str, debts: list[dict]):
    if not debts:
        return
    cursor = conn.cursor()
    cursor.execute("DELETE FROM debts WHERE project_id=?", (project_id,))
    for d in debts:
        cursor.execute(
            """INSERT INTO debts (project_id, debt_id, type, content, bury_chapter, collect_chapter, status)
               VALUES (?,?,?,?,?,?,?)""",
            (
                project_id,
                d.get("debt_id", ""),
                d.get("type", ""),
                d.get("content", ""),
                d.get("bury_chapter", 0),
                d.get("collect_chapter", None),
                d.get("status", "active"),
            ),
        )
    logger.info("导入 debts: %d 条", len(debts))


def insert_foreshadowing(conn: sqlite3.Connection, project_id: str, fs_list: list[dict]):
    if not fs_list:
        return
    cursor = conn.cursor()
    cursor.execute("DELETE FROM foreshadowing WHERE project_id=?", (project_id,))
    for f in fs_list:
        cursor.execute(
            """INSERT INTO foreshadowing (project_id, fs_id, bury_chapter, content, collect_chapter, type, status)
               VALUES (?,?,?,?,?,?,?)""",
            (
                project_id,
                f.get("fs_id", ""),
                f.get("bury_chapter", 0),
                f.get("content", ""),
                f.get("collect_chapter", None),
                f.get("type", ""),
                f.get("status", "active"),
            ),
        )
    logger.info("导入 foreshadowing: %d 条", len(fs_list))


def insert_rules(conn: sqlite3.Connection, project_id: str, rules: list[dict]):
    if not rules:
        return
    cursor = conn.cursor()
    cursor.execute("DELETE FROM consistency_rules WHERE project_id=?", (project_id,))
    for r in rules:
        cursor.execute(
            """INSERT INTO consistency_rules (project_id, rule_type, rule_content, enforcement_level)
               VALUES (?,?,?,?)""",
            (
                project_id,
                r.get("rule_type", ""),
                r.get("rule_content", ""),
                r.get("enforcement_level", "hard"),
            ),
        )
    logger.info("导入 rules: %d 条", len(rules))


def insert_terms(conn: sqlite3.Connection, project_id: str, skills: list[dict], outline: list[dict]):
    """从技能树和大纲中提取世界观术语，写入 term_dict。"""
    if not skills and not outline:
        return
    cursor = conn.cursor()
    cursor.execute("DELETE FROM term_dict WHERE project_id=?", (project_id,))

    # 从技能树提取
    for s in skills:
        name = s.get("skill_name", "").strip()
        if not name:
            continue
        cursor.execute(
            """INSERT OR REPLACE INTO term_dict (project_id, term, category, first_chapter, description)
               VALUES (?,?,?,?,?)""",
            (project_id, name, "技能", s.get("unlock_chapter", 0), s.get("description", "")),
        )

    # 从大纲 skill_unlocked 字段提取额外术语（解析形如 "鼓楼视野（觉醒）" 的字符串）
    import re
    for row in outline:
        ch = row.get("chapter", 0)
        skill_text = row.get("skill_unlocked", "")
        if not skill_text:
            continue
        # 提取括号前的技能名
        match = re.search(r'^([^（(]+)', skill_text.strip())
        if match:
            term = match.group(1).strip()
            if term and term not in [s.get("skill_name", "") for s in skills]:
                cursor.execute(
                    """INSERT OR REPLACE INTO term_dict (project_id, term, category, first_chapter, description)
                       VALUES (?,?,?,?,?)""",
                    (project_id, term, "技能", ch, skill_text),
                )

    logger.info("导入术语: %d 个", cursor.rowcount if cursor.rowcount > 0 else 0)


def insert_skills(conn: sqlite3.Connection, project_id: str, skills: list[dict]):
    if not skills:
        return
    cursor = conn.cursor()
    cursor.execute("DELETE FROM skill_tree WHERE project_id=?", (project_id,))
    for s in skills:
        cursor.execute(
            """INSERT INTO skill_tree (project_id, skill_name, unlock_chapter, description, used_chapters)
               VALUES (?,?,?,?,?)""",
            (
                project_id,
                s.get("skill_name", ""),
                s.get("unlock_chapter", 0),
                s.get("description", ""),
                s.get("used_chapters", ""),
            ),
        )
    logger.info("导入 skills: %d 个", len(skills))


def init_project_record(conn: sqlite3.Connection, project_id: str, name: str, genre: str, platform: str, base_path: str, total_chapters: int = 0):
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR REPLACE INTO projects (project_id, name, genre, platform, base_path, status, total_chapters, updated_at)
           VALUES (?, ?, ?, ?, ?, 'initialized', ?, datetime('now'))""",
        (project_id, name, genre, platform, base_path, total_chapters),
    )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Novel-OS 新书初始化")
    parser.add_argument("--book", required=True, help="book.yaml 路径")
    parser.add_argument("--data", required=True, help="数据文件路径 (Python 模块，包含 OUTLINE, CHARACTERS 等)")
    parser.add_argument("--max-chapter", type=int, default=10, help="人物状态默认生效到的最大章节号")
    parser.add_argument("--dry-run", action="store_true", help="只打印数据，不写入数据库")
    args = parser.parse_args()

    cfg = BookConfig.from_yaml(args.book)
    project_id = cfg.base_path.name
    db_path = cfg.base_path / "world_state.db"

    # 加载数据
    module = load_data_module(args.data)
    outline = getattr(module, "OUTLINE", [])
    characters = getattr(module, "CHARACTERS", [])
    debts = getattr(module, "DEBTS", [])
    foreshadowing = getattr(module, "FORESHADOWING", [])
    rules = getattr(module, "RULES", [])
    skills = getattr(module, "SKILLS", [])

    logger.info("加载数据: outline=%d, chars=%d, debts=%d, fs=%d, rules=%d, skills=%d",
                len(outline), len(characters), len(debts), len(foreshadowing), len(rules), len(skills))

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"project_id: {project_id}")
        print(f"db_path: {db_path}")
        for o in outline[:2]:
            print(f"  ch{o.get('chapter')}: {o.get('core_event', '')[:40]}")
        return 0

    # 初始化数据库
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_database(db_path, project_id)

    conn = sqlite3.connect(str(db_path))
    try:
        # 插入项目记录（避免外键约束失败）
        init_project_record(conn, project_id, cfg.project, cfg.genre, cfg.platform, str(cfg.base_path), getattr(cfg, 'chapters_target', 0))

        # 扫描大纲提取角色首次出场章节
        first_chapters = extract_first_chapters(outline, characters)
        logger.info("角色首次出场章节: %s", first_chapters)

        insert_outline(conn, project_id, outline)
        insert_characters(conn, project_id, characters, first_chapters=first_chapters)
        insert_debts(conn, project_id, debts)
        insert_foreshadowing(conn, project_id, foreshadowing)
        insert_rules(conn, project_id, rules)
        insert_skills(conn, project_id, skills)
        insert_terms(conn, project_id, skills, outline)

        conn.commit()

        # 初始化品类 DNA（必须走 StateManager 统一接口）
        state = StateManager(db_path, project_id=project_id)
        state.init_genre_dna(cfg.genre)
        logger.info("品类DNA已初始化: genre=%s", cfg.genre)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
