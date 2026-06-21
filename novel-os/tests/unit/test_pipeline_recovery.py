"""WritingPipeline 错误恢复单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.chapter_validator import ValidationIssue, ValidationResult
from core.writing.context import ChapterContext
from core.writing.pipeline import PipelineConfig, WritingPipeline


class MockValidator:
    """可编程的伪 ChapterValidator。"""

    def __init__(self, responses: list[ValidationResult]) -> None:
        self._responses = responses
        self._call_idx = 0

    def validate(self, text: str, context: dict | None = None) -> ValidationResult:
        result = self._responses[self._call_idx]
        self._call_idx += 1
        return result

    def build_retry_feedback(self, result: ValidationResult) -> str:
        return ""


def _make_context() -> ChapterContext:
    ctx = ChapterContext(
        chapter_num=1,
        project_id="test",
        book_config=MagicMock(),
        llm=MagicMock(),
        state=MagicMock(),
    )
    ctx.book_config.words_per_chapter = 2200
    ctx.book_config.words_tolerance = 400
    return ctx


class TestPipelineRecovery:
    """测试 WritingPipeline 对非致命 BLOCK 问题的自动恢复。"""

    def test_merge_corrections(self) -> None:
        """修正指令应合并而非覆盖。"""
        old = {"scene_writer": "已有指令", "global": "全局指令"}
        new = {"scene_writer": "新增指令", "hook_engineer": "钩子指令"}
        merged = WritingPipeline._merge_corrections(old, new)

        assert "已有指令" in merged["scene_writer"]
        assert "新增指令" in merged["scene_writer"]
        assert merged["global"] == "全局指令"
        assert merged["hook_engineer"] == "钩子指令"

    def test_overlength_and_other_block_merges_corrections(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """字数超标截断后仍有术语缺失时，应合并修正指令并继续重试。"""
        # 每次 attempt 会调用 2 次 validate：quick_check + full validation
        # 截断分支内还会再调用 1 次 validate
        responses = [
            # attempt 1 quick_check
            ValidationResult(
                verdict="BLOCK",
                issues=[
                    ValidationIssue("BLOCK", "字数", "字数超标: 3000 > 2600", 3000),
                    ValidationIssue("BLOCK", "术语", "强制术语缺失: '世界观术语'"),
                ],
                metrics={"word_count": 3000},
            ),
            # attempt 1 full validation
            ValidationResult(
                verdict="BLOCK",
                issues=[
                    ValidationIssue("BLOCK", "字数", "字数超标: 3000 > 2600", 3000),
                    ValidationIssue("BLOCK", "术语", "强制术语缺失: '世界观术语'"),
                ],
                metrics={"word_count": 3000},
            ),
            # after truncate re-validation
            ValidationResult(
                verdict="BLOCK",
                issues=[
                    ValidationIssue("BLOCK", "术语", "强制术语缺失: '世界观术语'"),
                ],
                metrics={"word_count": 2400},
            ),
            # attempt 2 quick_check
            ValidationResult(
                verdict="BLOCK",
                issues=[
                    ValidationIssue("BLOCK", "术语", "强制术语缺失: '世界观术语'"),
                ],
                metrics={"word_count": 2400},
            ),
            # attempt 2 full validation -> PASS
            ValidationResult(
                verdict="PASS",
                issues=[],
                metrics={"word_count": 2400},
            ),
        ]
        validator = MockValidator(responses)
        pipeline = WritingPipeline(steps=[], validator=validator, config=PipelineConfig(max_retries=3, enable_polish=False))

        monkeypatch.setattr(
            pipeline, "_truncate_if_overlength", lambda ctx, content: content[:50]
        )

        call_count = 0
        captured_corrections: dict[str, str] = {}

        def fake_run_steps(ctx: ChapterContext, corrections: dict[str, str]) -> str:
            nonlocal call_count, captured_corrections
            call_count += 1
            captured_corrections = corrections.copy()
            return "正文内容" * 100

        monkeypatch.setattr(pipeline, "_run_steps", fake_run_steps)

        ctx = _make_context()
        result = pipeline.execute(ctx)

        assert result.success is True
        assert call_count == 2
        # 第二次进入 _run_steps 时，修正指令应已累积术语补全指令
        assert "世界观术语" in captured_corrections.get("scene_writer", "")

    def test_shortage_and_other_block_merges_corrections(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """字数不足扩写后仍有其他阻塞问题时，应合并修正指令并继续重试。"""
        responses = [
            # attempt 1 quick_check
            ValidationResult(
                verdict="BLOCK",
                issues=[
                    ValidationIssue("BLOCK", "字数", "字数不足: 1500 < 1900", 1500),
                    ValidationIssue("BLOCK", "术语", "强制术语缺失: '核心术语'"),
                ],
                metrics={"word_count": 1500},
            ),
            # attempt 1 full validation
            ValidationResult(
                verdict="BLOCK",
                issues=[
                    ValidationIssue("BLOCK", "字数", "字数不足: 1500 < 1900", 1500),
                    ValidationIssue("BLOCK", "术语", "强制术语缺失: '核心术语'"),
                ],
                metrics={"word_count": 1500},
            ),
            # after first expand re-validation
            ValidationResult(
                verdict="BLOCK",
                issues=[
                    ValidationIssue("BLOCK", "术语", "强制术语缺失: '核心术语'"),
                ],
                metrics={"word_count": 2100},
            ),
            # attempt 2 quick_check
            ValidationResult(
                verdict="BLOCK",
                issues=[
                    ValidationIssue("BLOCK", "术语", "强制术语缺失: '核心术语'"),
                ],
                metrics={"word_count": 2100},
            ),
            # attempt 2 full validation -> PASS
            ValidationResult(
                verdict="PASS",
                issues=[],
                metrics={"word_count": 2100},
            ),
        ]
        validator = MockValidator(responses)
        pipeline = WritingPipeline(steps=[], validator=validator, config=PipelineConfig(max_retries=3, enable_polish=False))

        monkeypatch.setattr(
            pipeline,
            "_try_expand",
            lambda ctx, content, validation=None, short_by=None: content + "扩写" * 1000,
        )

        call_count = 0
        captured_corrections: dict[str, str] = {}

        def fake_run_steps(ctx: ChapterContext, corrections: dict[str, str]) -> str:
            nonlocal call_count, captured_corrections
            call_count += 1
            captured_corrections = corrections.copy()
            return "正文内容" * 100

        monkeypatch.setattr(pipeline, "_run_steps", fake_run_steps)

        ctx = _make_context()
        result = pipeline.execute(ctx)

        assert result.success is True
        assert call_count == 2
        assert "核心术语" in captured_corrections.get("scene_writer", "")

    def test_max_retries_enforced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """超过 max_retries 后应返回失败，防止无限循环。"""
        responses = [
            ValidationResult(
                verdict="BLOCK",
                issues=[ValidationIssue("BLOCK", "术语", "强制术语缺失: '术语'")],
                metrics={"word_count": 2200},
            )
        ] * 10
        validator = MockValidator(responses)
        pipeline = WritingPipeline(steps=[], validator=validator, config=PipelineConfig(max_retries=3, enable_polish=False))

        def fake_run_steps(ctx: ChapterContext, corrections: dict[str, str]) -> str:
            return "正文"

        monkeypatch.setattr(pipeline, "_run_steps", fake_run_steps)

        ctx = _make_context()
        result = pipeline.execute(ctx)

        assert result.success is False
        assert result.attempts == 3
