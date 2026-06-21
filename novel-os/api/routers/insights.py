"""洞察 API：选题生成与任务管理。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from core.insight_service import GenerateOutlinePreferences, GeneratePreferences, InsightService, Topic

logger = logging.getLogger("novel-os.api.insights")

router = APIRouter(prefix="/insights", tags=["insights"])

# 内存任务存储（MVP 版本，后续可迁移到 Redis/Celery）
tasks: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------

class CategoryNode(BaseModel):
    """分类节点。"""

    id: str
    name: str
    genre: str | None = None
    tags: list[str] | None = None
    children: list["CategoryNode"] | None = None


class CategoriesResponse(BaseModel):
    """分类树响应。"""

    categories: list[CategoryNode]


class GenerateTopicsPayload(BaseModel):
    """生成选题请求。"""

    category_id: str = Field(..., description="选中的三级分类 ID")
    platform: str = Field(default="起点", description="目标平台")
    style: str = Field(default="", description="风格偏好")
    chapters_target: int = Field(default=200, ge=3, le=2000)
    words_per_chapter: int = Field(default=2200, ge=500, le=10000)
    extra_notes: str = Field(default="", description="额外要求")


class GenerateTopicsResponse(BaseModel):
    """生成选题任务创建响应。"""

    task_id: str


class GenerateOutlinePayload(BaseModel):
    """生成大纲请求。"""

    topic: dict[str, Any] = Field(..., description="选中的选题对象")
    category_id: str = Field(..., description="选题所属分类 ID")
    platform: str = Field(default="起点", description="目标平台")
    style: str = Field(default="", description="风格偏好")
    chapters_target: int = Field(default=200, ge=3, le=2000)
    words_per_chapter: int = Field(default=2200, ge=500, le=10000)
    extra_notes: str = Field(default="", description="额外要求")


class TopicItem(BaseModel):
    """选题项。"""

    id: str
    title: str
    hook: str
    slap_points: list[str]
    target_reader: str
    risks: list[str]
    why_now: str


class TaskInfo(BaseModel):
    """任务信息。"""

    id: str
    type: str
    status: str
    progress: int
    result: Any | None = None
    error: str | None = None
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# 后台任务
# ---------------------------------------------------------------------------

def _run_topic_generation(
    task_id: str,
    category_id: str,
    preferences: GeneratePreferences,
) -> None:
    """在后台运行选题生成。"""
    task = tasks.get(task_id)
    if not task:
        logger.error("任务不存在: %s", task_id)
        return

    task["status"] = "running"
    task["updated_at"] = datetime.now().isoformat()

    try:
        service = InsightService()
        topics = service.generate_topics(category_id, preferences)
        task["status"] = "success"
        task["progress"] = 100
        task["result"] = [t.to_dict() for t in topics]
    except Exception as exc:  # noqa: BLE001
        logger.exception("选题生成任务失败: %s", task_id)
        task["status"] = "failed"
        task["error"] = str(exc)

    task["updated_at"] = datetime.now().isoformat()


def _run_outline_generation(
    task_id: str,
    topic: dict[str, Any],
    category_id: str,
    preferences: GenerateOutlinePreferences,
) -> None:
    """在后台运行大纲生成。"""
    task = tasks.get(task_id)
    if not task:
        logger.error("任务不存在: %s", task_id)
        return

    task["status"] = "running"
    task["updated_at"] = datetime.now().isoformat()

    try:
        service = InsightService()
        result = service.generate_outline(topic, category_id, preferences)
        task["status"] = "success"
        task["progress"] = 100
        task["result"] = result.to_dict()
    except Exception as exc:  # noqa: BLE001
        logger.exception("大纲生成任务失败: %s", task_id)
        task["status"] = "failed"
        task["error"] = str(exc)

    task["updated_at"] = datetime.now().isoformat()


# ---------------------------------------------------------------------------
# API 接口
# ---------------------------------------------------------------------------

@router.get("/categories")
async def get_categories() -> dict[str, Any]:
    """获取全部分类树。"""
    service = InsightService()
    categories = service.load_categories()
    return {"code": 200, "data": {"categories": categories}}


@router.post("/topics")
async def generate_topics(
    payload: GenerateTopicsPayload,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """创建选题生成任务。"""
    service = InsightService()
    if not service.find_category(payload.category_id):
        raise HTTPException(
            status_code=400,
            detail=f"分类不存在: {payload.category_id}",
        )

    task_id = f"topic_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    tasks[task_id] = {
        "id": task_id,
        "type": "topic_generation",
        "status": "pending",
        "progress": 0,
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    preferences = GeneratePreferences(
        platform=payload.platform,
        style=payload.style,
        chapters_target=payload.chapters_target,
        words_per_chapter=payload.words_per_chapter,
        extra_notes=payload.extra_notes,
    )

    background_tasks.add_task(_run_topic_generation, task_id, payload.category_id, preferences)

    return {"code": 200, "data": {"task_id": task_id}}


@router.post("/outline")
async def generate_outline(
    payload: GenerateOutlinePayload,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """创建大纲生成任务。"""
    service = InsightService()
    if not service.find_category(payload.category_id):
        raise HTTPException(
            status_code=400,
            detail=f"分类不存在: {payload.category_id}",
        )

    task_id = f"outline_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    tasks[task_id] = {
        "id": task_id,
        "type": "outline_generation",
        "status": "pending",
        "progress": 0,
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    preferences = GenerateOutlinePreferences(
        platform=payload.platform,
        style=payload.style,
        chapters_target=payload.chapters_target,
        words_per_chapter=payload.words_per_chapter,
        extra_notes=payload.extra_notes,
    )

    background_tasks.add_task(
        _run_outline_generation,
        task_id,
        payload.topic,
        payload.category_id,
        preferences,
    )

    return {"code": 200, "data": {"task_id": task_id}}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    """查询任务状态。"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    return {
        "code": 200,
        "data": {
            "id": task["id"],
            "type": task["type"],
            "status": task["status"],
            "progress": task["progress"],
            "result": task.get("result"),
            "error": task.get("error"),
            "created_at": task["created_at"],
            "updated_at": task["updated_at"],
        },
    }


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str) -> dict[str, Any]:
    """获取任务结果（成功时）。"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    if task["status"] != "success":
        raise HTTPException(
            status_code=400,
            detail=f"任务尚未完成，当前状态: {task['status']}",
        )

    return {"code": 200, "data": task.get("result", [])}
