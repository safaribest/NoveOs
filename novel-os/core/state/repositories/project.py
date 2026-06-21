"""projects 表 Repository。"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from core.state.models import ProjectInfo
from core.state.repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    """项目信息数据访问。"""

    TABLE_NAME = "projects"

    def get(self) -> ProjectInfo | None:
        """读取当前项目信息。"""
        row = self._fetchone(
            f"SELECT * FROM {self.TABLE_NAME} WHERE project_id = ?",
            (self._project_id,),
        )
        return self._row_to_model(row) if row else None

    def init(
        self,
        project_id: str,
        name: str,
        genre: str,
        platform: str,
        base_path: str,
        total_chapters: int,
    ) -> None:
        """初始化或替换项目记录。"""
        self._execute(
            f"""
            INSERT OR REPLACE INTO {self.TABLE_NAME}
            (project_id, name, genre, platform, base_path, total_chapters,
             status, current_chapter, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                name,
                genre,
                platform,
                base_path,
                total_chapters,
                "pending",
                0,
                datetime.now().isoformat(),
            ),
        )

    def update_status(self, current_chapter: int, status: str) -> None:
        """更新项目当前章节和状态。"""
        self._execute(
            f"""
            UPDATE {self.TABLE_NAME}
            SET current_chapter = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE project_id = ?
            """,
            (current_chapter, status, self._project_id),
        )

    def _row_to_model(self, row: sqlite3.Row) -> ProjectInfo:
        return ProjectInfo(
            project_id=row["project_id"],
            name=row["name"],
            genre=row["genre"],
            platform=row["platform"],
            base_path=row["base_path"],
            total_chapters=row["total_chapters"],
            status=row["status"] or "pending",
            current_chapter=row["current_chapter"] or 0,
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )
