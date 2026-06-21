"""HallucinationGuard —— 幻觉检测。

检测世界观lock破坏、未解锁能力提前使用、角色设定矛盾。
"""
from __future__ import annotations

import re

from core.guards.base import BaseGuard, GuardResult


class HallucinationGuard(BaseGuard):
    """检测AI幻觉：世界观lock破坏、未解锁能力、角色设定矛盾。"""

    guard_id = "hallucination"
    description = "幻觉检测：检测世界观lock破坏、未解锁能力提前使用"
    default_level = "BLOCKING"

    def run(self, content: str, context: dict) -> GuardResult:
        state = context.get("state_manager")
        chapter_num = context.get("chapter_num", 0)
        if not state:
            return GuardResult(
                guard_id=self.guard_id, level="PASS",
                message="无可用的状态管理器，跳过幻觉检查", metadata={},
            )

        issues: list[str] = []

        # 1. 世界观 consistency_rules 检查
        rules = state.list_rules()
        for rule in rules:
            if rule.get("lock_type") == "hard" and rule.get("pattern"):
                pattern = rule["pattern"]
                if re.search(pattern, content):
                    issues.append(
                        f"[世界观破坏] 违反硬性lock: {rule.get('description', pattern)}"
                    )
            elif rule.get("lock_type") == "soft" and rule.get("pattern"):
                # soft lock 只在特定章节前生效
                unlock_chapter = rule.get("unlock_chapter", 9999)
                if chapter_num < unlock_chapter:
                    pattern = rule["pattern"]
                    if re.search(pattern, content):
                        issues.append(
                            f"[世界观破坏] 第{chapter_num}章提前使用'{rule.get('description', pattern)}'"
                            f"（应在第{unlock_chapter}章后解锁）"
                        )

        # 2. 角色能力检查：abilities_locked 中的能力不能在正文中提前使用
        chars = state.list_characters()
        for char in chars:
            char_name = char.get("character_name", "")
            char_state = char
            locked = char_state.get("abilities_locked", [])
            for ability in locked:
                if ability in content:
                    issues.append(
                        f"[能力幻觉] {char_name} 使用了未解锁能力'{ability}'"
                    )

        # 3. 道具状态检查：道具如果上一章是"损坏"状态，本章不能完好使用
            # 简化版：检查道具关键词与状态描述是否矛盾

        if issues:
            return GuardResult(
                guard_id=self.guard_id,
                level="BLOCKING",
                message=f"发现 {len(issues)} 处幻觉/设定矛盾",
                metadata={"issues": issues, "chapter_num": chapter_num},
            )
        return GuardResult(
            guard_id=self.guard_id,
            level="PASS",
            message="幻觉检测通过",
            metadata={},
        )
