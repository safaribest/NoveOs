"""Polish Step —— 全文润色。"""
from __future__ import annotations

import logging
import re

from core.writing.context import ChapterContext
from core.writing.prompts import (
    build_persona_injection,
    get_agent_llm_params,
    log_full_prompt,
)
from core.writing.steps.base import PipelineStep, StepFailure, StepResult

logger = logging.getLogger("novel-os.steps.polish")


class PolishStep(PipelineStep):
    """基于风格质检，不合格重写。

    原 batch_writer._call_polish 的迁移版本。
    ★ 当前默认禁用，因为 Kimi-K2.5 对 Polish 任务极不稳定。
    """

    name = "Polish"

    def execute(self, ctx: ChapterContext) -> StepResult:
        draft = ctx.get_correction("__previous_content__")
        if not draft:
            raise StepFailure(
                step_name=self.name,
                reason="Polish 需要前置内容，但 __previous_content__ 未设置",
                retryable=False,
            )

        original_cn = len(re.findall(r'[\u4e00-\u9fff]', draft))
        target = ctx.word_target
        tol = ctx.word_tolerance

        system = (
            "你是 Polish（终审润色师）。\n"
            "质检清单（逐项检查，不合格必须修正）：\n"
            f"1. 字数：是否{target}±{tol}字？\n"
            "2. 开头：是否直接切入场景（不是概述）？前100字是否有动作+感官？\n"
            "3. 结尾：是否画面定格或疑问悬念？\n"
            "4. 对话：是否自然嵌入叙述（不是引号单独成段）？\n"
            "5. 术语：是否自然嵌入，不生硬？\n"
            "6. 去AI味：是否有首先…其次…最后/综上所述/值得注意的是/过了一会儿？\n"
            "7. 思考过程：是否有模型思考内容？有则删除\n"
            "8. 精确数字：是否有'0.5毫米/47赫兹/pH值'等参数？改为身体体感\n"
            "9. 情绪标签：是否有'恐惧/绝望/愤怒'等标签？改为生理反应\n"
            "\n【绝对铁律——违反任何一条，润色结果作废】\n"
            "- 保留所有情节和场景，禁止删减任何段落\n"
            "- 润色后的中文字数必须与原文字数相差不超过 5%\n"
            "- 只微调措辞、节奏和对话格式，不要重写\n"
            "- 绝对只输出纯正文，不要输出任何说明、润色总结、字数统计、自检表、思考过程或元信息\n"
            + build_persona_injection(ctx.book_config)
        )

        user = f"【任务】润色第{ctx.chapter_num}章\n\n【正文】\n{draft}"
        extra = ctx.get_correction("polish")
        if extra:
            user += f"\n\n【额外指令】\n{extra}"
        if ctx.style_rules:
            user += f"\n{ctx.style_rules}\n"

        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "polish", 0.3, 8000)
        log_full_prompt("polish", ctx.chapter_num, system, user, project_id=ctx.project_id)

        try:
            result = ctx.llm.call_for_agent("polish", system, user, temperature=temp, max_tokens=max_tok)
        except Exception as exc:
            raise StepFailure(
                step_name=self.name,
                reason=f"Polish LLM 调用失败: {exc}",
                retryable=True,
            )

        # 字数保护：损失超过 15% 回退原稿
        polished_cn = len(re.findall(r'[\u4e00-\u9fff]', result))
        if original_cn > 0 and polished_cn < original_cn * 0.85:
            logger.warning(
                "第 %d 章 Polish 后字数损失 %.1f%% (%d→%d)，回退到原稿",
                ctx.chapter_num, (1 - polished_cn/original_cn) * 100, original_cn, polished_cn
            )
            return StepResult(content=draft, metadata={"agent": "Polish", "fallback": True})

        return StepResult(content=result, metadata={"agent": "Polish"})
