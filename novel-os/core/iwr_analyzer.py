"""IWR (Information Withholding Ratio) 分析器 —— 章节级追读基因计算。

基于 RAG 全库分析结论：
- IWR = 每章问题数 / 每章答案数
- IWR 与追读分相关系数 r=0.898，是追读唯一独立驱动因子
- 高追读组 IWR=3.0，低追读组 IWR=1.2
"""
from __future__ import annotations

import re
from typing import Any


# 问题标记：显式问句 + 隐式悬念
_QUESTION_PATTERNS = [
    r'[？?]',
    r'(?:难道|莫非|究竟|到底|为何|怎么|会不会|是否|为何|何以|怎的|岂非|莫非|难不成)',
]

# 答案/揭示标记
_REVEAL_PATTERNS = [
    r'(?:原来|终于|发现|明白|知道|看来|果然|竟然|居然|突然|顿时|恍然|这才|方才)',
]

# 钩子/悬念结尾标记
_HOOK_PATTERNS = [
    r'(?:正要|就要|刚要|即将)',
    r'(?:心中|心想|暗道|念及|不知|隐隐|总觉得|仿佛)',
]

# 动作动词库（用于微张力振荡计算）
_ACTION_VERBS = r'走|跑|跳|打|杀|冲|追|逃|躲|飞|闪|摔|砸|劈|砍|刺|射|扑|跃|抓|握|扯|撕|咬|踢|踩|喊|叫|吼'


def _count_pattern(text: str, patterns: list[str]) -> int:
    """统计文本中匹配所有 pattern 的总次数。"""
    total = 0
    for p in patterns:
        total += len(re.findall(p, text))
    return total


def analyze_chapter(text: str) -> dict[str, Any]:
    """分析单章结构指标，返回完整指标字典。

    返回字段：
    - word_count: 中文字数
    - sentence_length: 平均句长（中文字数）
    - dialogue_ratio: 对话段落占比
    - ta_density: 他/她/它密度（%）
    - questions_count: 问题数（显式+隐式）
    - answers_count: 答案/揭示数
    - iwr_score: 信息扣留比
    - hook_ending: 是否钩子结尾（0/1）
    - oscillations: 微张力振荡次数
    """
    # 1. 基础字数
    cn_chars = len(re.findall(r'[一-鿿]', text))
    if cn_chars == 0:
        cn_chars = len(text)  # fallback

    # 2. 句子切分与句长
    sentences = [s.strip() for s in re.split(r'[。！？…；]+', text) if s.strip()]
    sent_lens = []
    for s in sentences:
        cn = len(re.findall(r'[一-鿿]', s))
        if cn > 0:
            sent_lens.append(cn)
    sentence_length = sum(sent_lens) / len(sent_lens) if sent_lens else 0.0

    # 3. 对话占比
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    dial_paras = 0
    for p in paragraphs:
        if re.search(r'[\"""\'\'「」『』]', p) or re.search(r'[说道问喊叫骂嚷答告诉讲谈聊吼喝]', p[:30]):
            dial_paras += 1
    dialogue_ratio = dial_paras / len(paragraphs) if paragraphs else 0.0

    # 4. 他密度
    ta_count = len(re.findall(r'[他她它]', text))
    ta_density = ta_count / cn_chars if cn_chars > 0 else 0.0

    # 5. IWR
    questions_count = _count_pattern(text, _QUESTION_PATTERNS)
    answers_count = _count_pattern(text, _REVEAL_PATTERNS)
    # 避免除零；如果没有答案，IWR = 问题数（极端情况）
    iwr_score = questions_count / max(answers_count, 1)

    # 6. 钩子结尾（检查后50字）
    tail = text[-50:] if len(text) >= 50 else text
    hook_ending = 1 if _count_pattern(tail, _HOOK_PATTERNS) > 0 else 0

    # 7. 微张力振荡
    oscillations = _compute_oscillations(paragraphs)

    return {
        "word_count": cn_chars,
        "sentence_length": round(sentence_length, 1),
        "dialogue_ratio": round(dialogue_ratio, 3),
        "ta_density": round(ta_density, 4),
        "questions_count": questions_count,
        "answers_count": answers_count,
        "iwr_score": round(iwr_score, 2),
        "hook_ending": hook_ending,
        "oscillations": oscillations,
    }


def _compute_oscillations(paragraphs: list[str]) -> int:
    """计算段落级微张力振荡次数。"""
    tensions = []
    for p in paragraphs:
        cn = max(len(re.findall(r'[一-鿿]', p)), 1)
        excl = len(re.findall(r'[！!]', p)) * 3
        actions = len(re.findall(_ACTION_VERBS, p)) * 2
        short = len(re.findall(r'[。！？…；][^。！？…；]{0,10}[。！？…；]', p))
        t = (excl + actions + short) / cn * 100
        tensions.append(t)

    oscillations = 0
    direction = None
    for i in range(1, len(tensions)):
        if tensions[i] > tensions[i - 1] * 1.05:
            if direction == 'down':
                oscillations += 1
            direction = 'up'
        elif tensions[i] < tensions[i - 1] * 0.95:
            if direction == 'up':
                oscillations += 1
            direction = 'down'
    return oscillations


def compute_iwr_for_chapter(text: str) -> float:
    """快捷函数：只返回 IWR 值。"""
    result = analyze_chapter(text)
    return result["iwr_score"]
