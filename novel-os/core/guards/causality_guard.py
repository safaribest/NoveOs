"""CausalityGuard —— 场景因果检测。

检测"没有原因的结果"（突然开挂、莫名反转、事件无铺垫）。
当前实现为轻量规则版，后续可升级为LLM版。
"""
from __future__ import annotations

import re

from core.guards.base import BaseGuard, GuardResult


class CausalityGuard(BaseGuard):
    """检测场景因果：是否存在没有铺垫的结果或突然反转。"""

    guard_id = "causality"
    description = "场景因果：检测突然开挂、莫名反转、无铺垫事件"
    default_level = "WARN"

    # 无铺垫结果的高危词
    SUDDEN_TURNS = ["突然", "莫名其妙", "不知为何", "毫无预兆", "凭空",
                    "莫名其妙地", "不知怎的", "不知怎么回事"]
    # 开挂类关键词
    CHEAT_KEYWORDS = ["瞬间领悟", "突然觉醒", "天赋异禀", "无师自通",
                      "莫名其妙变强", "突然会了", "意外获得"]
    # 因果断裂模式
    CAUSALITY_BREAK = ["虽然.*但是.*却.*", "明明.*却.*", "已经.*却.*"]

    def run(self, content: str, context: dict) -> GuardResult:
        issues: list[str] = []

        # 1. 检测无铺垫结果词
        for word in self.SUDDEN_TURNS:
            if word in content:
                # 找到上下文，检查是否有前文铺垫（简化：只计数）
                count = content.count(word)
                if count >= 3:
                    issues.append(f"[无铺垫结果] '{word}'出现{count}次，可能存在过多无因事件")

        # 2. 检测开挂关键词
        for word in self.CHEAT_KEYWORDS:
            if word in content:
                issues.append(f"[突兀开挂] 发现'{word}'，主角能力提升缺少铺垫过程")

        # 3. 检测因果断裂句式
        for pattern in self.CAUSALITY_BREAK:
            matches = re.findall(pattern, content)
            if len(matches) >= 2:
                issues.append(f"[因果断裂] 发现{len(matches)}处转折矛盾句式，逻辑可能不通")

        # 4. 检测连续事件无连接词
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs[1:], 1):
            # 如果一段全是动作但没有因果连接，且与前段场景突变
            if len(para) > 100 and not any(c in para[:30] for c in ["因为", "于是", "因此", "所以", "接着", "随后"]):
                prev_para = paragraphs[i - 1]
                # 简单判断场景是否突变（地点/人物变化）
                if self._scene_shift(prev_para, para):
                    issues.append(f"[场景跳切] 第{i+1}段与前段场景突变但无过渡连接")

        if issues:
            return GuardResult(
                guard_id=self.guard_id,
                level="WARN",
                message=f"发现 {len(issues)} 处因果/逻辑问题",
                metadata={"issues": issues},
            )
        return GuardResult(
            guard_id=self.guard_id,
            level="PASS",
            message="场景因果检查通过",
            metadata={},
        )

    @staticmethod
    def _scene_shift(prev: str, curr: str) -> bool:
        """简化判断两段是否发生了场景跳切。"""
        location_markers = ["在", "来到", "走进", "离开", "回到", "抵达"]
        prev_has_loc = any(m in prev for m in location_markers)
        curr_has_loc = any(m in curr for m in location_markers)
        # 如果前段有地点描写，当前段也有地点描写，且没有共享地点关键词
        if prev_has_loc and curr_has_loc:
            # 极度简化：如果有明确地点词变化则视为跳切
            common_locations = ["家里", "公司", "学校", "医院", "街上"]
            prev_locs = [loc for loc in common_locations if loc in prev]
            curr_locs = [loc for loc in common_locations if loc in curr]
            if prev_locs and curr_locs and not set(prev_locs) & set(curr_locs):
                return True
        return False
