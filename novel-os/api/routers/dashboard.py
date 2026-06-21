"""项目看板路由 —— 聚合大纲、人物、道具、技能、伏笔、债务、术语等全量设定。"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from core.state.repositories.base import UnitOfWork

router = APIRouter()


def _load_book_outline(base_path: Path) -> dict[str, Any]:
    """从项目目录的 book_data.py 读取 OUTLINE。

    兼容两种格式：
    1. OUTLINE = json.loads(r'''{"summary": ..., "volumes": ..., "outline": [...]}''')
    2. OUTLINE = [{"chapter": 1, "title": ..., "arc": ...}, ...]
    """
    book_data_path = base_path / "book_data.py"
    if not book_data_path.exists():
        return {}

    try:
        spec = importlib.util.spec_from_file_location("book_data", str(book_data_path))
        if not spec or not spec.loader:
            return {}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        outline = getattr(module, "OUTLINE", None)
    except Exception:
        return {}

    if outline is None:
        return {}

    if isinstance(outline, dict):
        return {
            "summary": outline.get("summary", ""),
            "volumes": outline.get("volumes", []),
            "chapters": outline.get("outline", outline.get("chapters", [])),
        }

    if isinstance(outline, list):
        # 按 arc 自动归卷
        volumes: list[dict[str, Any]] = []
        arc_numbers: dict[str, list[int]] = {}
        for chapter in outline:
            if not isinstance(chapter, dict):
                continue
            arc = chapter.get("arc") or "未分组"
            arc_numbers.setdefault(arc, []).append(chapter.get("chapter", 0))
        for arc, numbers in arc_numbers.items():
            numbers_sorted = sorted(n for n in numbers if n)
            range_str = ""
            if numbers_sorted:
                if numbers_sorted[0] == numbers_sorted[-1]:
                    range_str = f"第{numbers_sorted[0]}章"
                else:
                    range_str = f"第{numbers_sorted[0]}-{numbers_sorted[-1]}章"
            volumes.append({
                "title": arc,
                "range": range_str,
                "theme": "",
                "climax": "",
            })
        return {"summary": "", "volumes": volumes, "chapters": outline}

    return {}


def _list_terms(db_path: Path, project_id: str) -> list[dict[str, Any]]:
    """从 term_dict 表读取世界观术语。"""
    import sqlite3

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT term, category, first_chapter, description
            FROM term_dict
            WHERE project_id = ?
            ORDER BY COALESCE(first_chapter, 9999), term
            """,
            (project_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def _list_items(db_path: Path, project_id: str) -> list[dict[str, Any]]:
    """读取道具最新状态。"""
    with UnitOfWork(db_path, project_id) as uow:
        items = uow.items.list_all()
        return [item.__dict__ for item in items]


@router.get("/projects/{project_id}/dashboard")
async def get_dashboard(project_id: str):
    from api.main import orchestrator

    runtime = orchestrator._projects.get(project_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="项目不存在")

    state = runtime.state_manager
    base_path = Path(runtime.book_config.base_path)
    db_path = state.db_path

    # 优先从 book_data.py 读取完整大纲；失败则回退到 world_state.db 的 outline 表
    outline = _load_book_outline(base_path)
    if not outline.get("chapters"):
        db_outline = state.list_outline()
        outline = {
            "summary": "",
            "volumes": [],
            "chapters": db_outline,
        }

    return {
        "code": 200,
        "data": {
            "outline": outline,
            "characters": state.list_characters(),
            "items": _list_items(db_path, project_id),
            "skills": state.list_skills(),
            "debts": state.list_debts(),
            "foreshadowing": state.list_foreshadowing(),
            "terms": _list_terms(db_path, project_id),
        },
    }
