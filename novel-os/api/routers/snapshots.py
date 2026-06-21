"""章节快照与回滚 API。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.main import orchestrator

router = APIRouter()


class RollbackRequest(BaseModel):
    chapter: int
    snapshot_type: str


@router.get("/projects/{project_id}/snapshots")
async def list_snapshots(project_id: str, chapter: int | None = None):
    """列出项目下某章（或全部）的快照。"""
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    state = orchestrator.get_state_manager(project_id)
    if not state:
        raise HTTPException(status_code=404, detail="状态库不可用")

    snapshots = state.list_snapshots(chapter)
    return {"code": 200, "data": snapshots}


@router.post("/projects/{project_id}/snapshots/rollback")
async def rollback_snapshot(project_id: str, req: RollbackRequest):
    """回滚指定章节到最新快照。"""
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    runtime = orchestrator._projects.get(project_id)
    if not runtime or not runtime.snapshot_manager:
        raise HTTPException(status_code=404, detail="快照管理器不可用")

    result = runtime.snapshot_manager.rollback(req.chapter, req.snapshot_type)
    return {"code": 200, "data": result}
