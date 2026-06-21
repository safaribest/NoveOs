import gc
import os
import shutil
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.config_loader import BookConfig, get_novel_base_path
from core.project_factory import ProjectFactory

router = APIRouter()


class CreateProjectRequest(BaseModel):
    project_id: str
    name: str
    genre: str
    platform: str
    total_chapters: int


class CreateFromOutlineRequest(BaseModel):
    title: str
    outline: dict
    category_id: str | None = None
    chapters_target: int | None = Field(default=None, ge=3, le=2000)
    words_per_chapter: int | None = Field(default=None, ge=500, le=10000)


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    genre: str | None = None
    platform: str | None = None
    chapters_target: int | None = None
    words_per_chapter: int | None = None


@router.get("/projects")
async def list_projects():
    from api.main import orchestrator
    return {"code": 200, "data": orchestrator.get_all_projects()}


@router.post("/projects")
async def create_project(req: CreateProjectRequest):
    # 创建项目目录与 book.yaml 模板
    base = get_novel_base_path() / req.project_id
    base.mkdir(parents=True, exist_ok=True)

    yaml_path = base / "book.yaml"
    # 仅在 book.yaml 不存在时创建模板，不覆盖已有配置（保护 api_key 等手动配置）
    if not yaml_path.exists():
        yaml_content = (
            f"project: {req.name}\n"
            f"platform: {req.platform}\n"
            f"genre: {req.genre}\n"
            f"base_path: {base}\n"
            f"# crewai_db_path 已废弃，不再需要\n"
            f"total_words_target: 0\n"
            f"chapters_target: {req.total_chapters}\n"
            f"words_per_chapter: 4500\n"
            f"output_dir: chapters\n"
            f"plugin_id: \"\"\n"
            f"agent_query: {{}}\n"
            f"writing:\n"
            f"  tolerance: 450\n"
            f"  max_retries: 3\n"
            f"  batch_size: 5\n"
            f"llm:\n"
            f"  model: deepseek-ai/DeepSeek-V3\n"
            f"  api_key: ${{OPENAI_API_KEY}}\n"
            f"  api_base: https://api.siliconflow.cn/v1\n"
            f"  temperature: 0.7\n"
            f"  max_tokens: 8000\n"
            f"  timeout: 300\n"
            f"  reasoning_effort: high\n"
            f"  thinking_enabled: false\n"
        )
        yaml_path.write_text(yaml_content, encoding="utf-8")

    book_config = BookConfig.from_yaml(yaml_path)
    from api.main import orchestrator
    orchestrator.register_project(req.project_id, book_config)
    return {"code": 200, "data": {"project_id": req.project_id}}


@router.post("/projects/from-outline")
async def create_from_outline(req: CreateFromOutlineRequest):
    factory = ProjectFactory()
    result = factory.create_from_outline(
        title=req.title,
        outline=req.outline,
        category_id=req.category_id,
        chapters_target=req.chapters_target,
        words_per_chapter=req.words_per_chapter,
    )
    return {"code": 200, "data": result}


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    from api.main import orchestrator
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"code": 200, "data": status}


@router.put("/projects/{project_id}")
async def update_project(project_id: str, req: UpdateProjectRequest):
    from api.main import orchestrator
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        updated = orchestrator.update_project(
            project_id,
            name=req.name,
            genre=req.genre,
            platform=req.platform,
            chapters_target=req.chapters_target,
            words_per_chapter=req.words_per_chapter,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"code": 200, "data": updated}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    wipe: bool = Query(False, description="为 true 时彻底删除项目文件与全局注册表记录"),
):
    from api.main import orchestrator
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    deleted_files = False
    if wipe:
        orchestrator.stop_pipeline(project_id)

    orchestrator.unregister_project(project_id)

    if wipe:
        # 使用规范路径删除，避免旧项目 book.yaml/base_path 中残留错误路径导致删不干净
        base_path = get_novel_base_path() / project_id
        if base_path.exists():
            # 强制关闭并回收可能持有数据库文件句柄的连接
            gc.collect()
            # 先尝试直接删除；若 Windows 文件锁未释放，则短暂等待后重试
            for _ in range(3):
                try:
                    shutil.rmtree(base_path)
                    deleted_files = True
                    break
                except Exception:
                    time.sleep(0.5)
                    gc.collect()
            else:
                deleted_files = False

        # 删除全局 orchestrator.db 中的项目记录
        global_db = get_novel_base_path() / "orchestrator.db"
        if global_db.exists():
            try:
                with sqlite3.connect(str(global_db)) as conn:
                    conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
                    conn.commit()
            except Exception:
                pass

    return {"code": 200, "data": {"project_id": project_id, "deleted_files": deleted_files}}
