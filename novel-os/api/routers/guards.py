"""Guard Registry API —— 门禁管理接口。"""
from fastapi import APIRouter, Request

from core.guard_registry_init import get_registry

router = APIRouter()


@router.get("/projects/{project_id}/guards")
async def list_guards(project_id: str, request: Request):
    """列出当前项目的所有 Guard 状态。"""
    registry = get_registry()
    return {"code": 200, "data": registry.list_guards()}


@router.post("/projects/{project_id}/guards/run")
async def run_guards(project_id: str, content: str, context: dict | None = None, request: Request = None):
    """手动执行所有 Guard（调试用）。"""
    registry = get_registry()
    results = registry.run_all(content, context or {})
    return {
        "code": 200,
        "data": [
            {
                "guard_id": r.guard_id,
                "level": r.level,
                "message": r.message,
                "metadata": r.metadata,
            }
            for r in results
        ],
    }


@router.post("/projects/{project_id}/guards/calibrate")
async def calibrate_guards(project_id: str, threshold: float = 0.1, request: Request = None):
    """执行校准循环。"""
    registry = get_registry()
    adjustments = registry.calibrate_all(threshold=threshold)
    return {"code": 200, "data": adjustments}
