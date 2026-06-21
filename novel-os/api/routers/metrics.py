"""章节结构指标路由 —— IWR、平台适配度、品类 DNA。"""
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _get_orchestrator(request: Request):
    return request.app.state.orchestrator


@router.get("/projects/{project_id}/metrics")
async def list_metrics(project_id: str, request: Request):
    """返回所有章节的结构指标（IWR、平台适配度等）。"""
    orchestrator = _get_orchestrator(request)
    runtime = orchestrator._projects.get(project_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = runtime.state_manager.get_chapter_metrics()
    return {"code": 200, "data": data}


@router.get("/projects/{project_id}/metrics/{chapter_num}")
async def get_chapter_metric(project_id: str, chapter_num: int, request: Request):
    """返回单章结构指标。"""
    orchestrator = _get_orchestrator(request)
    runtime = orchestrator._projects.get(project_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = runtime.state_manager.get_chapter_metrics(chapter_num)
    return {"code": 200, "data": data[0] if data else {}}


@router.get("/projects/{project_id}/genre_dna")
async def get_genre_dna(project_id: str, request: Request):
    """返回项目品类 DNA 参数。"""
    orchestrator = _get_orchestrator(request)
    runtime = orchestrator._projects.get(project_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = runtime.state_manager.get_genre_dna()
    return {"code": 200, "data": data}
