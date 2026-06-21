"""chapter_history + chapter_snapshots 表 Repository。"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from core.state.models import ChapterHistory, ChapterSnapshot
from core.state.repositories.base import BaseRepository


class ChapterRepository(BaseRepository):
    """章节历史与快照数据访问。"""

    HISTORY_TABLE = "chapter_history"
    SNAPSHOT_TABLE = "chapter_snapshots"

    def get_history(self, chapter: int) -> ChapterHistory | None:
        """获取指定章节的章节历史。"""
        row = self._fetchone(
            f"""
            SELECT * FROM {self.HISTORY_TABLE}
            WHERE project_id = ? AND chapter = ?
            """,
            (self._project_id, chapter),
        )
        return self._row_to_history_model(row) if row else None

    def save_history(
        self,
        chapter: int,
        summary: str = "",
        word_count: int = 0,
        mode: str = "",
        title: str = "",
    ) -> None:
        """保存章节历史。"""
        self._execute(
            f"""
            INSERT OR REPLACE INTO {self.HISTORY_TABLE}
            (project_id, chapter, summary, word_count, mode, title, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._project_id,
                chapter,
                summary,
                word_count,
                mode,
                title,
                datetime.now().isoformat(),
            ),
        )

    def set_title(self, chapter: int, title: str) -> None:
        """保存章节标题；若记录不存在则先创建空记录。"""
        self._execute(
            f"""
            INSERT OR IGNORE INTO {self.HISTORY_TABLE}
            (project_id, chapter, summary, word_count, mode, title, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (self._project_id, chapter, "", 0, "", title),
        )
        self._execute(
            f"""
            UPDATE {self.HISTORY_TABLE}
            SET title = ?, created_at = datetime('now')
            WHERE project_id = ? AND chapter = ?
            """,
            (title, self._project_id, chapter),
        )

    def get_title(self, chapter: int) -> str:
        """获取指定章节的标题。"""
        row = self._fetchone(
            f"""
            SELECT title FROM {self.HISTORY_TABLE}
            WHERE project_id = ? AND chapter = ?
            """,
            (self._project_id, chapter),
        )
        return row["title"] if row and row["title"] else ""

    def list_all(self) -> list[ChapterHistory]:
        """列出所有章节历史。"""
        rows = self._fetchall(
            f"""
            SELECT chapter, title, summary, word_count, mode, created_at
            FROM {self.HISTORY_TABLE}
            WHERE project_id = ?
            ORDER BY chapter
            """,
            (self._project_id,),
        )
        return [self._row_to_history_model(r) for r in rows]

    def create_snapshot(self, chapter: int, snapshot_type: str, data: dict) -> None:
        """为指定章节创建快照。"""
        self._execute(
            f"""
            INSERT INTO {self.SNAPSHOT_TABLE}
            (project_id, chapter, snapshot_type, snapshot_data)
            VALUES (?, ?, ?, ?)
            """,
            (
                self._project_id,
                chapter,
                snapshot_type,
                json.dumps(data, ensure_ascii=False),
            ),
        )

    def get_latest_snapshot(
        self, chapter: int, snapshot_type: str
    ) -> ChapterSnapshot | None:
        """获取指定章节的最新快照。"""
        row = self._fetchone(
            f"""
            SELECT * FROM {self.SNAPSHOT_TABLE}
            WHERE project_id = ? AND chapter = ? AND snapshot_type = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (self._project_id, chapter, snapshot_type),
        )
        return self._row_to_snapshot_model(row) if row else None

    def list_snapshots(self, chapter: int | None = None) -> list[ChapterSnapshot]:
        """列出章节快照。"""
        conditions = ["project_id = ?"]
        params: list = [self._project_id]
        if chapter is not None:
            conditions.append("chapter = ?")
            params.append(chapter)
        where_clause = " AND ".join(conditions)
        rows = self._fetchall(
            f"""
            SELECT id, chapter, snapshot_type, snapshot_data, created_at
            FROM {self.SNAPSHOT_TABLE}
            WHERE {where_clause}
            ORDER BY chapter, created_at DESC
            """,
            tuple(params),
        )
        return [self._row_to_snapshot_model(r) for r in rows]

    def _row_to_history_model(self, row: sqlite3.Row) -> ChapterHistory:
        return ChapterHistory(
            chapter=row["chapter"],
            title=row["title"] or "",
            summary=row["summary"] or "",
            word_count=row["word_count"] or 0,
            mode=row["mode"] or "",
            created_at=row["created_at"] or "",
        )

    def _row_to_snapshot_model(self, row: sqlite3.Row) -> ChapterSnapshot:
        return ChapterSnapshot(
            id=row["id"],
            chapter=row["chapter"],
            snapshot_type=row["snapshot_type"],
            snapshot_data=row["snapshot_data"] or "",
            created_at=row["created_at"] or "",
        )
