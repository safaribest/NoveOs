"""正文清洗 —— 从 batch_writer._sanitize_content 提取。"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from core.content.formatter import split_long_paragraphs

logger = logging.getLogger("novel-os.content.sanitizer")


@dataclass(frozen=True)
class SanitizeRule:
    """清洗规则配置。"""

    max_sudden: int = 3  # '突然'保留上限
    max_paragraph_cn: int = 50  # 段落最大中文字符数
    english_replacements: dict[str, str] | None = None


class Sanitizer:
    """正文清洗器。

    职责：删除 Agent 自检残留、替换英文术语、控制'突然'用量、
          拆分超长段落、清洗精确数字铺陈、清洗情绪标签化。
    """

    # Agent 自检/思考过程残留模式
    _META_PATTERNS = [
        r"[（(]当前字数[：:].*?[）)]\n?",
        r"[（(]总进度[：:].*?[）)]\n?",
        r"[（(]字数[：:].*?[）)]\n?",
        r"=+.*?=+\n?[\s\S]*?=+.*?=+\n?",  # ===== 包裹区块
        r"请确认是否继续生成.*\n?",
        r"【润色说明】.*\n?",
        r"【字数统计】.*\n?",
        r"【自检表】.*\n?",
        r"```[\s\S]*?```\n?",
        r"在我的优化版本中：.*\n?",
        r"让我重新调整.*\n?",
        r"【.*?自检.*?】.*\n?",
        r"【优化说明】.*\n?",
        r"【思考过程】.*\n?",
        r"（优化版本）.*\n?",
        r"以下是优化后的.*\n?",
    ]

    # 精确数字铺陈清洗
    _NUMBER_PATTERNS = [
        (r"(?<![第\d])(?<![\d\-])\d+\.?\d*\s*毫米", "几分厚"),
        (r"\d+\s*赫兹", "某种频率"),
        (r"\d+\s*摄氏度", "异常的温"),
        (r"\d+\s*%\s*湿度", "湿闷的空气"),
        (r"pH值\s*低于\s*[\d\.]+", "强酸性"),
    ]

    # 概括性时间清洗
    _TIME_PATTERNS = [
        r"过了一会儿|不久之后|几天后|数秒后|片刻之后|转眼之间|一段时间后",
    ]

    # 情绪标签化清洗
    _EMOTION_LABELS = ["恐惧", "绝望", "愤怒", "悲伤", "快乐", "幸福", "焦虑", "紧张", "害怕"]

    # 英文术语替换（保留世界观白名单）
    _ENGLISH_DEFAULT = {
        r"\blogo\b": "标识",
        r"\bERROR\b": "报错",
        r"\bDNA\b": "基因",
        r"\bAI\b": "人工智能",
        r"\bLED\b": "发光二极管",
        r"\bUSB\b": "通用接口",
        r"\bWAV\b": "音频",
        r"\bHR[-_]?(\d+)\b": r"人事\1号",
    }

    _WHITELIST = {"KPI", "NULL", "HR", "Hz", "PPT"}

    def __init__(self, rules: SanitizeRule | None = None) -> None:
        self._rules = rules or SanitizeRule()

    def sanitize(self, text: str) -> str:
        """执行完整清洗流程。"""
        text = self._remove_meta(text)
        text = self._clean_numbers(text)
        text = self._clean_time_phrases(text)
        text = self._replace_english(text)
        text = self._limit_sudden(text)
        text = self._clean_emotion_labels(text)
        text = split_long_paragraphs(text, max_cn_chars=self._rules.max_paragraph_cn)
        return text

    def _remove_meta(self, text: str) -> str:
        for pattern in self._META_PATTERNS:
            text = re.sub(pattern, "", text)
        return text

    def _clean_numbers(self, text: str) -> str:
        for pattern, repl in self._NUMBER_PATTERNS:
            text = re.sub(pattern, repl, text)
        return text

    def _clean_time_phrases(self, text: str) -> str:
        for pattern in self._TIME_PATTERNS:
            text = re.sub(pattern, "", text)
        return text

    def _clean_emotion_labels(self, text: str) -> str:
        for label in self._EMOTION_LABELS:
            text = re.sub(
                rf"感到{label}|一种{label}感|充斥着{label}",
                f"[[{label}——改为生理反应]]",
                text,
            )
        return text

    def _replace_english(self, text: str) -> str:
        reps = self._rules.english_replacements or self._ENGLISH_DEFAULT
        for pattern, repl in reps.items():
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        return text

    def _limit_sudden(self, text: str) -> str:
        """保留前 N 个'突然'，其余替换。"""
        max_count = self._rules.max_sudden
        replacements = ["猛地", "骤然", "冷不防地", "毫无征兆地", "刹那间", "陡然"]
        count = 0
        result = []
        idx = 0
        while idx < len(text):
            pos = text.find("突然", idx)
            if pos == -1:
                result.append(text[idx:])
                break
            result.append(text[idx:pos])
            count += 1
            if count > max_count:
                rep = replacements[(count - max_count - 1) % len(replacements)]
                result.append(rep)
            else:
                result.append("突然")
            idx = pos + 2
        return "".join(result)
