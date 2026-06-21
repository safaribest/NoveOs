"""Novel-OS 状态管理器 —— SQLite 版跨章状态中心（多项目版本）。

替代 V9.0 的 JSON 状态管理，解决并发与版本控制问题，同时保留 JSON 导出视图。
支持 project_id 隔离，所有查询自动带 project_id 过滤。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from core.state.repositories.base import UnitOfWork


class StateManager:
    """管理小说跨章状态的 SQLite 后端。

    核心表:
    - projects:           项目注册表
    - runtime_logs:       运行日志
    - character_states:   人物动态（位置、情感、秘密、能力、对话指纹等）
    - item_states:        道具/关键物品状态
    - debts:              债务（伏笔的一种，带回收章节）
    - foreshadowing:      伏笔总表
    - cast_schedule:      配角出场调度
    - emotion_history:    情感坐标历史
    - chapter_snapshots:  章节快照（用于回滚）
    - consistency_rules:  跨章一致性约束
    - chapter_history:    已写章节摘要
    """

    def __init__(self, db_path: Path, project_id: str = "") -> None:
        self.db_path = db_path
        self.project_id = project_id
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """初始化所有表（若不存在）。"""
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id      TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    genre           TEXT NOT NULL,
                    platform        TEXT NOT NULL,
                    base_path       TEXT NOT NULL,
                    status          TEXT DEFAULT 'pending',
                    current_chapter INTEGER DEFAULT 0,
                    total_chapters  INTEGER NOT NULL,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS runtime_logs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id  TEXT NOT NULL,
                    log_id      TEXT NOT NULL,
                    level       TEXT NOT NULL,
                    agent       TEXT NOT NULL,
                    chapter_num INTEGER,
                    message     TEXT NOT NULL,
                    metadata    TEXT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_logs_project ON runtime_logs(project_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_logs_agent ON runtime_logs(project_id, agent);

                CREATE TABLE IF NOT EXISTS character_states (
                    project_id      TEXT NOT NULL,
                    chapter         INTEGER NOT NULL,
                    character_name  TEXT NOT NULL,
                    location        TEXT,
                    emotional_state TEXT,
                    known_secrets   TEXT,
                    unknown_secrets TEXT,
                    abilities_active TEXT,
                    abilities_locked TEXT,
                    dialog_fingerprint TEXT,
                    body_language   TEXT,
                    physical_description TEXT,
                    PRIMARY KEY (project_id, chapter, character_name),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_char ON character_states(project_id, character_name, chapter);

                CREATE TABLE IF NOT EXISTS item_states (
                    project_id  TEXT NOT NULL,
                    chapter     INTEGER NOT NULL,
                    item_name   TEXT NOT NULL,
                    location    TEXT,
                    state       TEXT,
                    rule        TEXT,
                    state_history TEXT,
                    PRIMARY KEY (project_id, chapter, item_name),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_item ON item_states(project_id, item_name, chapter);

                CREATE TABLE IF NOT EXISTS debts (
                    project_id      TEXT NOT NULL,
                    debt_id         TEXT NOT NULL,
                    type            TEXT,
                    content         TEXT NOT NULL,
                    bury_chapter    INTEGER NOT NULL,
                    collect_chapter INTEGER,
                    status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'collected', 'abandoned')),
                    PRIMARY KEY (project_id, debt_id),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_debt_status ON debts(project_id, status, collect_chapter);
                CREATE INDEX IF NOT EXISTS idx_debt_bury ON debts(project_id, bury_chapter);

                CREATE TABLE IF NOT EXISTS foreshadowing (
                    project_id      TEXT NOT NULL,
                    fs_id           TEXT NOT NULL,
                    bury_chapter    INTEGER NOT NULL,
                    content         TEXT NOT NULL,
                    collect_chapter TEXT,
                    type            TEXT,
                    status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'collected', 'abandoned')),
                    PRIMARY KEY (project_id, fs_id),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_fs_status ON foreshadowing(project_id, status, collect_chapter);
                CREATE INDEX IF NOT EXISTS idx_fs_bury ON foreshadowing(project_id, bury_chapter);

                CREATE TABLE IF NOT EXISTS cast_schedule (
                    project_id      TEXT NOT NULL,
                    character_name  TEXT NOT NULL,
                    chapter         INTEGER NOT NULL,
                    must_appear     BOOLEAN DEFAULT 0,
                    role_evolution  TEXT,
                    dialog_fingerprint TEXT,
                    physical_description TEXT,
                    PRIMARY KEY (project_id, character_name, chapter),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_cast_chapter ON cast_schedule(project_id, chapter);

                CREATE TABLE IF NOT EXISTS emotion_history (
                    project_id      TEXT NOT NULL,
                    chapter         INTEGER NOT NULL,
                    mode            TEXT,
                    nue_density     REAL,
                    tian_density    REAL,
                    shuang_density  REAL,
                    coordinate_x    REAL,
                    coordinate_y    REAL,
                    desc            TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (project_id, chapter),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS chapter_snapshots (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id      TEXT NOT NULL,
                    chapter         INTEGER NOT NULL,
                    snapshot_type   TEXT NOT NULL,
                    snapshot_data   TEXT NOT NULL,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_snapshot ON chapter_snapshots(project_id, chapter, snapshot_type);

                CREATE TABLE IF NOT EXISTS consistency_rules (
                    project_id          TEXT NOT NULL,
                    rule_type           TEXT NOT NULL,
                    rule_content        TEXT NOT NULL,
                    enforcement_level   TEXT DEFAULT 'hard' CHECK (enforcement_level IN ('hard', 'soft', 'info')),
                    PRIMARY KEY (project_id, rule_type, rule_content),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_rule_type ON consistency_rules(project_id, rule_type);

                CREATE TABLE IF NOT EXISTS chapter_history (
                    project_id      TEXT NOT NULL,
                    chapter         INTEGER NOT NULL,
                    summary         TEXT,
                    word_count      INTEGER,
                    mode            TEXT,
                    title           TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (project_id, chapter),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS outline (
                    project_id      TEXT NOT NULL,
                    chapter         INTEGER NOT NULL,
                    arc             TEXT,
                    core_event      TEXT,
                    face_slap_target TEXT,
                    face_slap_method TEXT,
                    husband_moment  TEXT,
                    chapter_hook    TEXT,
                    emotion_ratio   TEXT,
                    skill_unlocked  TEXT,
                    questions       TEXT,
                    reveal_at       INTEGER,
                    beat_pattern    TEXT,
                    PRIMARY KEY (project_id, chapter),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_outline_chapter ON outline(project_id, chapter);

                CREATE TABLE IF NOT EXISTS skill_tree (
                    project_id      TEXT NOT NULL,
                    skill_name      TEXT NOT NULL,
                    unlock_chapter  INTEGER,
                    description     TEXT,
                    used_chapters   TEXT,
                    PRIMARY KEY (project_id, skill_name),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS chapter_metrics (
                    project_id      TEXT NOT NULL,
                    chapter         INTEGER NOT NULL,
                    word_count      INTEGER,
                    sentence_length REAL,
                    dialogue_ratio  REAL,
                    ta_density      REAL,
                    iwr_score       REAL,
                    questions_count INTEGER,
                    answers_count   INTEGER,
                    hook_ending     INTEGER,
                    platform_score  REAL,
                    platform_grade  TEXT,
                    genre_dna_match REAL,
                    oscillations    INTEGER,
                    quality_passed  INTEGER,
                    gate_level      TEXT,
                    audit_report    TEXT,
                    reader_pull_score REAL,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (project_id, chapter),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_metrics_chapter ON chapter_metrics(project_id, chapter);

                CREATE TABLE IF NOT EXISTS genre_dna (
                    project_id      TEXT PRIMARY KEY,
                    genre           TEXT NOT NULL,
                    target_sent_len INTEGER,
                    sent_range_min  INTEGER,
                    sent_range_max  INTEGER,
                    dialogue_target REAL,
                    dialogue_min    REAL,
                    dialogue_max    REAL,
                    dao_shuo_ratio  TEXT,
                    ta_density_max  REAL,
                    word_target     INTEGER,
                    word_tolerance  INTEGER,
                    iwr_target      REAL,
                    iwr_min         REAL,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS outer_crew_reports (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id      TEXT NOT NULL,
                    chapter         INTEGER NOT NULL,
                    agent_type      TEXT NOT NULL,
                    report          TEXT NOT NULL,
                    findings        TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_outer_crew ON outer_crew_reports(project_id, chapter, agent_type);

                CREATE TABLE IF NOT EXISTS term_dict (
                    project_id      TEXT NOT NULL,
                    term            TEXT NOT NULL,
                    category        TEXT,
                    first_chapter   INTEGER,
                    description     TEXT,
                    PRIMARY KEY (project_id, term),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS chapter_specs (
                    project_id      TEXT NOT NULL,
                    chapter         INTEGER NOT NULL,
                    spec_key        TEXT NOT NULL,
                    spec_value      TEXT,
                    PRIMARY KEY (project_id, chapter, spec_key),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                );
                CREATE INDEX IF NOT EXISTS idx_chapter_specs ON chapter_specs(project_id, chapter);
                """
            )

        # 迁移：为已存在的 chapter_metrics 表补充新列
        self._migrate_chapter_metrics_columns()

    def _migrate_chapter_metrics_columns(self) -> None:
        """为旧版 chapter_metrics 表追加质量门禁相关列。"""
        columns = [
            ("quality_passed", "INTEGER"),
            ("gate_level", "TEXT"),
            ("audit_report", "TEXT"),
            ("reader_pull_score", "REAL"),
        ]
        with self._connect() as conn:
            existing = {
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(chapter_metrics)"
                ).fetchall()
            }
            for col, dtype in columns:
                if col not in existing:
                    try:
                        conn.execute(
                            f"ALTER TABLE chapter_metrics ADD COLUMN {col} {dtype}"
                        )
                    except Exception:
                        pass

    # ------------------------------------------------------------------
    # 项目级接口
    # ------------------------------------------------------------------
    def init_project(
        self,
        project_id: str,
        name: str,
        genre: str,
        platform: str,
        base_path: str,
        total_chapters: int,
    ) -> None:
        """初始化 projects 表记录。若已存在则替换。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.project import ProjectRepository
            repo = ProjectRepository(uow.conn, self.project_id)
            repo.init(project_id, name, genre, platform, base_path, total_chapters)

    def get_project_info(self) -> dict[str, Any]:
        """读取当前 project_id 对应的项目信息。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.project import ProjectRepository
            repo = ProjectRepository(uow.conn, self.project_id)
            info = repo.get()
            return info.__dict__ if info else {}

    # ------------------------------------------------------------------
    # 日志接口
    # ------------------------------------------------------------------
    def log_runtime(
        self,
        level: str,
        agent: str,
        chapter_num: int | None,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """写入 runtime_logs 表。"""
        log_id = f"log_{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_logs
                (project_id, log_id, level, agent, chapter_num, message, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.project_id,
                    log_id,
                    level,
                    agent,
                    chapter_num,
                    message,
                    json.dumps(metadata, ensure_ascii=False) if metadata else None,
                ),
            )

    def get_runtime_logs(
        self,
        limit: int = 100,
        level: str | None = None,
        agent: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询当前项目的运行日志。"""
        conditions = ["project_id = ?"]
        params: list[Any] = [self.project_id]
        if level:
            conditions.append("level = ?")
            params.append(level)
        if agent:
            conditions.append("agent = ?")
            params.append(agent)
        where_clause = " AND ".join(conditions)
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                SELECT * FROM runtime_logs
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def init_from_outline(self, outline: dict[str, Any]) -> None:
        """从大纲 JSON 一次性初始化所有表数据。

        outline 结构示例:
        {
          "characters": {"protagonist_female": {"name": "沈若楠", ...}},
          "world": {"key_items": [...], "locks": [...]},
          "plot": {"debts": [...], "foreshadowing": [...], ...}
        }
        """
        characters = outline.get("characters", {})
        world = outline.get("world", {})
        plot = outline.get("plot", {})
        pid = self.project_id

        # 确保 projects 表中存在当前 project_id 的记录（外键约束需要）
        meta = outline.get("meta", {})
        if meta:
            self.init_project(
                pid,
                meta.get("project", "untitled"),
                meta.get("genre", ""),
                meta.get("platform", ""),
                str(self.db_path.parent),
                meta.get("chapters_target", 0),
            )

        with self._connect() as conn:
            # 1. 人物初始状态（第 0 章表示"写第 1 章之前"的初始态）
            for role_key, c in characters.items():
                name = c.get("name", role_key)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO character_states (
                        project_id, chapter, character_name, location, emotional_state,
                        known_secrets, unknown_secrets, abilities_active,
                        abilities_locked, dialog_fingerprint, body_language, physical_description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid, 0, name, None, None,
                        json.dumps(c.get("a_track", {}).get("secrets_known", []), ensure_ascii=False),
                        json.dumps(c.get("b_track", {}).get("secrets_unknown", []), ensure_ascii=False),
                        json.dumps(c.get("a_track", {}).get("ability", []), ensure_ascii=False),
                        json.dumps([], ensure_ascii=False),
                        c.get("dialog_fingerprint", ""),
                        c.get("body_language", ""),
                        c.get("physical_description", ""),
                    ),
                )

            # 2. 道具初始状态
            for item in world.get("key_items", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO item_states
                    (project_id, chapter, item_name, location, state, rule, state_history)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        0,
                        item["name"],
                        item.get("initial_location", ""),
                        item.get("initial_state", ""),
                        json.dumps(item.get("rules", []), ensure_ascii=False),
                        json.dumps([{"chapter": 0, "state": item.get("initial_state", "")}], ensure_ascii=False),
                    ),
                )

            # 3. 债务
            for d in plot.get("debts", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO debts
                    (project_id, debt_id, type, content, bury_chapter, collect_chapter, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid, d["id"], d.get("type", ""), d["content"],
                        d["bury_chapter"], d.get("collect_chapter"), "active",
                    ),
                )

            # 4. 伏笔
            for f in plot.get("foreshadowing", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO foreshadowing
                    (project_id, fs_id, bury_chapter, content, collect_chapter, type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid, f["id"], f["bury_chapter"], f["content"],
                        f.get("collect_chapter", ""), f.get("type", ""), "active",
                    ),
                )

            # 5. 一致性约束
            for lock in world.get("locks", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO consistency_rules
                    (project_id, rule_type, rule_content, enforcement_level)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pid, "world_lock", lock, "hard"),
                )

            # 6. 章节大纲 (outline)
            for ch in outline.get("chapters", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO outline
                    (project_id, chapter, arc, core_event, face_slap_target, face_slap_method,
                     husband_moment, chapter_hook, emotion_ratio, skill_unlocked,
                     questions, reveal_at, beat_pattern)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid, ch.get("chapter"), ch.get("arc"), ch.get("core_event"),
                        ch.get("face_slap_target"), ch.get("face_slap_method"),
                        ch.get("husband_moment"), ch.get("chapter_hook"),
                        ch.get("emotion_ratio"), ch.get("skill_unlocked"),
                        json.dumps(ch.get("questions", []), ensure_ascii=False),
                        ch.get("reveal_at"),
                        json.dumps(ch.get("beat_pattern", {}), ensure_ascii=False),
                    ),
                )

            # 7. 技能树 (skill_tree)
            for sk in outline.get("skills", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO skill_tree
                    (project_id, skill_name, unlock_chapter, description, used_chapters)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        pid, sk.get("name"), sk.get("unlock_chapter"),
                        sk.get("description"), json.dumps(sk.get("used_chapters", []), ensure_ascii=False),
                    ),
                )

    # ------------------------------------------------------------------
    # 品类 DNA
    # ------------------------------------------------------------------
    def init_genre_dna(self, genre: str) -> None:
        """根据品类初始化 DNA 参数（RAG 分析数据驱动）。"""
        # RAG 分析得出的品类基准值
        dna_map = {
            "言情": {"sent": 23, "sent_min": 15, "sent_max": 35, "dialogue": 0.40, "dialogue_min": 0.25, "dialogue_max": 0.55, "dao_shuo": "0.4:0.6", "ta_max": 0.02, "words": 2000, "tolerance": 200, "iwr": 2.5, "iwr_min": 2.0},
            "武侠": {"sent": 25, "sent_min": 15, "sent_max": 35, "dialogue": 0.35, "dialogue_min": 0.20, "dialogue_max": 0.50, "dao_shuo": "0.5:0.5", "ta_max": 0.015, "words": 2000, "tolerance": 200, "iwr": 2.5, "iwr_min": 2.0},
            "都市": {"sent": 25, "sent_min": 15, "sent_max": 35, "dialogue": 0.40, "dialogue_min": 0.25, "dialogue_max": 0.55, "dao_shuo": "0.4:0.6", "ta_max": 0.02, "words": 2000, "tolerance": 200, "iwr": 2.5, "iwr_min": 2.0},
            "穿越": {"sent": 28, "sent_min": 18, "sent_max": 38, "dialogue": 0.35, "dialogue_min": 0.20, "dialogue_max": 0.50, "dao_shuo": "0.5:0.5", "ta_max": 0.02, "words": 2000, "tolerance": 200, "iwr": 2.5, "iwr_min": 2.0},
            "玄幻": {"sent": 31, "sent_min": 20, "sent_max": 42, "dialogue": 0.30, "dialogue_min": 0.15, "dialogue_max": 0.45, "dao_shuo": "0.55:0.45", "ta_max": 0.015, "words": 2500, "tolerance": 250, "iwr": 2.5, "iwr_min": 2.0},
            "科幻": {"sent": 32, "sent_min": 20, "sent_max": 45, "dialogue": 0.28, "dialogue_min": 0.15, "dialogue_max": 0.40, "dao_shuo": "0.55:0.45", "ta_max": 0.015, "words": 2500, "tolerance": 250, "iwr": 2.5, "iwr_min": 2.0},
            "竞技": {"sent": 28, "sent_min": 18, "sent_max": 38, "dialogue": 0.30, "dialogue_min": 0.15, "dialogue_max": 0.45, "dao_shuo": "0.5:0.5", "ta_max": 0.015, "words": 2000, "tolerance": 200, "iwr": 2.5, "iwr_min": 2.0},
            "网游": {"sent": 35, "sent_min": 22, "sent_max": 48, "dialogue": 0.25, "dialogue_min": 0.15, "dialogue_max": 0.35, "dao_shuo": "0.35:0.65", "ta_max": 0.02, "words": 2500, "tolerance": 250, "iwr": 2.0, "iwr_min": 1.5},
            "恐怖": {"sent": 28, "sent_min": 18, "sent_max": 38, "dialogue": 0.30, "dialogue_min": 0.15, "dialogue_max": 0.45, "dao_shuo": "0.55:0.45", "ta_max": 0.015, "words": 2000, "tolerance": 200, "iwr": 2.5, "iwr_min": 2.0},
            "历史": {"sent": 30, "sent_min": 20, "sent_max": 40, "dialogue": 0.30, "dialogue_min": 0.15, "dialogue_max": 0.45, "dao_shuo": "0.45:0.55", "ta_max": 0.015, "words": 2500, "tolerance": 250, "iwr": 2.5, "iwr_min": 2.0},
            "军事": {"sent": 28, "sent_min": 18, "sent_max": 38, "dialogue": 0.35, "dialogue_min": 0.20, "dialogue_max": 0.50, "dao_shuo": "0.5:0.5", "ta_max": 0.015, "words": 2000, "tolerance": 200, "iwr": 2.5, "iwr_min": 2.0},
            "腹黑": {"sent": 26, "sent_min": 16, "sent_max": 36, "dialogue": 0.45, "dialogue_min": 0.30, "dialogue_max": 0.60, "dao_shuo": "0.45:0.55", "ta_max": 0.02, "words": 2000, "tolerance": 200, "iwr": 2.5, "iwr_min": 2.0},
        }
        d = dna_map.get(genre, dna_map["都市"])
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO genre_dna
                (project_id, genre, target_sent_len, sent_range_min, sent_range_max,
                 dialogue_target, dialogue_min, dialogue_max, dao_shuo_ratio,
                 ta_density_max, word_target, word_tolerance, iwr_target, iwr_min)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.project_id, genre, d["sent"], d["sent_min"], d["sent_max"],
                 d["dialogue"], d["dialogue_min"], d["dialogue_max"], d["dao_shuo"],
                 d["ta_max"], d["words"], d["tolerance"], d["iwr"], d["iwr_min"]),
            )

    def get_genre_dna(self) -> dict[str, Any]:
        """读取当前项目的品类 DNA。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM genre_dna WHERE project_id = ?", (self.project_id,)
            ).fetchone()
            return dict(row) if row else {}

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------
    def get_character_state(self, chapter: int, character: str) -> dict[str, Any]:
        """获取某章某人物的完整状态。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.character import CharacterRepository
            repo = CharacterRepository(uow.conn, self.project_id)
            state = repo.get(chapter, character)
            if not state:
                return {}
            data = dict(state.__dict__)
            # 兼容外部调用习惯（数据库列名为 character_name）
            data.setdefault("character_name", state.name)
            return data

    def update_character_state(self, chapter: int, character: str, **kwargs: Any) -> None:
        """增量更新人物状态；若记录不存在则自动插入。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.character import CharacterRepository
            repo = CharacterRepository(uow.conn, self.project_id)
            repo.update(chapter, character, **kwargs)

    def get_active_debts(self, current_chapter: int) -> list[dict[str, Any]]:
        """查询在当前章节应该被回收的债务（collect_chapter <= current_chapter 且 status=active）。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.debt import DebtRepository
            repo = DebtRepository(uow.conn, self.project_id)
            debts = repo.get_active(current_chapter)
            return [d.__dict__ for d in debts]

    def get_active_foreshadowing(self, current_chapter: int) -> list[dict[str, Any]]:
        """查询在当前章节应该被回收的伏笔。"""
        with self._connect() as conn:
            # collect_chapter 可能是 "3/10" 这样的多章回收，简单处理：提取第一个数字
            cursor = conn.execute(
                """
                SELECT * FROM foreshadowing
                WHERE project_id = ?
                  AND status = 'active'
                  AND collect_chapter IS NOT NULL
                  AND collect_chapter != ''
                ORDER BY bury_chapter
                """,
                (self.project_id,),
            )
            rows = []
            for row in cursor.fetchall():
                collect = str(row["collect_chapter"])
                first_num = int("".join(filter(str.isdigit, collect.split("/")[0])) or 9999)
                if first_num <= current_chapter:
                    rows.append(dict(row))
            return rows

    # ------------------------------------------------------------------
    # 快照与回滚
    # ------------------------------------------------------------------
    def create_snapshot(self, chapter: int, snapshot_type: str, data: dict[str, Any]) -> None:
        """为指定章节创建快照。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.chapter import ChapterRepository
            repo = ChapterRepository(uow.conn, self.project_id)
            repo.create_snapshot(chapter, snapshot_type, data)

    def rollback_to_snapshot(self, chapter: int, snapshot_type: str) -> dict[str, Any]:
        """回滚到指定章节的最新快照，并返回快照数据。"""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT snapshot_data FROM chapter_snapshots
                WHERE project_id = ? AND chapter = ? AND snapshot_type = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (self.project_id, chapter, snapshot_type),
            ).fetchone()
            if row is None:
                raise ValueError(f"未找到快照: chapter={chapter}, type={snapshot_type}")
            return json.loads(row["snapshot_data"])

    # ------------------------------------------------------------------
    # 章节结束更新
    # ------------------------------------------------------------------
    def update_after_chapter(
        self, chapter_num: int, summary: str, word_count: int, mode: str, title: str = ""
    ) -> None:
        """每章写完后更新历史与情感坐标。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.chapter import ChapterRepository
            repo = ChapterRepository(uow.conn, self.project_id)
            repo.save_history(chapter_num, summary, word_count, mode, title)

    def update_emotion_history(
        self, chapter_num: int, mode: str, nue: float, tian: float, shuang: float,
        coord_x: float, coord_y: float, desc: str = ""
    ) -> None:
        """更新情感坐标历史。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO emotion_history
                (project_id, chapter, mode, nue_density, tian_density, shuang_density,
                 coordinate_x, coordinate_y, desc, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.project_id, chapter_num, mode, nue, tian, shuang, coord_x, coord_y, desc, datetime.now().isoformat()),
            )

    def update_reader_pull_score(self, chapter_num: int, score: float) -> None:
        """单独更新章节追读力分数（不覆盖其它指标）。"""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE chapter_metrics
                SET reader_pull_score = ?
                WHERE project_id = ? AND chapter = ?
                """,
                (score, self.project_id, chapter_num),
            )

    def update_chapter_metrics(
        self,
        chapter_num: int,
        metrics: dict[str, Any],
        quality_passed: bool | None = None,
        gate_level: str | None = None,
        audit_report: dict[str, Any] | None = None,
        reader_pull_score: float | None = None,
    ) -> None:
        """写入章节结构指标（IWR、平台适配度等）与质量门禁结果。"""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO chapter_metrics
                (project_id, chapter, word_count, sentence_length, dialogue_ratio,
                 ta_density, iwr_score, questions_count, answers_count, hook_ending,
                 platform_score, platform_grade, genre_dna_match, oscillations,
                 quality_passed, gate_level, audit_report, reader_pull_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.project_id, chapter_num,
                    metrics.get("word_count"),
                    metrics.get("sentence_length"),
                    metrics.get("dialogue_ratio"),
                    metrics.get("ta_density"),
                    metrics.get("iwr_score"),
                    metrics.get("questions_count"),
                    metrics.get("answers_count"),
                    metrics.get("hook_ending"),
                    metrics.get("platform_score"),
                    metrics.get("platform_grade"),
                    metrics.get("genre_dna_match"),
                    metrics.get("oscillations"),
                    1 if quality_passed else 0 if quality_passed is not None else None,
                    gate_level,
                    json.dumps(audit_report, ensure_ascii=False) if audit_report else None,
                    reader_pull_score,
                    datetime.now().isoformat(),
                ),
            )

    def get_chapter_metrics(self, chapter_num: int | None = None) -> list[dict[str, Any]]:
        """查询章节结构指标。"""
        with self._connect() as conn:
            if chapter_num is not None:
                row = conn.execute(
                    "SELECT * FROM chapter_metrics WHERE project_id = ? AND chapter = ?",
                    (self.project_id, chapter_num),
                ).fetchone()
                return [self._parse_chapter_metrics_row(row)] if row else []
            cursor = conn.execute(
                "SELECT * FROM chapter_metrics WHERE project_id = ? ORDER BY chapter",
                (self.project_id,),
            )
            return [self._parse_chapter_metrics_row(row) for row in cursor.fetchall()]

    def _parse_chapter_metrics_row(self, row: sqlite3.Row) -> dict[str, Any]:
        """将 chapter_metrics 行解析为字典，并反序列化 audit_report JSON。"""
        data = dict(row)
        audit_raw = data.get("audit_report")
        if isinstance(audit_raw, str) and audit_raw:
            try:
                data["audit_report"] = json.loads(audit_raw)
            except Exception:
                data["audit_report"] = None
        else:
            data["audit_report"] = None
        # SQLite 存储布尔为 0/1，转换为 Python bool
        qp = data.get("quality_passed")
        if qp is not None:
            data["quality_passed"] = bool(qp)
        return data

    def update_project_status(self, current_chapter: int, status: str) -> None:
        """更新项目当前章节和状态。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.project import ProjectRepository
            repo = ProjectRepository(uow.conn, self.project_id)
            repo.update_status(current_chapter, status)

    # ------------------------------------------------------------------
    # 查询接口（供 API 层使用）
    # ------------------------------------------------------------------
    def list_characters(self) -> list[dict[str, Any]]:
        """列出当前项目的所有角色的最新状态（按 chapter 降序取最新）。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.character import CharacterRepository
            repo = CharacterRepository(uow.conn, self.project_id)
            states = repo.list_all()
            return [s.__dict__ for s in states]

    def get_emotion_history(self) -> list[dict[str, Any]]:
        """查询情感坐标历史。"""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT chapter, mode, coordinate_x, coordinate_y, desc
                FROM emotion_history
                WHERE project_id = ?
                ORDER BY chapter
                """,
                (self.project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_outline(self) -> list[dict[str, Any]]:
        """列出当前项目的章节大纲。"""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT chapter, arc, core_event, face_slap_target, face_slap_method,
                       husband_moment, chapter_hook, emotion_ratio, skill_unlocked
                FROM outline
                WHERE project_id = ?
                ORDER BY chapter
                """,
                (self.project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_debts(self) -> list[dict[str, Any]]:
        """列出当前项目的所有债务。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.debt import DebtRepository
            repo = DebtRepository(uow.conn, self.project_id)
            debts = repo.list_all()
            return [d.__dict__ for d in debts]

    def list_foreshadowing(self) -> list[dict[str, Any]]:
        """列出当前项目的所有伏笔。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.foreshadowing import ForeshadowingRepository
            repo = ForeshadowingRepository(uow.conn, self.project_id)
            items = repo.list_all()
            return [i.__dict__ for i in items]

    def list_skills(self) -> list[dict[str, Any]]:
        """列出当前项目的技能树。"""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT skill_name, unlock_chapter, description, used_chapters
                FROM skill_tree
                WHERE project_id = ?
                ORDER BY unlock_chapter
                """,
                (self.project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_rules(self) -> list[dict[str, Any]]:
        """列出当前项目的写作规则。"""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT rule_type, rule_content, enforcement_level
                FROM consistency_rules
                WHERE project_id = ?
                ORDER BY rule_type
                """,
                (self.project_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_chapters(self) -> list[dict[str, Any]]:
        """列出当前项目的章节历史。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.chapter import ChapterRepository
            repo = ChapterRepository(uow.conn, self.project_id)
            chapters = repo.list_all()
            return [c.__dict__ for c in chapters]

    def list_snapshots(self, chapter: int | None = None) -> list[dict[str, Any]]:
        """列出当前项目的章节快照。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.chapter import ChapterRepository
            repo = ChapterRepository(uow.conn, self.project_id)
            snaps = repo.list_snapshots(chapter)
            return [s.__dict__ for s in snaps]

    # ------------------------------------------------------------------
    # 导出视图
    # ------------------------------------------------------------------
    def export_json_view(self, output_path: Path) -> None:
        """导出人类可读的 JSON 视图，便于外部审阅。"""
        view: dict[str, Any] = {
            "exported_at": datetime.now().isoformat(),
            "project_id": self.project_id,
            "characters": {},
            "items": {},
            "debts": [],
            "foreshadowing": [],
            "chapter_history": [],
        }
        pid = self.project_id

        with self._connect() as conn:
            # 人物：取每人的最新 chapter 状态
            for row in conn.execute(
                """
                SELECT * FROM character_states
                WHERE project_id = ?
                ORDER BY character_name, chapter DESC
                """,
                (pid,),
            ).fetchall():
                name = row["character_name"]
                if name not in view["characters"]:
                    view["characters"][name] = dict(row)

            # 道具
            for row in conn.execute(
                """
                SELECT * FROM item_states
                WHERE project_id = ?
                ORDER BY item_name, chapter DESC
                """,
                (pid,),
            ).fetchall():
                name = row["item_name"]
                if name not in view["items"]:
                    view["items"][name] = dict(row)

            view["debts"] = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM debts WHERE project_id = ?", (pid,)
                ).fetchall()
            ]
            view["foreshadowing"] = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM foreshadowing WHERE project_id = ?", (pid,)
                ).fetchall()
            ]
            view["chapter_history"] = [
                dict(r) for r in conn.execute(
                    """
                    SELECT * FROM chapter_history
                    WHERE project_id = ?
                    ORDER BY chapter
                    """,
                    (pid,),
                ).fetchall()
            ]

        output_path.write_text(
            json.dumps(view, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


    # ------------------------------------------------------------------
    # 扩展查询接口（供 batch_writer 使用，替代直接 SQL）
    # ------------------------------------------------------------------
    def get_chapter_title(self, chapter_num: int) -> str:
        """获取指定章节的标题。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.chapter import ChapterRepository
            repo = ChapterRepository(uow.conn, self.project_id)
            return repo.get_title(chapter_num)

    def set_chapter_title(self, chapter_num: int, title: str) -> None:
        """保存章节标题到 chapter_history。"""
        with UnitOfWork(self.db_path, self.project_id) as uow:
            from core.state.repositories.chapter import ChapterRepository
            repo = ChapterRepository(uow.conn, self.project_id)
            repo.set_title(chapter_num, title)

    def get_chapter_outline(self, chapter_num: int) -> dict[str, str]:
        """获取指定章节的大纲规划。"""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT arc, core_event, face_slap_target, face_slap_method,
                   husband_moment, chapter_hook, emotion_ratio, skill_unlocked
                   FROM outline WHERE project_id = ? AND chapter = ?""",
                (self.project_id, chapter_num),
            ).fetchone()
            if row:
                return {
                    "arc": row["arc"] or "",
                    "core_event": row["core_event"] or "",
                    "face_slap_target": row["face_slap_target"] or "",
                    "face_slap_method": row["face_slap_method"] or "",
                    "husband_moment": row["husband_moment"] or "",
                    "chapter_hook": row["chapter_hook"] or "",
                    "emotion_ratio": row["emotion_ratio"] or "",
                    "skill_unlocked": row["skill_unlocked"] or "",
                }
            return {}

    def get_characters_full(self) -> list[dict[str, Any]]:
        """获取所有活跃人物的完整状态（含对话指纹）。"""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT character_name, location, emotional_state, known_secrets,
                   unknown_secrets, abilities_active, dialog_fingerprint,
                   body_language, physical_description
                   FROM character_states WHERE project_id = ?""",
                (self.project_id,),
            ).fetchall()
            return [
                {
                    "name": r["character_name"],
                    "location": r["location"],
                    "emotional_state": r["emotional_state"],
                    "known_secrets": r["known_secrets"],
                    "unknown_secrets": r["unknown_secrets"],
                    "abilities": r["abilities_active"],
                    "dialog_fingerprint": r["dialog_fingerprint"] or "",
                    "body_language": r["body_language"] or "",
                    "description": r["physical_description"] or "",
                }
                for r in rows
            ]

    def get_characters_by_chapter(self, chapter: int) -> list[dict[str, Any]]:
        """获取到指定章节为止已出场的所有角色最新状态。"""
        with self._connect() as conn:
            # 子查询：取每个角色在 chapter <= ? 范围内的最新记录
            rows = conn.execute(
                """SELECT character_name, location, emotional_state, known_secrets,
                   unknown_secrets, abilities_active, dialog_fingerprint,
                   body_language, physical_description
                   FROM character_states AS cs1
                   WHERE project_id = ? AND chapter <= ?
                   AND chapter = (
                       SELECT MAX(chapter) FROM character_states AS cs2
                       WHERE cs2.project_id = cs1.project_id
                       AND cs2.character_name = cs1.character_name
                       AND cs2.chapter <= ?
                   )""",
                (self.project_id, chapter, chapter),
            ).fetchall()
            return [
                {
                    "name": r["character_name"],
                    "location": r["location"],
                    "emotional_state": r["emotional_state"],
                    "known_secrets": r["known_secrets"],
                    "unknown_secrets": r["unknown_secrets"],
                    "abilities": r["abilities_active"],
                    "dialog_fingerprint": r["dialog_fingerprint"] or "",
                    "body_language": r["body_language"] or "",
                    "description": r["physical_description"] or "",
                }
                for r in rows
            ]

    def get_hard_rules(self) -> list[str]:
        """获取所有 hard 级别的写作规则。"""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT rule_type, rule_content FROM consistency_rules
                   WHERE project_id = ? AND enforcement_level = 'hard'""",
                (self.project_id,),
            ).fetchall()
            return [f"[{r['rule_type']}] {r['rule_content']}" for r in rows]

    def get_term_dict(self) -> list[dict[str, Any]]:
        """获取术语字典。"""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT term, category, first_chapter, description
                   FROM term_dict WHERE project_id = ? ORDER BY first_chapter""",
                (self.project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_chapter_specs(self, spec_keys: list[str] | None = None) -> list[dict[str, Any]]:
        """获取章节规格（如 title、core_event 等）。"""
        with self._connect() as conn:
            if spec_keys:
                placeholders = ",".join(["?"] * len(spec_keys))
                rows = conn.execute(
                    f"""SELECT chapter, spec_key, spec_value FROM chapter_specs
                       WHERE project_id = ? AND spec_key IN ({placeholders})
                       ORDER BY chapter LIMIT 30""",
                    (self.project_id, *spec_keys),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT chapter, spec_key, spec_value FROM chapter_specs
                       WHERE project_id = ? ORDER BY chapter LIMIT 30""",
                    (self.project_id,),
                ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Interceptor / DeAI 扩展（Phase 2 预留）
    # ------------------------------------------------------------------
    def get_interceptor_rules(self) -> dict[str, Any]:
        """获取去 AI 拦截器配置（当前返回默认值，后续可从表读取）。"""
        # TODO: 当需要按项目自定义规则时，创建 interceptor_rules 表
        return {}

    def update_frequency_tracker(self, chapter_num: int, stats: dict[str, Any]) -> None:
        """更新频率追踪器（当前为占位，后续写入 SQLite）。"""
        # TODO: 创建 frequency_tracker 表并持久化
        pass
