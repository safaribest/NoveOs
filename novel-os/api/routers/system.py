from fastapi import APIRouter

from api.main import orchestrator

router = APIRouter()


@router.get("/system/stats")
async def system_stats():
    return {"code": 200, "data": orchestrator.get_global_stats()}


@router.get("/system/health")
async def health():
    return {"code": 200, "data": {"status": "ok"}}
