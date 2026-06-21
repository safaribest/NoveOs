"""Novel-OS 4 阶 Prompt 组装引擎 —— 领域层。

职责:
    - 从 BookConfig 读取 agent_query 配置
    - 从 StateManager 查询本章活跃债务、伏笔、人物状态
    - 注入字数铁律、去 AI 味核心规则、插件专属规则
    - 为 Director / Writer / Polish / Auditor 四个 Agent 组装 user prompt

约束:
    - 禁止包含业务规则（如"如果字数不足就扩写"）
    - 只负责"组装"，不负责决策
"""
from __future__ import annotations

import glob
import logging
import os
import re
from pathlib import Path
from typing import Any

from core.config_loader import BookConfig
from core.state_manager import StateManager

logger = logging.getLogger("novel-os.prompt_builder")

# 默认去 AI 味规则（当配置未提供时兜底）
_DEFAULT_DE_AI_RULES = """\
1. 他字密度：每100字中"他/她/它"不得超过10个。情绪必须物化（不是"他很害怕"，而是"指节发白，茶水在杯里晃出涟漪"）。
2. 禁用词（出现即严重扣分，每章不得超过3次）：缓缓、微微、淡淡、轻轻、默默、悄然、莫名、忽然、竟然、突然、与此同时、果不其然、不得不说、众所周知、就在这时、心中一凛、心头一震、下意识觉得。
3. 句式破坏：每200字必须有1处短句（≤8字）或非常规断句，禁止连续3句主谓宾整齐排比。单句长度控制在25字以内，超过35字必须拆句。
4. 感官锚定：每300字至少1处五感细节（味/嗅/触/听/视），禁止抽象概括。
5. 对话指纹：每个角色对话必须有独特口头禅或句式习惯，禁止所有角色说话像同一个人。对话占比不得超过30%，其余70%必须是环境描写、动作细节或心理外化。
6. IWR铁律（追读核心）：每章必须提出至少3个新的认知缺口（疑问/悬念），揭示词（原来/终于/发现/明白/突然/竟然/果然/顿时）总计不得超过5次。信息扣留比IWR必须≥2.0。
7. 钩子铁律：章末最后50字必须留下未解之谜——问句、动作悬念、或新威胁的引入。禁止以叙述总结或情绪收束结尾。
8. 开场铁律：优先以情境描写或动作切入开场，非必要不使用对话开场。前100字必须建立空间锚点（地点/光线/气味/声音）。
9. 比喻铁律：全文比喻不得超过3处。禁止公共库存比喻（像刀/像蛇/像铁板/像离水的鱼/像提线木偶/像蜡像/像木偶）。允许：私有比喻（必须与主角个人经历或本章特定物品绑定）。禁止通用比喻词：仿佛、好似、犹如、宛如、如同、像……一样、就像、好比。
10. 排版铁律：每段控制在15-25个中文字（约1-2句话），超过30字必须换行。对话和叙述交替时每句一换行，禁止大段连续描写。移动端阅读：短段落=高翻页率=高留存。
11. 细节代替概括：禁止"他很X"式抽象描述。必须用具体动作、神态、环境细节替代。例：不是"他很累"，而是"仰头靠在真皮座椅上，脸上露出深深的疲倦"。
12. 动作代替状态：禁止"他拒绝了/他逃跑了"等状态陈述。必须用连贯动作链表达。例：不是"他拒绝了"，而是"洒然一笑，不动声色的坐下"。
13. 对话推动剧情：禁止用叙述交代信息。关键信息必须通过对话自然带出。例：不是"他的朋友提醒他"，而是"狗日的陈汉升，你是不是咒我早点死？"
14. 环境暗示情绪：禁止直接写"他很孤独/他很压抑"。必须用环境细节暗示情绪。例：不是"他很孤独"，而是"天空湛蓝无云，马路还是泥土的，扬起的飞尘在阳光下一粒粒看的很清楚"。
15. 生理反应代替心理：禁止直接写心理活动"他很紧张/他很害怕"。必须用生理反应外化。例：不是"他很紧张"，而是"喉咙再次鼓动了一下，觉得自己嘴唇有些干燥的厉害"。
"""

_DEFAULT_FORBIDDEN_WORDS = [
    "然而", "不得不说", "众所周知", "突然", "竟然", "原来",
    "与此同时", "紧接着", "果不其然", "众所周知",
]

_DEFAULT_POLISH_OUTPUT_RULES = """\
【输出格式铁律 - 绝对不可违背】
1. 你必须只输出润色后的纯小说正文，禁止输出任何其他内容。
2. 禁止输出'润色修改清单'、'句式破坏完成情况'、'修改说明'等任何形式的元信息。
3. 禁止输出 markdown 标题（如 '# 润色后正文'）。
4. 禁止在正文末尾添加注释、总结、自检表。
5. 如果原文中有【节拍X】标签，直接删除，保持正文流畅。
6. 输出格式：直接以正文第一句开始，到最后一个字结束，中间不要任何非正文内容。
"""

_DEFAULT_AUDITOR_RULES = """\
【审计维度】
1. 字数统计（不含标点与空格）
2. 他字密度 = "他"出现次数 / 总字数
3. 红线词：政治敏感、色情描写、血腥细节
4. 禁用词：{forbidden_words}
5. 句式破坏评分（0-6分）：短句、变奏、倒装、省略
6. 感官细节计数（五感）
7. 年代/类型细节计数
8. 爽点计数
9. 章末结尾类型（悬念/情感爆点/转折/日常）

请返回 JSON 格式报告。
"""


class PromptBuilder:
    """4 阶 Prompt 组装引擎。"""

    def __init__(
        self,
        book_config: BookConfig,
        state_manager: StateManager,
    ) -> None:
        self.cfg = book_config
        self.state = state_manager
        self._plugin_rules = self._load_plugin_rules()

    # ------------------------------------------------------------------
    # 插件规则加载
    # ------------------------------------------------------------------
    def _load_plugin_rules(self) -> list[str]:
        """从 plugin_loader 加载插件专属规则（若不存在则跳过）。"""
        try:
            from core.plugin_loader import PluginLoader

            loader = PluginLoader()
            return loader.get_rules(self.cfg.plugin_id)
        except Exception as exc:
            logger.debug("插件规则加载失败（可能尚未实现 plugin_loader）: %s", exc)
            return []

    # ------------------------------------------------------------------
    # 内部辅助：状态查询
    # ------------------------------------------------------------------
    def _get_chapter_state(self, chapter_num: int) -> dict[str, Any]:
        """查询本章需要注入的活跃状态（债务、伏笔、人物）。"""
        state: dict[str, Any] = {
            "debts": self.state.get_active_debts(chapter_num),
            "foreshadowing": self.state.get_active_foreshadowing(chapter_num),
            "characters": [],
        }

        # 人物状态：优先尝试通过 state_manager 的扩展接口获取全量角色列表
        character_names: list[str] = []
        if hasattr(self.state, "get_character_names"):
            try:
                character_names = self.state.get_character_names()  # type: ignore[attr-defined]
            except Exception:
                pass
        elif hasattr(self.state, "_connect"):
            # 兜底：直接从 SQLite 读取所有出现过的角色名（内部实现依赖）
            try:
                import sqlite3

                conn = sqlite3.connect(str(self.state.db_path))
                rows = conn.execute(
                    "SELECT DISTINCT character_name FROM character_states ORDER BY character_name"
                ).fetchall()
                character_names = [r[0] for r in rows]
                conn.close()
            except Exception:
                pass

        for name in character_names:
            char_state = self.state.get_character_state(chapter_num, name)
            if char_state:
                state["characters"].append({"name": name, "state": char_state})

        return state

    def _format_state_context(self, state: dict[str, Any]) -> str:
        """将状态对象格式化为可读文本。"""
        lines: list[str] = []

        debts = state.get("debts", [])
        if debts:
            lines.append("=== 活跃债务 ===")
            for d in debts:
                lines.append(f"- [{d.get('debt_id')}] {d.get('content')} (回收章: {d.get('collect_chapter')})")

        foreshadowing = state.get("foreshadowing", [])
        if foreshadowing:
            lines.append("=== 活跃伏笔 ===")
            for f in foreshadowing:
                lines.append(f"- [{f.get('fs_id')}] {f.get('content')} (回收: {f.get('collect_chapter')})")

        characters = state.get("characters", [])
        if characters:
            lines.append("=== 人物状态 ===")
            for c in characters:
                cs = c.get("state", {})
                loc = cs.get("location") or "未知"
                emo = cs.get("emotional_state") or "未知"
                lines.append(f"- {c['name']}: 位置={loc}, 情感={emo}")

        return "\n".join(lines) if lines else "（无活跃状态）"

    # ------------------------------------------------------------------
    # 内部辅助：规则片段
    # ------------------------------------------------------------------
    def _build_word_count_rule(self) -> str:
        """字数铁律（目标 4500±450）。"""
        target = self.cfg.words_per_chapter
        tol = self.cfg.words_tolerance
        min_w = target - tol
        max_w = target + tol
        return (
            f"【系统指令 - 字数铁律 - 绝对不可违背】\n"
            f"1. 本章正文总字数（仅统计中文字符）必须严格控制在 {min_w} ~ {max_w} 字。\n"
            f"2. 目标字数：{target} 字。允许误差 ±{tol} 字，超出即失败。\n"
            f"3. 写作过程中每完成一个节拍，立即估算已写中文字数，确保进度与分配一致。\n"
            f"4. 完成全部正文后，必须再次精确统计中文字数。若不足 {min_w} 字，立即补充细节描写、对话或心理活动；若超过 {max_w} 字，立即删除冗余修辞和重复叙述。\n"
            f"5. 字数统计方法：只计算中文汉字（不计算标点、空格、英文字母、数字）。\n"
            f"6. 最终输出必须满足字数要求，否则整章废弃重写。"
        )

    def _build_beat_allocation(self) -> str:
        """节拍字数分配。"""
        target = self.cfg.words_per_chapter
        tol = self.cfg.words_tolerance
        min_w = target - tol
        return (
            f"【节拍字数分配 - 含自检节点】\n"
            f"- 节拍1（起）：约 {int(target * 0.20)} 字 → 写完后自检：应达 {int(target * 0.18)}~{int(target * 0.22)} 字\n"
            f"- 节拍2（承）：约 {int(target * 0.30)} 字 → 写完后自检：累计应达 {int(target * 0.48)}~{int(target * 0.52)} 字\n"
            f"- 节拍3（转）：约 {int(target * 0.30)} 字 → 写完后自检：累计应达 {int(target * 0.78)}~{int(target * 0.82)} 字\n"
            f"- 节拍4（合）：约 {int(target * 0.20)} 字 → 写完后自检：总字数必须 ≥{min_w} 字\n"
            f"注意：每个节拍完成后立即估算中文字数，不足就补充细节，超标就精简。"
        )

    def _build_format_rules(self) -> str:
        """正文格式铁律。"""
        return (
            "【正文格式铁律】\n"
            "- 禁止出现【节拍X】标签、markdown标记、自检表、字数统计\n"
            "- 每章开头直接以正文第一句开始，不要标题"
        )

    def _build_de_ai_rules(self) -> str:
        """去 AI 味核心规则。"""
        # 优先使用 book_config 中配置的规则，否则使用默认
        custom = self.cfg.writing.get("de_ai_rules", "")
        if custom:
            return f"【去AI味核心规则】\n{custom}"
        return _DEFAULT_DE_AI_RULES

    def _build_writing_constitution(self, chapter_num: int) -> str:
        """将 Validator 硬指标翻译成 LLM 前置写作指令。"""
        target = self.cfg.words_per_chapter
        tol = self.cfg.words_tolerance

        # 从 ChapterValidator 同步阈值，避免 prompt 与校验器脱节
        from core.chapter_validator import THRESHOLDS as VT

        iwr_target = VT.get("iwr_target", 2.5)
        q_min = VT.get("question_count_min", 5)
        r_max = VT.get("reveal_count_max", 3)
        sent_min = VT.get("sentence_length_min", 20)
        short_max = VT.get("short_sentence_max", 12)
        long_min = VT.get("long_sentence_min", 25)
        max_consec = VT.get("max_consecutive_short", 3)
        dlg_lo, dlg_hi = VT.get("dialogue_ratio", (0.25, 0.45))

        lines = [
            "【写作宪法——违反任何一条，整章作废重写】",
            "",
            f"1. 字数铁律：本章中文字数必须严格控制在 {target - tol} ~ {target + tol} 字。",
            f"   统计方式：只算汉字，不算标点、空格、英文、数字。",
            "",
            f"2. 悬念铁律（IWR≥{iwr_target}）：",
            f"   - 本章必须预埋至少 {q_min} 个悬念问句（用难道/究竟/怎么/会不会等）。",
            f"   - 揭示词（原来/终于/发现/明白/知道/看来/果然/竟然/突然/顿时）不得超过 {r_max} 个。",
            "   - 每提出一个悬念，必须在 500 字内给出部分线索，但不得在 2000 字内彻底揭晓。",
            "",
            f"3. 句长铁律（均值 {sent_min}-28 字）：",
            f"   - 禁止连续使用 {max_consec} 个以上≤{short_max} 字的句子。",
            f"   - 每个段落至少包含 1 个≥{long_min} 字的复合句。",
            '   - 碎片化动作（"他笑了。他走了。他回头。"）视为一级违规。',
            "",
            f"4. 视角铁律（他密度<{VT.get('max_ta_density', 0.10):.0%}）：",
            '   - 主语优先使用角色全名（林默/陈雨），其次用省略主语的无头句。',
            '   - 禁止用"他/她"指代前文超过 3 句未出现的角色。',
            "",
            f"5. 对话铁律（占比 {int(dlg_lo*100)}%-{int(dlg_hi*100)}%）：",
            "   - 对话簇（连续引号段落）不得超过 3 段。",
            "   - 规则条款用冷峻客观体，情感对话克制而撕裂。",
            "   - 禁止用对话交代世界观。",
            "",
            "6. 章末钩子铁律：",
            "   - 最后 100 字必须包含 1 个未解之谜或 1 个情绪定格画面。",
            '   - 禁止用"他不知道的是……"这种 AI 万能结尾。',
        ]
        return "\n".join(lines)

    def _build_plugin_rules(self) -> str:
        """插件专属规则。"""
        if not self._plugin_rules:
            return ""
        return "【插件专属规则】\n" + "\n".join(f"- {r}" for r in self._plugin_rules)

    def _build_polish_output_rules(self) -> str:
        """Polish 输出格式铁律。"""
        return _DEFAULT_POLISH_OUTPUT_RULES

    def _build_auditor_rules(self) -> str:
        """Auditor 审计规则。"""
        forbidden = self.cfg.writing.get("forbidden_words", _DEFAULT_FORBIDDEN_WORDS)
        return _DEFAULT_AUDITOR_RULES.format(forbidden_words=", ".join(forbidden))

    # ------------------------------------------------------------------
    # 内部辅助：agent_query 解析
    # ------------------------------------------------------------------
    def _get_agent_query(self, agent_type: str) -> dict[str, str]:
        """从 book_config 读取指定 agent 的 query 配置。"""
        return self.cfg.agent_query.get(agent_type, {})

    def _resolve_template(self, text: str, chapter_num: int) -> str:
        """替换模板变量。"""
        return text.replace("{chapter_number}", str(chapter_num))

    # ------------------------------------------------------------------
    # 公共接口：4 阶 Prompt 组装
    # ------------------------------------------------------------------
    def build_director_prompt(self, chapter_num: int, context: dict) -> str:
        """组装 Director Agent 的 user prompt。

        Director 负责生成本章任务卡（节拍规划、人物调度、情感坐标）。
        """
        query = self._get_agent_query("director")
        desc = self._resolve_template(query.get("description", ""), chapter_num)
        expected = self._resolve_template(query.get("expected_output", ""), chapter_num)

        # 注入本章状态
        state = self._get_chapter_state(chapter_num)
        state_text = self._format_state_context(state)

        parts: list[str] = []
        if desc:
            parts.append(desc)
        if context:
            parts.append(f"[外部上下文]\n{context}")
        parts.append(f"[本章状态]\n{state_text}")
        if expected:
            parts.append(f"[预期输出]\n{expected}")

        return "\n\n".join(parts)

    def build_writer_prompt(self, chapter_num: int, director_output: str, context: dict) -> str:
        """组装 Writer Agent 的 user prompt。

        Writer 负责生成小说正文初稿，需注入字数铁律、去 AI 味规则、插件规则。
        """
        query = self._get_agent_query("writer")
        desc = self._resolve_template(query.get("description", ""), chapter_num)
        expected = self._resolve_template(query.get("expected_output", ""), chapter_num)

        # 注入状态
        state = self._get_chapter_state(chapter_num)
        state_text = self._format_state_context(state)

        parts: list[str] = []

        # 1. 字数铁律（最高优先级，放最前）
        parts.append(self._build_word_count_rule())
        parts.append(self._build_beat_allocation())
        parts.append(self._build_format_rules())

        # 2. 去 AI 味核心规则
        parts.append(self._build_de_ai_rules())

        # 3. 写作宪法（把 Validator 硬指标前置注入）
        parts.append(self._build_writing_constitution(chapter_num))

        # 4. 插件专属规则
        plugin_rules = self._build_plugin_rules()
        if plugin_rules:
            parts.append(plugin_rules)

        # 5. Agent 描述
        if desc:
            parts.append(desc)

        # 6. 上下文与状态
        if context:
            parts.append(f"[外部上下文]\n{context}")
        parts.append(f"[本章状态]\n{state_text}")

        # 7. Director 任务卡
        parts.append(f"[Director 任务卡]\n{director_output[:5000]}")

        # 8. 预期输出
        if expected:
            parts.append(f"[预期输出]\n{expected}")

        return "\n\n".join(parts)

    def build_polish_prompt(self, chapter_num: int, draft: str) -> str:
        """组装 Polish Agent 的 user prompt。

        Polish 负责去 AI 味润色，只输出纯正文。
        """
        query = self._get_agent_query("polish")
        desc = self._resolve_template(query.get("description", ""), chapter_num)
        expected = self._resolve_template(query.get("expected_output", ""), chapter_num)

        parts: list[str] = []
        if desc:
            parts.append(desc)

        parts.append(f"[待润色正文]\n{draft[:8000]}")
        parts.append(self._build_polish_output_rules())

        # 注入去 AI 味规则（提醒 Polish 注意）
        parts.append(self._build_de_ai_rules())

        if expected:
            parts.append(f"[预期输出]\n{expected}")

        return "\n\n".join(parts)

    def build_auditor_prompt(self, chapter_num: int, content: str) -> str:
        """组装 Auditor Agent 的 user prompt。

        Auditor 负责审计正文并返回指标报告（JSON）。
        """
        query = self._get_agent_query("auditor")
        desc = self._resolve_template(query.get("description", ""), chapter_num)
        expected = self._resolve_template(query.get("expected_output", ""), chapter_num)

        # 字数铁律作为审计参考
        target = self.cfg.words_per_chapter
        tol = self.cfg.words_tolerance

        parts: list[str] = []
        if desc:
            parts.append(desc)

        parts.append(
            f"[字数标准] 本章目标字数 {target}±{tol} 字 "
            f"（{target - tol} ~ {target + tol}）。"
        )
        parts.append(f"[待审计正文]\n{content[:8000]}")
        parts.append(self._build_auditor_rules())

        if expected:
            parts.append(f"[预期输出]\n{expected}")

        return "\n\n".join(parts)
