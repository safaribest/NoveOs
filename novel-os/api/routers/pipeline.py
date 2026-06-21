from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from api.main import orchestrator

router = APIRouter()


class StartPipelineRequest(BaseModel):
    from_step: str = "writer"
    resume: bool = False
    chapter_range: str = "1-100"  # 支持 "1-10"、"5"、"1-10,15-20"

    @field_validator("chapter_range")
    @classmethod
    def validate_chapter_range(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("chapter_range 不能为空")
        parts = [p.strip() for p in v.split(",") if p.strip()]
        if not parts:
            raise ValueError("chapter_range 格式无效")
        normalized: list[str] = []
        for part in parts:
            if "-" in part:
                start_str, end_str = part.split("-", 1)
                start = int(start_str)
                end = int(end_str)
            else:
                start = end = int(part)
            if start <= 0:
                raise ValueError("章节起始必须大于 0")
            if start > end:
                raise ValueError("章节起始不能大于结束")
            normalized.append(f"{start}-{end}")
        return ",".join(normalized)


@router.get("/projects/{project_id}/status")
async def project_status(project_id: str):
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"code": 200, "data": status}


@router.get("/projects/{project_id}/pipeline")
async def pipeline_status(project_id: str):
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    # audit 字段：从最近一次章节审计结果取值
    last_audit = status.get("last_audit") or {}
    audit = {
        "quality_passed": last_audit.get("quality_passed", False),
        "sensitive_passed": last_audit.get("sensitive_passed", False),
    }

    pipeline_id = status.get("pipeline_id")
    is_running = pipeline_id is not None

    return {
        "code": 200,
        "data": {
            "pipeline_id": pipeline_id,
            "status": status.get("status"),
            "current_step_index": status.get("current_chapter", 0),
            "can_start": not is_running,
            "is_running": is_running,
            "audit": audit,
            "reader_pull_score": status.get("reader_pull_score"),
        },
    }


@router.post("/projects/{project_id}/pipeline/start")
async def start_pipeline(project_id: str, req: StartPipelineRequest):
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")
    if status.get("pipeline_id") is not None:
        raise HTTPException(status_code=409, detail="项目正在运行中")

    # 解析为范围列表
    ranges: list[tuple[int, int]] = []
    for part in req.chapter_range.split(","):
        start_str, end_str = part.split("-")
        ranges.append((int(start_str), int(end_str)))

    try:
        pipeline_id = orchestrator.start_pipeline(project_id, ranges, req.resume)
        return {"code": 200, "data": {"pipeline_id": pipeline_id}}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/projects/{project_id}/pipeline/pause")
async def pause_pipeline(project_id: str):
    try:
        orchestrator.pause_pipeline(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": None}


@router.post("/projects/{project_id}/pipeline/stop")
async def stop_pipeline(project_id: str):
    try:
        orchestrator.stop_pipeline(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "data": None}
