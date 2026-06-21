"""内容指标计算单元测试。"""
from __future__ import annotations

import pytest

from core.content.metrics import count_chinese_chars, ta_density, iwr_score


def test_count_chinese_chars() -> None:
    assert count_chinese_chars("测试中文字数") == 6
    assert count_chinese_chars("hello世界") == 2


def test_ta_density() -> None:
    text = "他来了，她走了，它跑了。"
    assert ta_density(text) == 3 / 9  # 3个他/她/它，9个中文字


def test_iwr_score() -> None:
    text = "测试文本" * 50 + "究竟发生了什么？"
    score = iwr_score(text)
    assert score > 0
