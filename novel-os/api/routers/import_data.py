"""创作数据导入路由 —— 接收 JSON 大纲，写入 world_state.db。

替代 CLI 的 `python init_book.py --data book_data.py`，
让前端可以直接上传大纲数据完成项目初始化。

POST /api/v1/projects/{project_id}/import
"""
from __future__ import annotations

import sqlite3
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("novel-os.import_data")
router = APIRouter()


def _get_orchestrator(request: Request):
    return request.app.state.orchestrator


# ── Pydantic models matching book_data.py structure ──

class OutlineItem(BaseModel):
    chapter: int
    arc: str = ""
    core_event: str = ""
    face_slap_target: str = ""
    face_slap_method: str = ""
    husband_moment: str = ""
    chapter_hook: str = ""
    emotion_ratio: str = ""
    skill_unlocked: str = ""


class CharacterItem(BaseModel):
    name: str
    location: str = ""
    emotional_state: str = ""
    known_secrets: str = ""
    unknown_secrets: str = ""
    abilities_active: str = ""
    abilities_locked: str = ""
    dialog_fingerprint: str = ""
    body_language: str = ""
    physical_description: str = ""


class DebtItem(BaseModel):
    debt_id: str
    type: str = ""
    content: str = ""
    bury_chapter: int = 0
    collect_chapter: Optional[int] = None
    status: str = "active"


class ForeshadowingItem(BaseModel):
    fs_id: str
    bury_chapter: int = 0
    content: str = ""
    collect_chapter: Optional[int] = None
    type: str = ""
    status: str = "active"


class RuleItem(BaseModel):
    rule_type: str = ""
    rule_content: str = ""
    enforcement_level: str = "hard"


class SkillItem(BaseModel):
    skill_name: str
    unlock_chapter: int = 0
    description: str = ""
    used_chapters: str = ""


class ImportRequest(BaseModel):
    """前端提交的创作数据，与 book_data.py 结构一一对应。"""
    outline: list[OutlineItem] = []
    characters: list[CharacterItem] = []
    debts: list[DebtItem] = []
    foreshadowing: list[ForeshadowingItem] = []
    rules: list[RuleItem] = []
    skills: list[SkillItem] = []


class ImportResult(BaseModel):
    outline: int
    characters: int
    debts: int
    foreshadowing: int
    rules: int
    skills: int


# ── Insert helpers (same logic as init_book.py) ──

def _insert_outline(conn: sqlite3.Connection, project_id: str, data: list[OutlineItem]):
    conn.execute("DELETE FROM outline WHERE project_id=?", (project_id,))
    for row in data:
        conn.execute(
            """INSERT INTO outline (project_id, chapter, arc, core_event, face_slap_target,
               face_slap_method, husband_moment, chapter_hook, emotion_ratio, skill_unlocked)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (project_id, row.chapter, row.arc, row.core_event, row.face_slap_target,
             row.face_slap_method, row.husband_moment, row.chapter_hook,
             row.emotion_ratio, row.skill_unlocked),
        )


def _insert_characters(conn: sqlite3.Connection, project_id: str, data: list[CharacterItem]):
    conn.execute("DELETE FROM character_states WHERE project_id=?", (project_id,))
    total_chapters = conn.execute(
        "SELECT total_chapters FROM projects WHERE project_id=?", (project_id,)
    ).fetchone()
    max_chapter = total_chapters[0] if total_chapters else 120
    for char in data:
        conn.execute(
            """INSERT INTO character_states (project_id, chapter, character_name, location,
               emotional_state, known_secrets, unknown_secrets, abilities_active,
               abilities_locked, dialog_fingerprint, body_language, physical_description)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (project_id, max_chapter, char.name, char.location, char.emotional_state,
             char.known_secrets, char.unknown_secrets, char.abilities_active,
             char.abilities_locked, char.dialog_fingerprint, char.body_language,
             char.physical_description),
        )


def _insert_debts(conn: sqlite3.Connection, project_id: str, data: list[DebtItem]):
    conn.execute("DELETE FROM debts WHERE project_id=?", (project_id,))
    for d in data:
        conn.execute(
            """INSERT INTO debts (project_id, debt_id, type, content, bury_chapter, collect_chapter, status)
               VALUES (?,?,?,?,?,?,?)""",
            (project_id, d.debt_id, d.type, d.content, d.bury_chapter, d.collect_chapter, d.status),
        )


def _insert_foreshadowing(conn: sqlite3.Connection, project_id: str, data: list[ForeshadowingItem]):
    conn.execute("DELETE FROM foreshadowing WHERE project_id=?", (project_id,))
    for f in data:
        conn.execute(
            """INSERT INTO foreshadowing (project_id, fs_id, bury_chapter, content, collect_chapter, type, status)
               VALUES (?,?,?,?,?,?,?)""",
            (project_id, f.fs_id, f.bury_chapter, f.content, f.collect_chapter, f.type, f.status),
        )


def _insert_rules(conn: sqlite3.Connection, project_id: str, data: list[RuleItem]):
    conn.execute("DELETE FROM consistency_rules WHERE project_id=?", (project_id,))
    for r in data:
        conn.execute(
            """INSERT INTO consistency_rules (project_id, rule_type, rule_content, enforcement_level)
               VALUES (?,?,?,?)""",
            (project_id, r.rule_type, r.rule_content, r.enforcement_level),
        )


def _insert_skills(conn: sqlite3.Connection, project_id: str, data: list[SkillItem]):
    conn.execute("DELETE FROM skill_tree WHERE project_id=?", (project_id,))
    for s in data:
        conn.execute(
            """INSERT INTO skill_tree (project_id, skill_name, unlock_chapter, description, used_chapters)
               VALUES (?,?,?,?,?)""",
            (project_id, s.skill_name, s.unlock_chapter, s.description, s.used_chapters),
        )


# ── Route ──

@router.post("/projects/{project_id}/import", response_model=dict)
async def import_book_data(project_id: str, req: ImportRequest, request: Request):
    """导入创作数据（大纲、人设、债务、伏笔、规则、技能）到 world_state.db。"""
    orchestrator = _get_orchestrator(request)
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    db_path = Path(status["base_path"]) / "world_state.db"
    if not db_path.exists():
        raise HTTPException(status_code=400, detail="项目数据库未初始化，请先创建项目")

    conn = sqlite3.connect(str(db_path))
    try:
        _insert_outline(conn, project_id, req.outline)
        _insert_characters(conn, project_id, req.characters)
        _insert_debts(conn, project_id, req.debts)
        _insert_foreshadowing(conn, project_id, req.foreshadowing)
        _insert_rules(conn, project_id, req.rules)
        _insert_skills(conn, project_id, req.skills)

        # 更新项目总章节数（以 outline 的最大 chapter 为准）
        if req.outline:
            max_ch = max(o.chapter for o in req.outline)
            conn.execute(
                "UPDATE projects SET total_chapters=?, status='initialized', updated_at=datetime('now') WHERE project_id=?",
                (max_ch, project_id),
            )
        conn.commit()

        result = ImportResult(
            outline=len(req.outline),
            characters=len(req.characters),
            debts=len(req.debts),
            foreshadowing=len(req.foreshadowing),
            rules=len(req.rules),
            skills=len(req.skills),
        )
        logger.info("项目 %s 数据导入完成: %s", project_id, result.model_dump())
        return {"code": 200, "data": result.model_dump()}

    except Exception as exc:
        conn.rollback()
        logger.exception("导入失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"导入失败: {exc}")
    finally:
        conn.close()
