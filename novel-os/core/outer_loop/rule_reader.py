"""RuleReader —— 统一读取所有可优化生产资料。

从代码模块中读取 THRESHOLDS、BANNED_PATTERNS、EMOTION_LABELS、
PipelineConfig、ChapterGoal 等参数的当前值。
"""

from __future__ import annotations

import copy
import importlib
import logging
from pathlib import Path
from typing import Any

from core.outer_loop.assets_index import (
    ASSET_REGISTRY,
    ASSETS_BY_KEY,
    AssetDef,
)

logger = logging.getLogger("novel-os.outer_loop.reader")


class RuleReader:
    """统一读取所有生产资料。"""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    # ── 公共接口 ──
    def read_all(self) -> dict[str, Any]:
        """读取所有注册资产，返回 {asset_key: current_value}。"""
        result: dict[str, Any] = {}
        for asset in ASSET_REGISTRY:
            try:
                result[asset.key] = self.read_one(asset.key)
            except Exception as exc:
                logger.warning("读取 %s 失败: %s", asset.key, exc)
                result[asset.key] = None
        return result

    def read_one(self, asset_key: str) -> Any:
        """读取单个资产的当前值。"""
        if asset_key in self._cache:
            return copy.deepcopy(self._cache[asset_key])

        asset = ASSETS_BY_KEY.get(asset_key)
        if not asset:
            raise KeyError(f"未知资产: {asset_key}")

        if asset.asset_type in ("threshold", "config"):
            value = self._read_threshold(asset)
        elif asset.asset_type == "wordlist":
            value = self._read_wordlist(asset)
        elif asset.asset_type in ("prompt_template", "skill_file"):
            value = self._read_file_content(asset)
        else:
            raise ValueError(f"不支持的资产类型: {asset.asset_type}")

        self._cache[asset_key] = copy.deepcopy(value)
        return value

    def invalidate_cache(self) -> None:
        """清除缓存（在规则被修改后调用）。"""
        self._cache.clear()

    def read_all_current_values(self) -> dict[str, Any]:
        """读取全部 WATCHED_PARAMS 相关的当前值，供 ConvergenceDetector 使用。

        返回 {param_key: current_value}，key 直接用 WATCHED_PARAMS 中的名称
        （如 "max_ta_density"），value 为数值类型。
        """
        result: dict[str, Any] = {}
        all_values = self.read_all()
        # read_all 返回 {asset_key: value}，asset_key 即为 WATCHED_PARAMS 中的名称
        for key, val in all_values.items():
            if isinstance(val, (int, float)):
                result[key] = val
            elif isinstance(val, (list, tuple)) and val and isinstance(val[0], (int, float)):
                # dialogue_ratio 等 tuple 类型，取均值
                result[key] = sum(val) / len(val)
        return result

    # ── 阈值读取 ──
    def _read_threshold(self, asset: AssetDef) -> Any:
        """从代码模块读取阈值参数。"""
        key = asset.key

        # ChapterValidator THRESHOLDS → 优先读 rule_overrides.json（跨进程持久化）
        if key in (
            "min_words", "max_words", "max_ta_density", "max_redline",
            "max_forbidden_patterns", "max_sudden_count",
            "question_count_min", "reveal_count_max", "suspense_ending_min",
            "short_sentence_max", "max_consecutive_short", "long_sentence_min",
            "min_burstiness", "max_perplexity",
            "sensory_min_per_500", "precise_number_threshold",
        ):
            from core.outer_loop.rule_config import get as config_get
            override_val = config_get(f"THRESHOLDS.{key}")
            if override_val is not None:
                return override_val
            from core.chapter_validator import THRESHOLDS
            return THRESHOLDS.get(key)

        # dialogue_ratio tuple → 同样优先 rule_overrides.json
        if key == "dialogue_ratio_min":
            from core.outer_loop.rule_config import get as config_get
            val = config_get("THRESHOLDS.dialogue_ratio_min")
            if val is not None:
                return val
            from core.chapter_validator import THRESHOLDS
            return THRESHOLDS.get("dialogue_ratio", (0.15, 0.55))[0]
        if key == "dialogue_ratio_max":
            from core.outer_loop.rule_config import get as config_get
            val = config_get("THRESHOLDS.dialogue_ratio_max")
            if val is not None:
                return val
            from core.chapter_validator import THRESHOLDS
            return THRESHOLDS.get("dialogue_ratio", (0.15, 0.55))[1]

        # StyleRuleEngine / ChapterGoal / PipelineConfig → 从 rule_overrides.json 读取
        config_key_map = {
            "max_not_x_but_y":          "StyleRuleEngine.max_not_x_but_y",
            "max_xiang":                "StyleRuleEngine.max_xiang",
            "max_cn_numbers":           "StyleRuleEngine.max_cn_numbers",
            "max_repetition":           "StyleRuleEngine.max_repetition",
            "goal_word_min":            "ChapterGoal.word_min",
            "goal_word_max":            "ChapterGoal.word_max",
            "goal_max_rule_score":      "ChapterGoal.max_rule_score",
            "goal_max_cn_number_density": "ChapterGoal.max_cn_number_density",
            "max_retries":              "PipelineConfig.max_retries",
            "polish_interval":          "PipelineConfig.polish_interval",
        }
        if key in config_key_map:
            from core.outer_loop.rule_config import get as config_get
            return config_get(config_key_map[key])

        # 番茄课程规则资产
        if asset.path.startswith("FanqieRules."):
            return self._read_fanqie_threshold(asset)

        raise KeyError(f"未实现的阈值读取: {key}")

    def _read_fanqie_threshold(self, asset: AssetDef) -> Any:
        """读取番茄课程规则中的阈值。"""
        from core.fanqie_course import load_fanqie_rules

        rules = load_fanqie_rules()
        path = asset.path
        inner = path[len("FanqieRules.") :]
        keys = inner.split(".")

        # 情绪配比占位符：返回默认配比
        if "<genre>" in keys:
            default = rules.get_emotion_ratio("")
            emotion = keys[-1]
            return default.get(emotion)

        if keys[0] == "opening":
            data = rules.get_opening_rules()
        elif keys[0] == "chapter_beat":
            data = rules.get_chapter_beat_rules()
        elif keys[0] == "pacing":
            data = rules.get_pacing_rules()
        elif keys[0] == "dialogue":
            data = rules.get_dialogue_rules()
        else:
            data = rules.get_all_rules().get("rules", {})

        for k in keys[1:]:
            if isinstance(data, dict):
                data = data.get(k)
            else:
                return None
        return data

    def _read_wordlist(self, asset: AssetDef) -> list[str]:
        """读取词表资产。"""
        key = asset.key

        if key == "forbidden_words":
            from core.chapter_validator import BANNED_PATTERNS
            return list(BANNED_PATTERNS.get("禁用词", []))

        if key == "ai_ending":
            from core.chapter_validator import BANNED_PATTERNS
            return list(BANNED_PATTERNS.get("AI万能结尾", []))

        if key == "template_metaphors":
            from core.chapter_validator import BANNED_PATTERNS
            return list(BANNED_PATTERNS.get("模板比喻", []))

        if key == "ai_expressions":
            from core.chapter_validator import BANNED_PATTERNS
            return list(BANNED_PATTERNS.get("标志性AI表情", []))

        if key == "emotion_labels":
            from core.writing.style_rule_engine import StyleRuleEngine
            engine = StyleRuleEngine()
            return list(engine.EMOTION_LABELS)

        if key == "stock_metaphors":
            from core.writing.style_rule_engine import StyleRuleEngine
            engine = StyleRuleEngine()
            return list(engine.STOCK_METAPHORS)

        if key == "system_panel_words":
            from core.writing.style_rule_engine import StyleRuleEngine
            engine = StyleRuleEngine()
            return list(engine.SYSTEM_PANEL_WORDS)

        raise KeyError(f"未实现的词表读取: {key}")

    def _read_file_content(self, asset: AssetDef) -> str:
        """读取 prompt 模板内容。"""
        key = asset.key

        if key == "scene_writer_dna":
            from core.writing.prompts import build_scene_writer_dna
            # 需要一个 dummy book_config，返回核心部分
            return self._extract_scene_writer_core()

        if key == "polish_system_prompt":
            return self._extract_polish_core()

        if key == "auditor_system_prompt":
            return self._extract_auditor_core()

        raise NotImplementedError("文件类型资产读取尚未实现: {}".format(asset.key))

    @staticmethod
    def _extract_scene_writer_core() -> str:
        """提取 SceneWriter DNA 核心文本（不依赖 book_config）。"""
        import inspect
        from core.writing import prompts
        source = inspect.getsource(prompts.build_scene_writer_dna)
        # 返回源码中【核心叙事原则】之后的部分作为参考
        return source

    @staticmethod
    def _extract_polish_core() -> str:
        """提取 Polish system prompt 核心。"""
        import inspect
        from core.writing.steps import polish
        source = inspect.getsource(polish.PolishStep.execute)
        return source

    @staticmethod
    def _extract_auditor_core() -> str:
        """提取 Auditor system prompt 核心。"""
        import inspect
        from core.writing.steps import auditor
        source = inspect.getsource(auditor.AuditorStep._build_auditor_system_prompt)
        return source

    # ── 批量序列化（用于传给 Analyzer Agent） ──
    def snapshot_to_dict(self) -> dict[str, Any]:
        """生成当前所有规则的完整快照，用于传给 LLM。"""
        return {
            "assets": self.read_all(),
            "metadata": {
                "total_assets": len(ASSET_REGISTRY),
                "thresholds_count": len([a for a in ASSET_REGISTRY if a.asset_type == "threshold"]),
                "wordlists_count": len([a for a in ASSET_REGISTRY if a.asset_type == "wordlist"]),
            },
        }

    def snapshot_for_llm(self) -> str:
        """生成人类可读的规则摘要，注入 Analyzer prompt。"""
        lines = ["=== 当前规则快照 ==="]
        for asset in ASSET_REGISTRY:
            try:
                val = self.read_one(asset.key)
                if asset.asset_type == "threshold":
                    lines.append(f"- {asset.key} = {val}  ({asset.description})")
                elif asset.asset_type == "wordlist":
                    lst = val if isinstance(val, list) else []
                    lines.append(f"- {asset.key}: {len(lst)} 词 → {lst[:8]}{'...' if len(lst) > 8 else ''}")
            except Exception:
                lines.append(f"- {asset.key}: [读取失败]")
        return "\n".join(lines)
