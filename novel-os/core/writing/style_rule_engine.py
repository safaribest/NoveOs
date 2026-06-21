"""StyleRuleEngine —— 去 AI 味硬规则引擎。

把“禁止清单”变成可执行、可测试、不会漏判的代码规则。
用于：
1. StyleCriticStep 前置快速扫描
2. 流水线最终输出拦截
3. 生成 AI 味评分报告
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StyleIssue:
    """单条规则命中。"""

    rule: str
    type: str
    text: str
    position: int = 0
    suggestion: str = ""


class StyleRuleEngine:
    """去 AI 味规则引擎。"""

    # 情绪标签词表
    EMOTION_LABELS = [
        "恐惧", "绝望", "愤怒", "悲伤", "焦虑", "害怕", "惊恐", "慌张", "紧张", "兴奋",
        "高兴", "快乐", "痛苦", "难过", "欣慰", "满足", "得意", "羞愧", "内疚", "嫉妒",
        "厌恶", "憎恨", "喜爱", "爱恋", "冷漠", "麻木", "疲惫", "厌烦", "期待", "渴望",
        "希望", "失望", "沮丧", "郁闷", "恼火", "气愤", "震怒", "狂喜", "欣喜", "安心",
        "平静", "慌乱", "震惊", "惊讶", "惊愕", "错愕", "困惑", "迷茫", "彷徨", "孤独",
        "寂寞", "无助", "委屈", "释然", "轻松", "沉重", "压抑", "窒息",
    ]

    # 系统面板常见词
    SYSTEM_PANEL_WORDS = ["宿主", "面板", "属性点", "经验条", "冷却时间", "侵蚀度"]

    # 公共库存比喻靶子
    STOCK_METAPHORS = ["像刀", "像蛇", "像铁板", "像离弦的箭", "像蜡像", "像提线木偶"]

    # 精确数字模式（阿拉伯数字 + 单位 / 百分比 / 赫兹等）
    PRECISE_NUMBER_RE = re.compile(
        r"\d+(?:\.\d+)?\s*(?:毫米|厘米|米|克|千克|斤|两|赫兹|度|℃|%)|"
        r"百分之\s*\d+(?:\.\d+)?"
    )

    # 中文数词（用于统计密度）
    CN_NUMBER_RE = re.compile(r"[一二三四五六七八九十百千万亿]+")

    def __init__(
        self,
        max_not_x_but_y: int = 3,
        max_xiang: int = 5,
        max_cn_numbers: int = 50,
        max_repetition: int = 5,
    ) -> None:
        # 外层回路覆盖：读取 rule_overrides.json（如果存在）
        try:
            from core.outer_loop.rule_config import load_overrides
            overrides = load_overrides()
            max_not_x_but_y = overrides.get("StyleRuleEngine.max_not_x_but_y", max_not_x_but_y)
            max_xiang = overrides.get("StyleRuleEngine.max_xiang", max_xiang)
            max_cn_numbers = overrides.get("StyleRuleEngine.max_cn_numbers", max_cn_numbers)
            max_repetition = overrides.get("StyleRuleEngine.max_repetition", max_repetition)
        except Exception:
            pass  # 外层回路模块不可用时使用默认值
        self.max_not_x_but_y = max_not_x_but_y
        self.max_xiang = max_xiang
        self.max_cn_numbers = max_cn_numbers
        self.max_repetition = max_repetition

    def detect(self, text: str, chapter_num: int = 0) -> list[StyleIssue]:
        """扫描文本，返回所有风格问题。"""
        issues: list[StyleIssue] = []
        issues.extend(self._detect_not_x_but_y(text))
        issues.extend(self._detect_xiang(text))
        issues.extend(self._detect_system_markers(text))
        issues.extend(self._detect_emotion_labels(text))
        issues.extend(self._detect_precise_numbers(text))
        issues.extend(self._detect_repetition(text))
        issues.extend(self._detect_stock_metaphors(text))
        return issues

    def fix(self, text: str) -> tuple[str, list[StyleIssue]]:
        """自动修复能安全处理的问题，返回修复后文本和未修复问题。"""
        issues = self.detect(text)
        auto_fixable = [i for i in issues if i.rule in ("system_marker",)]
        remaining = [i for i in issues if i.rule not in ("system_marker",)]

        if auto_fixable:
            # 去除 【】 括号，保留内部文字
            text = re.sub(r"【([^】]+)】", r"\1", text)
            # 清理空括号残留
            text = re.sub(r"[【】]", "", text)

        return text, remaining

    def score(self, text: str) -> dict[str, Any]:
        """计算 AI 味评分，分数越高问题越严重。"""
        issues = self.detect(text)
        cn_chars = max(len(re.findall(r"[\u4e00-\u9fff]", text)), 1)
        cn_numbers = len(self.CN_NUMBER_RE.findall(text))

        breakdown = {}
        for issue in issues:
            breakdown.setdefault(issue.rule, 0)
            breakdown[issue.rule] += 1

        # 归一化得分（0–1，越高越 AI）
        scores = {
            "not_x_but_y": min(1, breakdown.get("not_x_but_y", 0) / self.max_not_x_but_y),
            "xiang": min(1, breakdown.get("xiang", 0) / self.max_xiang),
            "system_marker": min(1, breakdown.get("system_marker", 0) / 3),
            "emotion_label": min(1, breakdown.get("emotion_label", 0) / 3),
            "precise_number": min(1, breakdown.get("precise_number", 0) / 3),
            "repetition": min(1, breakdown.get("repetition", 0) / 5),
            "stock_metaphor": min(1, breakdown.get("stock_metaphor", 0) / 3),
            "cn_number_density": min(1, cn_numbers / self.max_cn_numbers),
        }
        total = sum(scores.values()) / len(scores)
        scores["total"] = round(total, 3)
        return {
            "score": scores,
            "issue_count": len(issues),
            "breakdown": breakdown,
            "cn_number_density": round(cn_numbers / (cn_chars / 1000), 1),
        }

    def count_not_x_but_y(self, text: str) -> int:
        """返回 '不是X，是Y' 句式命中次数。"""
        return len(self._detect_not_x_but_y(text))

    def count_xiang(self, text: str) -> int:
        """返回 '像…' 比喻命中次数。"""
        return len(self._detect_xiang(text))

    def has_ending_hook(self, text: str) -> bool:
        """检查最后 200 字是否有悬念钩子。"""
        if not text:
            return False
        tail = text[-200:]
        return bool(re.search(r"[？?]|正要|就要|刚要|即将|不知道|不明白|然而|可是|但$", tail))

    def cn_number_density(self, text: str) -> float:
        """返回每千字中文数词数。"""
        cn_chars = max(len(re.findall(r"[\u4e00-\u9fff]", text)), 1)
        cn_numbers = len(self.CN_NUMBER_RE.findall(text))
        return round(cn_numbers / (cn_chars / 1000), 1)

    def _detect_not_x_but_y(self, text: str) -> list[StyleIssue]:
        """检测 '不是X，是Y' 句式。"""
        pattern = re.compile(r"不是[^。！？\n]{1,35}是[^。！？\n]{0,25}[。！？]")
        return [
            StyleIssue(
                rule="not_x_but_y",
                type="禁用句式",
                text=m.group(0),
                position=m.start(),
                suggestion="改为直接描述，避免'不是X，是Y'结构",
            )
            for m in pattern.finditer(text)
        ]

    def _detect_xiang(self, text: str) -> list[StyleIssue]:
        """检测 '像……' 比喻。"""
        pattern = re.compile(r"像[^，。！？\n]{1,25}")
        return [
            StyleIssue(
                rule="xiang",
                type="比喻",
                text=m.group(0),
                position=m.start(),
                suggestion="减少比喻，或用更具体的感官描写替代",
            )
            for m in pattern.finditer(text)
        ]

    def _detect_system_markers(self, text: str) -> list[StyleIssue]:
        """检测系统面板标记和词汇。"""
        issues = []
        for m in re.finditer(r"[【】]", text):
            issues.append(StyleIssue(
                rule="system_marker",
                type="系统面板标记",
                text=m.group(0),
                position=m.start(),
                suggestion="去除【】括号，改为自然叙述",
            ))
        for word in self.SYSTEM_PANEL_WORDS:
            for m in re.finditer(re.escape(word), text):
                issues.append(StyleIssue(
                    rule="system_marker",
                    type="系统面板词",
                    text=m.group(0),
                    position=m.start(),
                    suggestion=f"避免使用'{word}'，改为身体化/噩梦化表达",
                ))
        return issues

    def _detect_emotion_labels(self, text: str) -> list[StyleIssue]:
        """检测情绪标签词。"""
        issues = []
        for label in self.EMOTION_LABELS:
            for m in re.finditer(re.escape(label), text):
                issues.append(StyleIssue(
                    rule="emotion_label",
                    type="情绪标签",
                    text=m.group(0),
                    position=m.start(),
                    suggestion="改为生理反应或行为表现",
                ))
        return issues

    def _detect_precise_numbers(self, text: str) -> list[StyleIssue]:
        """检测精确数字参数。"""
        return [
            StyleIssue(
                rule="precise_number",
                type="精确数字",
                text=m.group(0),
                position=m.start(),
                suggestion="改为身体体感描述，避免精确参数",
            )
            for m in self.PRECISE_NUMBER_RE.finditer(text)
        ]

    def _detect_repetition(self, text: str) -> list[StyleIssue]:
        """检测高频复读意象。"""
        keywords = ["虎口", "旧疤", "黑丝", "识海", "倒影", "污染", "裂缝", "铜锈味", "铁锈味", "透明液体"]
        issues = []
        for kw in keywords:
            count = len(re.findall(re.escape(kw), text))
            if count > self.max_repetition:
                issues.append(StyleIssue(
                    rule="repetition",
                    type="复读意象",
                    text=f"{kw} 出现 {count} 次",
                    suggestion=f"每章'{kw}'出现不超过 {self.max_repetition} 次，换其他身体反应入口",
                ))
        return issues

    def _detect_stock_metaphors(self, text: str) -> list[StyleIssue]:
        """检测公共库存比喻。"""
        issues = []
        for stock in self.STOCK_METAPHORS:
            for m in re.finditer(re.escape(stock), text):
                issues.append(StyleIssue(
                    rule="stock_metaphor",
                    type="公共库存比喻",
                    text=m.group(0),
                    position=m.start(),
                    suggestion="替换为具体、新鲜的感官描写",
                ))
        return issues
