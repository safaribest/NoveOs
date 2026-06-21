"""StatisticalFingerprintOptimizer —— 统计指纹优化器。

基于洞察报告核心发现：AI检测工具通过"困惑度"(perplexity)和"突发性"(burstiness)
两个统计指标判断文本是否为AI生成。本模块通过主动优化这两个指标，降低AI检测概率。

核心策略：
1. 困惑度优化：引入低频词、打破高频词模式、增加不可预测性
2. 突发性优化：制造句长变异（短句爆发+长句沉淀）
3. 情感不一致性：允许逻辑跳跃和情绪突变（人类特征）

参考：GPTZero/Turnitin检测原理（perplexity + burstiness）
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class FingerprintMetrics:
    """统计指纹指标。"""

    perplexity_score: float  # 0-1，越高越像人类（AI倾向低困惑度）
    burstiness_score: float  # 0-1，越高越像人类（AI倾向低突发性）
    sentence_length_cv: float  # 句长变异系数
    transition_density: float  # 过渡词密度
    le_density: float  # "了"字密度
    overall_human_score: float  # 综合人类相似度


class StatisticalFingerprintOptimizer:
    """统计指纹优化器。

    不是简单替换词汇，而是系统性调整文本的统计特征，使其更接近人类写作模式。
    """

    # 高频AI过渡词（检测器重点监控）
    HIGH_FREQ_TRANSITIONS = [
        "然而", "此外", "值得注意的是", "综上所述", "总而言之",
        "首先", "其次", "最后", "不仅如此", "更重要的是",
        "从这个角度来看", "换句话说", "本质上", "归根结底",
    ]

    # 低频词库（用于提升困惑度）
    LOW_FREQ_WORDS = [
        "窸窣", "斑驳", "氤氲", "黏稠", "涩", "钝", "滞",
        "蜷", "佝", "趔趄", "踉跄", "倏地", "蓦地", "陡然",
        "戛然", "兀自", "径自", "独个儿", "愣怔", "恍惚",
        "怔忡", "惴惴", "悻悻", "悻然", "怏怏", "惘然",
    ]

    # 口语化替换词（打破书面语模式）
    COLLOQUIAL_REPLACEMENTS = {
        "非常": ["挺", "怪", "老", "忒", "贼"],
        "很": ["挺", "怪", "老", "蛮", "够"],
        "十分": ["挺", "怪", "老", "蛮"],
        "极其": ["老", "忒", "贼", "死"],
        "特别": ["挺", "怪", "老", "蛮"],
        "因此": ["所以", "于是", "就这么", "这下"],
        "于是": ["就这么", "这下", "接着", "然后"],
        "但是": ["可", "不过", "只是", "偏偏", "奈何"],
        "然而": ["可", "不过", "偏偏", "奈何", "岂料"],
        "因为": ["由于", "仗着", "凭着", "就凭"],
    }

    # 常见形容词 → 低频词映射（困惑度优化用）
    COMMON_TO_LOW_FREQ = {
        "黑暗": ["黢黑", "墨黑", "漆黑"],
        "安静": ["阒寂", "寂然", "悄无声息"],
        "潮湿": ["溻湿", "潮润", "水汽氤氲"],
        "寒冷": ["凛冽", "砭骨", "刺骨"],
        "炎热": ["燠热", "闷热", "热浪蒸腾"],
        "疼痛": ["刺痛", "钝痛", "绞痛", "抽痛"],
        "快速": ["倏忽", "骤然", "陡然", "蓦地"],
        "缓慢": ["徐徐", "渐次", "一点一点地"],
    }

    # 碎片化短句库（突发性优化用）
    SHORT_FRAGMENTS = [
        "风停了。", "灯灭了。", "没人说话。", "沉默。",
        "远处有狗叫。", "雨还在下。", "他不知道。", "就这样。",
        "呼吸一滞。", "血往上涌。", "指尖发凉。", "后颈发麻。",
    ]

    # 半截话库（人类不完美注入用）
    HALF_SENTENCES = [
        "其实……", "怎么说呢……", "反正就是……",
        "你也知道……", "怎么说呢，", "反正",
    ]

    # 重复修正库（人类不完美注入用）
    CORRECTIONS = [
        "不对，不是那样。", "等等，让我想想。",
        "怎么说呢，反正就是……", "也不是，就是……",
    ]

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self._used_low_freq: set[str] = set()

    def optimize(self, text: str, aggressiveness: float = 0.5) -> str:
        """执行统计指纹优化。

        Args:
            text: 待优化文本
            aggressiveness: 优化强度 0.0-1.0

        Returns:
            优化后的文本
        """
        if not text:
            return text

        # Step 1: 句长突发性优化（核心）
        text = self._optimize_burstiness(text, aggressiveness)

        # Step 2: 困惑度优化（低频词注入）
        text = self._optimize_perplexity(text, aggressiveness)

        # Step 3: 过渡词稀释
        text = self._dilute_transitions(text, aggressiveness)

        # Step 4: 口语化替换（打破书面语模式）
        text = self._colloquialize(text, aggressiveness)

        # Step 5: 允许"不完美"（人类特征）
        text = self._inject_human_imperfections(text, aggressiveness)

        return text

    def compute_metrics(self, text: str) -> FingerprintMetrics:
        """计算当前文本的统计指纹指标。"""
        cn_chars = max(len(re.findall(r"[一-鿿]", text)), 1)

        # 句长变异系数（突发性核心指标）
        sentences = [s for s in re.split(r"[。！？…；]", text) if s.strip()]
        sent_lens = [len(re.findall(r"[一-鿿]", s)) for s in sentences if len(re.findall(r"[一-鿿]", s)) > 0]
        if len(sent_lens) >= 2:
            mean_len = sum(sent_lens) / len(sent_lens)
            variance = sum((x - mean_len) ** 2 for x in sent_lens) / len(sent_lens)
            std = variance ** 0.5
            cv = std / mean_len if mean_len > 0 else 0
        else:
            cv = 0

        # 过渡词密度
        trans_count = sum(text.count(w) for w in self.HIGH_FREQ_TRANSITIONS)
        trans_density = trans_count / max(1, cn_chars / 1000)

        # "了"字密度
        le_count = text.count("了")
        le_density = le_count / max(1, cn_chars / 100)

        # 综合评分（越高越像人类）
        # 人类文本特征：高CV(>0.5)、低过渡词密度(<2)、低了密度(<5)
        perplexity = max(0, min(1, 1 - trans_density / 3))  # 过渡词越少，困惑度越高
        burstiness = max(0, min(1, cv / 0.8))  # CV越高，突发性越高

        overall = (perplexity * 0.4 + burstiness * 0.4 + max(0, 1 - le_density / 5) * 0.2)

        return FingerprintMetrics(
            perplexity_score=round(perplexity, 3),
            burstiness_score=round(burstiness, 3),
            sentence_length_cv=round(cv, 3),
            transition_density=round(trans_density, 3),
            le_density=round(le_density, 3),
            overall_human_score=round(overall, 3),
        )

    # ------------------------------------------------------------------
    # Step 1: 突发性优化 —— 句长变异
    # ------------------------------------------------------------------
    def _optimize_burstiness(self, text: str, aggressiveness: float) -> str:
        """优化句长分布，增加突发性。

        策略：
        - 连续中等长度句子 → 拆分为短句+长句组合
        - 超长句 → 在关键位置拆分，制造"呼吸感"
        - 插入碎片化短句（3-8字）作为节奏标点
        """
        sentences = re.split(r"([。！？…；]+)", text)
        result = []

        for i in range(0, len(sentences) - 1, 2):
            sent = sentences[i]
            punct = sentences[i + 1] if i + 1 < len(sentences) else ""
            cn_len = len(re.findall(r"[一-鿿]", sent))

            # 策略A：在合适位置插入碎片化短句（制造爆发点）
            if cn_len > 20 and self.rng.random() < aggressiveness * 0.3:
                fragment = self.rng.choice(self.SHORT_FRAGMENTS)
                result.append(fragment)
                result.append(sent + punct)
                continue

            # 策略B：拆分超长句
            if cn_len > 35 and self.rng.random() < aggressiveness * 0.5:
                split_point = self._find_split_point(sent)
                if split_point > 0:
                    result.append(sent[:split_point] + "。")
                    result.append(sent[split_point:] + punct)
                    continue

            # 策略C：合并连续短句为长句（避免过度碎片化）
            if cn_len < 10 and result:
                prev = result[-1].rstrip("。！？…；")
                if len(re.findall(r"[一-鿿]", prev)) < 25:
                    result[-1] = prev + "，" + sent + punct
                    continue

            result.append(sent + punct)

        return "".join(result)

    def _find_split_point(self, sentence: str) -> int:
        """找到最佳拆分点（在逗号或顿号处）。"""
        mid = len(sentence) // 2
        # 优先在"，"处拆分
        for offset in range(0, 20):
            for direction in [1, -1]:
                pos = mid + offset * direction
                if 0 <= pos < len(sentence):
                    if sentence[pos] == "，":
                        return pos + 1
        return 0

    # ------------------------------------------------------------------
    # Step 2: 困惑度优化 —— 低频词注入
    # ------------------------------------------------------------------
    def _optimize_perplexity(self, text: str, aggressiveness: float) -> str:
        """通过低频词替换提升困惑度。

        策略：
        - 将常见形容词替换为低频词
        - 避免同一低频词重复使用
        """
        for common, replacements in self.COMMON_TO_LOW_FREQ.items():
            if common in text and self.rng.random() < aggressiveness * 0.4:
                available = [r for r in replacements if r not in self._used_low_freq]
                if not available:
                    available = replacements
                replacement = self.rng.choice(available)
                self._used_low_freq.add(replacement)
                text = text.replace(common, replacement, 1)

        return text

    # ------------------------------------------------------------------
    # Step 3: 过渡词稀释
    # ------------------------------------------------------------------
    def _dilute_transitions(self, text: str, aggressiveness: float) -> str:
        """稀释AI高频过渡词。

        策略：
        - 删除而非替换（替换会引入新的模式）
        - 用动作或环境描写替代过渡词的功能
        """
        for word in self.HIGH_FREQ_TRANSITIONS:
            if word in text and self.rng.random() < aggressiveness * 0.7:
                # 策略：删除过渡词，用句号断句或直接用逗号连接
                text = text.replace(word + "，", "")
                text = text.replace(word, "")
        return text

    # ------------------------------------------------------------------
    # Step 4: 口语化替换
    # ------------------------------------------------------------------
    def _colloquialize(self, text: str, aggressiveness: float) -> str:
        """用口语化表达替换书面语。"""
        for formal, colloquials in self.COLLOQUIAL_REPLACEMENTS.items():
            if formal in text and self.rng.random() < aggressiveness * 0.5:
                colloquial = self.rng.choice(colloquials)
                text = text.replace(formal, colloquial, 1)
        return text

    # ------------------------------------------------------------------
    # Step 5: 注入人类"不完美"
    # ------------------------------------------------------------------
    def _inject_human_imperfections(self, text: str, aggressiveness: float) -> str:
        """注入人类写作特有的"不完美"特征。

        这些特征恰恰是AI被训练消除的：
        - 逻辑跳跃
        - 半截话
        - 重复修正
        - 口语冗余
        """
        if self.rng.random() < aggressiveness * 0.2:
            # 插入半截话
            # 在段落开头插入
            paragraphs = text.split("\n")
            if len(paragraphs) > 2:
                idx = self.rng.randint(1, len(paragraphs) - 1)
                if paragraphs[idx].strip():
                    paragraphs[idx] = self.rng.choice(self.HALF_SENTENCES) + paragraphs[idx]
            text = "\n".join(paragraphs)

        if self.rng.random() < aggressiveness * 0.15:
            # 插入重复修正（"不是……是……"的口语化版本）
            paragraphs = text.split("\n")
            if len(paragraphs) > 3:
                idx = self.rng.randint(1, len(paragraphs) - 2)
                paragraphs.insert(idx, self.rng.choice(self.CORRECTIONS))
            text = "\n".join(paragraphs)

        return text
