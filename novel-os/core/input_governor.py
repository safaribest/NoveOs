"""InputGovernor —— 输入治理层（对标 InkOS plan → compose → write）。

在 Director 之后、Writer 之前运行：
1. 从全量状态库中筛选本章最相关的上下文
2. 编译规则栈（MUST > SHOULD > NICE，去冲突去冗余）
3. 生成本章意图（must-keep / must-avoid）
4. 输出精简后的 prompt 产物，控制 Writer 的输入长度
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config_loader import BookConfig
from core.state_manager import StateManager

logger = logging.getLogger("novel-os.input_governor")


@dataclass
class ChapterIntent:
    """本章意图——Planner 的产物。"""
    must_keep: list[str] = field(default_factory=list)
    must_avoid: list[str] = field(default_factory=list)
    core_event: str = ""
    emotion_target: str = ""
    word_target: int = 4500
    iwr_target: float = 2.5


@dataclass
class RuleStack:
    """编译后的规则栈——Composer 的产物。"""
    must_rules: list[str] = field(default_factory=list)
    should_rules: list[str] = field(default_factory=list)
    nice_rules: list[str] = field(default_factory=list)
    overrides: list[str] = field(default_factory=list)  # 本章特殊覆盖


@dataclass
class CompiledContext:
    """编译后的上下文——注入 Writer 的全部输入。"""
    intent: ChapterIntent = field(default_factory=ChapterIntent)
    rule_stack: RuleStack = field(default_factory=RuleStack)
    character_context: str = ""           # 精简人物状态
    foreshadowing_context: str = ""       # 相关伏笔
    debt_context: str = ""                # 相关债务
    recent_summary: str = ""              # 最近 3 章摘要
    runtime_trace: dict[str, Any] = field(default_factory=dict)

    def format_writer_prompt(self) -> str:
        """把编译产物格式化为 Writer 的 user prompt。"""
        parts = []

        # 意图
        intent = self.intent
        parts.append("【本章意图】")
        parts.append(f"核心事件：{intent.core_event}")
        if intent.must_keep:
            parts.append("必须保留：")
            for item in intent.must_keep:
                parts.append(f"  - {item}")
        if intent.must_avoid:
            parts.append("必须避免：")
            for item in intent.must_avoid:
                parts.append(f"  - {item}")
        parts.append(f"情绪目标：{intent.emotion_target}")
        parts.append("")

        # 规则栈
        stack = self.rule_stack
        parts.append("【规则栈——优先级从高到低】")
        parts.append("MUST（违反即作废）：")
        for r in stack.must_rules:
            parts.append(f"  ★ {r}")
        parts.append("SHOULD（尽量满足）：")
        for r in stack.should_rules:
            parts.append(f"  ○ {r}")
        if stack.nice_rules:
            parts.append("NICE（有余力再做）：")
            for r in stack.nice_rules:
                parts.append(f"  □ {r}")
        if stack.overrides:
            parts.append("本章特殊覆盖：")
            for r in stack.overrides:
                parts.append(f"  → {r}")
        parts.append("")

        # 上下文
        parts.append("【相关上下文】")
        if self.recent_summary:
            parts.append(self.recent_summary)
            parts.append("")
        if self.character_context:
            parts.append(self.character_context)
            parts.append("")
        if self.foreshadowing_context:
            parts.append(self.foreshadowing_context)
            parts.append("")
        if self.debt_context:
            parts.append(self.debt_context)
            parts.append("")

        return "\n".join(parts)


class InputGovernor:
    """输入治理器：从全量状态库中编译 Writer 的精简输入。"""

    def __init__(
        self,
        book_config: BookConfig,
        state_manager: StateManager,
    ) -> None:
        self.cfg = book_config
        self.state = state_manager

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def compile(self, chapter_num: int, director_task_card: str = "") -> CompiledContext:
        """编译本章输入。

        Args:
            chapter_num: 本章编号
            director_task_card: Director Agent 产出的任务卡（可选）

        Returns:
            CompiledContext: 精简后的全部输入
        """
        logger.info("[InputGovernor] 编译第 %d 章输入", chapter_num)

        ctx = CompiledContext()

        # 1. 意图（Planner 层）
        ctx.intent = self._compile_intent(chapter_num, director_task_card)

        # 2. 规则栈（Composer 层）
        ctx.rule_stack = self._compile_rule_stack(chapter_num)

        # 3. 上下文裁剪（Composer 层）
        ctx.character_context = self._select_characters(chapter_num)
        ctx.foreshadowing_context = self._select_foreshadowing(chapter_num)
        ctx.debt_context = self._select_debts(chapter_num)
        ctx.recent_summary = self._select_recent_summaries(chapter_num)

        # 4. 运行时痕迹
        ctx.runtime_trace = {
            "chapter_num": chapter_num,
            "selected_chars": len(ctx.character_context.splitlines()),
            "selected_fs": len(ctx.foreshadowing_context.splitlines()),
            "selected_debts": len(ctx.debt_context.splitlines()),
            "total_chars": sum(len(x) for x in [
                ctx.character_context, ctx.foreshadowing_context,
                ctx.debt_context, ctx.recent_summary
            ]),
        }

        logger.info(
            "[InputGovernor] 第 %d 章编译完成: 意图=%s字, 人物=%d行, 伏笔=%d行, 债务=%d行",
            chapter_num,
            len(ctx.intent.core_event),
            len(ctx.character_context.splitlines()),
            len(ctx.foreshadowing_context.splitlines()),
            len(ctx.debt_context.splitlines()),
        )
        return ctx

    # ------------------------------------------------------------------
    # 意图编译（Planner 层）
    # ------------------------------------------------------------------
    def _compile_intent(self, chapter_num: int, director_task_card: str) -> ChapterIntent:
        """编译本章意图。"""
        intent = ChapterIntent(word_target=self.cfg.words_per_chapter)

        # 从大纲提取核心事件
        outline = self.state.list_outline()
        chapter_outline = next((o for o in outline if o.get("chapter") == chapter_num), None)
        if chapter_outline:
            intent.core_event = chapter_outline.get("core_event", "")
            intent.emotion_target = chapter_outline.get("emotion", "")
            # must-keep / must-avoid 从大纲的约束提取
            constraints = chapter_outline.get("constraints", [])
            for c in constraints:
                if c.startswith("!"):
                    intent.must_avoid.append(c[1:])
                else:
                    intent.must_keep.append(c)

        # 从 Director 任务卡补充
        if director_task_card:
            # 简单提取：找 "必须" "禁止" 等关键词
            for line in director_task_card.splitlines():
                line = line.strip()
                if "必须保留" in line or "must keep" in line.lower():
                    intent.must_keep.append(line.split("：", 1)[-1].strip()[:100])
                elif "必须避免" in line or "must avoid" in line.lower():
                    intent.must_avoid.append(line.split("：", 1)[-1].strip()[:100])
                elif "核心事件" in line:
                    intent.core_event = line.split("：", 1)[-1].strip()[:200]

        # 字数目标
        try:
            spec = self.state.get_chapter_spec(chapter_num, "target_words")
            if spec:
                intent.word_target = int(spec.get("spec_value", self.cfg.words_per_chapter))
        except Exception:
            pass

        # IWR 目标
        intent.iwr_target = getattr(self.cfg, "iwr_target", 2.5)

        return intent

    # ------------------------------------------------------------------
    # 规则栈编译（Composer 层）
    # ------------------------------------------------------------------
    def _compile_rule_stack(self, chapter_num: int) -> RuleStack:
        """编译规则栈。"""
        stack = RuleStack()

        # MUST：字数、他密度、IWR
        w = self.cfg.words_per_chapter
        tol = getattr(self.cfg, "tolerance", 450)
        stack.must_rules.append(f"字数：{w - tol} ~ {w + tol} 中文字")
        stack.must_rules.append("他密度 < 10%（优先用角色全名或省略主语）")
        stack.must_rules.append(f"IWR ≥ 2.5（认知缺口 ≥5 个，揭示词 ≤3 个）")
        stack.must_rules.append("禁用词总计 ≤3 次")

        # SHOULD：句长、对话、感官
        stack.should_rules.append("句长均值 22-28 字，禁止连续 3 个短句")
        stack.should_rules.append("对话占比 25%-45%，对话簇 ≤3 段")
        stack.should_rules.append("每 500 字 ≥1 处五感细节")
        stack.should_rules.append("章末最后 50 字留悬念")

        # NICE：比喻、排版
        stack.nice_rules.append("比喻 ≤3 处，绑定主角经历")
        stack.nice_rules.append("每段 15-25 字")

        # 本章特殊覆盖（从 chapter_specs 读取）
        try:
            spec_type = self.state.get_chapter_spec(chapter_num, "chapter_type")
            if spec_type:
                ctype = spec_type.get("spec_value", "")
                if ctype == "钩子章":
                    stack.overrides.append("开头 50 字必须抛悬念，结尾 100 字必须留未解之谜")
                elif ctype == "爆发章":
                    stack.overrides.append("动作动词密度 +50%，句长缩短到 20 字以内")
                elif ctype == "过渡章":
                    stack.overrides.append("IWR 可降至 1.5，以信息释放为主")
                elif ctype == "副本章":
                    stack.overrides.append("规则条款占 20% 字数，对话占比降至 30%")
                elif ctype == "情感章":
                    stack.overrides.append("感官描写占 15%，触觉>听觉>视觉")
        except Exception:
            pass

        return stack

    # ------------------------------------------------------------------
    # 上下文裁剪（Composer 层）
    # ------------------------------------------------------------------
    def _select_characters(self, chapter_num: int) -> str:
        """选择本章相关人物（最多 5 个活跃人物）。"""
        try:
            chars = self.state.list_characters()[:5]
        except Exception:
            chars = []

        if not chars:
            return ""

        lines = ["【本章活跃人物】"]
        for c in chars:
            name = c.get("character_name", "未知")
            loc = c.get("location", "未知")
            emotion = c.get("emotional_state", "未知")
            secret = c.get("known_secrets", "")[:30]
            fingerprint = c.get("dialog_fingerprint", "")[:50]
            lines.append(f"- {name}：位置={loc}，情绪={emotion}，秘密={secret}...")
            if fingerprint:
                lines.append(f"  对话指纹：{fingerprint}")
        return "\n".join(lines)

    def _select_foreshadowing(self, chapter_num: int) -> str:
        """选择相关伏笔（即将回收或本章埋入的）。"""
        try:
            all_fs = self.state.list_foreshadowing()
        except Exception:
            return ""

        # 筛选：计划在本章或未来 5 章回收的伏笔
        relevant = []
        for f in all_fs:
            if f.get("status") != "active":
                continue
            try:
                collect_ch = int(f.get("collect_chapter", 999))
            except (ValueError, TypeError):
                continue
            if collect_ch <= chapter_num + 5:
                relevant.append(f)
        relevant = relevant[:8]

        if not relevant:
            return ""

        lines = ["【相关伏笔】"]
        for f in relevant:
            bury = f.get("bury_chapter", "?")
            collect = f.get("collect_chapter", "?")
            content = f.get("content", "")[:50]
            lines.append(f"- [{bury}章埋->{collect}章收] {content}...")
        return "\n".join(lines)

    def _select_debts(self, chapter_num: int) -> str:
        """选择相关债务（即将到期或本章产生的）。"""
        try:
            all_debts = self.state.list_debts()
        except Exception:
            return ""

        relevant = []
        for d in all_debts:
            if d.get("status") != "active":
                continue
            try:
                due_ch = int(d.get("due_chapter", 999))
            except (ValueError, TypeError):
                continue
            if due_ch <= chapter_num + 5:
                relevant.append(d)
        relevant = relevant[:5]

        if not relevant:
            return ""

        lines = ["【相关债务】"]
        for d in relevant:
            desc = d.get("description", "")[:50]
            due = d.get("due_chapter", "?")
            lines.append(f"- [第{due}章到期] {desc}...")
        return "\n".join(lines)

    def _select_recent_summaries(self, chapter_num: int) -> str:
        """选择最近 3 章摘要。"""
        try:
            history = self.state.list_chapters()
        except Exception:
            return ""

        recent = [h for h in history if h.get("chapter", 0) < chapter_num][-3:]
        if not recent:
            return ""

        lines = ["【前情提要（最近 3 章）】"]
        for h in recent:
            ch = h.get("chapter", "?")
            summary = (h.get("summary") or "")[:80]
            lines.append(f"- 第{ch}章：{summary}...")
        return "\n".join(lines)
