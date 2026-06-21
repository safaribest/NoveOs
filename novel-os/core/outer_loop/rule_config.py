"""规则配置持久层 —— 替代 monkey-patch。

将外层回路修改的参数写入 rule_overrides.json，
StyleRuleEngine / ChapterGoal 初始化时读取此文件即可生效。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("novel-os.outer_loop.config")

# 配置文件路径 —— 放在 novel-os 根目录
CONFIG_PATH = Path(__file__).parent.parent.parent / "rule_overrides.json"

# 默认值（即代码中的原始默认值，作为回退）
DEFAULTS: dict[str, Any] = {
    # StyleRuleEngine
    "StyleRuleEngine.max_not_x_but_y": 3,
    "StyleRuleEngine.max_xiang": 5,
    "StyleRuleEngine.max_cn_numbers": 50,
    "StyleRuleEngine.max_repetition": 5,
    # ChapterGoal
    "ChapterGoal.word_min": 1900,
    "ChapterGoal.word_max": 2600,
    "ChapterGoal.max_rule_score": 0.25,
    "ChapterGoal.max_cn_number_density": 0.08,
    "ChapterGoal.dialogue_ratio_min": 0.15,
    "ChapterGoal.dialogue_ratio_max": 0.55,
    # PipelineConfig
    "PipelineConfig.max_retries": 3,
    "PipelineConfig.polish_interval": 3,
    # THRESHOLDS (ChapterValidator) — 跨进程持久化
    "THRESHOLDS.min_words": 1900,
    "THRESHOLDS.max_words": 2600,
    "THRESHOLDS.max_ta_density": 0.04,
    "THRESHOLDS.max_redline": 0,
    "THRESHOLDS.max_forbidden_patterns": 3,
    "THRESHOLDS.max_sudden_count": 3,
    "THRESHOLDS.question_count_min": 3,
    "THRESHOLDS.reveal_count_max": 5,
    "THRESHOLDS.suspense_ending_min": 1,
    "THRESHOLDS.short_sentence_max": 12,
    "THRESHOLDS.max_consecutive_short": 8,
    "THRESHOLDS.long_sentence_min": 25,
    "THRESHOLDS.min_burstiness": 0.35,
    "THRESHOLDS.max_perplexity": 0.30,
    "THRESHOLDS.sensory_min_per_500": 1,
    "THRESHOLDS.precise_number_threshold": 8,
    "THRESHOLDS.dialogue_ratio_min": 0.15,
    "THRESHOLDS.dialogue_ratio_max": 0.55,
}


def load_overrides() -> dict[str, Any]:
    """加载 rule_overrides.json，文件不存在则返回空。"""
    if not CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        logger.debug("加载规则覆盖: %d 项", len(data))
        return data
    except Exception as exc:
        logger.warning("rule_overrides.json 解析失败，使用默认值: %s", exc)
        return {}


def save_overrides(overrides: dict[str, Any]) -> None:
    """保存覆盖值到 rule_overrides.json。"""
    CONFIG_PATH.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("规则覆盖已保存: %d 项 → %s", len(overrides), CONFIG_PATH)


def get(key: str, default: Any = None) -> Any:
    """读取单个覆盖值。优先读文件，其次 DEFAULTS，最后传入的 default。"""
    overrides = load_overrides()
    if key in overrides:
        return overrides[key]
    if key in DEFAULTS:
        return DEFAULTS[key]
    return default


def set_and_save(key: str, value: Any) -> None:
    """设置单个覆盖值并持久化。"""
    overrides = load_overrides()
    overrides[key] = value
    save_overrides(overrides)


def delete_key(key: str) -> None:
    """删除单个覆盖值（恢复默认）。"""
    overrides = load_overrides()
    if key in overrides:
        del overrides[key]
        save_overrides(overrides)


def merge_and_save(updates: dict[str, Any]) -> None:
    """批量更新覆盖值并持久化。"""
    overrides = load_overrides()
    overrides.update(updates)
    save_overrides(overrides)


def get_all() -> dict[str, Any]:
    """获取所有覆盖值（合并默认值）。"""
    result = dict(DEFAULTS)
    result.update(load_overrides())
    return result


def reset_all() -> None:
    """重置所有覆盖值（删除 rule_overrides.json）。"""
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        logger.info("rule_overrides.json 已删除，恢复所有默认值")
