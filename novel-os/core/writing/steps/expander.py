"""Expander Step —— 字数不足时扩写补充。"""
from __future__ import annotations

import logging

from core.writing.context import ChapterContext
from core.writing.prompts import get_agent_llm_params, log_full_prompt
from core.writing.steps.base import PipelineStep, StepFailure, StepResult

logger = logging.getLogger("novel-os.steps.expander")


class ExpanderStep(PipelineStep):
    """接收现有正文和字数缺口，输出补充内容。

    原 batch_writer._call_expander 的迁移版本。
    """

    name = "Expander"

    def execute(self, ctx: ChapterContext) -> StepResult:
        raise StepFailure(
            step_name=self.name,
            reason="ExpanderStep 不支持独立执行，请通过 Pipeline 的扩写逻辑调用",
            retryable=False,
        )

    def expand(self, ctx: ChapterContext, content: str, short_by: int) -> str:
        """基于已有内容扩写，返回补充文本。"""
        system = (
            "你是一位专业的小说扩写师。你的任务是根据已有的章节内容，"
            "补充更多细节描写，使总字数达到要求。"
            "\n\n规则："
            "\n1. 不要重复已有内容，而是补充新的场景细节、人物对话、心理活动或环境氛围。"
            "\n2. 补充内容必须自然衔接原文，保持情节连贯。"
            "\n3. 直接输出补充的正文段落。"
            "\n4. 绝对不要输出任何说明、润色总结、字数统计、自检表、思考过程或元信息。"
            "\n5. 只输出中文正文。"
        )
        user = (
            f"以下是第 {ctx.chapter_num} 章的已有内容（当前字数不足，需要补充约 {short_by} 字）：\n\n"
            f"{content[:3000]}\n\n"
            f"【任务】请基于以上内容，补充至少 {short_by} 字的新内容。"
            f"这是硬性要求——你必须写满 {short_by} 字，只多不少。\n\n"
            f"【补充策略——按优先级】\n"
            f"1. 优先补充叙述性细节：环境氛围、感官描写、动作细节、心理活动\n"
            f"2. 次要补充对话：只在必要时添加，避免对话块超过3段\n"
            f"3. 不要重复已有情节，而是深化已有场景\n"
            f"4. 补充内容必须自然衔接，保持风格一致\n\n"
            f"直接输出补充的正文段落，不要任何说明。"
        )
        default_max_tok = min(12000, ctx.book_config.llm.get("max_tokens", 12000))
        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "expander", 0.5, default_max_tok)
        log_full_prompt("expander", ctx.chapter_num, system, user, project_id=ctx.project_id)

        try:
            result = ctx.llm.call_for_agent("expander", system, user, temperature=temp, max_tokens=max_tok)
        except Exception as exc:
            logger.warning("Expander 调用失败: %s", exc)
            raise StepFailure(
                step_name=self.name,
                reason=f"Expander LLM 调用失败: {exc}",
                retryable=True,
            )
        return result
