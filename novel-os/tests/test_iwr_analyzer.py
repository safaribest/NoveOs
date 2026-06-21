"""IWR分析器单元测试。"""
from __future__ import annotations

import pytest

from core.iwr_analyzer import analyze_chapter


class TestIWRAnalyzer:
    """测试analyze_chapter的核心指标计算。"""

    def test_empty_text(self) -> None:
        """空文本应返回默认值。"""
        result = analyze_chapter("")
        assert result["word_count"] == 0
        assert result["iwr_score"] == 0.0

    def test_basic_metrics(self) -> None:
        """基础指标计算正确性。"""
        text = "张三问道：'你怎么来了？'李四终于明白了。'"
        result = analyze_chapter(text)
        assert result["word_count"] > 0
        assert result["sentence_length"] > 0
        assert 0 <= result["dialogue_ratio"] <= 1
        assert result["questions_count"] >= 1  # "怎么"
        assert result["answers_count"] >= 1    # "终于"在_REVEAL_PATTERNS中

    def test_iwr_calculation(self) -> None:
        """IWR = 问题数/答案数。"""
        # 高IWR：问题多答案少
        text = "难道这就是真相？究竟发生了什么？为什么他会在这里？"
        result = analyze_chapter(text)
        assert result["questions_count"] >= 3
        assert result["answers_count"] == 0
        assert result["iwr_score"] >= 5

    def test_low_iwr(self) -> None:
        """低IWR：答案多问题少。"""
        text = "原来如此。终于明白了。果然是这样。"
        result = analyze_chapter(text)
        assert result["answers_count"] >= 3
        assert result["questions_count"] == 0
        assert result["iwr_score"] == 0.0

    def test_hook_ending(self) -> None:
        """钩子结尾检测。"""
        text = "故事继续。他正要开口，忽然——"
        result = analyze_chapter(text)
        assert result["hook_ending"] == 1

    def test_no_hook_ending(self) -> None:
        """非钩子结尾。"""
        text = "故事结束了。大家都很高兴。"
        result = analyze_chapter(text)
        assert result["hook_ending"] == 0

    def test_ta_density(self) -> None:
        """他字密度计算。"""
        text = "他走了，她也走了，它还在。"
        result = analyze_chapter(text)
        assert result["ta_density"] > 0
        assert result["ta_density"] < 1

    def test_oscillations(self) -> None:
        """微张力振荡检测。"""
        # 多段落，每段张力不同，产生振荡
        text = (
            "张三跑了起来。\n\n"
            "李四追了上去！\n\n"
            "张三躲开了。\n\n"
            "李四又追！冲了过去！"
        )
        result = analyze_chapter(text)
        assert result["oscillations"] >= 1
