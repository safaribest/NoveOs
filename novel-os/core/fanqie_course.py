"""番茄课程规则引擎 —— 统一加载和查询官方课程规则。

规则来源：《番茄小说创作课》222 节官方课程整理。
基础规则存放于 config/fanqie_course_rules.yaml，
外层 Loop 的自动调参结果存放于 fanqie_course_overrides.yaml。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("novel-os.fanqie_course")

DEFAULT_RULES_PATH = Path(__file__).parent.parent / "config" / "fanqie_course_rules.yaml"
OVERRIDES_PATH = Path(__file__).parent.parent / "fanqie_course_overrides.yaml"


def _deep_merge(base: Any, override: Any) -> Any:
    """递归合并两个字典，override 优先。"""
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    return override if override is not None else base


def _get_by_dotted(data: dict[str, Any], dotted_key: str) -> Any:
    """通过点分键从字典取值。"""
    parts = dotted_key.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


class FanqieCourseRules:
    """番茄小说创作课规则管理器。"""

    def __init__(
        self,
        rules_path: Path | str | None = None,
        overrides_path: Path | str | None = None,
    ) -> None:
        self.rules_path = Path(rules_path) if rules_path else DEFAULT_RULES_PATH
        self.overrides_path = Path(overrides_path) if overrides_path else OVERRIDES_PATH
        self.rules: dict[str, Any] = self._load_yaml(self.rules_path)
        self.overrides: dict[str, Any] = self._load_yaml(self.overrides_path)

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """加载 YAML 文件，不存在则返回空字典。"""
        if not path.exists():
            logger.debug("番茄课程文件不存在: %s", path)
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning("加载番茄课程文件失败 %s: %s", path, exc)
            return {}

    # ── 查询接口 ──
    def get_opening_rules(self) -> dict[str, Any]:
        """获取开篇规则。"""
        base = _get_by_dotted(self.rules, "rules.opening") or {}
        override = _get_by_dotted(self.overrides, "rules.opening") or {}
        return _deep_merge(base, override)

    def get_chapter_beat_rules(self) -> dict[str, Any]:
        """获取章节节奏规则。"""
        base = _get_by_dotted(self.rules, "rules.chapter_beat") or {}
        override = _get_by_dotted(self.overrides, "rules.chapter_beat") or {}
        return _deep_merge(base, override)

    def get_dialogue_rules(self) -> dict[str, Any]:
        """获取对话规则。"""
        base = _get_by_dotted(self.rules, "rules.dialogue") or {}
        override = _get_by_dotted(self.overrides, "rules.dialogue") or {}
        return _deep_merge(base, override)

    def get_pacing_rules(self) -> dict[str, Any]:
        """获取节奏规则。"""
        base = _get_by_dotted(self.rules, "rules.pacing") or {}
        override = _get_by_dotted(self.overrides, "rules.pacing") or {}
        return _deep_merge(base, override)

    def get_emotion_ratio(self, genre_key: str) -> dict[str, float]:
        """获取指定品类的情绪配比，未找到则返回默认值。"""
        pacing_rules = self.get_pacing_rules()
        ratios = pacing_rules.get("emotion_ratios", {})
        ratio = ratios.get(genre_key)
        if ratio and isinstance(ratio, dict):
            return {
                "shuang": float(ratio.get("shuang", 0.35)),
                "tian": float(ratio.get("tian", 0.25)),
                "ping": float(ratio.get("ping", 0.25)),
                "nue": float(ratio.get("nue", 0.15)),
            }
        default = pacing_rules.get("default_emotion_ratio", {})
        return {
            "shuang": float(default.get("shuang", 0.35)),
            "tian": float(default.get("tian", 0.25)),
            "ping": float(default.get("ping", 0.25)),
            "nue": float(default.get("nue", 0.15)),
        }

    def get_character_rules(self) -> dict[str, Any]:
        """获取人物规则。"""
        base = _get_by_dotted(self.rules, "rules.character") or {}
        override = _get_by_dotted(self.overrides, "rules.character") or {}
        return _deep_merge(base, override)

    def get_platform_rules(self) -> dict[str, Any]:
        """获取平台安全规则。"""
        base = _get_by_dotted(self.rules, "rules.platform") or {}
        override = _get_by_dotted(self.overrides, "rules.platform") or {}
        return _deep_merge(base, override)

    def get_all_rules(self) -> dict[str, Any]:
        """获取完整合并后的规则。"""
        return _deep_merge(self.rules, self.overrides)


def load_fanqie_rules(
    rules_path: Path | str | None = None,
    overrides_path: Path | str | None = None,
) -> FanqieCourseRules:
    """便捷函数：加载番茄课程规则。"""
    return FanqieCourseRules(rules_path=rules_path, overrides_path=overrides_path)
