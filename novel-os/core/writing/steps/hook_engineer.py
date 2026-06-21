"""HookEngineer Step —— 开头/结尾优化。"""
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

logger = logging.getLogger("novel-os.steps.hook_engineer")


class HookEngineerStep(PipelineStep):
    """优化开头和结尾，确保 IWR 和钩子密度。

    原 batch_writer._call_hook_engineer 的迁移版本。
    """

    name = "HookEngineer"

    def execute(self, ctx: ChapterContext) -> StepResult:
        # Pipeline 已做字数保护：达标时直接跳过此 Step
        scene_draft = ctx.get_correction("__previous_content__")
        if not scene_draft:
            raise StepFailure(
                step_name=self.name,
                reason="HookEngineer 需要前置内容，但 __previous_content__ 未设置",
                retryable=False,
            )

        original_cn = len(re.findall(r'[\u4e00-\u9fff]', scene_draft))
        system = (
            "你是 HookEngineer（钩子工程师）。\n"
            "你的职责：优化章节的开头和结尾，确保信息扣留比（IWR）≥2.0 且钩子密度足够。\n"
            "你只做三件事：\n"
            "1. 检查开头是否在前50字内抛出情境悬念（不是概述，而是让读者想知道'发生了什么'）。\n"
            "2. 检查结尾是否留下未解之谜（不立刻揭示答案，答案留到后续章节）。\n"
            "3. 如果开头/结尾不满足要求，只修改这两处，保留中间正文不变。\n"
            "\n规则：\n"
            "- 开头前50字必须有未解之谜（可用：难道/莫非/究竟/为何/怎么/会不会/是否）\n"
            "- 结尾最后100字必须留下至少1个未解之谜（不要回答！让读者好奇）\n"
            "- 不要在结尾揭示本章悬念的答案\n"
            "- 保留中间所有正文内容，只改开头和结尾\n"
            "\n【结尾多样性铁律 - 绝对不可违背】\n"
            "- 禁止使用'主角静止动作 + 物品特写 + 悬念信息'作为连续两章的结尾结构。\n"
            "- 三章内，结尾必须轮换至少两种不同的收束方式。\n"
            "- 推荐的结尾节奏（轮换使用）：\n"
            "  1. 对话戛然而止（某人说出半句话被打断/沉默）\n"
            "  2. 环境突变（灯灭/声音消失/温度骤降）\n"
            "  3. 主角做出反直觉动作（放弃抵抗/主动走向危险/对不该笑的人笑）\n"
            "  4. 第三方突然介入（一个不该出现的人/声音/物品闯入画面）\n"
            "  5. 视角强制抽离（主角失去意识/被拽走/画面突然切断）"
            + build_persona_injection(ctx.book_config)
        )

        user = f"【任务】优化第{ctx.chapter_num}章的开头（前50字）和结尾（最后100字），确保钩子密度。\n\n【当前正文】\n{scene_draft}\n"
        corrections = ctx.get_correction("hook_engineer")
        if corrections:
            user += f"\n【修正指令 - 必须执行】\n{corrections}\n"
        if ctx.style_rules:
            user += f"\n{ctx.style_rules}\n"
        user += (
            "\n【输出要求】\n"
            "1. 如果开头/结尾已满足要求，原样输出全文。\n"
            "2. 如果需要修改，只改开头和结尾，中间正文一字不动。\n"
            "3. 只输出纯正文，不要任何说明、标记或元信息。"
        )

        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "hook_engineer", 0.1, 8000)
        log_full_prompt("hook_engineer", ctx.chapter_num, system, user, project_id=ctx.project_id)

        try:
            result = ctx.llm.call_for_agent("hook_engineer", system, user, temperature=temp, max_tokens=max_tok)
        except Exception as exc:
            raise StepFailure(
                step_name=self.name,
                reason=f"HookEngineer LLM 调用失败: {exc}",
                retryable=True,
            )

        result_cn = len(re.findall(r'[\u4e00-\u9fff]', result))
        if original_cn > 0 and result_cn < original_cn * 0.85:
            logger.warning(
                "第 %d 章 HookEngineer 字数损失 %.1f%% (%d→%d)，回退原稿",
                ctx.chapter_num, (1 - result_cn/original_cn) * 100, original_cn, result_cn
            )
            return StepResult(content=scene_draft, metadata={"agent": "HookEngineer", "fallback": True})

        return StepResult(content=result, metadata={"agent": "HookEngineer"})
