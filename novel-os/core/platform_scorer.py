"""平台适配度评分器 —— 6维度100分制评分模型。

基于 RAG 全库分析结论：
- 平台适配分 = 章字数CV(25) + 章长(20) + 对话密度(15) + 句长(15) + 他密度(15) + 悬念节奏(10)
- S级(≥85): 平台最优适配
- A级(70-84): 良好适配
- B级(55-69): 可接受
- C级(<55): 需要优化
"""
from __future__ import annotations

import math
import statistics
from typing import Any


def score_chapter_length_cv(chapter_word_counts: list[int]) -> float:
    """章字数一致性评分（满分25）。

    CV = 标准差 / 均值 * 100
    CV<10%:25 / <20%:20 / <35%:12 / else:5
    """
    if len(chapter_word_counts) < 2:
        return 20.0  # 数据不足，给默认良好
    mean = statistics.mean(chapter_word_counts)
    if mean == 0:
        return 5.0
    try:
        stdev = statistics.stdev(chapter_word_counts)
    except statistics.StatisticsError:
        return 25.0
    cv = stdev / mean * 100
    if cv < 10:
        return 25.0
    elif cv < 20:
        return 20.0
    elif cv < 35:
        return 12.0
    else:
        return 5.0


def score_chapter_length(word_count: int, target: int = 2000) -> float:
    """章长评分（满分20）。

    1500-2500字:20 / 2500-3500:15 / >=1000:8 / else:3
    """
    if 1500 <= word_count <= 2500:
        return 20.0
    elif 2500 < word_count <= 3500:
        return 15.0
    elif 1000 <= word_count < 1500:
        return 8.0
    else:
        return 3.0


def score_dialogue_ratio(ratio: float) -> float:
    """对话密度评分（满分15）。

    25-45%:15 / 15-55%:10 / else:5
    """
    if 0.25 <= ratio <= 0.45:
        return 15.0
    elif 0.15 <= ratio <= 0.55:
        return 10.0
    else:
        return 5.0


def score_sentence_length(sent_len: float, target: int = 24) -> float:
    """句长评分（满分15）。

    18-28字:15 / 15-35:10 / else:5
    """
    if 18 <= sent_len <= 28:
        return 15.0
    elif 15 <= sent_len <= 35:
        return 10.0
    else:
        return 5.0


def score_ta_density(ta_density: float) -> float:
    """他密度评分（满分15）。

    <1.0%:15 / <2.0%:12 / <3.0%:7 / else:3
    """
    if ta_density < 0.01:
        return 15.0
    elif ta_density < 0.02:
        return 12.0
    elif ta_density < 0.03:
        return 7.0
    else:
        return 3.0


def score_suspense_rhythm(hook_ending: int, iwr: float) -> float:
    """悬念节奏评分（满分10）。

    钩子结尾 + IWR>=2.0:10
    IWR>=1.5:7
    else:3
    """
    if hook_ending and iwr >= 2.0:
        return 10.0
    elif iwr >= 1.5:
        return 7.0
    else:
        return 3.0


def grade_from_score(score: float) -> str:
    """分数转等级。"""
    if score >= 85:
        return "S"
    elif score >= 70:
        return "A"
    elif score >= 55:
        return "B"
    else:
        return "C"


def score_platform_adaptation(
    chapter_metrics: dict[str, Any],
    chapter_history_word_counts: list[int] | None = None,
) -> dict[str, Any]:
    """计算单章平台适配度评分。

    输入:
    - chapter_metrics: analyze_chapter 返回的指标字典
    - chapter_history_word_counts: 历史章节字数列表（用于计算CV）

    返回:
    - platform_score: 总分(0-100)
    - platform_grade: S/A/B/C
    - breakdown: 6维度分项得分
    """
    word_count = chapter_metrics.get("word_count", 0)
    dialogue_ratio = chapter_metrics.get("dialogue_ratio", 0.0)
    sentence_length = chapter_metrics.get("sentence_length", 0.0)
    ta_density = chapter_metrics.get("ta_density", 0.0)
    hook_ending = chapter_metrics.get("hook_ending", 0)
    iwr = chapter_metrics.get("iwr_score", 0.0)

    # 计算CV（如果有历史数据）
    cv_score = 20.0
    if chapter_history_word_counts:
        cv_score = score_chapter_length_cv(chapter_history_word_counts + [word_count])

    breakdown = {
        "chapter_length_cv": round(cv_score, 1),
        "chapter_length": round(score_chapter_length(word_count), 1),
        "dialogue_ratio": round(score_dialogue_ratio(dialogue_ratio), 1),
        "sentence_length": round(score_sentence_length(sentence_length), 1),
        "ta_density": round(score_ta_density(ta_density), 1),
        "suspense_rhythm": round(score_suspense_rhythm(hook_ending, iwr), 1),
    }

    total = sum(breakdown.values())
    grade = grade_from_score(total)

    return {
        "platform_score": round(total, 1),
        "platform_grade": grade,
        "breakdown": breakdown,
    }


def compute_genre_dna_match(
    metrics: dict[str, Any], genre_dna: dict[str, Any]
) -> float:
    """计算当前章节与品类DNA的匹配度（0-100）。

    比较句长、对话占比、他密度三个核心维度。
    """
    if not genre_dna:
        return 100.0  # 无DNA数据时跳过审计（视为免检），避免误触发重写

    scores = []

    # 句长匹配
    target_sent = genre_dna.get("target_sent_len", 25)
    actual_sent = metrics.get("sentence_length", target_sent)
    sent_diff = abs(actual_sent - target_sent)
    scores.append(max(0, 100 - sent_diff * 5))

    # 对话占比匹配
    target_dialogue = genre_dna.get("dialogue_target", 0.35)
    actual_dialogue = metrics.get("dialogue_ratio", target_dialogue)
    dial_diff = abs(actual_dialogue - target_dialogue)
    scores.append(max(0, 100 - dial_diff * 200))

    # 他密度匹配
    target_ta = genre_dna.get("ta_density_max", 0.02)
    actual_ta = metrics.get("ta_density", 0.0)
    if actual_ta <= target_ta:
        scores.append(100.0)
    else:
        scores.append(max(0, 100 - (actual_ta - target_ta) * 5000))

    return round(sum(scores) / len(scores), 1)
