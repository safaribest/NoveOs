"""AntiDetectReviser —— 反检测改写器（对标 InkOS revise --mode anti-detect）。

系统性消除 AI 痕迹，不是简单润色，而是结构性手术：
- 句长分布重排
- 过渡词替换为动作/删除
- "了"字连锁打断
- 段落长度故意打乱
- 抽象概括→感官直写
"""

from __future__ import annotations

import logging
import random
import re

from core.statistical_fingerprint_optimizer import (
    FingerprintMetrics,
    StatisticalFingerprintOptimizer,
)

logger = logging.getLogger("novel-os.anti_detect")


class AntiDetectReviser:
    """反检测改写器。"""

    # 过渡词 → 替换选项（空字符串=删除）
    # 注意：每个词必须提供 >=3 个非空替换，避免单一替换词在全文重复
    TRANSITION_REPLACE = {
        "仿佛": ["像是", "好似", "如", ""],
        "忽然": ["猛地", "骤然", "一下", ""],
        "竟然": ["居然", "怎的", "反倒", ""],
        "不禁": ["不由得", "不自禁地", "下意识", ""],
        "宛如": ["如同", "好似", "像", "就如"],
        "猛地": ["突然", "骤然", "一下", "陡然"],
        "微微": ["一点", "些许", "稍", ""],
        "缓缓": ["慢慢", "一点一点地", "渐次", ""],
        "淡淡": ["隐约", "若有若无地", "薄", ""],
        "默默": ["无声地", "不发一言地", "一声不吭地", ""],
        "悄然": ["无声", "不知不觉间", "暗地里", ""],
    }

    # 元叙事词：直接删除
    METANARRATIVE = ["显然", "不言而喻", "众所周知", "不难看出", "值得注意的是", "综上所述", "总而言之"]

    # ★ 抽象→具体映射已删除：硬编码统一替换会导致全书法同质化。
    # 如果未来需要恢复，必须提供至少5种随机替换选项，而非单一固定句式。

    def __init__(self, seed: int | None = None) -> None:
        """初始化改写器。

        Args:
            seed: 随机种子，用于可复现测试。
        """
        self.rng = random.Random(seed)
        self._used_replacements: dict[str, int] = {}

    def revise(self, text: str, aggressiveness: float = 0.7) -> str:
        """执行辞林过滤 + 反检测改写 + 统计指纹优化。"""
        if not text:
            return text

        # Step 0: 辞林红线过滤（前置）
        text = self._lexicon_filter(text)

        # Step 1-5: 反检测手术（从轻到重）
        text = self._remove_metanarrative(text)
        text = self._replace_transitions(text, aggressiveness)
        text = self._break_le_chain(text, aggressiveness)
        text = self._reshuffle_sentence_length(text, aggressiveness)
        text = self._scramble_paragraphs(text, aggressiveness)

        # Step 6: 修复格式硬伤
        text = self._fix_dialogue_quotes(text)
        text = self._deduplicate_conjunctions(text)

        # Step 7: 统计指纹优化（困惑度 + 突发性）
        optimizer = StatisticalFingerprintOptimizer(seed=self.rng.randint(0, 2**31 - 1))
        text = optimizer.optimize(text, aggressiveness=aggressiveness * 0.8)
        logger.info("[AntiDetect] Step 7 统计指纹优化完成")

        return text

    # ------------------------------------------------------------------
    # 辞林红线过滤
    # ------------------------------------------------------------------
    def _lexicon_filter(self, text: str) -> str:
        """辞林红线过滤：扫描角色台词是否触发 dialog_taboo 红线。

        不是替换同义词，而是标记必须重写的句子。
        """
        # 跨角色通用红线
        universal_taboo = [
            "赋能", "抓手", "闭环", "沉淀", "底层逻辑",
            "赛道", "颗粒度", "方法论", "其实", "说白了",
            "归根结底", "值得注意的是", "首先", "其次", "最后",
        ]

        # 陆远舟专属红线
        luyuanzhou_taboo = [
            "其实", "说白了", "归根结底", "值得注意的是",
            "可以理解", "毕竟", "缓缓", "微微", "淡淡", "轻轻", "默默", "悄然",
        ]

        lines = text.split("\n")
        flagged_lines = []

        for line in lines:
            if not line.strip():
                continue
            flagged = False

            # 检查跨角色红线
            for taboo in universal_taboo:
                if taboo in line:
                    flagged = True
                    break

            # 检查陆远舟红线（在对话行中）
            if not flagged and self._is_dialogue_line(line):
                for taboo in luyuanzhou_taboo:
                    if taboo in line:
                        flagged = True
                        break

            if flagged:
                flagged_lines.append(line)

        # 如果检测到红线，在文本末尾添加标记（供 auditor 处理）
        if flagged_lines:
            text = text + "\n\n[LEXICON_FLAGGED]\n"
            for fl in flagged_lines:
                text = text + f"[RED_TABOO] {fl[:50]}...\n"

        return text

    @staticmethod
    def _is_dialogue_line(line: str) -> bool:
        """判断一行是否包含对话。支持中文直角引号与西式引号。"""
        return any(q in line for q in ['"', '"', "'", "'", "「", "」", "『", "』"])

    # ------------------------------------------------------------------
    # 元叙事词删除
    # ------------------------------------------------------------------
    def _remove_metanarrative(self, text: str) -> str:
        """删除元叙事词。"""
        for word in self.METANARRATIVE:
            text = re.sub(re.escape(word) + r"[，。；]", "。", text)
            text = re.sub(re.escape(word) + r"(?=\s)", "", text)
        return text

    # ------------------------------------------------------------------
    # 过渡词替换
    # ------------------------------------------------------------------
    def _replace_transitions(self, text: str, aggressiveness: float) -> str:
        """过渡词替换或删除，并避免同一替换词过度重复。"""
        for word, replacements in self.TRANSITION_REPLACE.items():
            if word not in text:
                continue

            parts = text.split(word)
            new_parts = [parts[0]]
            for part in parts[1:]:
                if self.rng.random() < aggressiveness:
                    # 优先选择使用次数少的替换
                    replacement = self._pick_diverse_replacement(word, replacements)
                    new_parts.append(replacement + part)
                    self._used_replacements[replacement] = self._used_replacements.get(replacement, 0) + 1
                else:
                    new_parts.append(word + part)
            text = "".join(new_parts)
        return text

    def _pick_diverse_replacement(self, word: str, replacements: list[str]) -> str:
        """选择使用次数最少的替换，避免全文重复。"""
        # 过滤掉英文错误项
        candidates = [r for r in replacements if r and not r.startswith(" ")]
        if not candidates:
            return ""
        if len(candidates) == 1:
            return candidates[0]
        # 按使用次数排序，优先选少的；相同则随机
        counts = {r: self._used_replacements.get(r, 0) for r in candidates}
        min_count = min(counts.values())
        best = [r for r, c in counts.items() if c == min_count]
        return self.rng.choice(best)

    # ------------------------------------------------------------------
    # "了"字连锁打断
    # ------------------------------------------------------------------
    def _break_le_chain(self, text: str, aggressiveness: float) -> str:
        """打断"了"字连锁：每2句最多保留1句含"了"。"""
        sentences = re.split(r"([。！？…；]+)", text)
        result = []
        le_count = 0
        for i in range(0, len(sentences) - 1, 2):
            sent = sentences[i]
            punct = sentences[i + 1] if i + 1 < len(sentences) else ""
            if "了" in sent:
                le_count += 1
                if le_count > 1 and self.rng.random() < aggressiveness:
                    rewritten = self._rewrite_le_sentence(sent)
                    # 仅当改写后语义仍通顺才采用（简单启发：长度不要暴跌）
                    if len(rewritten) >= len(sent) * 0.6:
                        sent = rewritten
                        le_count = 0 if "了" not in sent else 1
            else:
                le_count = 0
            result.append(sent + punct)
        return "".join(result)

    def _rewrite_le_sentence(self, sent: str) -> str:
        """改写含"了"的句子，尝试删除"了"或替换。"""
        # 策略1：把"V了"改为"V过"（只改一次，避免过度）
        sent = re.sub(r"(.)了([，。；！？])", r"\1过\2", sent, count=1)
        # 策略2：删除"了"（只改一次）
        if "了" in sent:
            sent = re.sub(r"(.)了(.{1,3})([，。；！？])", r"\1\2\3", sent, count=1)
        return sent

    # ------------------------------------------------------------------
    # 句长分布重排
    # ------------------------------------------------------------------
    def _reshuffle_sentence_length(self, text: str, aggressiveness: float) -> str:
        """句长分布重排：把等长句子打乱。"""
        sentences = re.split(r"([。！？…；]+)", text)
        result = []
        for i in range(0, len(sentences) - 1, 2):
            sent = sentences[i]
            punct = sentences[i + 1] if i + 1 < len(sentences) else ""
            cn_len = len(re.findall(r"[一-鿿]", sent))

            # 连续短句合并
            if cn_len < 12 and i > 0 and self.rng.random() < aggressiveness * 0.6:
                if result:
                    prev = result[-1].rstrip("。！？…；")
                    # 避免把对话和非对话硬合并
                    if self._can_merge(prev, sent):
                        result[-1] = prev + "，" + sent + punct
                        continue
            # 超长句拆分
            elif cn_len > 35 and self.rng.random() < aggressiveness * 0.6:
                mid = len(sent) // 2
                split_pos = max(
                    sent.rfind("，", mid - 15, mid + 15),
                    sent.rfind("、", mid - 15, mid + 15),
                )
                if split_pos > 0:
                    result.append(sent[:split_pos] + "。")
                    result.append(sent[split_pos + 1:] + punct)
                    continue
            result.append(sent + punct)
        return "".join(result)

    @staticmethod
    def _can_merge(prev: str, curr: str) -> bool:
        """判断两句是否可以合并。避免跨引号合并。"""
        prev_quotes = prev.count("\"") + prev.count("\"")
        curr_quotes = curr.count("\"") + curr.count("\"")
        if prev_quotes % 2 != 0 or curr_quotes % 2 != 0:
            return False
        return True

    # ------------------------------------------------------------------
    # 段落长度打乱
    # ------------------------------------------------------------------
    def _scramble_paragraphs(self, text: str, aggressiveness: float) -> str:
        """故意打乱段落长度，避免等长。"""
        paragraphs = text.split("\n")
        result = []
        for p in paragraphs:
            cn_len = len(re.findall(r"[一-鿿]", p))
            if cn_len > 0 and self.rng.random() < aggressiveness * 0.25:
                if cn_len > 45:
                    # 长段落变短：在合理位置切分
                    idx = p.find("。", 25)
                    if idx > 0:
                        result.append(p[: idx + 1])
                        p = p[idx + 1 :].strip()
            result.append(p)
        return "\n".join(result)

    # ------------------------------------------------------------------
    # 格式修复：引号配对
    # ------------------------------------------------------------------
    QUOTE_PAIRS = {
        "\"": "\"",
        "\"": "\"",
        "'": "'",
        "'": "'",
        "「": "」",
        "『": "』",
    }

    def _fix_dialogue_quotes(self, text: str) -> str:
        """修复对话引号的不匹配（最保守策略）。

        仅处理段落内部引号成对，不跨段落补引号。
        """
        lines = text.split("\n")
        fixed = []
        for line in lines:
            fixed_line = self._fix_line_quotes(line)
            fixed.append(fixed_line)
        return "\n".join(fixed)

    def _fix_line_quotes(self, line: str) -> str:
        """修复单行引号。仅修复简单场景：以开引号开头但没有闭引号。"""
        stripped = line.strip()
        if not stripped:
            return line

        # 如果整行以开引号 Western 开头，且没有闭引号，末尾补一个
        if stripped.startswith('"') and stripped.count('"') == 1 and not stripped.endswith('"'):
            return line + '"'
        if stripped.startswith("'") and stripped.count("'") == 1 and not stripped.endswith("'"):
            return line + "'"
        if stripped.startswith("「") and "」" not in stripped:
            return line + "」"
        if stripped.startswith("『") and "』" not in stripped:
            return line + "』"

        # 如果整行以非引号内容开头，但包含一个单独的开引号，且该行是对话行，尝试闭合
        if stripped.count('"') == 1 and '"' in stripped:
            #  conservatively add closing quote at line end only if line looks like dialogue
            if self._looks_like_dialogue(stripped):
                return line + '"'

        return line

    @staticmethod
    def _looks_like_dialogue(line: str) -> bool:
        """判断一行是否像对话。"""
        # 包含常见对话提示或口语词
        hints = ["？", "！", "吗", "呢", "吧", "啊", "了", "我", "你", "他"]
        return any(h in line for h in hints)

    # ------------------------------------------------------------------
    # 去重：连续相同连接词
    # ------------------------------------------------------------------
    @staticmethod
    def _deduplicate_conjunctions(text: str) -> str:
        """删除连续出现的相同过渡词/连接词。"""
        # 例如"然后然后"、"但是但是"
        for word in ["然后", "但是", "可是", "不过", "接着"]:
            text = re.sub(re.escape(word) + r"{2,}", word, text)
        return text

    # ------------------------------------------------------------------
    # AI 痕迹评分（含统计指纹指标）
    # ------------------------------------------------------------------
    @staticmethod
    def compute_ai_marker_score(text: str) -> dict[str, float]:
        """计算 AI 痕迹分数（0-1，越高越像 AI）并附加统计指纹指标。"""
        cn_chars = max(len(re.findall(r"[一-鿿]", text)), 1)
        scores: dict[str, float] = {}

        # 段落等长
        paragraphs = [p for p in text.split("\n") if p.strip()]
        para_lens = [len(re.findall(r"[一-鿿]", p)) for p in paragraphs]
        if len(para_lens) >= 5:
            mean_len = sum(para_lens) / len(para_lens)
            variance = sum((x - mean_len) ** 2 for x in para_lens) / len(para_lens)
            std = variance ** 0.5
            scores["paragraph_uniformity"] = max(0, 1 - std / 10)
        else:
            scores["paragraph_uniformity"] = 0

        # 过渡词密度
        transition_words = ["仿佛", "忽然", "竟然", "不禁", "宛如", "猛地"]
        total_transitions = sum(text.count(w) for w in transition_words)
        scores["transition_density"] = min(1, total_transitions / max(1, cn_chars / 3000))

        # "了"字密度
        le_count = text.count("了")
        scores["le_density"] = min(1, le_count / max(1, cn_chars / 100))

        # 禁用词密度
        forbidden = ["缓缓", "微微", "淡淡", "轻轻", "默默", "悄然", "莫名", "忽然"]
        total_forbidden = sum(text.count(w) for w in forbidden)
        scores["forbidden_density"] = min(1, total_forbidden / max(1, cn_chars / 2000))

        # 公式化转折
        formulaic = len(re.findall(r"不是……?而是……?|虽然.*但是.*却.*|明明.*却.*", text))
        scores["formulaic"] = min(1, formulaic / 3)

    # 统计指纹指标（perplexity / burstiness）
        optimizer = StatisticalFingerprintOptimizer()
        metrics = optimizer.compute_metrics(text)
        scores["perplexity"] = metrics.perplexity_score
        scores["burstiness"] = metrics.burstiness_score
        scores["overall_human_score"] = metrics.overall_human_score

        # 综合分数（加入统计指纹权重）
        # 传统指标权重 60%，统计指纹权重 40%
        traditional = [
            scores["paragraph_uniformity"],
            scores["transition_density"],
            scores["le_density"],
            scores["forbidden_density"],
            scores["formulaic"],
        ]
        traditional_avg = sum(traditional) / len(traditional)
        fingerprint = [
            1 - scores["perplexity"],  # perplexity越高越像人类，所以取反
            1 - scores["burstiness"],    # burstiness越高越像人类，所以取反
        ]
        fingerprint_avg = sum(fingerprint) / len(fingerprint)
        scores["total"] = round(traditional_avg * 0.6 + fingerprint_avg * 0.4, 3)
        return scores
