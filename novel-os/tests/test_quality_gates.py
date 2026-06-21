"""质量门单元测试。"""
from __future__ import annotations

import pytest

from core.quality_gates import QualityGates, GateResult


class TestQualityGates:
    """测试QualityGates的审计逻辑。"""

    @pytest.fixture
    def gates(self) -> QualityGates:
        return QualityGates(min_words=1000, max_words=2000)

    def test_pass(self, gates: QualityGates) -> None:
        """所有指标通过。"""
        report = {
            "word_count": 1500,
            "ta_density": 0.05,
            "redline_words": [],
            "forbidden_words": [],
            "broken_sentences": [],
        }
        result = gates.audit("正文", report)
        assert result.level == "PASS"
        assert result.passed is True

    def test_block_word_count_low(self, gates: QualityGates) -> None:
        """字数不足BLOCKING。"""
        report = {
            "word_count": 500,
            "ta_density": 0.05,
            "redline_words": [],
            "forbidden_words": [],
        }
        result = gates.audit("正文", report)
        assert result.level == "BLOCKING"
        assert "字数不足" in result.reasons[0]

    def test_block_word_count_high(self, gates: QualityGates) -> None:
        """字数超标BLOCKING。"""
        report = {
            "word_count": 3000,
            "ta_density": 0.05,
            "redline_words": [],
            "forbidden_words": [],
        }
        result = gates.audit("正文", report)
        assert result.level == "BLOCKING"
        assert "字数超标" in result.reasons[0]

    def test_block_redline(self, gates: QualityGates) -> None:
        """红线词BLOCKING。"""
        report = {
            "word_count": 1500,
            "ta_density": 0.05,
            "redline_words": ["敏感词"],
            "forbidden_words": [],
        }
        result = gates.audit("正文", report)
        assert result.level == "BLOCKING"
        assert "红线词" in result.reasons[0]

    def test_block_ta_density(self, gates: QualityGates) -> None:
        """他字密度超标BLOCKING。"""
        report = {
            "word_count": 1500,
            "ta_density": 0.20,
            "redline_words": [],
            "forbidden_words": [],
        }
        result = gates.audit("正文", report)
        assert result.level == "BLOCKING"
        assert "他字密度" in result.reasons[0]

    def test_warn_broken_sentences(self, gates: QualityGates) -> None:
        """句式破坏WARN。"""
        report = {
            "word_count": 1500,
            "ta_density": 0.05,
            "redline_words": [],
            "forbidden_words": [],
            "broken_sentences": ["破碎句1"],
        }
        result = gates.audit("正文", report)
        assert result.level == "WARN"
        assert result.passed is True

    def test_truncate(self, gates: QualityGates) -> None:
        """截断超长文本。"""
        text = "这是一个很长的句子。" * 200
        truncated = gates.truncate_if_needed(text, 100)
        assert len(truncated) <= 100 + 30  # 允许截断标记
        assert "[本章因超字数截断" in truncated

    def test_should_retry_blocking(self, gates: QualityGates) -> None:
        """BLOCKING应该重试。"""
        result = GateResult(passed=False, level="BLOCKING", reasons=[])
        assert gates.should_retry(result, attempt=1, max_retries=3) is True

    def test_should_not_retry_pass(self, gates: QualityGates) -> None:
        """PASS不重试。"""
        result = GateResult(passed=True, level="PASS", reasons=[])
        assert gates.should_retry(result, attempt=1, max_retries=3) is False

    def test_should_not_retry_max(self, gates: QualityGates) -> None:
        """达到最大重试次数不重试。"""
        result = GateResult(passed=False, level="BLOCKING", reasons=[])
        assert gates.should_retry(result, attempt=3, max_retries=3) is False

    def test_build_retry_prompt(self, gates: QualityGates) -> None:
        """重试prompt包含反馈信息。"""
        result = GateResult(
            passed=False, level="BLOCKING",
            reasons=["字数不足"],
            metrics={"word_count": 500},
        )
        prompt = gates.build_retry_prompt("原始prompt", result)
        assert "字数不足" in prompt
        assert "当前字数: 500" in prompt
