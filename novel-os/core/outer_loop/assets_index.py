"""资产索引 —— 定义所有可被外层回路优化的参数注册表。

每项资产包含:
- path: 在代码中的位置
- type: threshold | wordlist | prompt_template | skill_file | config
- current_value_getter: 读取当前值的函数引用
- constraints: 安全约束（min/max/枚举值等）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AssetDef:
    """单个可优化资产的定义。"""

    key: str                     # 唯一标识，如 "max_ta_density"
    path: str                    # 人类可读路径，如 "THRESHOLDS.max_ta_density"
    asset_type: str              # "threshold" | "wordlist" | "prompt_template" | "config"
    category: str                # "P0_blocking" | "P1_warning" | "P2_info" | "pipeline"
    description: str
    current_value: Any = None    # 运行时注入
    constraints: dict[str, Any] = field(default_factory=dict)
    # constraints 示例: {"min": 0.01, "max": 0.15, "step": 0.005, "type": "float"}


# ═══════════════════════════════════════════════════════════════
# 完整的资产注册表
# ═══════════════════════════════════════════════════════════════
ASSET_REGISTRY: list[AssetDef] = [
    # ── P0: BLOCKING 级阈值 ──
    AssetDef(
        key="min_words",
        path="THRESHOLDS.min_words",
        asset_type="threshold",
        category="P0_blocking",
        description="每章最低中文字数，不足则 BLOCK",
        constraints={"min": 1000, "max": 5000, "step": 50, "type": "int"},
    ),
    AssetDef(
        key="max_words",
        path="THRESHOLDS.max_words",
        asset_type="threshold",
        category="P0_blocking",
        description="每章最高中文字数，超出则 BLOCK",
        constraints={"min": 1500, "max": 8000, "step": 50, "type": "int"},
    ),
    AssetDef(
        key="max_ta_density",
        path="THRESHOLDS.max_ta_density",
        asset_type="threshold",
        category="P0_blocking",
        description="他/她/它字密度上限，超出 BLOCK。人类网文通常 4-8%",
        constraints={"min": 0.02, "max": 0.15, "step": 0.005, "type": "float"},
    ),
    AssetDef(
        key="max_redline",
        path="THRESHOLDS.max_redline",
        asset_type="threshold",
        category="P0_blocking",
        description="红线词最大容忍数量，当前 0 容忍",
        constraints={"min": 0, "max": 5, "step": 1, "type": "int"},
    ),

    # ── P1: WARNING 级阈值 ──
    AssetDef(
        key="max_forbidden_patterns",
        path="THRESHOLDS.max_forbidden_patterns",
        asset_type="threshold",
        category="P1_warning",
        description="禁用模式命中超过此数触发 WARN",
        constraints={"min": 1, "max": 10, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="dialogue_ratio_min",
        path="THRESHOLDS.dialogue_ratio[0]",
        asset_type="threshold",
        category="P1_warning",
        description="对话占比下限",
        constraints={"min": 0.05, "max": 0.50, "step": 0.05, "type": "float"},
    ),
    AssetDef(
        key="dialogue_ratio_max",
        path="THRESHOLDS.dialogue_ratio[1]",
        asset_type="threshold",
        category="P1_warning",
        description="对话占比上限",
        constraints={"min": 0.30, "max": 0.80, "step": 0.05, "type": "float"},
    ),
    AssetDef(
        key="max_sudden_count",
        path="THRESHOLDS.max_sudden_count",
        asset_type="threshold",
        category="P1_warning",
        description="'突然'每章最大出现次数",
        constraints={"min": 1, "max": 10, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="question_count_min",
        path="THRESHOLDS.question_count_min",
        asset_type="threshold",
        category="P1_warning",
        description="悬念问句最少数量，不足则IWR弱",
        constraints={"min": 1, "max": 10, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="reveal_count_max",
        path="THRESHOLDS.reveal_count_max",
        asset_type="threshold",
        category="P1_warning",
        description="揭示词最大数量，超出则信息过度释放",
        constraints={"min": 1, "max": 15, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="suspense_ending_min",
        path="THRESHOLDS.suspense_ending_min",
        asset_type="threshold",
        category="P1_warning",
        description="章末悬念收尾最少检测数（问句/动作悬念/认知缺口）",
        constraints={"min": 0, "max": 3, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="short_sentence_max",
        path="THRESHOLDS.short_sentence_max",
        asset_type="threshold",
        category="P1_warning",
        description="短句判定阈值（<=此字数视为短句）",
        constraints={"min": 5, "max": 20, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="max_consecutive_short",
        path="THRESHOLDS.max_consecutive_short",
        asset_type="threshold",
        category="P1_warning",
        description="连续短句最多容忍数",
        constraints={"min": 3, "max": 15, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="long_sentence_min",
        path="THRESHOLDS.long_sentence_min",
        asset_type="threshold",
        category="P1_warning",
        description="长句判定阈值（>=此字数视为长句）",
        constraints={"min": 15, "max": 50, "step": 5, "type": "int"},
    ),

    # ── 统计指纹阈值 ──
    AssetDef(
        key="min_burstiness",
        path="THRESHOLDS.min_burstiness",
        asset_type="threshold",
        category="P1_warning",
        description="突发性最低阈值，低于此值疑似AI（句长过于均匀）",
        constraints={"min": 0.10, "max": 0.60, "step": 0.05, "type": "float"},
    ),
    AssetDef(
        key="max_perplexity",
        path="THRESHOLDS.max_perplexity",
        asset_type="threshold",
        category="P1_warning",
        description="困惑度最高阈值（反向指标），低于此值文本过于可预测",
        constraints={"min": 0.10, "max": 0.60, "step": 0.05, "type": "float"},
    ),

    # ── P2: INFO 级阈值 ──
    AssetDef(
        key="sensory_min_per_500",
        path="THRESHOLDS.sensory_min_per_500",
        asset_type="threshold",
        category="P2_info",
        description="每500字至少应有几处非视觉感官描写",
        constraints={"min": 0, "max": 5, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="precise_number_threshold",
        path="THRESHOLDS.precise_number_threshold",
        asset_type="threshold",
        category="P2_info",
        description="精确数字+量词组合阈值，超出则疑似AI量化铺陈",
        constraints={"min": 3, "max": 20, "step": 1, "type": "int"},
    ),

    # ── Pipeline 配置 ──
    AssetDef(
        key="max_retries",
        path="PipelineConfig.max_retries",
        asset_type="config",
        category="pipeline",
        description="最大重试次数",
        constraints={"min": 1, "max": 5, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="polish_interval",
        path="PipelineConfig.polish_interval",
        asset_type="config",
        category="pipeline",
        description="Polish 间隔（每N章一次）",
        constraints={"min": 1, "max": 10, "step": 1, "type": "int"},
    ),

    # ── StyleRuleEngine 参数 ──
    AssetDef(
        key="max_not_x_but_y",
        path="StyleRuleEngine.max_not_x_but_y",
        asset_type="threshold",
        category="P1_warning",
        description="'不是X，是Y'句式最大容忍数",
        constraints={"min": 0, "max": 10, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="max_xiang",
        path="StyleRuleEngine.max_xiang",
        asset_type="threshold",
        category="P1_warning",
        description="'像…'比喻最大容忍数",
        constraints={"min": 0, "max": 15, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="max_cn_numbers",
        path="StyleRuleEngine.max_cn_numbers",
        asset_type="threshold",
        category="P1_warning",
        description="中文数词最大容忍数量",
        constraints={"min": 10, "max": 100, "step": 5, "type": "int"},
    ),
    AssetDef(
        key="max_repetition",
        path="StyleRuleEngine.max_repetition",
        asset_type="threshold",
        category="P1_warning",
        description="单意象最大复读次数",
        constraints={"min": 1, "max": 10, "step": 1, "type": "int"},
    ),

    # ── ChapterGoal 参数 ──
    AssetDef(
        key="goal_word_min",
        path="ChapterGoal.word_min",
        asset_type="threshold",
        category="P0_blocking",
        description="LoopController 字数下限",
        constraints={"min": 1000, "max": 4000, "step": 100, "type": "int"},
    ),
    AssetDef(
        key="goal_word_max",
        path="ChapterGoal.word_max",
        asset_type="threshold",
        category="P0_blocking",
        description="LoopController 字数上限",
        constraints={"min": 1500, "max": 6000, "step": 100, "type": "int"},
    ),
    AssetDef(
        key="goal_max_rule_score",
        path="ChapterGoal.max_rule_score",
        asset_type="threshold",
        category="P0_blocking",
        description="LoopController 可接受的最高AI味评分",
        constraints={"min": 0.10, "max": 0.50, "step": 0.05, "type": "float"},
    ),
    AssetDef(
        key="goal_max_cn_number_density",
        path="ChapterGoal.max_cn_number_density",
        asset_type="threshold",
        category="P1_warning",
        description="每千中文字允许的中文数词数",
        constraints={"min": 0.02, "max": 0.15, "step": 0.01, "type": "float"},
    ),

    # ── 词表资产（wordlist 类型）──
    AssetDef(
        key="forbidden_words",
        path="BANNED_PATTERNS.禁用词",
        asset_type="wordlist",
        category="P1_warning",
        description="禁用词列表（缓缓/微微/淡淡/轻轻/默默/悄然/莫名/忽然/竟然/突然...）",
    ),
    AssetDef(
        key="ai_ending",
        path="BANNED_PATTERNS.AI万能结尾",
        asset_type="wordlist",
        category="P1_warning",
        description="AI万能结尾禁用列表",
    ),
    AssetDef(
        key="template_metaphors",
        path="BANNED_PATTERNS.模板比喻",
        asset_type="wordlist",
        category="P1_warning",
        description="模板比喻/公共库存比喻黑名单",
    ),
    AssetDef(
        key="ai_expressions",
        path="BANNED_PATTERNS.标志性AI表情",
        asset_type="wordlist",
        category="P1_warning",
        description="标志性AI表情禁用列表",
    ),
    AssetDef(
        key="emotion_labels",
        path="StyleRuleEngine.EMOTION_LABELS",
        asset_type="wordlist",
        category="P1_warning",
        description="情绪标签词表（恐惧/绝望/愤怒...）",
    ),
    AssetDef(
        key="stock_metaphors",
        path="StyleRuleEngine.STOCK_METAPHORS",
        asset_type="wordlist",
        category="P1_warning",
        description="公共库存比喻靶子列表",
    ),
    AssetDef(
        key="system_panel_words",
        path="StyleRuleEngine.SYSTEM_PANEL_WORDS",
        asset_type="wordlist",
        category="P1_warning",
        description="系统面板常见词列表",
    ),
    # ── Prompt 模板资产（prompt_template 类型）──
    AssetDef(
        key="scene_writer_dna",
        path="prompts.build_scene_writer_dna()",
        asset_type="prompt_template",
        category="pipeline",
        description="SceneWriter 的核心叙事DNA（动作驱动/事件载体/情绪在事中）",
    ),
    AssetDef(
        key="polish_system_prompt",
        path="PolishStep.execute.system",
        asset_type="prompt_template",
        category="pipeline",
        description="Polish 的 system prompt（润色质检清单）",
    ),
    AssetDef(
        key="auditor_system_prompt",
        path="AuditorStep._build_auditor_system_prompt()",
        asset_type="prompt_template",
        category="pipeline",
        description="Auditor 的 system prompt（5维度审计）",
    ),

    # ── 番茄课程规则资产 ──
    AssetDef(
        key="opening_max_lead_in_words",
        path="FanqieRules.opening.max_lead_in_words",
        asset_type="threshold",
        category="P1_warning",
        description="开篇钩子必须在多少字内出现",
        constraints={"min": 100, "max": 800, "step": 50, "type": "int"},
    ),
    AssetDef(
        key="chapter_min_climax",
        path="FanqieRules.chapter_beat.min_climax_per_chapter",
        asset_type="threshold",
        category="P1_warning",
        description="每章最少爽点/情绪爆点数",
        constraints={"min": 0, "max": 5, "step": 1, "type": "int"},
    ),
    AssetDef(
        key="ending_hook_zone",
        path="FanqieRules.chapter_beat.ending_hook_zone",
        asset_type="threshold",
        category="P1_warning",
        description="章末钩子检测范围（最后 N 字）",
        constraints={"min": 50, "max": 500, "step": 50, "type": "int"},
    ),
    AssetDef(
        key="emotion_ratio_shuang",
        path="FanqieRules.pacing.emotion_ratios.<genre>.shuang",
        asset_type="threshold",
        category="P1_warning",
        description="爽情绪目标占比",
        constraints={"min": 0.0, "max": 1.0, "step": 0.05, "type": "float"},
    ),
    AssetDef(
        key="emotion_ratio_tian",
        path="FanqieRules.pacing.emotion_ratios.<genre>.tian",
        asset_type="threshold",
        category="P1_warning",
        description="甜情绪目标占比",
        constraints={"min": 0.0, "max": 1.0, "step": 0.05, "type": "float"},
    ),
]


# ═══════════════════════════════════════════════════════════════
# 便捷查询
# ═══════════════════════════════════════════════════════════════
ASSETS_BY_KEY: dict[str, AssetDef] = {a.key: a for a in ASSET_REGISTRY}
ASSETS_BY_TYPE: dict[str, list[AssetDef]] = {}
for a in ASSET_REGISTRY:
    ASSETS_BY_TYPE.setdefault(a.asset_type, []).append(a)
ASSETS_BY_CATEGORY: dict[str, list[AssetDef]] = {}
for a in ASSET_REGISTRY:
    ASSETS_BY_CATEGORY.setdefault(a.category, []).append(a)
