"""cast_schedule 表 Repository。"""
from __future__ import annotations

import sqlite3

from core.state.models import CastSchedule
from core.state.repositories.base import BaseRepository


class CastRepository(BaseRepository):
    """配角出场调度数据访问。"""

    TABLE_NAME = "cast_schedule"

    def get(self, character_name: str, chapter: int) -> CastSchedule | None:
        """查询某角色在某章的出场调度。"""
        row = self._fetchone(
            f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE project_id = ? AND character_name = ? AND chapter = ?
            """,
            (self._project_id, character_name, chapter),
        )
        return self._row_to_model(row) if row else None

    def list_by_chapter(self, chapter: int) -> list[CastSchedule]:
        """列出某章的所有配角出场调度。"""
        rows = self._fetchall(
            f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE project_id = ? AND chapter = ?
            ORDER BY character_name
            """,
            (self._project_id, chapter),
        )
        return [self._row_to_model(r) for r in rows]

    def save(self, schedule: CastSchedule) -> None:
        """保存配角出场调度。"""
        self._execute(
            f"""
            INSERT OR REPLACE INTO {self.TABLE_NAME}
            (project_id, character_name, chapter, must_appear, role_evolution,
             dialog_fingerprint, physical_description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._project_id,
                schedule.character_name,
                schedule.chapter,
                schedule.must_appear,
                schedule.role_evolution,
                schedule.dialog_fingerprint,
                schedule.physical_description,
            ),
        )

    def _row_to_model(self, row: sqlite3.Row) -> CastSchedule:
        return CastSchedule(
            character_name=row["character_name"],
            chapter=row["chapter"],
            must_appear=bool(row["must_appear"]),
            role_evolution=row["role_evolution"] or "",
            dialog_fingerprint=row["dialog_fingerprint"] or "",
            physical_description=row["physical_description"] or "",
        )
