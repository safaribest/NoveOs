from fastapi import APIRouter, HTTPException

from api.main import orchestrator

router = APIRouter()


@router.get("/projects/{project_id}/emotions")
async def get_emotions(project_id: str):
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    state = orchestrator.get_state_manager(project_id)
    if not state:
        raise HTTPException(status_code=404, detail="状态库不可用")

    rows = state.get_emotion_history()
    coordinates = [
        {
            "chapter": r["chapter"],
            "x": r["coordinate_x"],
            "y": r["coordinate_y"],
            "mode": r["mode"],
            "desc": r["desc"],
        }
        for r in rows
    ]
    return {"code": 200, "data": {"coordinates": coordinates}}
