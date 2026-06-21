"""debts 表 Repository。"""
from __future__ import annotations

import sqlite3

from core.state.models import Debt
from core.state.repositories.base import BaseRepository


class DebtRepository(BaseRepository):
    """债务数据访问。"""

    TABLE_NAME = "debts"

    def get_active(self, current_chapter: int) -> list[Debt]:
        """查询在当前章节应该被回收的债务。"""
        rows = self._fetchall(
            f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE project_id = ?
              AND status = 'active'
              AND collect_chapter IS NOT NULL
              AND collect_chapter <= ?
            ORDER BY collect_chapter
            """,
            (self._project_id, current_chapter),
        )
        return [self._row_to_model(r) for r in rows]

    def list_all(self) -> list[Debt]:
        """列出所有债务。"""
        rows = self._fetchall(
            f"""
            SELECT debt_id, type, content, bury_chapter, collect_chapter, status
            FROM {self.TABLE_NAME}
            WHERE project_id = ?
            ORDER BY bury_chapter
            """,
            (self._project_id,),
        )
        return [self._row_to_model(r) for r in rows]

    def save(self, debt: Debt) -> None:
        """保存债务。"""
        self._execute(
            f"""
            INSERT OR REPLACE INTO {self.TABLE_NAME}
            (project_id, debt_id, type, content, bury_chapter, collect_chapter, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._project_id,
                debt.debt_id,
                debt.type,
                debt.content,
                debt.bury_chapter,
                debt.collect_chapter,
                debt.status,
            ),
        )

    def _row_to_model(self, row: sqlite3.Row) -> Debt:
        return Debt(
            debt_id=row["debt_id"],
            type=row["type"] or "",
            content=row["content"],
            bury_chapter=row["bury_chapter"],
            collect_chapter=row["collect_chapter"],
            status=row["status"] or "active",
        )
