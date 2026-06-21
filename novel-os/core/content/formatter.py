"""段落格式化 —— 拆分超长段落等。"""
from __future__ import annotations

import re


def split_long_paragraphs(text: str, max_cn_chars: int = 50) -> str:
    """将超长段落按句末标点拆分为短段落。

    原 batch_writer._split_long_paragraphs 的逻辑提取为纯函数。
    """
    lines = text.split("\n")
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append(line)
            continue

        cn_chars = len(re.findall(r"[\u4e00-\u9fff]", stripped))
        if cn_chars <= max_cn_chars:
            new_lines.append(line)
            continue

        sentences = _split_into_sentences(stripped)
        new_lines.extend(_merge_sentences(sentences, max_cn_chars))

    return "\n".join(new_lines)


def _split_into_sentences(text: str) -> list[str]:
    """按句末标点拆分，保留标点。"""
    raw_parts = re.split(r"([。！？；])", text)
    sentences = []
    i = 0
    while i < len(raw_parts):
        s = raw_parts[i]
        if i + 1 < len(raw_parts) and raw_parts[i + 1] in "。！？；":
            s += raw_parts[i + 1]
            i += 2
        else:
            i += 1
        if not s:
            continue
        # 处理引号闭合
        if sentences and s.startswith('"') and sentences[-1] and sentences[-1][-1] in "。！？；":
            sentences[-1] += s
        else:
            sentences.append(s)
    return sentences


def _merge_sentences(sentences: list[str], max_cn: int) -> list[str]:
    """将句子合并为不超过 max_cn 中文字符的段落。"""
    result = []
    buf = ""
    buf_cn = 0

    for sent in sentences:
        sent_cn = len(re.findall(r"[\u4e00-\u9fff]", sent))

        # 单句本身超长，先在逗号/顿号处子分割
        if sent_cn > max_cn:
            sub_parts = _split_by_comma(sent)
            for sp in sub_parts:
                sp_cn = len(re.findall(r"[\u4e00-\u9fff]", sp))
                if buf_cn + sp_cn > max_cn and buf:
                    result.append(buf)
                    buf = sp
                    buf_cn = sp_cn
                else:
                    buf += sp
                    buf_cn += sp_cn
            continue

        if buf_cn + sent_cn > max_cn and buf:
            result.append(buf)
            buf = sent
            buf_cn = sent_cn
        else:
            buf += sent
            buf_cn += sent_cn

    if buf:
        result.append(buf)
    return result


def _split_by_comma(text: str) -> list[str]:
    """按逗号/顿号拆分，保留标点。"""
    raw = re.split(r"([，、])", text)
    parts = []
    i = 0
    while i < len(raw):
        s = raw[i]
        if i + 1 < len(raw) and raw[i + 1] in "，、":
            s += raw[i + 1]
            i += 2
        else:
            i += 1
        if s:
            parts.append(s)
    return parts
