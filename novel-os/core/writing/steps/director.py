"""Director Step —— 生成本章任务卡。"""
from __future__ import annotations

import logging

from core.content.title import extract_from_director
from core.writing.context import ChapterContext
from core.writing.dequantify import dequantify_dict, dequantify_text
from core.writing.prompts import (
    build_system_prompt,
    build_task_user_prompt,
    get_agent_llm_params,
    get_chapter_title_from_outline_md,
    log_full_prompt,
)
from core.writing.steps.base import PipelineStep, StepFailure, StepResult

logger = logging.getLogger("novel-os.steps.director")


class DirectorStep(PipelineStep):
    """小说导演：读取大纲和状态库，生成本章任务卡（含标题）。

    原 batch_writer._call_director 的迁移版本。
    """

    name = "Director"

    def execute(self, ctx: ChapterContext) -> StepResult:
        # 重试时复用
        if ctx.director_prompt:
            logger.info("[Director] 第 %d 章 复用已有任务卡", ctx.chapter_num)
            return StepResult(content=ctx.director_prompt, metadata={"agent": "Director", "reused": True})

        system = build_system_prompt(ctx.book_config, ctx.state, "director")
        user = self._build_user_prompt(ctx)

        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "director", 0.1, 4000)
        log_full_prompt("director", ctx.chapter_num, system, user, project_id=ctx.project_id)

        try:
            result = ctx.llm.call_for_agent("director", system, user, temperature=temp, max_tokens=max_tok)
        except Exception as exc:
            raise StepFailure(
                step_name=self.name,
                reason=f"LLM 调用失败: {exc}",
                retryable=True,
            )

        if not result or len(result) < 50:
            raise StepFailure(
                step_name=self.name,
                reason="Director 返回内容过短，疑似无效",
                retryable=True,
            )

        ctx.director_prompt = result
        title = extract_from_director(result, ctx.chapter_num)
        logger.info("[Director] 第 %d 章 任务卡已生成，标题=%s", ctx.chapter_num, title or "未提取")

        return StepResult(content=result, metadata={"agent": "Director", "title": title})

    def _build_user_prompt(self, ctx: ChapterContext) -> str:
        chapter_num = ctx.chapter_num
        md_title = get_chapter_title_from_outline_md(ctx.book_config, chapter_num)

        outline = ctx.outline
        outline_text = ""
        if outline:
            # Loop Engineering: 预处理大纲，降低中文数词密度
            outline = dequantify_dict(outline)
            outline_text = (
                f"\n【本章大纲——必须严格遵循，禁止擅自修改核心事件与人物名称】\n"
                f"卷名/篇名：{outline.get('arc', '')}\n"
                f"核心事件：{outline.get('core_event', '')}\n"
                f"打脸对象：{outline.get('face_slap_target', '')}\n"
                f"打脸方式：{outline.get('face_slap_method', '')}\n"
                f"护妻时刻/人性高光：{outline.get('husband_moment', '')}\n"
                f"章末钩子：{outline.get('chapter_hook', '')}\n"
                f"情绪配比：{outline.get('emotion_ratio', '')}\n"
                f"技能解锁：{outline.get('skill_unlocked', '')}\n"
            )
        else:
            outline_text = "\n【注意】本章暂无大纲，请基于上下文合理设计。\n"

        chars = ctx.character_states
        chars_text = ""
        if chars:
            chars_text = "\n【人物状态——逐句核对对话指纹】\n" + "\n".join(
                f"- {c.get('name','')}（{c.get('location','未知')}）：{c.get('emotional_state','')}。\n"
                f"  对话指纹：{c.get('dialog_fingerprint','')}\n"
                f"  肢体语言：{c.get('body_language','')}"
                for c in chars[:5]
            )

        rules = ctx.consistency_rules
        rules_text = ""
        if rules:
            rules_text = "\n【必须遵守的写作铁律】\n" + "\n".join(f"{i+1}. {r}" for i, r in enumerate(rules))

        terms = ctx.terms
        terms_text = ""
        if terms:
            terms_text = "\n【世界观术语——出现即FAIL】\n" + "\n".join(
                f"- {t['term']}（{t.get('category','')}，第{t.get('first_chapter','?')}章首次出现）：{t.get('description','')}"
                for t in terms
            )

        prev_text = f"\n【前情摘要】\n{ctx.prev_summary}" if ctx.prev_summary else ""

        title_constraint = ""
        if md_title:
            title_constraint = (
                f"\n【章节标题——绝对不可更改】\n"
                f"本章标题必须为：第{chapter_num}章：{md_title}\n"
                f"严禁使用其他标题，严禁缩写或改写。"
            )

        extra_ctx = f"活跃债务: {ctx.debts}\n活跃伏笔: {ctx.foreshadowing}"

        lexicon_text = ctx.lexicon_injection
        if lexicon_text:
            extra_ctx += f"\n{lexicon_text}\n"

        user = build_task_user_prompt(
            ctx.book_config, "director", chapter_num,
            context=f"{extra_ctx}{outline_text}{chars_text}{rules_text}{terms_text}{prev_text}{title_constraint}"
        )
        user += (
            f"\n\n【输出格式要求】\n"
            f"任务卡第一行必须是章节标题，格式：【标题】第{chapter_num}章：标题名\n"
        )
        if md_title:
            user += f"【绝对铁律】标题必须严格使用『第{chapter_num}章：{md_title}』，一字不可改。\n"
        else:
            user += f"标题名要求：4-8个字，紧扣本章核心事件，有网文感，不要文艺腔。\n"
        user += (
            f"【绝对铁律】当前是第{chapter_num}章，任务卡中的标题必须写'第{chapter_num}章'，严禁写其他章节的编号。\n"
            f"标题后空一行，再写正文任务卡内容。\n"
            f"任务卡必须严格基于【本章大纲】设计，不能偏离大纲中的核心事件、打脸方式和章末钩子。"
        )
        return user
