"""文本指标计算 —— 纯函数，无副作用。"""
from __future__ import annotations

import re


def count_chinese_chars(text: str) -> int:
    """统计中文字符数（不含标点）。"""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def count_total_chars(text: str) -> int:
    """统计总字符数（含标点、空格）。"""
    return len(text)


def ta_density(text: str) -> float:
    """计算'他/她/它'密度（占中文字符的比例）。"""
    cn = count_chinese_chars(text)
    if cn == 0:
        return 0.0
    ta_count = len(re.findall(r"[他她它牠祂]", text))
    return ta_count / cn


def sentence_length_avg(text: str) -> float:
    """平均句长（中文字符 / 句子数）。"""
    sentences = re.split(r"[。！？；]", text)
    valid = [s for s in sentences if s.strip()]
    if not valid:
        return 0.0
    total_cn = sum(count_chinese_chars(s) for s in valid)
    return total_cn / len(valid)


def dialogue_ratio(text: str) -> float:
    """对话占比（对话字数 / 总中文字数）。

    简单实现：匹配 "..." 包裹的内容作为对话。
    """
    cn = count_chinese_chars(text)
    if cn == 0:
        return 0.0
    dialogues = re.findall(r'"([^"]*?)"', text)
    dialog_cn = sum(count_chinese_chars(d) for d in dialogues)
    return dialog_cn / cn


def dao_shuo_ratio(text: str) -> float:
    """'道/说'比率（对话提示词中 '道' 占 '道+说' 的比例）。

    年代文要求多用'道'，少用'说'，以提升古风/年代感。
    """
    dao = len(re.findall(r"[道說]", text))  # 简化：统计所有道/说
    shuo = len(re.findall(r"[说說説]", text))
    total = dao + shuo
    if total == 0:
        return 0.0
    return dao / total


def iwr_score(text: str) -> float:
    """Information-Wanting-Response 分数（章末悬念强度）。

    简化算法：统计结尾 200 字内的问号和未解之谜关键词。
    """
    # 取最后 200 中文字符
    cn_chars = re.findall(r"[\u4e00-\u9fff]", text)
    tail = "".join(cn_chars[-200:])
    questions = tail.count("？") + tail.count("?")
    hooks = len(re.findall(r"究竟|难道|怎么回事|为什么|谁|什么|难道", tail))
    return float(questions + hooks * 0.5)
