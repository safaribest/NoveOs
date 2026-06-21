"""ReaderPullGuard —— 读者拉力检测。

检测段落过长无对话、信息密度过低、节奏拖沓、开篇/结尾钩子、爽点密度。
"""
from __future__ import annotations

import re

from core.fanqie_course import load_fanqie_rules
from core.guards.base import BaseGuard, GuardResult


class ReaderPullGuard(BaseGuard):
    """检测读者拉力：段落过长、信息密度低、节奏拖沓、钩子与爽点密度。"""

    guard_id = "reader_pull"
    description = "读者拉力：检测段落过长无对话、信息密度过低、钩子与爽点密度"
    default_level = "WARN"

    def __init__(self) -> None:
        self._fanqie_rules = load_fanqie_rules()

    def _check_opening_hook(self, content: str, chapter_num: int) -> list[str]:
        """检测开篇钩子与禁用模式（仅对前 3 章生效）。"""
        opening = self._fanqie_rules.get_opening_rules()
        active_chapters = opening.get("active_chapters", [1, 2, 3])
        if chapter_num not in active_chapters:
            return []

        max_lead = opening.get("max_lead_in_words", 300)
        lead_in = content[:max_lead]
        hook_markers = opening.get("hook_markers", [])
        forbidden_patterns = opening.get("forbidden_patterns", [])
        issues: list[str] = []

        if not any(marker in lead_in for marker in hook_markers):
            issues.append(
                f"[开篇缺钩子] 前 {max_lead} 字未检测到冲突/悬念/转折"
            )

        for pattern in forbidden_patterns:
            indicators = pattern.get("indicators", [])
            if any(ind in lead_in for ind in indicators):
                issues.append(f"[开篇禁用模式] {pattern.get('name', '')}")

        return issues

    def _check_ending_hook(self, content: str) -> list[str]:
        """检测章节末是否留下未解问题或下一章诱惑。"""
        beat = self._fanqie_rules.get_chapter_beat_rules()
        if not beat.get("ending_hook_required", True):
            return []

        zone = beat.get("ending_hook_zone", 200)
        ending_zone = content[-zone:] if len(content) >= zone else content
        markers = beat.get("ending_hook_markers", [])
        if not any(marker in ending_zone for marker in markers):
            return [
                f"[章节末缺钩子] 最后 {zone} 字未留下未解问题或下一章诱惑"
            ]
        return []

    def _check_climax_density(self, content: str) -> list[str]:
        """检测爽点/高潮关键词密度是否达标。

        修复说明（2026-06-20）：按段落去重，每段每个关键词最多计1次，
        避免同段重复刷分。
        """
        # 过短的文本（如单元测试桩）不触发爽点密度检测，避免误报
        if len(content) < 200:
            return []

        beat = self._fanqie_rules.get_chapter_beat_rules()
        min_climax = beat.get("min_climax_per_chapter", 1)
        keywords = beat.get("climax_keywords", [])
        # ★ 按段落去重计数
        paragraphs = [p for p in content.split("\n") if p.strip()]
        count = 0
        for para in paragraphs:
            for kw in keywords:
                if kw in para:
                    count += 1
                    break  # 每段最多计1次
        if count < min_climax:
            return [
                f"[爽点不足] 本章仅检测到 {count} 处情绪爆点标记，建议 ≥{min_climax}"
            ]
        return []

    def run(self, content: str, context: dict) -> GuardResult:
        issues: list[str] = []
        chapter_num = context.get("chapter_num", 0)

        # 1. 检测超长叙述段落（>300字无对话）
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            para_len = len(para)
            # 判断是否包含对话（简化：包含引号）
            has_dialogue = '"' in para or '"' in para or '"' in para or '"' in para
            if para_len > 300 and not has_dialogue:
                issues.append(f"[叙述冗长] 第{i+1}段 {para_len} 字无对话，读者容易疲劳")

        # 2. 检测信息密度：连续3段都是纯描写（无动作/无对话/无冲突）
        pure_desc_count = 0
        for i, para in enumerate(paragraphs):
            has_action = any(v in para for v in ["打", "杀", "跑", "追", "喊", "骂", "笑", "哭"])
            has_conflict = any(v in para for v in ["但", "却", "不过", "然而", "反对", "拒绝", "质问"])
            has_dialogue = '"' in para or '"' in para
            if not has_action and not has_conflict and not has_dialogue and len(para) > 50:
                pure_desc_count += 1
                if pure_desc_count >= 3:
                    issues.append(f"[信息密度低] 第{i-1}~{i+1}段连续纯描写，缺少动作/冲突/对话")
                    pure_desc_count = 0
            else:
                pure_desc_count = 0

        # 3. 检测重复信息（同一段落内关键词高频重复）
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', content)
        from collections import Counter
        word_counts = Counter(words)
        repeated = [(w, c) for w, c in word_counts.most_common(10) if c >= 8 and len(w) >= 2]
        if repeated:
            issues.append(f"[词汇重复] 高频重复词: {', '.join(f'{w}({c}次)' for w, c in repeated[:3])}")

        # 4. 检测节奏拖沓：连续多段以"了""着""过"结尾
        weak_endings = 0
        for para in paragraphs:
            if para.endswith(("。", "着。", "过。", "起来。", "下去。")):
                weak_endings += 1
        if weak_endings >= len(paragraphs) * 0.5 and len(paragraphs) >= 5:
            issues.append(f"[节奏拖沓] {weak_endings}/{len(paragraphs)}段以弱化动词结尾，节奏偏慢")

        # 5. 番茄课程：开篇钩子检测
        issues.extend(self._check_opening_hook(content, chapter_num))

        # 6. 番茄课程：章节末钩子检测
        issues.extend(self._check_ending_hook(content))

        # 7. 番茄课程：爽点密度检测
        issues.extend(self._check_climax_density(content))

        if issues:
            return GuardResult(
                guard_id=self.guard_id,
                level="WARN",
                message=f"发现 {len(issues)} 处读者拉力问题",
                metadata={"issues": issues},
            )
        return GuardResult(
            guard_id=self.guard_id,
            level="PASS",
            message="读者拉力检查通过",
            metadata={},
        )
