"""SpotFix Step —— PostWriteValidator 命中后的最小改动修正。"""
from __future__ import annotations

import logging
import re

from core.writing.context import ChapterContext
from core.writing.prompts import get_agent_llm_params, log_full_prompt
from core.writing.steps.base import PipelineStep, StepFailure, StepResult

logger = logging.getLogger("novel-os.steps.spot_fix")


class SpotFixStep(PipelineStep):
    """根据修正指令对文本做最小改动。

    原 batch_writer._call_spot_fix 的迁移版本。
    """

    name = "SpotFix"

    def execute(self, ctx: ChapterContext) -> StepResult:
        raise StepFailure(
            step_name=self.name,
            reason="SpotFixStep 不支持独立执行，需要提供 content 和 instruction",
            retryable=False,
        )

    def fix(self, ctx: ChapterContext, content: str, instruction: str) -> str:
        """执行 spot-fix，返回修正后的文本。"""
        original_cn = len(re.findall(r'[\u4e00-\u9fff]', content))

        system = (
            "你是 SpotFix Agent。你的任务是根据修正指令对文本做最小改动。\n"
            "规则：\n"
            "- 只修改指令中指出的问题，其他内容一字不动\n"
            "- 不要添加新情节\n"
            "- 绝对只输出修正后的纯正文\n"
        )
        user = f"【修正指令】\n{instruction}\n\n【待修正正文】\n{content}"
        logger.info("第 %d 章 调用 SpotFix", ctx.chapter_num)

        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "spot_fix", 0.3, 8000)
        log_full_prompt("spot_fix", ctx.chapter_num, system, user, project_id=ctx.project_id)

        try:
            result = ctx.llm.call_for_agent("spot_fix", system, user, temperature=temp, max_tokens=max_tok)
        except Exception as exc:
            logger.warning("SpotFix 调用失败: %s", exc)
            return content

        # 防御：SpotFix 返回非正文时回退原稿
        result_cn = len(re.findall(r'[\u4e00-\u9fff]', result))
        if original_cn > 500 and result_cn < original_cn * 0.5:
            logger.warning(
                "第 %d 章 SpotFix 返回内容疑似非正文（%d→%d 字），回退原稿",
                ctx.chapter_num, original_cn, result_cn
            )
            return content
        # 检测修正指令残留
        if "修正指令" in result[:200] or "指令指出" in result[:200]:
            logger.warning("第 %d 章 SpotFix 返回内容含指令残留，回退原稿", ctx.chapter_num)
            return content
        return result
