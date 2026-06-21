"""FanqieCourseGuard —— 番茄课程平台安全与人物规则检测。

可选 Guard：处理平台安全红线、人物标签禁用词等番茄课程规则。
默认 WARN 级别，不阻塞生成流程。
"""
from __future__ import annotations

from core.fanqie_course import load_fanqie_rules
from core.guards.base import BaseGuard, GuardResult


class FanqieCourseGuard(BaseGuard):
    """番茄课程规则检测：平台安全、人物标签等。"""

    guard_id = "fanqie_course"
    description = "番茄课程：平台安全红线、人物标签规则"
    default_level = "WARN"

    def __init__(self) -> None:
        self._fanqie_rules = load_fanqie_rules()

    def _check_platform_safety(self, content: str) -> list[str]:
        """检测平台安全红线话题。"""
        rules = self._fanqie_rules.get_platform_rules()
        redlines = rules.get("redline_topics", [])
        issues: list[str] = []
        for topic in redlines:
            if topic in content:
                issues.append(f"[平台安全] 内容涉及红线话题：{topic}")
        return issues

    def _check_character_traits(self, content: str) -> list[str]:
        """检测人物是否使用了扁平化、被禁止的标签词。"""
        rules = self._fanqie_rules.get_character_rules()
        forbidden_traits = rules.get("forbidden_flat_traits", [])
        issues: list[str] = []
        for trait in forbidden_traits:
            if trait in content:
                issues.append(f"[人物标签] 发现扁平化标签：{trait}，建议用行为/对话展现")
        return issues

    def run(self, content: str, context: dict) -> GuardResult:
        """执行番茄课程平台与人物规则检测。"""
        issues: list[str] = []
        issues.extend(self._check_platform_safety(content))
        issues.extend(self._check_character_traits(content))

        if issues:
            return GuardResult(
                guard_id=self.guard_id,
                level="WARN",
                message=f"发现 {len(issues)} 处番茄课程规则问题",
                metadata={"issues": issues},
            )
        return GuardResult(
            guard_id=self.guard_id,
            level="PASS",
            message="番茄课程规则检查通过",
            metadata={},
        )
