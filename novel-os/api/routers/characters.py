from fastapi import APIRouter, HTTPException

from api.main import orchestrator

router = APIRouter()


@router.get("/projects/{project_id}/characters")
async def list_characters(project_id: str):
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    state = orchestrator.get_state_manager(project_id)
    if not state:
        raise HTTPException(status_code=404, detail="状态库不可用")

    characters = state.list_characters()
    return {"code": 200, "data": characters}
