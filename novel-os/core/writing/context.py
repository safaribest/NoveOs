"""章节上下文 —— 写作流水线的数据载体。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from core.config_loader import BookConfig
from core.lexicon_injector import LexiconInjector
from core.llm_client import LLMClient
from core.state_manager import StateManager

logger = logging.getLogger("novel-os.writing.context")


@dataclass
class ChapterContext:
    """单章写作所需的全部上下文数据。

    由 BatchWriter 在流水线启动前组装，
    Step 只读不写（中间状态除外），保证数据流单向透明。
    """

    # --- 标识 ---
    chapter_num: int
    project_id: str
    book_config: BookConfig

    # --- 运行时依赖（依赖注入，不直接实例化） ---
    llm: LLMClient = field(repr=False)
    """LLM 调用客户端。"""

    state: StateManager = field(repr=False)
    """状态管理器。"""

    # --- 来自状态库的查询结果 ---
    outline: dict[str, str] = field(default_factory=dict)
    """本章大纲：核心事件、打脸方式、护妻时刻、章末钩子。"""

    prev_summary: str = ""
    """前一章摘要，用于 continuity。"""

    character_states: list[dict[str, Any]] = field(default_factory=list)
    """本章涉及的人物状态。"""

    consistency_rules: list[str] = field(default_factory=list)
    """跨章一致性约束。"""

    debts: list[Any] = field(default_factory=list)
    """本章需要埋/收的债务。"""

    foreshadowing: list[Any] = field(default_factory=list)
    """本章需要埋/收的伏笔。"""

    genre_dna: dict[str, Any] = field(default_factory=dict)
    """品类 DNA 基准。"""

    style_rules: str = ""
    """风格规则注入文本（来自 novel-style-guide skill）。"""

    terms: list[dict[str, Any]] = field(default_factory=list)
    """世界观术语字典。"""

    lexicon_injection: str = ""
    """辞林约束注入文本（场景词条+角色红线）。"""

    # --- 外层 CrewAI 反馈 ---
    outer_crew_retcons: list[str] = field(default_factory=list)
    emotion_targets: list[dict[str, Any]] = field(default_factory=list)
    outer_crew_priorities: list[str] = field(default_factory=list)

    # --- 流水线中间状态（Steps 填充，后续 Steps 读取） ---
    director_prompt: str = ""
    """Director 生成的任务卡。重试时复用。"""

    beat_plan: str = ""
    """BeatPlanner 生成的六段式节拍。重试时复用。"""

    corrections: dict[str, str] = field(default_factory=dict)
    """各 Agent 的修正指令，key 为 step_name。"""

    compiled: Any = None
    """InputGovernor 编译后的上下文。"""

    input_governor: Any = None
    """InputGovernor 实例，供 SceneWriter 懒编译。"""

    @property
    def word_target(self) -> int:
        """本章目标字数。"""
        return self.book_config.words_per_chapter

    @property
    def word_tolerance(self) -> int:
        """本章字数容差。"""
        return getattr(self.book_config, "words_tolerance", 450)

    @property
    def word_min(self) -> int:
        return self.word_target - self.word_tolerance

    @property
    def word_max(self) -> int:
        return self.word_target + self.word_tolerance

    def get_correction(self, step_name: str) -> str:
        """获取指定 Step 的修正指令。"""
        return self.corrections.get(step_name, "")


class ChapterContextBuilder:
    """组装 ChapterContext 的构建器。

    原 batch_writer._build_chapter_context 的迁移版本。
    """

    def __init__(
        self,
        book_config: BookConfig,
        state: StateManager,
        input_governor: Any = None,
    ) -> None:
        self.cfg = book_config
        self.state = state
        self.input_governor = input_governor
        self.lexicon_injector = LexiconInjector()

        # 外层 CrewAI 反馈
        self._pending_retcons: list[str] = []
        self._emotion_targets: list[dict[str, Any]] = []
        self._outer_crew_priorities: list[str] = []

    def set_outer_crew_feedback(
        self,
        retcons: list[str] | None = None,
        emotion_targets: list[dict[str, Any]] | None = None,
        priorities: list[str] | None = None,
    ) -> None:
        if retcons is not None:
            self._pending_retcons = retcons
        if emotion_targets is not None:
            self._emotion_targets = emotion_targets
        if priorities is not None:
            self._outer_crew_priorities = priorities

    def build(self, chapter_num: int, llm: LLMClient) -> ChapterContext:
        """组装本章需要的全部状态上下文。"""
        ctx = ChapterContext(
            chapter_num=chapter_num,
            project_id=self.cfg.base_path.name,
            book_config=self.cfg,
            llm=llm,
            state=self.state,
            outline=self._get_chapter_outline(chapter_num),
            prev_summary=self._get_prev_summary(chapter_num),
            character_states=self._get_character_states(chapter_num),
            consistency_rules=self._get_consistency_rules(),
            debts=self.state.get_active_debts(chapter_num),
            foreshadowing=self.state.get_active_foreshadowing(chapter_num),
            genre_dna=self.state.get_genre_dna(),
            style_rules=self._build_style_rules(),
            terms=self.state.get_term_dict(),
            input_governor=self.input_governor,
        )
        ctx.lexicon_injection = self._build_lexicon_injection(ctx)
        if self._pending_retcons:
            ctx.outer_crew_retcons = self._pending_retcons
        if self._emotion_targets:
            ctx.emotion_targets = self._emotion_targets
        if self._outer_crew_priorities:
            ctx.outer_crew_priorities = self._outer_crew_priorities
        return ctx

    def _get_prev_summary(self, chapter_num: int) -> str:
        if chapter_num <= 1:
            return ""
        try:
            history = self.state.list_chapters()
            for h in history:
                if h.get("chapter") == chapter_num - 1:
                    return h.get("summary", "") or ""
        except Exception:
            pass
        return ""

    def _build_style_rules(self) -> str:
        """风格规则由 StyleRetrievalStep 运行时统一加载。"""
        return ""

    def _get_chapter_outline(self, chapter_num: int) -> dict[str, str]:
        try:
            return self.state.get_chapter_outline(chapter_num)
        except Exception as exc:
            logger.warning("读取 outline 失败: %s", exc)
        return {}

    def _get_character_states(self, chapter_num: int) -> list[dict[str, Any]]:
        try:
            return self.state.get_characters_by_chapter(chapter_num)
        except Exception as exc:
            logger.warning("读取人物状态失败: %s", exc)
        return []

    def _get_consistency_rules(self) -> list[str]:
        try:
            return self.state.get_hard_rules()
        except Exception as exc:
            logger.warning("读取规则失败: %s", exc)
        return []

    def _build_lexicon_injection(self, ctx: ChapterContext) -> str:
        """构建辞林约束注入文本。"""
        try:
            char_names = [c.get("name", "") for c in ctx.character_states if c.get("name")]
            return self.lexicon_injector.build_injection_text(
                outline=ctx.outline,
                chapter_num=ctx.chapter_num,
                character_names=char_names,
                prev_summary=ctx.prev_summary,
                seed=ctx.chapter_num,
            )
        except Exception as exc:
            logger.warning("构建辞林注入失败: %s", exc)
            return ""

