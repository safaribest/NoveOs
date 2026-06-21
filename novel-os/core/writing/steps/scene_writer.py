"""SceneWriter Step —— 场景正文创作。"""
from __future__ import annotations

import logging
import re

from core.chapter_validator import TERM_MANDATORY
from core.content.metrics import count_chinese_chars
from core.writing.context import ChapterContext
from core.writing.prompts import (
    build_scene_writer_dna,
    get_agent_llm_params,
    log_full_prompt,
)
from core.writing.steps.base import PipelineStep, StepFailure, StepResult

logger = logging.getLogger("novel-os.steps.scene_writer")


class SceneWriterStep(PipelineStep):
    """按节拍表创作场景正文。

    原 batch_writer._call_scene_writer / _call_scene_writer_half / _call_merger 的迁移版本。
    当前策略：单次调用（full）写作完整章。
    """

    name = "SceneWriter"

    def execute(self, ctx: ChapterContext) -> StepResult:
        beat_plan = ctx.beat_plan
        if not beat_plan:
            raise StepFailure(
                step_name=self.name,
                reason="BeatPlan 为空，无法创作场景正文",
                retryable=True,
            )

        target = ctx.word_target
        compiled_context = ""
        if ctx.compiled is not None and hasattr(ctx.compiled, "format_writer_prompt"):
            compiled_context = ctx.compiled.format_writer_prompt()

        # InputGovernor 懒编译（若 Director 后未编译）
        if compiled_context == "" and ctx.input_governor is not None and ctx.director_prompt:
            compiled = ctx.input_governor.compile(ctx.chapter_num, ctx.director_prompt)
            ctx.compiled = compiled
            if hasattr(compiled, "format_writer_prompt"):
                compiled_context = compiled.format_writer_prompt()

        logger.info("第 %d 章 启动 SceneWriter 单次写作（目标%d字）", ctx.chapter_num, target)

        draft = self._call_scene_writer_half(ctx, beat_plan, "full", target, compiled_context)
        words = count_chinese_chars(draft)
        logger.info("第 %d 章 SceneWriter 完成: %d字", ctx.chapter_num, words)
        return StepResult(content=draft.strip(), metadata={"agent": "SceneWriter", "word_count": words})

    def _call_scene_writer_half(
        self,
        ctx: ChapterContext,
        beat_plan: str,
        half: str,
        word_target: int,
        compiled_context: str = "",
    ) -> str:
        """SceneWriter 半章/全章写作。"""
        dna = build_scene_writer_dna(ctx.book_config)
        target = ctx.word_target
        tol = ctx.word_tolerance
        min_w = ctx.word_min
        chapter_num = ctx.chapter_num

        # 构建当前章节必须包含的强制术语列表
        required_terms = [
            term for term, cfg in TERM_MANDATORY.items()
            if chapter_num >= cfg.get("first_chapter", 1)
        ]
        terms_section = ""
        if required_terms:
            term_lines = [f"{', '.join(required_terms)}"]
            for term in required_terms:
                cfg = TERM_MANDATORY.get(term, {})
                good = cfg.get("good_example", "")
                bad = cfg.get("bad_example", "")
                if good or bad:
                    term_lines.append(f"\n■ {term}：")
                    if good:
                        term_lines.append(f"  正确写法：{good}")
                    if bad:
                        term_lines.append(f"  错误写法（禁止）：{bad}")
            terms_section = (
                f"\n【强制术语——必须在正文中自然出现，禁止意译或替换】\n"
                f"本章必须包含以下世界观核心术语（共{len(required_terms)}个）：\n"
                f"\n".join(term_lines) + "\n"
                f"术语必须自然嵌入叙述或对话中，禁止生硬插入或整段解释。禁止百科式说明。\n"
            )

        # 开头多样性
        OPENING_ROTATION = {
            0: "触感/身体感受开场（主角身体的某个感受直接切入，但禁止用工牌/指腹意象）",
            1: "对话/声音开场（一句对话或一个声音直接切入）",
            2: "动作/突发事件开场（一个动作或意外直接切入）",
            3: "环境/氛围开场（一个环境细节或氛围变化直接切入）",
            4: "内心独白/回忆开场（主角的一个念头或闪回直接切入）",
            5: "悬念/疑问开场（一个未解之谜或反常现象直接切入）",
        }
        opening_idx = (chapter_num - 1) % 6
        opening_type = OPENING_ROTATION[opening_idx]
        prev_idx = (chapter_num - 2) % 6 if chapter_num > 1 else -1
        prev_type = OPENING_ROTATION.get(prev_idx, "")
        opening_section = (
            f"\n【开场类型要求——禁止与上一章重复】\n"
            f"本章必须使用以下方式开场：{opening_type}\n"
        )
        if prev_type:
            opening_section += f"上一章（第{chapter_num-1}章）已使用：{prev_type}，本章严禁重复。\n"
        opening_section += "前100字必须有动作+感官细节，禁止概述。\n"

        if half == "first":
            user = (
                f"【任务】创作第{chapter_num}章的前半部分（起-承1-承2）\n\n"
                f"【字数铁律——绝对不可违背】\n"
                f"1. 这部分必须写满 {word_target} 字。绝对不能少于 {word_target - 200} 字。\n"
                f"2. 全章总目标 {target}±{tol} 字，前半部分占一半，必须达到 {word_target} 字。\n"
                f"3. 写完后立即估算中文字数。如果不足 {word_target} 字，立即补充：\n"
                f"   - 更详细的场景描写和环境氛围渲染\n"
                f"   - 人物对话和心理活动\n"
                f"   - 动作细节和感官体验\n"
                f"   - 不要草草结束，不要留空白\n"
                f"{terms_section}"
                f"{opening_section}\n"
                f"【分工说明】\n"
                f"你只负责前三段（起、承1、承2）。写到【承2】结束即可。\n"
                f"结尾处停在情节即将升级的瞬间，为后半部分（转-合1-合2）留下张力。\n"
                f"绝对不要写后半部分的情节，也不要写本章结局。\n\n"
                f"{compiled_context}\n"
                f"【节拍分配表】\n{beat_plan}\n"
            )
        elif half == "second":
            user = (
                f"【任务】创作第{chapter_num}章的后半部分（转-合1-合2）\n\n"
                f"【字数铁律——绝对不可违背】\n"
                f"1. 这部分必须写满 {word_target} 字。绝对不能少于 {word_target - 200} 字。\n"
                f"2. 全章总目标 {target}±{tol} 字，后半部分占一半，必须达到 {word_target} 字。\n"
                f"3. 后半部分和前半部分同等重要，同样需要大量细节描写。\n"
                f"4. 写完后立即估算中文字数。如果不足 {word_target} 字，立即补充：\n"
                f"   - 更详细的场景描写和环境氛围渲染\n"
                f"   - 人物对话和心理活动\n"
                f"   - 动作细节和感官体验\n"
                f"   - 不要草草结束，不要留空白\n"
                f"{terms_section}"
                f"{opening_section}\n"
                f"【分工说明】\n"
                f"你只负责后三段（转、合1、合2）。\n"
                f"前半部分（起-承1-承2）已经写好了，情节发展到【承2】结束时的紧张状态。\n"
                f"请从这里继续写：核心冲突爆发、情绪对峙、章末钩子。\n"
                f"不要重复前半部分已写的情节。\n\n"
                f"{compiled_context}\n"
                f"【节拍分配表】\n{beat_plan}\n"
            )
        elif half == "full":
            user = (
                f"【任务】一次性创作第{chapter_num}章的完整正文\n\n"
                f"【本章核心任务——必须优先于字数和格式】\n"
                f"{compiled_context}\n\n"
                f"【字数铁律——绝对不可违背】\n"
                f"1. 本章目标字数 {target}±{tol} 字，尽量接近目标，但不要为凑字数而截断句子或添加冗余。\n"
                f"2. 写完后立即估算中文字数。如果不足 {word_target} 字，优先补充对话交锋、动作细节和感官描写。\n"
                f"   如果超过 {word_target + 400} 字，精简冗余描写，保留核心情节。\n"
                f"{terms_section}"
                f"{opening_section}\n"
                f"【结构要求】\n"
                f"完整包含六段式结构：起-承1-承2-转-合1-合2。\n"
                f"起：直接切入场景，前100字必须有动作+感官细节。\n"
                f"承1-承2：情节推进，伏笔铺设，细节描写。\n"
                f"转：核心冲突爆发，情绪升级。\n"
                f"合1-合2：对峙/解决，章末钩子（不要回答悬念）。\n\n"
                f"【节拍分配表】\n{beat_plan}\n"
            )

        if ctx.lexicon_injection:
            user += f"\n{ctx.lexicon_injection}\n"

        # 注入风格规则（来自 novel-style-guide skill）
        if ctx.style_rules:
            user += f"\n{ctx.style_rules}\n"

        corrections = ctx.get_correction("scene_writer")
        if corrections:
            user += f"\n【修正指令】\n{corrections}\n"

        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "scene_writer", 0.75, 12000)
        log_full_prompt(f"scene_writer_{half}", chapter_num, dna, user, project_id=ctx.project_id)

        try:
            result = ctx.llm.call_for_agent("scene_writer", dna, user, temperature=temp, max_tokens=max_tok)
        except Exception as exc:
            raise StepFailure(
                step_name=self.name,
                reason=f"SceneWriter LLM 调用失败: {exc}",
                retryable=True,
            )
        return result

    def merge(self, ctx: ChapterContext, draft_first: str, draft_second: str) -> str:
        """合并前半章和后半章，消除接缝问题。"""
        chapter_num = ctx.chapter_num
        system = (
            "你是 Merger（章节合并师）。\n"
            "你接收两篇小说片段（前半章 + 后半章），任务是检查接缝并消除问题。\n"
            "\n检查清单：\n"
            "1. 接缝处是否有逻辑断裂（前半结尾和后半开头不连贯）\n"
            "2. 是否有重复内容（后半开头重复了前半结尾的情节）\n"
            "3. 人称/视角是否一致\n"
            "4. 情绪节奏是否自然过渡\n"
            "\n处理规则：\n"
            "- 只修改接缝处±200字，保留其他内容一字不动\n"
            "- 删除重复内容，保留更精彩的版本\n"
            "- 如有断裂，用1-2句过渡句衔接\n"
            "- 绝对不要添加新的情节或改变故事走向\n"
            "- 绝对不要输出任何说明、标记、字数统计\n"
        )
        first_tail = draft_first[-500:] if len(draft_first) > 500 else draft_first
        second_head = draft_second[:500] if len(draft_second) > 500 else draft_second
        user = (
            f"【任务】合并第{chapter_num}章的两个片段\n\n"
            f"【前半章结尾】\n{first_tail}\n\n"
            f"【后半章开头】\n{second_head}\n\n"
            f"【输出要求】\n"
            f"1. 输出修正后的完整合并正文（前半章 + 后半章，接缝已修复）\n"
            f"2. 不要任何说明、润色总结、字数统计或标记\n"
            f"3. 第一行必须是章节标题：第{chapter_num}章：标题名"
        )
        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "merger", 0.3, 12000)
        log_full_prompt("merger", chapter_num, system, user, project_id=ctx.project_id)

        try:
            result = ctx.llm.call_for_agent("merger", system, user, temperature=temp, max_tokens=max_tok)
        except Exception as exc:
            logger.warning("Merger 调用失败: %s", exc)
            return draft_first + "\n\n" + draft_second
        return result
