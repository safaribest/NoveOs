"""平台适配度评分器单元测试。"""
from __future__ import annotations

import pytest

from core.platform_scorer import (
    score_chapter_length,
    score_chapter_length_cv,
    score_dialogue_ratio,
    score_platform_adaptation,
    score_sentence_length,
    compute_genre_dna_match,
)


class TestPlatformScorer:
    """测试平台适配度评分。"""

    def test_chapter_length_cv_perfect(self) -> None:
        """CV<10%得满分25。"""
        scores = [2000, 2050, 1980, 2020]
        assert score_chapter_length_cv(scores) == 25.0

    def test_chapter_length_cv_poor(self) -> None:
        """CV>35%得低分。"""
        scores = [500, 5000, 1000, 8000]
        assert score_chapter_length_cv(scores) == 5.0

    def test_chapter_length_optimal(self) -> None:
        """1500-2500字得满分20。"""
        assert score_chapter_length(2000) == 20.0

    def test_chapter_length_too_short(self) -> None:
        """<1000字得低分。"""
        assert score_chapter_length(500) == 3.0

    def test_dialogue_ratio_optimal(self) -> None:
        """25-45%得满分15。"""
        assert score_dialogue_ratio(0.35) == 15.0

    def test_dialogue_ratio_poor(self) -> None:
        """对话太少得低分。"""
        assert score_dialogue_ratio(0.05) == 5.0

    def test_sentence_length_optimal(self) -> None:
        """18-28字得满分15。"""
        assert score_sentence_length(22) == 15.0

    def test_platform_adaptation(self) -> None:
        """整体平台评分。"""
        metrics = {
            "word_count": 2000,
            "sentence_length": 22,
            "dialogue_ratio": 0.35,
            "ta_density": 0.08,
            "iwr_score": 3.0,
            "hook_ending": 1,
            "oscillations": 5,
        }
        result = score_platform_adaptation(metrics, [2000, 2100, 1950])
        assert result["platform_score"] > 0
        assert result["platform_grade"] in ("S", "A", "B", "C")
        assert "breakdown" in result

    def test_dna_match_perfect(self) -> None:
        """完全匹配DNA。"""
        metrics = {
            "sentence_length": 23,
            "dialogue_ratio": 0.40,
            "ta_density": 0.02,
            "iwr_score": 2.5,
        }
        dna = {
            "sent": 23, "dialogue": 0.40, "ta_max": 0.02, "iwr": 2.5,
        }
        match = compute_genre_dna_match(metrics, dna)
        assert match >= 90

    def test_dna_match_poor(self) -> None:
        """严重偏离DNA。"""
        metrics = {
            "sentence_length": 50,
            "dialogue_ratio": 0.05,
            "ta_density": 0.20,
            "iwr_score": 0.5,
        }
        dna = {
            "sent": 23, "dialogue": 0.40, "ta_max": 0.02, "iwr": 2.5,
        }
        match = compute_genre_dna_match(metrics, dna)
        assert match < 50
