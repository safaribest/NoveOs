"""item_states 表 Repository。"""
from __future__ import annotations

import sqlite3

from core.state.models import ItemState
from core.state.repositories.base import BaseRepository


class ItemRepository(BaseRepository):
    """道具/关键物品状态数据访问。"""

    TABLE_NAME = "item_states"

    def get_latest(self, item_name: str) -> ItemState | None:
        """查询某道具最近一章的状态。"""
        row = self._fetchone(
            f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE project_id = ? AND item_name = ?
            ORDER BY chapter DESC LIMIT 1
            """,
            (self._project_id, item_name),
        )
        return self._row_to_model(row) if row else None

    def get(self, chapter: int, item_name: str) -> ItemState | None:
        """查询某章某道具的完整状态。"""
        row = self._fetchone(
            f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE project_id = ? AND chapter = ? AND item_name = ?
            """,
            (self._project_id, chapter, item_name),
        )
        return self._row_to_model(row) if row else None

    def list_all(self) -> list[ItemState]:
        """列出所有道具的最新状态。"""
        rows = self._fetchall(
            f"""
            SELECT * FROM {self.TABLE_NAME} i1
            WHERE project_id = ?
              AND chapter = (
                  SELECT MAX(chapter) FROM {self.TABLE_NAME} i2
                  WHERE i2.project_id = i1.project_id
                    AND i2.item_name = i1.item_name
              )
            ORDER BY item_name
            """,
            (self._project_id,),
        )
        return [self._row_to_model(r) for r in rows]

    def save(self, state: ItemState) -> None:
        """保存道具状态。"""
        self._execute(
            f"""
            INSERT OR REPLACE INTO {self.TABLE_NAME}
            (project_id, chapter, item_name, location, state, rule, state_history)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._project_id,
                state.chapter,
                state.item_name,
                state.location,
                state.state,
                state.rule,
                state.state_history,
            ),
        )

    def _row_to_model(self, row: sqlite3.Row) -> ItemState:
        return ItemState(
            item_name=row["item_name"],
            chapter=row["chapter"],
            location=row["location"] or "",
            state=row["state"] or "",
            rule=row["rule"] or "",
            state_history=row["state_history"] or "",
        )
