"""LoopController —— 基于 Loop Engineering 思想的写作循环控制器。

核心设计：
1. 目标清晰：用 ChapterGoal 把“好章节”翻译成可验证的完成条件。
2. 边界明确：定义绝对不能越过的护栏（情节丢失、字数暴跌、AI味回灌）。
3. 反馈及时：每次迭代后检查目标，失败则给出最小化修正路径。
4. 失败降级：主策略失败后，有备用策略避免卡死。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from core.content.metrics import count_chinese_chars
from core.writing.style_rule_engine import StyleRuleEngine

logger = logging.getLogger("novel-os.loop")


@dataclass
class ChapterGoal:
    """章节完成目标 —— 必须可验证、可量化。

    修复说明（2026-06-20）：
    原默认 word_min=1900, word_max=2600 与 book.yaml 的 4500 字标准严重不一致，
    导致 LoopController 认为 2600 字就达标，但 QualityGates 要 4050 字才放行。
    现默认值改为 4050/4950（对齐 book.yaml words_per_chapter=4500 ± 450），
    并支持 from_book_config() 工厂方法从 book_config 动态计算。
    """

    word_min: int = 4050
    word_max: int = 4950
    max_rule_score: float = 0.25
    max_not_x_but_y: int = 0
    max_xiang: int = 3
    require_ending_hook: bool = True
    dialogue_ratio_range: tuple[float, float] = (0.15, 0.55)
    max_cn_number_density: float = 0.08  # 每千中文字允许的中文数词数
    boundaries: list[str] = field(default_factory=lambda: [
        "禁止删除情节、人物或核心事件以满足指标",
        "禁止丢失章末悬念钩子",
        "禁止通过扩写环境/心理来凑字数",
        "Polish 后规则评分不能上升",
    ])

    def __post_init__(self):
        """外层回路覆盖：读取 rule_overrides.json（如果存在）。"""
        try:
            from core.outer_loop.rule_config import load_overrides
            overrides = load_overrides()
            if "ChapterGoal.word_min" in overrides:
                self.word_min = overrides["ChapterGoal.word_min"]
            if "ChapterGoal.word_max" in overrides:
                self.word_max = overrides["ChapterGoal.word_max"]
            if "ChapterGoal.max_rule_score" in overrides:
                self.max_rule_score = overrides["ChapterGoal.max_rule_score"]
            if "ChapterGoal.max_cn_number_density" in overrides:
                self.max_cn_number_density = overrides["ChapterGoal.max_cn_number_density"]
        except Exception:
            pass  # 外层回路模块不可用时使用默认值

    @classmethod
    def from_book_config(cls, book_config: Any) -> "ChapterGoal":
        """从 book_config 动态计算字数目标。

        word_min = words_per_chapter - words_tolerance
        word_max = words_per_chapter + words_tolerance

        注意：book_config 的值优先于 rule_overrides.json 中的 ChapterGoal 覆盖，
        因为字数目标应该跟随 book.yaml 配置，不应被外层回路的旧覆盖值锁死。
        """
        target = getattr(book_config, "words_per_chapter", 4500)
        tol = getattr(book_config, "words_tolerance", 450)
        goal = cls()  # 先用默认值初始化（__post_init__ 会读 rule_overrides）
        # ★ book_config 值强制覆盖 rule_overrides 中的旧值
        goal.word_min = target - tol
        goal.word_max = target + tol
        return goal


@dataclass
class GoalCheckResult:
    """目标检查结果。"""

    passed: bool
    score: dict[str, Any]
    failed_checks: list[str]
    boundary_violations: list[str]
    fallback: str = ""  # 推荐 fallback 策略


class LoopController:
    """章节写作循环控制器。"""

    def __init__(self, goal: ChapterGoal | None = None) -> None:
        self.goal = goal or ChapterGoal()
        self.engine = StyleRuleEngine()

    def check(self, text: str, dialogue_ratio: float | None = None) -> GoalCheckResult:
        """检查文本是否满足章节完成目标。"""
        wc = count_chinese_chars(text)
        rule_result = self.engine.score(text)
        scores = rule_result["score"]
        breakdown = rule_result.get("breakdown", {})

        failed: list[str] = []
        boundaries: list[str] = []

        # P0: 字数
        if wc < self.goal.word_min:
            failed.append(f"字数不足: {wc} < {self.goal.word_min}")
        elif wc > self.goal.word_max:
            failed.append(f"字数超标: {wc} > {self.goal.word_max}")

        # P0: 综合 AI 味评分
        if scores["total"] > self.goal.max_rule_score:
            failed.append(f"AI味评分 {scores['total']:.3f} > {self.goal.max_rule_score}")

        # P0: 禁用句式
        not_x_but_y = self.engine.count_not_x_but_y(text)
        if not_x_but_y > self.goal.max_not_x_but_y:
            failed.append(f"'不是X，是Y' {not_x_but_y} 处 > {self.goal.max_not_x_but_y}")

        # P0: 比喻数量
        xiang = self.engine.count_xiang(text)
        if xiang > self.goal.max_xiang:
            failed.append(f"'像…'比喻 {xiang} 处 > {self.goal.max_xiang}")

        # P0: 章末钩子
        if self.goal.require_ending_hook and not self.engine.has_ending_hook(text):
            failed.append("章末未检测到悬念钩子")

        # P1: 对话占比（边界较宽，仅作为 WARN 不阻塞）
        if dialogue_ratio is not None:
            lo, hi = self.goal.dialogue_ratio_range
            if not (lo <= dialogue_ratio <= hi):
                failed.append(f"对话占比 {dialogue_ratio:.1%} 不在 [{lo:.0%}, {hi:.0%}]")

        # P1: 中文数词密度
        cn_density = rule_result.get("cn_number_density", 0)
        if cn_density > self.goal.max_cn_number_density * 1000:
            failed.append(f"中文数词密度 {cn_density}/千字 > {self.goal.max_cn_number_density * 1000:.0f}/千字")

        # 推荐 fallback
        fallback = self._recommend_fallback(failed)

        return GoalCheckResult(
            passed=len(failed) == 0,
            score={
                "word_count": wc,
                "rule_score": scores["total"],
                "not_x_but_y": not_x_but_y,
                "xiang": xiang,
                "ending_hook": self.engine.has_ending_hook(text),
                "cn_number_density": cn_density,
                "dialogue_ratio": dialogue_ratio,
            },
            failed_checks=failed,
            boundary_violations=boundaries,
            fallback=fallback,
        )

    def check_boundary(self, before: str, after: str, step_name: str) -> list[str]:
        """检查某一步是否触发了护栏（回灌 AI 味、丢失钩子等）。"""
        violations: list[str] = []

        before_score = self.engine.score(before)["score"]["total"]
        after_score = self.engine.score(after)["score"]["total"]
        if after_score > before_score + 0.03:
            violations.append(
                f"{step_name} 后 AI 味评分上升 {before_score:.3f} -> {after_score:.3f}"
            )

        before_hook = self.engine.has_ending_hook(before)
        after_hook = self.engine.has_ending_hook(after)
        if before_hook and not after_hook:
            violations.append(f"{step_name} 后丢失章末悬念钩子")

        before_wc = count_chinese_chars(before)
        after_wc = count_chinese_chars(after)
        if before_wc > 0 and after_wc < before_wc * 0.85:
            violations.append(
                f"{step_name} 后字数流失 {(1 - after_wc / before_wc) * 100:.1f}%"
            )

        return violations

    @staticmethod
    def _recommend_fallback(failed: list[str]) -> str:
        """根据失败项推荐 fallback 策略。"""
        if any("字数不足" in f for f in failed):
            return "expander"
        if any("字数超标" in f for f in failed):
            return "truncate"
        if any("AI味评分" in f or "不是X" in f or "像…" in f for f in failed):
            return "style_critic_strict"
        if any("章末" in f for f in failed):
            return "hook_engineer"
        if any("数词密度" in f for f in failed):
            return "outline_dequantify"
        if any("对话占比" in f for f in failed):
            return "dialogue_tuner"
        return "full_retry"


