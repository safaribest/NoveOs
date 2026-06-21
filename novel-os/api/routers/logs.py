import asyncio
import json
import time
import uuid
from collections import deque

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.main import orchestrator

router = APIRouter()


@router.get("/projects/{project_id}/logs")
async def get_logs(
    project_id: str, limit: int = 100, level: str = None, agent: str = None
):
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    state = orchestrator.get_state_manager(project_id)
    if not state:
        raise HTTPException(status_code=404, detail="状态库不可用")

    logs = state.get_runtime_logs(limit=limit, level=level, agent=agent)
    return {"code": 200, "data": logs}


@router.get("/projects/{project_id}/logs/stream")
async def stream_logs(project_id: str):
    """SSE 实时日志流。每 2 秒轮询一次数据库，只推送新增日志。"""
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    state = orchestrator.get_state_manager(project_id)
    if not state:
        raise HTTPException(status_code=404, detail="状态库不可用")

    # 限制最近 5000 条已见日志，防止内存无限增长
    seen_log_ids: deque[str] = deque(maxlen=5000)

    async def event_generator():
        # 先推送一次历史最近 20 条，帮助客户端快速填充
        try:
            logs = state.get_runtime_logs(limit=20)
            for log in reversed(logs):
                if log["log_id"] not in seen_log_ids:
                    seen_log_ids.append(log["log_id"])
                    yield f"data: {json.dumps(log, ensure_ascii=False)}\n\n"
        except Exception:
            pass

        last_heartbeat = time.monotonic()
        while True:
            await asyncio.sleep(2)

            # 每 30 秒发送一次心跳注释
            now = time.monotonic()
            if now - last_heartbeat >= 30:
                yield ": heartbeat\n\n"
                last_heartbeat = now

            try:
                logs = state.get_runtime_logs(limit=100)
                # 按时间正序推送新日志
                new_logs = [log for log in logs if log["log_id"] not in seen_log_ids]
                for log in reversed(new_logs):
                    seen_log_ids.append(log["log_id"])
                for log in sorted(new_logs, key=lambda x: x.get("created_at", "")):
                    yield f"data: {json.dumps(log, ensure_ascii=False)}\n\n"
            except Exception as e:
                # 数据库异常时发送错误事件并关闭连接，不再无限挂起
                yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
                return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/projects/{project_id}/audit")
async def run_audit(project_id: str):
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 批量自检（Phase 2 实现）
    audit_id = f"audit_{uuid.uuid4().hex[:12]}"
    return {"code": 200, "data": {"audit_id": audit_id, "status": "running"}}
