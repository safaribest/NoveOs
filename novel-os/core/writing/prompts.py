"""共享 Prompt 构建工具 —— 从 batch_writer.py 迁移。

原 _build_system_prompt、_build_task_user_prompt、_build_scene_writer_dna 等
方法提取为模块级函数，供各 Step 复用。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from core.chapter_validator import TERM_MANDATORY
from core.config_loader import BookConfig
from core.fanqie_course import load_fanqie_rules
from core.state_manager import StateManager

logger = logging.getLogger("novel-os.writing.prompts")


# ------------------------------------------------------------------
# P2-⑤ StyleCritic 高频模式反哺（初稿去AI味前置）
# ------------------------------------------------------------------
def _load_style_critic_hot_patterns(top_n: int = 8) -> list[dict]:
    """读取 .style_critic_patterns.json，返回出现频次最高的 issue 类型。

    返回格式: [{"type": "not_x_but_y", "total": 17, "chapters": 5}, ...]
    文件不存在或为空时返回空列表。
    """
    import json as _json

    patterns_file = Path(".style_critic_patterns.json")
    if not patterns_file.exists():
        return []
    try:
        data = _json.loads(patterns_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    cumulative = data.get("cumulative", {})
    items = [
        {"type": k, "total": v.get("total", 0), "chapters": v.get("chapters", 0)}
        for k, v in cumulative.items()
    ]
    items.sort(key=lambda x: x["total"], reverse=True)
    return items[:top_n]



# ------------------------------------------------------------------
# Agent LLM 参数
# ------------------------------------------------------------------
def get_agent_llm_params(
    book_config: BookConfig, agent_type: str, default_temp: float, default_max_tokens: int
) -> tuple[float, int, bool]:
    """从 book.yaml agent_query 读取 agent 的 temperature/max_tokens/thinking_enabled。"""
    query = book_config.agent_query.get(agent_type, {})
    # 优先从 agent_llm 配置读取 thinking 设置
    agent_llm_cfg = getattr(book_config, 'agent_llm', {}).get(agent_type, {})
    thinking_enabled = agent_llm_cfg.get('thinking_enabled', query.get('thinking_enabled', False))
    return (
        query.get('temperature', default_temp),
        query.get('max_tokens', default_max_tokens),
        thinking_enabled,
    )


# ------------------------------------------------------------------
# Prompt 日志
# ------------------------------------------------------------------
def log_full_prompt(agent_type: str, chapter_num: int, system: str, user: str, project_id: str = "") -> None:
    """在每次 LLM 调用前，将完整的 system prompt 和 user prompt 写入日志文件。

    如果提供了 project_id，日志将按项目分目录存储（logs/prompts/{project_id}/），
    避免多项目日志混叠。
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path("logs/prompts")
    if project_id:
        log_dir = log_dir / project_id
    log_dir.mkdir(parents=True, exist_ok=True)
    filename = log_dir / f"ch{chapter_num:03d}_{agent_type}_{ts}.txt"
    content = (
        f"=== Agent: {agent_type} | Chapter: {chapter_num} | Time: {ts} ===\n\n"
        f"----- SYSTEM PROMPT -----\n{system}\n\n"
        f"----- USER PROMPT -----\n{user}\n"
    )
    try:
        filename.write_text(content, encoding="utf-8")
        logger.debug("Prompt 已记录: %s", filename)
    except Exception as exc:
        logger.warning("记录 prompt 失败: %s", exc)


# ------------------------------------------------------------------
# 世界观 / 规则加载
# ------------------------------------------------------------------
def load_worldview_rules(state: StateManager) -> str:
    """从 state 数据库读取术语字典和世界观铁律，注入 system prompt。"""
    rules_parts = []
    try:
        terms = state.get_term_dict()
        if not terms:
            terms = [
                {
                    "term": k,
                    "category": v.get("category", ""),
                    "first_chapter": v.get("first_chapter", 1),
                    "description": v.get("description", ""),
                }
                for k, v in TERM_MANDATORY.items()
            ]
        if terms:
            rules_parts.append("【世界观铁律——出现任何一条术语错误，整章废弃重写】")
            for t in terms:
                rules_parts.append(
                    f"- {t['term']}（{t.get('category', '')}，第{t.get('first_chapter', '?')}章首次出现）：{t.get('description', '')}"
                )

        specs = state.get_chapter_specs(spec_keys=["title", "core_event"])
        if specs:
            rules_parts.append("\n【章节任务——必须严格呈现以下核心事件】")
            for s in specs:
                if s.get("spec_key") == "core_event" and s.get("spec_value"):
                    rules_parts.append(f"- 第{s['chapter']}章：{s['spec_value'][:80]}")
    except Exception as exc:
        logger.warning("读取世界观铁律失败: %s", exc)
    return "\n".join(rules_parts)


def get_character_states(state: StateManager) -> list[dict[str, Any]]:
    """从 state 数据库读取活跃人物状态。"""
    try:
        return state.get_characters_full()
    except Exception as exc:
        logger.warning("读取人物状态失败: %s", exc)
    return []


def get_consistency_rules(state: StateManager) -> list[str]:
    """从 state 数据库读取写作规则。"""
    try:
        return state.get_hard_rules()
    except Exception as exc:
        logger.warning("读取规则失败: %s", exc)
    return []


# ------------------------------------------------------------------
# System Prompt 构建
# ------------------------------------------------------------------
def build_system_prompt(book_config: BookConfig, state: StateManager, agent_type: str) -> str:
    """根据 Agent 类型构造 system prompt，所有书籍配置从数据库动态加载。"""
    query = book_config.agent_query.get(agent_type, {})
    role = query.get("role", f"小说{agent_type}")
    cfg = query

    worldview = load_worldview_rules(state)
    parts = []
    if worldview:
        parts.append(worldview)

    persona = book_config.author_persona
    if persona:
        parts.append("\n【作者人格——所有正文必须体现以下风格特征】")
        voice = persona.get("voice", "")
        if voice:
            parts.append(f"叙事声音：{voice}")
        wound = persona.get("core_wound", "")
        if wound:
            parts.append(f"核心创伤：{wound}")
        rhythm = persona.get("sentence_rhythm", [])
        if rhythm:
            parts.append("句式节奏：")
            for r in rhythm:
                parts.append(f"  - {r}")
        sensory = persona.get("sensory_priority", [])
        if sensory:
            parts.append(f"感官优先级：{' > '.join(sensory)}")
        moves = persona.get("signature_moves", [])
        if moves:
            parts.append("标志性动作（必须出现）：")
            for m in moves:
                parts.append(f"  - {m}")
        forbidden = persona.get("forbidden_rhetoric", [])
        if forbidden:
            parts.append("禁止修辞：")
            for f in forbidden:
                parts.append(f"  - {f}")

    parts.append("\n【网文禁区——出现即FAIL】")
    parts.append("- 禁止'不知道为什么/仿佛/似乎/好像/他意识到'")
    parts.append("- 禁止'一些/实际上/在一定程度上/本质上/换句话说'")
    parts.append("- 禁止概括性时间：'过了一会儿/不久之后'")
    parts.append("- 禁止情绪标签：'恐惧/绝望'→改成生理反应")

    chars = get_character_states(state)
    if chars:
        parts.append("\n【人物对话指纹——逐句核对】")
        for c in chars:
            name = c.get("name", "")
            fp = c.get("dialog_fingerprint", "")
            if name and fp:
                parts.append(f"- {name}：{fp}")

    parts.append(f"你是 {role}。")
    if cfg.get("goal"):
        parts.append(f"你的目标是：{cfg['goal']}")
    if cfg.get("backstory"):
        parts.append(cfg["backstory"])
    return "\n\n".join(parts)


def build_task_user_prompt(book_config: BookConfig, agent_type: str, chapter_num: int, context: str = "") -> str:
    """构造 user prompt。"""
    query = book_config.agent_query.get(agent_type, {})
    role = query.get("role", f"小说{agent_type}")
    desc = query.get("description", "")
    expected = query.get("expected_output", "")

    for placeholder in ["{chapter_number}", "{chapter}"]:
        desc = desc.replace(placeholder, str(chapter_num))
        expected = expected.replace(placeholder, str(chapter_num))

    parts = [desc] if desc else []
    if context:
        parts.append(f"\n[上文/输入]\n{context[:5000]}")
    if expected:
        parts.append(f"\n[预期输出]\n{expected}")

    if agent_type == "writer":
        target = book_config.words_per_chapter
        tol = book_config.words_tolerance
        min_w = target - tol
        max_w = target + tol
        word_count_section = (
            f"\n【字数要求——硬性下限】\n"
            f"本章目标中文字数：{target} 字（舒适范围 {min_w}~{max_w}）。\n"
            f"字数下限 {min_w} 字是硬性要求，低于此值视为失败。情节完整与字数达标同等重要。\n"
            f"若接近字数上限，请优先把当前句子/段落写完，不要在句中截断；系统会在完整句末截断。\n"
            f"采用分场景配额制：把本章拆成 4-6 个节拍，每个节拍写 600-900 字，自然累加达标。\n"
            f"字数不足时按优先级补充：①新增推进情节的事件或对话交锋 ②扩写已有动作的细节拆解 ③补充感官与废动作。\n"
            f"禁止为凑字数而添加：精确参数、重复描写、无意义的心理分析、概括性场景概述。\n\n"
            f"【正文格式铁律】\n"
            f"- 禁止出现【节拍X】标签、markdown标记、自检表、字数统计\n"
            f"- 正文内不要写章节标题（如“第{chapter_num}章：XXX”），直接从正文第一句开始\n"
            f"- 直接从正文第一句开始，不要有空行开头\n\n"
            f"【对话铁律】\n"
            f"1. 本章对话占比控制在 25%-45%。对话是推动情节的核心手段，不是点缀。\n"
            f"2. 每章至少包含 3-5 组人物对话场景，每组对话不少于 3 轮交锋。\n"
            f"3. 对话中禁止用'道/说'以外的同义替换词（不可：低语/呢喃/沉声道/冷声道/缓缓道）。\n"
            f"4. 对话簇长度≤3段，禁止出现'对话块'超过3段的连续对话。\n"
            f"5. 对话口语化：允许打断、重复、半截话、口癖、脏话。禁止书面语台词和完美逻辑链。\n\n"
            f"【氛围与叙事铁律】\n"
            f"1. 禁止为凑字数而写纯氛围/环境铺陈；所有景物必须服务于即将发生的事件或角色动作。\n"
            f"2. 禁止用'像XX'类比喻直接解释情绪；情绪只能通过动作、事件、对话、身体反应来表达。\n"
            f"3. 字数不足时，优先增加具体事件、对话交锋、动作细节，而不是扩写环境或心理。\n"
            f"4. 每章至少包含3个相互关联的小事件，用事件链推动核心情节前进。\n\n"
        )
        parts.append(word_count_section)
        parts.append(build_fanqie_injection(chapter_num, book_config.genre))

    return "\n".join(parts)


# ------------------------------------------------------------------
# 番茄官方课程规则注入
# ------------------------------------------------------------------
GENRE_TO_FANQIE_KEY: dict[str, str] = {
    "年代商战": "male_dushi_zhongsheng",
    "重生逆袭": "male_dushi_zhongsheng",
    "都市异能": "male_dushi_yineng",
    "东方玄幻": "male_xuanhuan_dongfang",
    "异世大陆": "male_xuanhuan_yishi",
    "悬疑推理": "male_xuanyi_tuili",
    "末世危机": "male_kehuan_moshi",
    "古代穿越重生": "female_gudai_chuanyue",
    "穿越重生": "female_gudai_chuanyue",
    "宫斗宅斗": "female_gudai_gongdou",
    "甜宠": "female_xiandai_tianchong",
    "现代甜宠": "female_xiandai_tianchong",
    "虐恋": "female_xiandai_nuelian",
    "现代虐恋": "female_xiandai_nuelian",
    # ★ 2026-06-20 新增：短篇世情/家庭伦理/都市现实映射
    "现代都市": "female_xiandai_nuelian",   # 直播离婚类：偏虐→逆袭，用虐恋配比（nue高→shuang高）
    "家庭伦理": "female_xiandai_nuelian",
    "世情": "female_xiandai_nuelian",
    "规则怪谈": "male_xuanyi_tuili",         # 规则怪谈归入悬疑推理
    "无限流": "male_xuanyi_tuili",
    # 兼容项目内常用的英文 genre 编码
    "era_biz": "male_dushi_zhongsheng",
}


def map_genre_to_course_key(genre: str) -> str:
    """将 book_config.genre 映射到 fanqie_course_rules.yaml 中的品类 key。"""
    return GENRE_TO_FANQIE_KEY.get(genre, "default")


def build_fanqie_injection(chapter_num: int, genre: str) -> str:
    """根据番茄官方课程规则生成写作注入段（checklist 形式，保持简短）。"""
    try:
        rules = load_fanqie_rules()
    except Exception as exc:
        logger.warning("加载番茄课程规则失败: %s", exc)
        return ""

    genre = genre or "default"
    parts: list[str] = []

    # 前 3 章注入开篇铁律
    opening = rules.get_opening_rules()
    if chapter_num <= 3 and opening:
        max_lead_in = opening.get("max_lead_in_words", 300)
        parts.append(f"\n【番茄官方·开篇铁律（第{chapter_num}章）】")
        parts.append(
            f"1. 前 {max_lead_in} 字必须让主角出场，并建立核心冲突/目标/悬念；"
        )
        parts.append("2. 禁止大段世界观铺陈、群像缓慢登场、抒情回忆；")
        parts.append("3. 章节结尾必须留下强钩子。")

    # 所有章节注入节奏铁律
    chapter_beat = rules.get_chapter_beat_rules()
    dialogue = rules.get_dialogue_rules()
    if chapter_beat:
        min_climax = chapter_beat.get("min_climax_per_chapter", 1)
        ending_zone = chapter_beat.get("ending_hook_zone", 200)
        ratio = dialogue.get("ratio_range", [0.25, 0.45]) if dialogue else [0.25, 0.45]
        min_exchanges = dialogue.get("min_exchanges_per_scene", 3) if dialogue else 3
        lo, hi = ratio[0] * 100, ratio[1] * 100
        parts.append("\n【番茄官方·章节节奏铁律】")
        parts.append(f"1. 每章至少 {min_climax} 个爽点或情绪爆点；")
        parts.append(
            f"2. 对话占比控制在 {lo:.0f}%-{hi:.0f}%，每组对话不少于 {min_exchanges} 轮交锋；"
        )
        parts.append(
            f"3. 【结构铁律】最后一个节拍必须是钩子——未解问题、新危机或下一章诱惑三选一，出现在章节最后 {ending_zone} 字内。缺失即失败。"
        )

    # 情绪配比
    genre_key = map_genre_to_course_key(genre)
    emotion = rules.get_emotion_ratio(genre_key)
    parts.append("\n【番茄官方·情绪配比】")
    parts.append(
        f"本章及后续章节建议情绪配比："
        f"爽{emotion['shuang'] * 100:.0f}% / "
        f"甜{emotion['tian'] * 100:.0f}% / "
        f"平{emotion['ping'] * 100:.0f}% / "
        f"虐{emotion['nue'] * 100:.0f}%。"
    )

    return "\n".join(parts)


# ------------------------------------------------------------------
# 作者人格注入
# ------------------------------------------------------------------
def build_persona_injection(book_config: BookConfig) -> str:
    """生成 author_persona 注入文本，供后处理 Agent 使用。"""
    persona = book_config.author_persona
    if not persona:
        return ""
    parts = ["\n【作者人格——修改时必须保持此风格】"]
    voice = persona.get("voice", "")
    if voice:
        parts.append(f"叙事声音：{voice}")
    forbidden = persona.get("forbidden_rhetoric", [])
    if forbidden:
        parts.append(f"绝对禁止引入：{'、'.join(forbidden)}")
    return "\n".join(parts)


# ------------------------------------------------------------------
# SceneWriter DNA
# ------------------------------------------------------------------
def build_scene_writer_dna(book_config: BookConfig) -> str:
    """构建 SceneWriter 的 system prompt（风格DNA），基于 book.yaml author_persona 动态注入。"""
    persona = book_config.author_persona
    parts = []
    parts.append("【作者人格——你必须以这个人格写作，而非通用网文风格】")

    voice = persona.get("voice", "") if persona else ""
    if voice:
        parts.append(f"你的叙事声音是：{voice}")

    wound = persona.get("core_wound", "") if persona else ""
    if wound:
        parts.append(f"你的核心创伤视角：{wound}")

    rhythm = persona.get("sentence_rhythm", []) if persona else []
    if rhythm:
        parts.append("句式节奏（必须体现）：")
        for r in rhythm:
            parts.append(f"  - {r}")

    sensory = persona.get("sensory_priority", []) if persona else []
    if sensory:
        parts.append(f"感官优先级：{' > '.join(sensory)}")

    moves = persona.get("signature_moves", []) if persona else []
    if moves:
        parts.append("标志性动作（每章至少出现2处）：")
        for m in moves:
            parts.append(f"  - {m}")

    forbidden = persona.get("forbidden_rhetoric", []) if persona else []
    if forbidden:
        parts.append("绝对禁止（出现即失败）：")
        for f in forbidden:
            parts.append(f"  - {f}")

    parts.append("\n【写作风格——像下面的片段一样写。不要遵守\"去AI味\"规则，遵守这些片段里的写法。】")
    parts.append("")
    parts.append("## 网文写作的核心特征（来自《斗罗大陆》等爆款玄幻）")
    parts.append("")
    parts.append("1. 情绪可以直接写。斗罗大陆写\"唐三很冷静\"\"眼睛湿润了\"\"发自内心的兴奋\"——")
    parts.append("   叙述者直接点明角色情绪，不是写动作暗示。读者不需要猜。")
    parts.append("2. 对话标签用\"道\"为主（占80%），但允许\"冷冷道\"\"激动道\"\"失声道\"等情绪修饰。")
    parts.append("   也允许用动作伴随对话：\"唐昊冷冷的看着他，道\"。")
    parts.append("3. 背景和设定可以大段交代。斗罗大陆开场就是\"巴蜀，历来有天府之国的美誉\"——")
    parts.append("   直接交代世界背景，不需要全部嵌入场景。信息量大是网文的优势。")
    parts.append("4. 精确数字可以使用。\"十九下\"\"十七道身影\"\"两百年\"——数字增加可信度。")
    parts.append("5. 比喻可以用，但要是角色视角内的：\"如同雕像一样\"\"宛如星丸跳跃\"——不是公共库存比喻。")
    parts.append("6. 段落短、切得碎。1-3句换段占70%。一句话一段很常见。阅读节奏要快。")
    parts.append("7. 动作流程要拆细：\"以腿带腰，以腰带背，以背带臂\"——每个环节都写出来。")
    parts.append("8. 设定信息层层递进，不要一次倒完。从角色口中自然带出，不是旁白说明。")
    parts.append("9. 每章要有\"干货\"——一个修炼细节、一个新设定、一个打斗技巧的拆解。")
    parts.append("10. 【结构铁律】章节必须以钩子收尾——最后一个节拍是未解问题、新威胁或意外发现。没有钩子的章节视为失败。")
    parts.append("")
    parts.append("## 两条铁律（仅此两条）")
    parts.append("  禁止\"不是X，是Y\"句式。")
    parts.append("  禁止系统面板词：宿主、面板、属性点、经验条、冷却时间。")

    # ★ P2-⑤ 修复（2026-06-20）：从 StyleCritic 累积日志提取高频问题模式，
    # 反哺到 SceneWriter DNA，让初稿直接避开（前置去AI味）。
    hot_patterns = _load_style_critic_hot_patterns(top_n=8)
    if hot_patterns:
        parts.append("")
        parts.append("## 已知高频AI味模式（从历史修订日志提取，初稿必须避开）")
        for item in hot_patterns:
            parts.append(f"  - {item['type']}：累计 {item['total']} 次 / {item['chapters']} 章")

    parts.append("\n【格式】")
    parts.append("- 正文中不要写章节标题，直接从正文第一句开始")
    parts.append("- 段落之间空一行（网文标准排版，适合移动端阅读）")
    parts.append("- 不要出现【节拍X】标签、markdown、自检表、思考过程")
    parts.append("- 接近字数上限时，优先把当前句子/段落写完再结束，不要留下半截话")

    return "\n".join(parts)


# ------------------------------------------------------------------
# 辅助：从 outline.md 读取标题
# ------------------------------------------------------------------
def get_chapter_title_from_outline_md(book_config: BookConfig, chapter_num: int) -> str:
    """从 outline.md 解析指定章节的标题。"""
    outline_path = book_config.base_path / "outline.md"
    if not outline_path.exists():
        return ""
    try:
        text = outline_path.read_text(encoding="utf-8")
        pattern = rf'[#]{{2,4}}\s*第\s*{chapter_num}\s*章[：:]\s*(.+)'
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ""
