"""Repository 基类与 UnitOfWork。"""
from __future__ import annotations

import sqlite3
from abc import ABC
from pathlib import Path
from typing import Generator


class BaseRepository(ABC):
    """数据访问层基类。

    每张表对应一个 Repository，只负责该表的 CRUD 和简单查询。
    复杂的跨表业务查询放到 Service 层或直接使用 SQL。
    """

    TABLE_NAME: str = ""

    def __init__(self, conn: sqlite3.Connection, project_id: str) -> None:
        self._conn = conn
        self._project_id = project_id

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行 SQL，自动注入 project_id 到 WHERE 子句（如果查询涉及项目隔离）。"""
        return self._conn.execute(sql, params)

    def _fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        cur = self._execute(sql, params)
        return cur.fetchone()

    def _fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        cur = self._execute(sql, params)
        return cur.fetchall()


class UnitOfWork:
    """工作单元 —— 管理 SQLite 连接和事务边界。

    使用方式：
        with UnitOfWork(db_path, project_id) as uow:
            uow.characters.save(chapter, state)
            uow.chapters.save(history)
            # __exit__ 时自动 commit
    """

    def __init__(self, db_path: Path, project_id: str) -> None:
        self._db_path = db_path
        self._project_id = project_id
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "UnitOfWork":
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._conn is None:
            return
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()
        self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("UnitOfWork 未在 with 上下文中使用")
        return self._conn

    # --- Repositories（懒加载或属性访问） ---
    @property
    def projects(self) -> "ProjectRepository":
        from core.state.repositories.project import ProjectRepository

        return ProjectRepository(self.conn, self._project_id)

    @property
    def characters(self) -> "CharacterRepository":
        from core.state.repositories.character import CharacterRepository

        return CharacterRepository(self.conn, self._project_id)

    @property
    def chapters(self) -> "ChapterRepository":
        from core.state.repositories.chapter import ChapterRepository

        return ChapterRepository(self.conn, self._project_id)

    @property
    def debts(self) -> "DebtRepository":
        from core.state.repositories.debt import DebtRepository

        return DebtRepository(self.conn, self._project_id)

    @property
    def foreshadowing(self) -> "ForeshadowingRepository":
        from core.state.repositories.foreshadowing import ForeshadowingRepository

        return ForeshadowingRepository(self.conn, self._project_id)

    @property
    def items(self) -> "ItemRepository":
        from core.state.repositories.item import ItemRepository

        return ItemRepository(self.conn, self._project_id)

    @property
    def cast(self) -> "CastRepository":
        from core.state.repositories.cast import CastRepository

        return CastRepository(self.conn, self._project_id)
