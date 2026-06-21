"""Novel-OS 全局编排器 —— 多项目调度中心。"""
from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.batch_writer import BatchWriter
from core.config_loader import BookConfig, get_novel_base_path
from core.event_bus import (
    CHAPTER_COMPLETE,
    CHAPTER_ERROR,
    CHAPTER_START,
    EVENT_TYPES,
    EventBus,
    OUTER_CREW_INSPECTION_COMPLETE,
    OUTER_CREW_INSPECTION_START,
    OUTER_CREW_RETCON_TRIGGERED,
    PIPELINE_COMPLETE,
    PIPELINE_PAUSE,
    PIPELINE_START,
)
from core.outer_crew_runner import OuterCrewRunner
from core.snapshot_manager import SnapshotManager
from core.state_manager import StateManager

logger = logging.getLogger("novel-os.orchestrator")


@dataclass
class ProjectRuntime:
    """项目运行时上下文。"""

    project_id: str
    book_config: BookConfig
    state_manager: StateManager
    batch_writer: BatchWriter
    status: str = "pending"  # pending / outlining / configuring / writing / auditing / completed / paused / error
    current_chapter: int = 0
    pipeline_id: str | None = None
    future: Future | None = None
    last_audit: dict[str, Any] = field(default_factory=dict)
    reader_pull_score: float | None = None
    snapshot_manager: SnapshotManager | None = None
    outer_crew_runner: OuterCrewRunner | None = None
    pending_retcons: list[str] = field(default_factory=list)
    emotion_targets: list[dict[str, Any]] = field(default_factory=list)
    outer_crew_reports: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class Orchestrator:
    """管理多个项目的生命周期与流水线调度。

    设计约束:
    - 单项目串行: 同一项目章节必须串行
    - 跨项目并行: 不同项目可并发 Worker
    - 失败隔离: Worker 崩溃只影响当前章节，Orchestrator 自动标记 error
    - 可观测: 每个状态变更通过 EventBus 推送
    """

    def __init__(self, max_workers: int = 10) -> None:
        self.max_workers = max_workers
        self._projects: dict[str, ProjectRuntime] = {}
        self._lock = threading.RLock()
        self._paused: set[str] = set()
        self._stopped: set[str] = set()
        self._event_bus = EventBus()
        self._event_handlers: list[Callable[[str, dict[str, Any]], None]] = []
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="novelos_worker"
        )
        self._global_db_path = get_novel_base_path() / "orchestrator.db"
        self._global_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_global_db()
        self._load_projects_from_db()
        self._setup_runtime_log_handler()

    # ------------------------------------------------------------------
    # 全局数据库
    # ------------------------------------------------------------------
    def _init_global_db(self) -> None:
        with sqlite3.connect(str(self._global_db_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id      TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    genre           TEXT NOT NULL,
                    platform        TEXT NOT NULL,
                    base_path       TEXT NOT NULL,
                    status          TEXT DEFAULT 'pending',
                    current_chapter INTEGER DEFAULT 0,
                    total_chapters  INTEGER NOT NULL,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def _persist_project(self, project_id: str, info: ProjectRuntime) -> None:
        with sqlite3.connect(str(self._global_db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO projects
                (project_id, name, genre, platform, base_path, status, current_chapter, total_chapters, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    info.book_config.project,
                    info.book_config.genre,
                    info.book_config.platform,
                    str(info.book_config.base_path),
                    info.status,
                    info.current_chapter,
                    info.book_config.chapters_target,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    def _load_projects_from_db(self) -> None:
        """启动时从全局注册表恢复项目列表（若 book.yaml 存在则自动注册）。"""
        try:
            with sqlite3.connect(str(self._global_db_path)) as conn:
                cur = conn.execute(
                    "SELECT project_id, base_path FROM projects"
                )
                for row in cur.fetchall():
                    project_id, base_path = row[0], row[1]
                    yaml_path = Path(base_path) / "book.yaml"
                    if yaml_path.exists():
                        try:
                            book_config = BookConfig.from_yaml(yaml_path)
                            self.register_project(project_id, book_config)
                            logger.info("从注册表恢复项目: %s", project_id)
                        except Exception:
                            logger.exception("恢复项目 %s 失败", project_id)
                    else:
                        logger.warning(
                            "项目 %s 的 book.yaml 不存在，跳过恢复", project_id
                        )
        except Exception:
            logger.exception("恢复项目列表失败")

    # ------------------------------------------------------------------
    # 项目注册 / 注销
    # ------------------------------------------------------------------
    def register_project(self, project_id: str, book_config: BookConfig) -> None:
        """注册新项目并初始化状态库与 BatchWriter。

        若数据库中已有该项目的进度记录，则继承现有状态（不重置为 pending）。
        """
        with self._lock:
            db_path = book_config.base_path / "world_state.db"
            state = StateManager(db_path, project_id)
            state.init_project(
                project_id=project_id,
                name=book_config.project,
                genre=book_config.genre,
                platform=book_config.platform,
                base_path=str(book_config.base_path),
                total_chapters=book_config.chapters_target,
            )
            # 初始化品类 DNA（RAG 分析驱动）
            state.init_genre_dna(book_config.genre)

            writer = BatchWriter(book_config, state_manager=state, event_bus=self._event_bus)

            # 初始化外层 CrewAI 运行器（如果启用）
            outer_crew_cfg = book_config.outer_crew
            outer_runner = None
            if outer_crew_cfg.get("enabled", True):
                try:
                    outer_runner = OuterCrewRunner(book_config, state, writer.llm)
                    if outer_runner.is_available():
                        logger.info("项目 %s 外层 CrewAI 已启用", project_id)
                    else:
                        logger.warning("项目 %s 外层 CrewAI 配置不可用", project_id)
                        outer_runner = None
                except Exception as exc:
                    logger.warning("项目 %s 外层 CrewAI 初始化失败: %s", project_id, exc)
                    outer_runner = None

            # 从全局数据库读取已有进度，避免重启后丢失状态
            existing_status = "pending"
            existing_chapter = 0
            try:
                with sqlite3.connect(str(self._global_db_path)) as conn:
                    row = conn.execute(
                        "SELECT status, current_chapter FROM projects WHERE project_id = ?",
                        (project_id,),
                    ).fetchone()
                    if row:
                        existing_status, existing_chapter = row[0], row[1] or 0
                        # 进程重启后，运行中状态会丢失 pipeline_id/future，变成脏状态
                        if existing_status in ("writing", "auditing"):
                            logger.warning(
                                "项目 %s 注册时发现运行中脏状态 %s，重置为 pending",
                                project_id,
                                existing_status,
                            )
                            existing_status = "pending"
            except Exception:
                pass

            runtime = ProjectRuntime(
                project_id=project_id,
                book_config=book_config,
                state_manager=state,
                batch_writer=writer,
                snapshot_manager=SnapshotManager(state),
                outer_crew_runner=outer_runner,
                status=existing_status,
                current_chapter=existing_chapter,
            )
            self._projects[project_id] = runtime
            self._persist_project(project_id, runtime)
            logger.info("项目 %s 已注册 (status=%s, chapter=%d)", project_id, existing_status, existing_chapter)
            state.log_runtime(
                level="INFO",
                agent="system",
                chapter_num=existing_chapter,
                message=f"项目已注册 (status={existing_status}, chapter={existing_chapter})",
                metadata={"status": existing_status, "current_chapter": existing_chapter},
            )

    def unregister_project(self, project_id: str) -> None:
        """从调度器中注销项目（不删除文件）。"""
        with self._lock:
            info = self._projects.pop(project_id, None)
            if info and info.future and not info.future.done():
                info.future.cancel()
            logger.info("项目 %s 已注销", project_id)

    def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        genre: str | None = None,
        platform: str | None = None,
        chapters_target: int | None = None,
        words_per_chapter: int | None = None,
    ) -> dict[str, Any] | None:
        """更新项目元信息并持久化到 book.yaml 和全局注册表。"""
        with self._lock:
            runtime = self._projects.get(project_id)
            if not runtime:
                return None

            # 流水线运行时禁止修改核心参数
            if runtime.status in ("writing", "auditing") and (chapters_target is not None or words_per_chapter is not None):
                raise ValueError("流水线运行中，不能修改章节数或每章字数")

            total_words_target = None
            if chapters_target is not None and words_per_chapter is not None:
                total_words_target = chapters_target * words_per_chapter
            elif chapters_target is not None:
                total_words_target = chapters_target * runtime.book_config.words_per_chapter
            elif words_per_chapter is not None:
                total_words_target = runtime.book_config.chapters_target * words_per_chapter

            new_config = runtime.book_config.update_fields(
                project=name,
                genre=genre,
                platform=platform,
                chapters_target=chapters_target,
                words_per_chapter=words_per_chapter,
                total_words_target=total_words_target,
            )
            runtime.book_config = new_config

            self._persist_project(project_id, runtime)
            logger.info("项目 %s 信息已更新", project_id)
            return self.get_project_status(project_id)

    # ------------------------------------------------------------------
    # 流水线控制
    # ------------------------------------------------------------------
    def start_pipeline(
        self,
        project_id: str,
        chapter_range: tuple[int, int] | list[tuple[int, int]],
        resume: bool = False,
    ) -> str:
        """启动项目流水线，提交到 Worker Pool。

        chapter_range 支持单范围 (start, end) 或多范围列表。
        """
        ranges = [chapter_range] if isinstance(chapter_range, tuple) else chapter_range
        if not ranges:
            raise ValueError("章节范围不能为空")

        with self._lock:
            if project_id not in self._projects:
                raise ValueError(f"项目不存在: {project_id}")
            runtime = self._projects[project_id]
            if runtime.status in ("writing", "auditing"):
                # 若状态为运行中但 pipeline_id / future 均已清空，说明上次流水线
                # 异常中断或进程重启后遗留的脏状态，自动重置为 pending 允许重新启动。
                if runtime.pipeline_id is None and (
                    runtime.future is None or runtime.future.done()
                ):
                    logger.warning(
                        "项目 %s 状态为 %s 但无运行中的流水线，自动重置为 pending",
                        project_id,
                        runtime.status,
                    )
                    runtime.status = "pending"
                else:
                    raise ValueError("项目正在运行中，请先暂停或停止当前流水线")

            pipeline_id = f"pipe_{datetime.utcnow():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
            runtime.pipeline_id = pipeline_id
            runtime.status = "writing"
            runtime.current_chapter = ranges[0][0]
            self._paused.discard(project_id)
            self._stopped.discard(project_id)

            future = self._executor.submit(
                self._run_pipeline, project_id, ranges, resume, pipeline_id
            )
            runtime.future = future
            self._persist_project(project_id, runtime)

            logger.info(
                "项目 %s 流水线 %s 启动，章节范围 %s",
                project_id,
                pipeline_id,
                ranges,
            )
            return pipeline_id

    def pause_pipeline(self, project_id: str) -> None:
        """暂停流水线（当前章节完成后停止）。"""
        with self._lock:
            runtime = self._projects.get(project_id)
            if not runtime:
                raise ValueError(f"项目不存在: {project_id}")
            if runtime.status in ("writing", "auditing"):
                self._paused.add(project_id)
                runtime.status = "paused"
                self._persist_project(project_id, runtime)
                logger.info("项目 %s 流水线暂停", project_id)

    def stop_pipeline(self, project_id: str) -> None:
        """停止流水线（立即取消）。"""
        with self._lock:
            runtime = self._projects.get(project_id)
            if not runtime:
                raise ValueError(f"项目不存在: {project_id}")
            self._stopped.add(project_id)
            if runtime.future and not runtime.future.done():
                runtime.future.cancel()
            runtime.status = "pending"
            runtime.pipeline_id = None
            self._persist_project(project_id, runtime)
            logger.info("项目 %s 流水线停止", project_id)

    # ------------------------------------------------------------------
    # Worker 线程中的实际执行逻辑
    # ------------------------------------------------------------------
    def _run_pipeline(
        self,
        project_id: str,
        chapter_ranges: list[tuple[int, int]],
        resume: bool,
        pipeline_id: str,
    ) -> None:
        """在 Worker 线程中执行的实际流水线。"""
        try:
            self._event_bus.emit(
                PIPELINE_START,
                {
                    "project_id": project_id,
                    "pipeline_id": pipeline_id,
                    "chapter_ranges": chapter_ranges,
                },
            )

            with self._lock:
                runtime = self._projects.get(project_id)
                if not runtime:
                    return
                writer = runtime.batch_writer

            failed_chapters: list[int] = []
            consecutive_failures = 0
            max_consecutive_failures = 3  # 防止连续失败浪费 API Token

            for chapter_range in chapter_ranges:
                start, end = chapter_range
                for num in range(start, end + 1):
                    # 检查暂停/停止
                    if project_id in self._stopped:
                        logger.info("项目 %s 被停止", project_id)
                        break
                    if project_id in self._paused:
                        logger.info("项目 %s 被暂停", project_id)
                        self._event_bus.emit(
                            PIPELINE_PAUSE,
                            {"project_id": project_id, "pipeline_id": pipeline_id, "paused_at": num},
                        )
                        break

                    # resume 模式下跳过已存在的章节
                    if resume and writer._chapter_exists(num):
                        logger.info("项目 %s 第 %d 章已存在，跳过", project_id, num)
                        with self._lock:
                            runtime.current_chapter = num
                            self._persist_project(project_id, runtime)
                        continue

                    self._event_bus.emit(
                        CHAPTER_START,
                        {
                            "project_id": project_id,
                            "pipeline_id": pipeline_id,
                            "chapter_num": num,
                        },
                    )

                    try:
                        result = writer.write_chapter(num)
                        with self._lock:
                            runtime.current_chapter = num
                            if result.success:
                                runtime.status = "writing"
                                consecutive_failures = 0
                            else:
                                failed_chapters.append(num)
                                consecutive_failures += 1
                                runtime.status = "writing"
                                logger.warning(
                                    "项目 %s 第 %d 章失败 (gate=%s)，继续后续章节",
                                    project_id, num, result.gate_level,
                                )
                                if consecutive_failures >= max_consecutive_failures:
                                    logger.error(
                                        "项目 %s 连续 %d 章失败，停止流水线",
                                        project_id, consecutive_failures,
                                    )
                                    runtime.status = "error"
                                    self._persist_project(project_id, runtime)
                                    break
                            # 记录最近一次审计结果
                            runtime.last_audit = {
                                "quality_passed": result.gate_level != "BLOCKING",
                                "sensitive_passed": len(result.audit_report.get("forbidden_words", [])) == 0,
                            }
                            # 计算追读力分数（多维度：字数 + 质量门 + 对话密度 + 节奏）
                            runtime.reader_pull_score = self._calc_reader_pull_score(result)
                            writer.update_reader_pull_score(num, runtime.reader_pull_score)
                            self._persist_project(project_id, runtime)

                        self._event_bus.emit(
                            CHAPTER_COMPLETE,
                            {
                                "project_id": project_id,
                                "pipeline_id": pipeline_id,
                                "chapter_num": num,
                                "word_count": result.word_count,
                                "gate_level": result.gate_level,
                                "success": result.success,
                            },
                        )

                        # ★ 外层 CrewAI 巡检触发
                        if self._should_trigger_outer_crew(project_id, num):
                            self._run_outer_crew_inspection(project_id, num)

                    except Exception as exc:
                        logger.exception("项目 %s 第 %d 章写作失败", project_id, num)
                        self._event_bus.emit(
                            CHAPTER_ERROR,
                            {
                                "project_id": project_id,
                                "pipeline_id": pipeline_id,
                                "chapter_num": num,
                                "error": str(exc),
                            },
                        )
                        with self._lock:
                            runtime.status = "error"
                            self._persist_project(project_id, runtime)
                        break

            # 全部完成
            with self._lock:
                if runtime.status not in ("paused", "error"):
                    # 即使有个别章节失败，只要跑完范围就算完成，避免用户手动 resume。
                    # 失败章节的草稿已保存，用户可通过日志/文件定位。
                    runtime.status = "completed"
                runtime.pipeline_id = None
                runtime.future = None
                self._persist_project(project_id, runtime)

            self._event_bus.emit(
                PIPELINE_COMPLETE,
                {
                    "project_id": project_id,
                    "pipeline_id": pipeline_id,
                    "final_status": runtime.status,
                    "last_chapter": runtime.current_chapter,
                    "failed_chapters": failed_chapters,
                },
            )

        except Exception:
            logger.exception("项目 %s 流水线异常终止", project_id)
            with self._lock:
                runtime = self._projects.get(project_id)
                if runtime:
                    # 保护已完成的流水线不被 event handler 或 persist 异常覆盖
                    if runtime.status not in ("completed", "paused"):
                        runtime.status = "error"
                    runtime.pipeline_id = None
                    runtime.future = None
                    self._persist_project(project_id, runtime)

    # ------------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------------
    def _get_completed_chapters(self, runtime: ProjectRuntime) -> int:
        """从章节历史表计算实际已完成并落盘的章节数。

        current_chapter 只表示当前正在处理的章节，可能仍在写作中，
        因此不能把它当作已完成计数。只有 chapter_history 里真实存在的
        章节才计入已完成。
        """
        try:
            db_path = Path(runtime.book_config.base_path) / "world_state.db"
            if not db_path.exists():
                return 0
            with sqlite3.connect(str(db_path)) as conn:
                row = conn.execute(
                    "SELECT MAX(chapter) FROM chapter_history WHERE project_id = ?",
                    (runtime.project_id,),
                ).fetchone()
                history_max = row[0] or 0
        except Exception:
            history_max = 0
        return history_max

    def get_project_status(self, project_id: str) -> dict[str, Any] | None:
        """获取单个项目状态。

        优先从内存读取，若内存中 current_chapter 为 0（可能由 cli.py 直接写入数据库），
        则从数据库 projects 表读取最新的 current_chapter 和 status。
        completed_chapters 会基于章节历史表再校准一次，确保项目卡片展示的是真实进度。
        """
        with self._lock:
            runtime = self._projects.get(project_id)
            if not runtime:
                return None

            status = runtime.status
            current_chapter = runtime.current_chapter

            # 若内存状态滞后（cli.py 直接运行时绕过 orchestrator），从数据库补齐
            if current_chapter == 0 and status in ("pending", "initialized", ""):
                try:
                    with sqlite3.connect(str(self._global_db_path)) as conn:
                        row = conn.execute(
                            "SELECT status, current_chapter FROM projects WHERE project_id = ?",
                            (project_id,),
                        ).fetchone()
                        if row:
                            db_status, db_chapter = row[0], row[1] or 0
                            if db_chapter > 0:
                                current_chapter = db_chapter
                                status = db_status
                except Exception:
                    pass

            completed_chapters = self._get_completed_chapters(runtime)
            return {
                "project_id": runtime.project_id,
                "name": runtime.book_config.project,
                "genre": runtime.book_config.genre,
                "platform": runtime.book_config.platform,
                "status": status,
                "current_chapter": current_chapter,
                "completed_chapters": completed_chapters,
                "total_chapters": runtime.book_config.chapters_target,
                "words_per_chapter": runtime.book_config.words_per_chapter,
                "total_words_target": runtime.book_config.total_words_target,
                "pipeline_id": runtime.pipeline_id,
                "base_path": str(runtime.book_config.base_path),
                "llm": runtime.book_config.llm,
                "last_audit": runtime.last_audit,
                "reader_pull_score": runtime.reader_pull_score,
                "created_at": runtime.created_at,
            }

    def get_all_projects(self) -> list[dict[str, Any]]:
        """获取所有项目列表。"""
        with self._lock:
            return [
                {
                    "project_id": p.project_id,
                    "name": p.book_config.project,
                    "genre": p.book_config.genre,
                    "platform": p.book_config.platform,
                    "status": p.status,
                    "current_chapter": p.current_chapter,
                    "completed_chapters": self._get_completed_chapters(p),
                    "created_at": p.created_at,
                    "total_chapters": p.book_config.chapters_target,
                }
                for p in self._projects.values()
            ]

    def get_global_stats(self) -> dict[str, Any]:
        """获取全局统计。"""
        with self._lock:
            active = sum(
                1 for p in self._projects.values() if p.status in ("writing", "auditing")
            )
            return {
                "total_projects": len(self._projects),
                "active_projects": active,
                "max_workers": self.max_workers,
                "pending_projects": sum(
                    1 for p in self._projects.values() if p.status == "pending"
                ),
                "completed_projects": sum(
                    1 for p in self._projects.values() if p.status == "completed"
                ),
                "health": "healthy" if active < self.max_workers else "degraded",
            }

    def get_state_manager(self, project_id: str) -> StateManager | None:
        """获取项目的 StateManager 实例。"""
        with self._lock:
            runtime = self._projects.get(project_id)
            return runtime.state_manager if runtime else None

    # ------------------------------------------------------------------
    # 事件总线封装
    # ------------------------------------------------------------------
    def _setup_runtime_log_handler(self) -> None:
        """将 EventBus 事件同步写入项目状态库的 runtime_logs，供前端日志面板展示。"""

        def _handler(event_type: str, payload: dict[str, Any]) -> None:
            project_id = payload.get("project_id")
            if not project_id:
                return
            runtime = self._projects.get(project_id)
            if not runtime or not runtime.state_manager:
                return
            chapter_num = payload.get("chapter_num")
            detail = payload.get("detail", "")
            message = detail or event_type
            if "pipeline_id" in payload:
                message += f" (pipeline={payload['pipeline_id']})"
            runtime.state_manager.log_runtime(
                level="INFO",
                agent=event_type,
                chapter_num=chapter_num,
                message=message,
                metadata=payload,
            )

        for event_type in EVENT_TYPES:
            def _make_handler(et: str = event_type) -> Callable[[str, dict[str, Any]], None]:
                return lambda _event_type, payload: _handler(et, payload)
            self._event_bus.on(event_type, _make_handler())

    def on_event(self, handler: Callable[[str, dict[str, Any]], None]) -> None:
        """注册全局事件处理器（供 WebSocket 等使用）。"""
        for event_type in EVENT_TYPES:
            self._event_bus.on(event_type, handler)
        self._event_handlers.append(handler)

    def remove_event_handler(self, handler: Callable[[str, dict[str, Any]], None]) -> None:
        """注销全局事件处理器。"""
        for event_type in EVENT_TYPES:
            self._event_bus.off(event_type, handler)
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """直接发布事件（供外部模块使用）。"""
        self._event_bus.emit(event_type, payload)

    # ------------------------------------------------------------------
    # 外层 CrewAI 调度
    # ------------------------------------------------------------------
    def _should_trigger_outer_crew(self, project_id: str, chapter_num: int) -> bool:
        """判断当前章节是否需要触发外层 CrewAI 巡检。"""
        with self._lock:
            runtime = self._projects.get(project_id)
            if not runtime or not runtime.outer_crew_runner:
                return False

        cfg = runtime.book_config.outer_crew
        if not cfg.get("enabled", True):
            return False

        interval = cfg.get("inspection_interval", 5)
        return chapter_num > 1 and chapter_num % interval == 0

    def _run_outer_crew_inspection(self, project_id: str, chapter_num: int) -> None:
        """执行外层 CrewAI 巡检（失败隔离，不阻塞写作）。"""
        with self._lock:
            runtime = self._projects.get(project_id)
            if not runtime or not runtime.outer_crew_runner:
                return

        runner = runtime.outer_crew_runner
        cfg = runtime.book_config.outer_crew

        self._event_bus.emit(
            OUTER_CREW_INSPECTION_START,
            {"project_id": project_id, "chapter_num": chapter_num},
        )

        try:
            # 1. Novel Architect（每 inspection_interval 章）
            arch_report = runner.run_architecture_review(chapter_num)
            runner.save_report(
                chapter_num, "novel_architect", arch_report.raw_report,
                {"health_grade": arch_report.health_grade, "deviations": len(arch_report.deviations)}
            )
            logger.info(
                "[外层] %s Novel Architect 完成，健康度=%s",
                project_id, arch_report.health_grade or "N/A"
            )

            # 2. Continuity Inspector（每 inspection_interval 章）
            conti_report = runner.run_continuity_check(chapter_num)
            runner.save_report(
                chapter_num, "continuity_inspector", conti_report.raw_report,
                {"issues": len(conti_report.issues), "critical": conti_report.has_critical}
            )
            logger.info(
                "[外层] %s Continuity Inspector 完成，矛盾=%d，致命=%s",
                project_id, len(conti_report.issues), conti_report.has_critical
            )

            # 3. 如果有致命矛盾 → Retcon Manager
            if conti_report.has_critical and cfg.get("auto_apply", True):
                self._event_bus.emit(
                    OUTER_CREW_RETCON_TRIGGERED,
                    {
                        "project_id": project_id,
                        "chapter_num": chapter_num,
                        "issue_count": len(conti_report.issues),
                    },
                )
                retcon_plan = runner.run_retcon_fix(conti_report.issues, chapter_num)
                runner.save_report(
                    chapter_num, "retcon_manager", retcon_plan.raw_report,
                    {"actions": len(retcon_plan.actions)}
                )
                # 提取修复文案注入后续章节
                with self._lock:
                    for action in retcon_plan.actions:
                        if action.fix_text:
                            runtime.pending_retcons.append(action.fix_text)
                    # 限制保留数量
                    max_retcons = cfg.get("max_retcons", 3)
                    runtime.pending_retcons = runtime.pending_retcons[-max_retcons:]
                logger.info(
                    "[外层] %s Retcon Manager 完成，修复方案=%d",
                    project_id, len(retcon_plan.actions)
                )

            # 4. Pacing Analyst（每 pacing_interval 章）
            pacing_interval = cfg.get("pacing_interval", 10)
            if chapter_num % pacing_interval == 0:
                pacing_report = runner.run_pacing_analysis(chapter_num)
                runner.save_report(
                    chapter_num, "pacing_analyst", pacing_report.raw_report,
                    {"diagnosis": pacing_report.rhythm_diagnosis}
                )
                # 提取情绪目标注入后续章节
                with self._lock:
                    runtime.emotion_targets = [
                        {"chapter": chapter_num + i + 1, "suggestion": s}
                        for i, s in enumerate(pacing_report.next_10_suggestions[:5])
                    ]
                logger.info(
                    "[外层] %s Pacing Analyst 完成，诊断=%s",
                    project_id, pacing_report.rhythm_diagnosis or "N/A"
                )

            # 5. 将反馈注入 BatchWriter 后续章节上下文
            if cfg.get("auto_apply", True):
                with self._lock:
                    priorities = arch_report.next_5_priorities if arch_report.next_5_priorities else []
                    runtime.batch_writer.set_outer_crew_feedback(
                        retcons=runtime.pending_retcons,
                        emotion_targets=runtime.emotion_targets,
                        priorities=priorities,
                    )

            # 6. 记录报告摘要
            if arch_report.next_5_priorities:
                with self._lock:
                    runtime.outer_crew_reports.append({
                        "chapter": chapter_num,
                        "type": "architecture",
                        "priorities": arch_report.next_5_priorities,
                    })

            self._event_bus.emit(
                OUTER_CREW_INSPECTION_COMPLETE,
                {
                    "project_id": project_id,
                    "chapter_num": chapter_num,
                    "arch_grade": arch_report.health_grade,
                    "conti_issues": len(conti_report.issues),
                    "has_critical": conti_report.has_critical,
                },
            )

        except Exception as exc:
            logger.exception("[外层] %s 巡检失败: %s", project_id, exc)
            # 失败不阻塞，继续写作

    # ------------------------------------------------------------------
    # 追读力评分算法
    # ------------------------------------------------------------------
    @staticmethod
    def _calc_reader_pull_score(result: Any) -> float:
        """多维度追读力评分算法。

        维度:
            - 基础分: 3.0
            - 字数得分: min(word_count / 1000, 3.0)
            - 质量门得分: PASS=1.5, WARN=0.8, BLOCKING=0
            - 对话密度: 引号段落占比 × 2.0，上限 2.0
            - 节奏得分: 一次通过 1.0，每次重试 -0.3
        """
        if not result.success or result.gate_level == "BLOCKING":
            return 0.0

        score = 3.0

        # 字数得分
        score += min(result.word_count / 1000, 3.0)

        # 质量门得分
        gate_bonus = {"PASS": 1.5, "WARN": 0.8, "BLOCKING": 0.0}
        score += gate_bonus.get(result.gate_level, 0.0)

        # 对话密度得分
        content = result.final_content or ""
        lines = content.split("\n")
        dialogue_lines = sum(1 for line in lines if line.strip().startswith(("「", "\"", "'", "【")))
        dialogue_ratio = dialogue_lines / max(len(lines), 1)
        score += min(dialogue_ratio * 2.0, 2.0)

        # 节奏得分（一次通过奖励，重试扣分）
        rhythm = 1.0 - (result.attempts - 1) * 0.3
        score += max(rhythm, 0.0)

        return round(min(score, 10.0), 1)
