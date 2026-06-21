"""foreshadowing 表 Repository。"""
from __future__ import annotations

import sqlite3

from core.state.models import Foreshadowing
from core.state.repositories.base import BaseRepository


class ForeshadowingRepository(BaseRepository):
    """伏笔数据访问。"""

    TABLE_NAME = "foreshadowing"

    def list_active(self, current_chapter: int) -> list[Foreshadowing]:
        """查询在当前章节应该被回收的伏笔。
        
        collect_chapter 可能是 "3/10" 这样的多章回收，简单处理：提取第一个数字。
        """
        rows = self._fetchall(
            f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE project_id = ?
              AND status = 'active'
              AND collect_chapter IS NOT NULL
              AND collect_chapter != ''
            ORDER BY bury_chapter
            """,
            (self._project_id,),
        )
        result = []
        for row in rows:
            collect = str(row["collect_chapter"])
            first_num = int("".join(filter(str.isdigit, collect.split("/")[0])) or 9999)
            if first_num <= current_chapter:
                result.append(self._row_to_model(row))
        return result

    def list_all(self) -> list[Foreshadowing]:
        """列出所有伏笔。"""
        rows = self._fetchall(
            f"""
            SELECT fs_id, bury_chapter, content, collect_chapter, type, status
            FROM {self.TABLE_NAME}
            WHERE project_id = ?
            ORDER BY bury_chapter
            """,
            (self._project_id,),
        )
        return [self._row_to_model(r) for r in rows]

    def save(self, fs: Foreshadowing) -> None:
        """保存伏笔。"""
        self._execute(
            f"""
            INSERT OR REPLACE INTO {self.TABLE_NAME}
            (project_id, fs_id, bury_chapter, content, collect_chapter, type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._project_id,
                fs.fs_id,
                fs.bury_chapter,
                fs.content,
                fs.collect_chapter,
                fs.type,
                fs.status,
            ),
        )

    def _row_to_model(self, row: sqlite3.Row) -> Foreshadowing:
        return Foreshadowing(
            fs_id=row["fs_id"],
            content=row["content"],
            bury_chapter=row["bury_chapter"],
            collect_chapter=row["collect_chapter"] or "",
            type=row["type"] or "",
            status=row["status"] or "active",
        )
