"""VoiceConsistencyGuard —— 角色声音一致性检测。

检测角色对话指纹漂移：霸总不能说网络梗，古言角色不能说现代词汇。
"""
from __future__ import annotations

import re

from core.guards.base import BaseGuard, GuardResult


class VoiceConsistencyGuard(BaseGuard):
    """检测角色声音一致性：对话指纹是否漂移。"""

    guard_id = "voice_consistency"
    description = "声音一致性：检测角色对话指纹漂移"
    default_level = "WARN"

    # 时代错位词库（可扩展）
    ANACHRONISMS = {
        "古代": ["手机", "电脑", "互联网", "二维码", "高铁", "外卖", "直播",
                "OK", "拜拜", "拜拜了", "拜拜您嘞", "老铁", "666", "yyds"],
        "民国": ["手机", "互联网", "二维码", "高铁", "直播", "yyds"],
        "70年代": ["互联网", "二维码", "直播", "外卖", "yyds", "老铁"],
    }

    def run(self, content: str, context: dict) -> GuardResult:
        state = context.get("state_manager")
        chapter_num = context.get("chapter_num", 0)
        genre = context.get("genre", "")
        if not state:
            return GuardResult(
                guard_id=self.guard_id, level="PASS",
                message="无可用的状态管理器，跳过声音一致性检查", metadata={},
            )

        issues: list[str] = []

        # 1. 检测时代错位词
        era = self._detect_era(genre)
        if era and era in self.ANACHRONISMS:
            banned = self.ANACHRONISMS[era]
            for word in banned:
                if word in content:
                    # 检查是否在对话中
                    dialogues = re.findall(r'[""""]([^""""]+)[""""]', content)
                    for dialogue in dialogues:
                        if word in dialogue:
                            issues.append(f"[时代错位] 对话中出现'{word}'，与{era}背景不符")
                            break

        # 2. 检测角色对话指纹漂移
        chars = state.list_characters()
        for char in chars:
            char_name = char.get("character_name", "")
            char_state = char
            fingerprint = char_state.get("dialog_fingerprint", "")
            if not fingerprint:
                continue
            # 提取该角色在本章的对话
            dialogues = self._extract_character_dialogues(content, char_name)
            if not dialogues:
                continue
            # 检查指纹特征是否在对话中体现
            fingerprint_traits = fingerprint.split(",")
            missing_traits = []
            for trait in fingerprint_traits:
                trait = trait.strip()
                if trait and not any(trait in d for d in dialogues):
                    missing_traits.append(trait)
            if missing_traits and len(dialogues) >= 3:
                issues.append(
                    f"[声音漂移] {char_name}: 对话指纹'{fingerprint}'中的"
                    f"'{', '.join(missing_traits[:2])}'未体现（本章{len(dialogues)}句对话）"
                )

        # 3. 检测所有角色说话风格趋同（简单版：统计高频口头禅）
        all_dialogues = re.findall(r'[""""]([^""""]+)[""""]', content)
        if len(all_dialogues) >= 6:
            common_phrases = ["好的", "知道了", "明白了", "没问题", "可以"]
            for phrase in common_phrases:
                count = sum(1 for d in all_dialogues if phrase in d)
                if count >= len(all_dialogues) * 0.5:
                    issues.append(f"[风格趋同] 超过半数角色使用'{phrase}'，对话缺乏差异化")
                    break

        if issues:
            return GuardResult(
                guard_id=self.guard_id,
                level="WARN",
                message=f"发现 {len(issues)} 处声音一致性问题",
                metadata={"issues": issues},
            )
        return GuardResult(
            guard_id=self.guard_id,
            level="PASS",
            message="声音一致性检查通过",
            metadata={},
        )

    @staticmethod
    def _detect_era(genre: str) -> str | None:
        """从genre中检测时代背景。"""
        if any(k in genre for k in ["古代", "古言", "仙侠", "武侠", "穿越古代"]):
            return "古代"
        if any(k in genre for k in ["民国", "抗战", "谍战"]):
            return "民国"
        if any(k in genre for k in ["70年代", "80年代", "90年代", "年代", "重生", "穿越"]) and "古代" not in genre:
            return "70年代"
        return None

    @staticmethod
    def _extract_character_dialogues(content: str, char_name: str) -> list[str]:
        """提取某角色的对话（简化：角色名后出现引号的对话）。"""
        dialogues = []
        # 支持中文引号 "" 和英文引号 ""
        for quote_open, quote_close in [('"', '"'), ('"', '"'), ('"', '"'), ('"', '"'), ('「', '」'), ('『', '』')]:
            pattern = re.compile(
                re.escape(char_name) + r'[说道问道答喊骂冷笑怒].{0,5}' + re.escape(quote_open) + r'([^' + re.escape(quote_close) + r']+)' + re.escape(quote_close)
            )
            matches = pattern.findall(content)
            dialogues.extend(matches)
        return dialogues
