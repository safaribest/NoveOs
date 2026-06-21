"""DialogueTuner Step —— 对话优化。"""
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

logger = logging.getLogger("novel-os.steps.dialogue_tuner")


class DialogueTunerStep(PipelineStep):
    """优化对话密度和道说比，确保符合品类 DNA。

    原 batch_writer._call_dialogue_tuner 的迁移版本。
    """

    name = "DialogueTuner"

    def execute(self, ctx: ChapterContext) -> StepResult:
        hook_draft = ctx.get_correction("__previous_content__")
        if not hook_draft:
            raise StepFailure(
                step_name=self.name,
                reason="DialogueTuner 需要前置内容，但 __previous_content__ 未设置",
                retryable=False,
            )

        # 字数保护：输入已超标时直接返回
        input_cn = len(re.findall(r'[\u4e00-\u9fff]', hook_draft))
        if input_cn > ctx.word_max:
            logger.warning("第 %d 章 DialogueTuner 输入已超标(%d > %d)，跳过", ctx.chapter_num, input_cn, ctx.word_max)
            return StepResult(content=hook_draft, metadata={"agent": "DialogueTuner", "skipped": True})

        system = (
            "你是 DialogueTuner（对话调优师）。\n"
            "你的职责：优化全章对话，确保对话占比和'道/说'比率符合品类 DNA。\n"
            "你只做两件事：\n"
            "1. 调整对话密度（目标占比依品类而定，言情通常 40-55%）。\n"
            "2. 优化'道/说'比（目标依品类而定，言情通常 0.6-0.8，即'道'是'说'的60-80%）。\n"
            "\n规则：\n"
            "- 对话段落（以引号开头）应占全章的 25%-45%（言情 40-55%）\n"
            "- '道'字出现次数与'说'字出现次数的比值应接近品类 DNA\n"
            "- 对话簇≤3段（连续对话不超过3个来回）\n"
            "- 对话内容体现角色差异，避免千人一面\n"
            "- 优先保留核心对话，精简冗余对白\n"
            "- 如果对话占比过低，适当添加对话；如果过高，转为叙述\n"
            "\n【对话去AI味铁律——违反即回退】\n"
            "- 禁止书面语台词：'既然如此''那么''综上所述''首先''其次'\n"
            "- 禁止完美逻辑链：人说话会跑题、会自相矛盾、会只说半句\n"
            "- 禁止连续3句以上用'道/说'以外的提示词（低语/呢喃/沉声道/冷声道/缓缓道）\n"
            "- 允许：口癖、脏话、打断、重复、反问、不回答对方问题\n"
            "- 每个角色的对话必须体现其对话指纹，禁止千人一面"
            + build_persona_injection(ctx.book_config)
        )

        genre_dna = ctx.genre_dna
        target_dialogue = genre_dna.get("dialogue_ratio", 40)
        target_daoshuo = genre_dna.get("dao_shuo_ratio", 0.7)

        user = f"【任务】优化第{ctx.chapter_num}章的对话，确保品类DNA匹配。\n\n【当前正文】\n{hook_draft}\n"
        corrections = ctx.get_correction("dialogue_tuner")
        if corrections:
            user += f"\n【修正指令 - 必须执行】\n{corrections}\n"
        if ctx.style_rules:
            user += f"\n{ctx.style_rules}\n"
        user += (
            f"\n【品类DNA目标】\n"
            f"- 对话占比目标: {target_dialogue}%\n"
            f"- 道说比目标: {target_daoshuo}（'道'次数 / '说'次数）\n"
            f"\n【输出要求】\n"
            f"1. 输出优化后的完整正文。\n"
            f"2. 只改对话部分，叙述和描写尽量不动。\n"
            f"3. 只输出纯正文，不要任何说明、标记或元信息。"
        )

        temp, max_tok, _ = get_agent_llm_params(ctx.book_config, "dialogue_tuner", 0.1, 8000)
        log_full_prompt("dialogue_tuner", ctx.chapter_num, system, user, project_id=ctx.project_id)

        try:
            result = ctx.llm.call_for_agent("dialogue_tuner", system, user, temperature=temp, max_tokens=max_tok)
        except Exception as exc:
            raise StepFailure(
                step_name=self.name,
                reason=f"DialogueTuner LLM 调用失败: {exc}",
                retryable=True,
            )

        tuned_cn = len(re.findall(r'[\u4e00-\u9fff]', result))
        if input_cn > 0 and tuned_cn < input_cn * 0.85:
            logger.warning(
                "第 %d 章 DialogueTuner 字数损失 %.1f%% (%d→%d)，回退原稿",
                ctx.chapter_num, (1 - tuned_cn/input_cn) * 100, input_cn, tuned_cn
            )
            return StepResult(content=hook_draft, metadata={"agent": "DialogueTuner", "fallback": True})

        return StepResult(content=result, metadata={"agent": "DialogueTuner"})
