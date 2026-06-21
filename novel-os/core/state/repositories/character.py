"""character_states 表 Repository。"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from core.state.models import CharacterState
from core.state.repositories.base import BaseRepository


class CharacterRepository(BaseRepository):
    """人物状态数据访问。"""

    TABLE_NAME = "character_states"

    def get_latest(self, character_name: str) -> CharacterState | None:
        """查询某人物最近一章的状态。"""
        row = self._fetchone(
            f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE project_id = ? AND character_name = ?
            ORDER BY chapter DESC LIMIT 1
            """,
            (self._project_id, character_name),
        )
        return self._row_to_model(row) if row else None

    def get(self, chapter: int, character_name: str) -> CharacterState | None:
        """查询某章某人物的完整状态。"""
        row = self._fetchone(
            f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE project_id = ? AND chapter = ? AND character_name = ?
            """,
            (self._project_id, chapter, character_name),
        )
        return self._row_to_model(row) if row else None

    def get_all_at_chapter(self, chapter: int) -> list[CharacterState]:
        """查询某章的所有人物状态。"""
        rows = self._fetchall(
            f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE project_id = ? AND chapter = ?
            """,
            (self._project_id, chapter),
        )
        return [self._row_to_model(r) for r in rows]

    def list_all(self) -> list[CharacterState]:
        """列出所有角色的最新状态（按 chapter 降序取最新）。"""
        rows = self._fetchall(
            f"""
            SELECT * FROM {self.TABLE_NAME} cs1
            WHERE project_id = ?
              AND chapter = (
                  SELECT MAX(chapter) FROM {self.TABLE_NAME} cs2
                  WHERE cs2.project_id = cs1.project_id
                    AND cs2.character_name = cs1.character_name
              )
            ORDER BY character_name
            """,
            (self._project_id,),
        )
        return [self._row_to_model(r) for r in rows]

    def save(self, chapter: int, state: CharacterState) -> None:
        """保存人物状态。"""
        self._execute(
            f"""
            INSERT OR REPLACE INTO {self.TABLE_NAME}
            (project_id, chapter, character_name, location, emotional_state,
             known_secrets, unknown_secrets, abilities_active, abilities_locked,
             dialog_fingerprint, body_language, physical_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._project_id,
                chapter,
                state.name,
                state.location,
                state.emotional_state,
                state.known_secrets,
                state.unknown_secrets,
                state.abilities_active,
                state.abilities_locked,
                state.dialog_fingerprint,
                state.body_language,
                state.physical_description,
            ),
        )

    def update(self, chapter: int, character_name: str, **kwargs: Any) -> None:
        """增量更新人物状态；若记录不存在则自动插入。"""
        allowed = {
            "location", "emotional_state", "known_secrets", "unknown_secrets",
            "abilities_active", "abilities_locked", "dialog_fingerprint",
            "body_language", "physical_description",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        existing = self._fetchone(
            f"""
            SELECT 1 FROM {self.TABLE_NAME}
            WHERE project_id = ? AND chapter = ? AND character_name = ?
            """,
            (self._project_id, chapter, character_name),
        )
        if existing:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            self._execute(
                f"""
                UPDATE {self.TABLE_NAME} SET {set_clause}
                WHERE project_id = ? AND chapter = ? AND character_name = ?
                """,
                (*updates.values(), self._project_id, chapter, character_name),
            )
        else:
            columns = ", ".join(updates.keys())
            placeholders = ", ".join(["?"] * len(updates))
            self._execute(
                f"""
                INSERT INTO {self.TABLE_NAME}
                (project_id, chapter, character_name, {columns})
                VALUES (?, ?, ?, {placeholders})
                """,
                (self._project_id, chapter, character_name, *updates.values()),
            )

    def _row_to_model(self, row: sqlite3.Row) -> CharacterState:
        return CharacterState(
            name=row["character_name"],
            chapter=row["chapter"],
            location=row["location"] or "",
            emotional_state=row["emotional_state"] or "",
            known_secrets=row["known_secrets"] or "",
            unknown_secrets=row["unknown_secrets"] or "",
            abilities_active=row["abilities_active"] or "",
            abilities_locked=row["abilities_locked"] or "",
            dialog_fingerprint=row["dialog_fingerprint"] or "",
            body_language=row["body_language"] or "",
            physical_description=row["physical_description"] or "",
        )
