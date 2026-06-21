import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# 自动加载项目根目录的 .env 文件（与 cli.py 保持一致）
# main.py 位于 novel-os/api/main.py，因此 .env 在上两级目录
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    with open(_ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key = _key.strip()
                _val = _val.strip().strip('"').strip("'")
                os.environ[_key] = _val

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from core.orchestrator import Orchestrator
from core.config_loader import BookConfig, get_novel_base_path

# 强制 Windows 终端使用 UTF-8，避免日志/输出乱码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 统一日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

class Utf8JSONResponse(JSONResponse):
    def __init__(self, content: Any, status_code: int = 200, **kwargs: Any) -> None:
        headers = kwargs.pop("headers", {}) or {}
        headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate")
        headers.setdefault("Pragma", "no-cache")
        super().__init__(content, status_code=status_code, headers=headers, **kwargs)

    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


app = FastAPI(
    title="Novel-OS API",
    description="AI 小说写作操作系统后端 API",
    version="1.0.0",
    default_response_class=Utf8JSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Orchestrator 单例（必须在 routers 导入前定义，避免循环导入）
orchestrator = Orchestrator(max_workers=10)
app.state.orchestrator = orchestrator

from api.routers import chapters, characters, dashboard, emotions, guards, logs, pipeline, projects, reports, search, snapshots, system, task_card, outline, tracker, metrics, import_data, settings, insights, auth


# 认证中间件：除登录接口和 CORS 预检外，所有 /api/v1/* 请求都需要有效 JWT
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or path == "/api/v1/auth/login":
        return await call_next(request)

    if path.startswith("/api/v1/"):
        from api.routers.auth import _verify_token, _USERNAME

        token: str | None = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            # SSE/EventSource 无法设置请求头，允许通过 query token 认证
            token = request.query_params.get("token")

        if not token:
            return Utf8JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"code": 401, "message": "缺少认证令牌", "data": None},
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            payload = _verify_token(token)
            if payload.get("sub") != _USERNAME:
                raise ValueError("Invalid user")
        except Exception:
            return Utf8JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"code": 401, "message": "无效的认证令牌", "data": None},
                headers={"WWW-Authenticate": "Bearer"},
            )

    return await call_next(request)


app.include_router(projects.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(chapters.router, prefix="/api/v1")
app.include_router(characters.router, prefix="/api/v1")
app.include_router(emotions.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(guards.router, prefix="/api/v1")
app.include_router(task_card.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(snapshots.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(outline.router, prefix="/api/v1")
app.include_router(tracker.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(import_data.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(insights.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")


# 全局异常处理
@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException) -> Utf8JSONResponse:
    """统一 HTTP 异常响应格式。"""
    return Utf8JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> Utf8JSONResponse:
    """捕获未处理异常，记录日志并返回统一格式。"""
    logging.getLogger("novel-os.api").exception("未处理异常: %s", exc)
    return Utf8JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": 500, "message": "服务器内部错误", "data": None},
    )


@app.on_event("startup")
async def startup():
    """启动事件：扫描 books/ 目录自动注册项目，并处理 Orc 初始化。"""

    # ── 1. 扫描 books/ 目录，自动注册未在 DB 中的项目 ──
    books_root = get_novel_base_path()
    if books_root.exists():
        registered = {p.project_id for p in orchestrator._projects.values()}
        for book_dir in books_root.iterdir():
            if not book_dir.is_dir():
                continue
            yaml_path = book_dir / "book.yaml"
            if not yaml_path.exists():
                continue
            # 用目录名作为 project_id
            project_id = book_dir.name
            if project_id in registered:
                continue
            try:
                book_config = BookConfig.from_yaml(yaml_path)
                orchestrator.register_project(project_id, book_config)
                logging.getLogger("novel-os.api").info(
                    "自动注册项目: %s (%s · %s · %d章)",
                    project_id,
                    book_config.genre,
                    book_config.platform,
                    book_config.chapters_target,
                )
                # 持久化到全局 DB
                orchestrator._persist_project(
                    project_id,
                    orchestrator._projects[project_id],
                )
            except Exception:
                logging.getLogger("novel-os.api").exception(
                    "自动注册项目失败: %s", project_id
                )

    # ── 2. 挂载前端静态文件（开发时由 Vite dev server 提供，生产时由此处提供）──
    dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if dist_dir.exists():
        from fastapi import APIRouter

        fe_router = APIRouter()

        @fe_router.get("/{full_path:path}")
        async def serve_frontend(full_path: str) -> FileResponse:
            file_path = dist_dir / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(dist_dir / "index.html"))

        app.include_router(fe_router)
        logging.getLogger("novel-os.api").info(
            "前端路由已配置: %s", dist_dir
        )
