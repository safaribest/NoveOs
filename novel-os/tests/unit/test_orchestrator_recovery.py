"""Orchestrator 错误恢复单元测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.orchestrator import Orchestrator, ProjectRuntime
from core.writing.output import WriteResult


class FakeBatchWriter:
    """用于 Orchestrator 测试的伪 BatchWriter。"""

    def __init__(self, results: dict[int, WriteResult]) -> None:
        self._results = results
        self._calls: list[int] = []

    def write_chapter(self, num: int) -> WriteResult:
        self._calls.append(num)
        return self._results.get(num, WriteResult(
            chapter_num=num,
            success=True,
            final_content=f"第{num}章",
            word_count=2000,
            gate_level="PASS",
            attempts=1,
        ))

    def _chapter_exists(self, num: int) -> bool:
        return False

    def update_reader_pull_score(self, chapter_num: int, score: float) -> None:
        """更新章节 reader pull score（测试桩）。"""
        return


def _make_runtime(project_id: str, writer: FakeBatchWriter) -> ProjectRuntime:
    """构造一个最小可用的 ProjectRuntime。"""
    runtime = ProjectRuntime(
        project_id=project_id,
        book_config=MagicMock(),
        state_manager=MagicMock(),
        batch_writer=writer,  # type: ignore[arg-type]
    )
    runtime.book_config.project = "test"
    runtime.book_config.genre = "test"
    runtime.book_config.platform = "test"
    runtime.book_config.base_path = Path(tempfile.mkdtemp())
    runtime.book_config.chapters_target = 5
    runtime.book_config.llm = {}
    runtime.book_config.outer_crew = {"enabled": False}
    return runtime


class TestOrchestratorRecovery:
    """测试 Orchestrator 在章节失败时的恢复行为。"""

    @pytest.fixture(autouse=True)
    def _patch_persist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """避免测试写入真实 SQLite 数据库。"""
        monkeypatch.setattr(Orchestrator, "_persist_project", lambda self, pid, info: None)

    def test_continue_on_single_chapter_failure(self) -> None:
        """单章验证失败不应停止整个流水线。"""
        orch = Orchestrator(max_workers=1)
        results = {
            1: WriteResult(
                chapter_num=1,
                success=False,
                final_content="draft",
                word_count=1800,
                gate_level="BLOCKING",
                attempts=3,
            ),
        }
        writer = FakeBatchWriter(results)
        runtime = _make_runtime("proj_1", writer)
        orch._projects["proj_1"] = runtime

        orch.start_pipeline("proj_1", (1, 3), resume=False)
        future = runtime.future
        assert future is not None
        future.result(timeout=5)
        orch._executor.shutdown(wait=False)

        assert writer._calls == [1, 2, 3]
        assert runtime.current_chapter == 3
        # 有个别章节失败，但跑完范围，状态应为 completed
        assert runtime.status == "completed"

    def test_stop_on_consecutive_failures(self) -> None:
        """连续多章失败应停止流水线，防止无限浪费 API。"""
        orch = Orchestrator(max_workers=1)
        results = {
            1: WriteResult(
                chapter_num=1,
                success=False,
                final_content="draft1",
                word_count=1800,
                gate_level="BLOCKING",
                attempts=3,
            ),
            2: WriteResult(
                chapter_num=2,
                success=False,
                final_content="draft2",
                word_count=1800,
                gate_level="BLOCKING",
                attempts=3,
            ),
            3: WriteResult(
                chapter_num=3,
                success=False,
                final_content="draft3",
                word_count=1800,
                gate_level="BLOCKING",
                attempts=3,
            ),
        }
        writer = FakeBatchWriter(results)
        runtime = _make_runtime("proj_2", writer)
        orch._projects["proj_2"] = runtime

        orch.start_pipeline("proj_2", (1, 5), resume=False)
        future = runtime.future
        assert future is not None
        future.result(timeout=5)
        orch._executor.shutdown(wait=False)

        # 连续 3 章失败后停止
        assert writer._calls == [1, 2, 3]
        assert runtime.status == "error"

    def test_reset_consecutive_failures_after_success(self) -> None:
        """成功一章后应重置连续失败计数。"""
        orch = Orchestrator(max_workers=1)
        results = {
            1: WriteResult(
                chapter_num=1,
                success=False,
                final_content="draft1",
                word_count=1800,
                gate_level="BLOCKING",
                attempts=3,
            ),
            2: WriteResult(
                chapter_num=2,
                success=False,
                final_content="draft2",
                word_count=1800,
                gate_level="BLOCKING",
                attempts=3,
            ),
        }
        writer = FakeBatchWriter(results)
        runtime = _make_runtime("proj_3", writer)
        orch._projects["proj_3"] = runtime

        orch.start_pipeline("proj_3", (1, 5), resume=False)
        future = runtime.future
        assert future is not None
        future.result(timeout=5)
        orch._executor.shutdown(wait=False)

        # 第 1、2 章失败，第 3 章成功重置计数，第 4、5 章也成功
        assert writer._calls == [1, 2, 3, 4, 5]
        assert runtime.status == "completed"
