"""全文搜索 API —— 基于 SQLite FTS5。"""
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.main import orchestrator
from core.fts_index import FTSIndexManager

router = APIRouter()


@router.get("/projects/{project_id}/search")
async def search_chapters(project_id: str, q: str = "", limit: int = 10):
    """在项目章节全文索引中搜索。"""
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    db_path = Path(status["base_path"]) / "world_state.db"
    fts = FTSIndexManager(db_path)
    results = fts.search(q, limit=limit)
    return {"code": 200, "data": results}
