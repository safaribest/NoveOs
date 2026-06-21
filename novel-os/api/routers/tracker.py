"""债务/伏笔追踪器路由。"""
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _get_orchestrator(request: Request):
    return request.app.state.orchestrator


@router.get("/projects/{project_id}/debts")
async def list_debts(project_id: str, request: Request):
    orchestrator = _get_orchestrator(request)
    runtime = orchestrator._projects.get(project_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = runtime.state_manager.list_debts()
    return {"code": 200, "data": data}


@router.get("/projects/{project_id}/foreshadowing")
async def list_foreshadowing(project_id: str, request: Request):
    orchestrator = _get_orchestrator(request)
    runtime = orchestrator._projects.get(project_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = runtime.state_manager.list_foreshadowing()
    return {"code": 200, "data": data}
