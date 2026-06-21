"""Novel-OS FTS5 全文索引管理器 —— 章节内容长期记忆。"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator


class FTSIndexManager:
    """基于 SQLite FTS5 的章节全文索引管理器。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fallback = False
        self._init_fts5()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_fts5(self) -> None:
        """初始化 FTS5 虚拟表（若支持）；否则降级为普通表。"""
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS fts_chapters USING fts5(
                        chapter_id UNINDEXED,
                        title,
                        content,
                        tokenize='porter unicode61'
                    )
                    """
                )
            except sqlite3.OperationalError as exc:
                if "fts5" in str(exc).lower():
                    self._fallback = True
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS fts_chapters_fallback (
                            chapter_id TEXT PRIMARY KEY,
                            title TEXT,
                            content TEXT
                        )
                        """
                    )
                else:
                    raise

    def index_chapter(self, chapter_id: str, title: str, content: str) -> None:
        """索引或更新单章内容。"""
        with self._connect() as conn:
            self._delete_chapter_raw(conn, chapter_id)
            if self._fallback:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO fts_chapters_fallback (chapter_id, title, content)
                    VALUES (?, ?, ?)
                    """,
                    (chapter_id, title, content),
                )
            else:
                conn.execute(
                    "INSERT INTO fts_chapters (chapter_id, title, content) VALUES (?, ?, ?)",
                    (chapter_id, title, content),
                )

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """FTS5 全文搜索。"""
        with self._connect() as conn:
            if self._fallback:
                cursor = conn.execute(
                    """
                    SELECT chapter_id, title, content
                    FROM fts_chapters_fallback
                    WHERE title LIKE ? OR content LIKE ?
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", limit),
                )
                return [dict(row) for row in cursor.fetchall()]

            cursor = conn.execute(
                """
                SELECT chapter_id, title, content
                FROM fts_chapters
                WHERE fts_chapters MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_chapter(self, chapter_id: str) -> None:
        """从索引中删除指定章节。"""
        with self._connect() as conn:
            self._delete_chapter_raw(conn, chapter_id)

    def _delete_chapter_raw(self, conn: sqlite3.Connection, chapter_id: str) -> None:
        if self._fallback:
            conn.execute(
                "DELETE FROM fts_chapters_fallback WHERE chapter_id = ?",
                (chapter_id,),
            )
        else:
            conn.execute(
                "DELETE FROM fts_chapters WHERE chapter_id = ?",
                (chapter_id,),
            )
