"""ContinuityGuard —— 跨章连续性检查。

检测人物位置/道具状态/情绪的突变，防止"写到后面忘了前面"。
"""
from __future__ import annotations

from core.guards.base import BaseGuard, GuardResult


class ContinuityGuard(BaseGuard):
    """检查本章与上一章的连续性：人物位置、道具状态、情绪是否出现不合理跳变。"""

    guard_id = "continuity"
    description = "跨章连续性：检测人物位置/道具状态/情绪突变"
    default_level = "BLOCKING"

    def run(self, content: str, context: dict) -> GuardResult:
        state = context.get("state_manager")
        chapter_num = context.get("chapter_num", 0)
        if not state or chapter_num <= 1:
            return GuardResult(
                guard_id=self.guard_id,
                level="PASS",
                message="首章或无可用的状态管理器，跳过连续性检查",
                metadata={},
            )

        issues: list[str] = []

        # 1. 人物位置突变检查
        prev_chars = state.list_characters(chapter_num - 1)
        curr_chars = state.list_characters(chapter_num)
        for char_name, prev_state in prev_chars.items():
            curr_state = curr_chars.get(char_name)
            if not curr_state:
                continue
            prev_loc = prev_state.get("location", "")
            curr_loc = curr_state.get("location", "")
            if prev_loc and curr_loc and prev_loc != curr_loc:
                # 允许合理的场景切换（如"北京→上海"需要铺垫）
                # 简化：如果正文中没有出现位置切换描写，则标记
                if curr_loc not in content and prev_loc not in content:
                    issues.append(
                        f"[位置跳变] {char_name}: 上章在'{prev_loc}'，本章在'{curr_loc}'，"
                        f"但正文中未提及位置变化"
                    )

        # 2. 道具状态突变检查
        prev_items = state.list_items(chapter_num - 1)
        curr_items = state.list_items(chapter_num)
        for item_name, prev_state in prev_items.items():
            curr_state = curr_items.get(item_name)
            if not curr_state:
                continue
            prev_status = prev_state.get("status", "")
            curr_status = curr_state.get("status", "")
            if prev_status and curr_status and prev_status != curr_status:
                if item_name not in content:
                    issues.append(
                        f"[道具跳变] {item_name}: 状态从'{prev_status}'变为'{curr_status}'，"
                        f"但正文中未提及"
                    )

        # 3. 情绪剧烈跳变检查
        for char_name, prev_state in prev_chars.items():
            curr_state = curr_chars.get(char_name)
            if not curr_state:
                continue
            prev_emo = prev_state.get("emotional_state", "")
            curr_emo = curr_state.get("emotional_state", "")
            # 简单规则：愤怒→平静 或 平静→狂喜 需要过渡
            drastic_swings = {
                ("愤怒", "平静"), ("平静", "狂喜"), ("悲伤", "兴奋"),
                ("恐惧", "镇定"), ("绝望", "希望"),
            }
            if (prev_emo, curr_emo) in drastic_swings:
                issues.append(
                    f"[情绪跳变] {char_name}: 从'{prev_emo}'直接变为'{curr_emo}'，缺少过渡描写"
                )

        if issues:
            return GuardResult(
                guard_id=self.guard_id,
                level="BLOCKING",
                message=f"发现 {len(issues)} 处连续性问题",
                metadata={"issues": issues, "chapter_num": chapter_num},
            )
        return GuardResult(
            guard_id=self.guard_id,
            level="PASS",
            message="跨章连续性检查通过",
            metadata={},
        )
