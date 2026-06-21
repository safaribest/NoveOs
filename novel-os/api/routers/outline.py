"""大纲路由 —— 提供章节规划、技能树、规则查询。"""
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _get_orchestrator(request: Request):
    return request.app.state.orchestrator


@router.get("/projects/{project_id}/outline")
async def list_outline(project_id: str, request: Request):
    orchestrator = _get_orchestrator(request)
    runtime = orchestrator._projects.get(project_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = runtime.state_manager.list_outline()
    return {"code": 200, "data": data}


@router.get("/projects/{project_id}/skills")
async def list_skills(project_id: str, request: Request):
    orchestrator = _get_orchestrator(request)
    runtime = orchestrator._projects.get(project_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = runtime.state_manager.list_skills()
    return {"code": 200, "data": data}


@router.get("/projects/{project_id}/rules")
async def list_rules(project_id: str, request: Request):
    orchestrator = _get_orchestrator(request)
    runtime = orchestrator._projects.get(project_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = runtime.state_manager.list_rules()
    return {"code": 200, "data": data}
