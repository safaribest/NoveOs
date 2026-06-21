"""RuleWriter —— 应用已批准的规则变更，支持快照与回滚。

职责:
1. 在应用变更前自动保存快照
2. 将 AssetChange 写入对应代码模块
3. 修改后刷新 RuleReader 缓存
4. 支持一键回滚到任意快照
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from core.outer_loop.assets_index import ASSETS_BY_KEY, AssetDef
from core.outer_loop.models import AssetChange

logger = logging.getLogger("novel-os.outer_loop.writer")

# 快照存储目录
SNAPSHOT_DIR = Path(__file__).parent.parent.parent.parent / ".rule_snapshots"


class RuleWriter:
    """规则写入器 + 快照管理器。"""

    def __init__(self) -> None:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self._applied: list[AssetChange] = []

    # ── 公共接口 ──
    def apply_all(self, changes: list[AssetChange], snapshot_label: str = "") -> str:
        """应用一批已批准的变更，返回 snapshot_id。"""
        if not changes:
            return ""

        # 1. 保存快照
        snapshot_id = self._save_snapshot(label=snapshot_label)

        # 2. 逐条应用
        applied = []
        failed = []
        for change in changes:
            try:
                self._apply_one(change)
                applied.append(change.asset_path)
                change.approved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except Exception as exc:
                logger.error("应用变更失败 %s: %s", change.asset_path, exc)
                failed.append({"path": change.asset_path, "error": str(exc)})

        if failed:
            logger.warning("部分变更应用失败 (%d/%d)，尝试回滚", len(failed), len(changes))
            self._rollback_to(snapshot_id)
            raise RuntimeError(f"变更应用失败，已回滚: {failed}")

        self._applied = changes
        logger.info("成功应用 %d 条变更，snapshot=%s", len(applied), snapshot_id)
        return snapshot_id

    def rollback(self, snapshot_id: str) -> bool:
        """回滚到指定快照。"""
        return self._rollback_to(snapshot_id)

    def list_snapshots(self) -> list[dict]:
        """列出所有快照。"""
        snapshots = []
        for f in sorted(SNAPSHOT_DIR.glob("snapshot_*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                snapshots.append({
                    "id": f.stem,
                    "label": data.get("label", ""),
                    "created_at": data.get("created_at", ""),
                    "asset_count": len(data.get("assets", {})),
                })
            except Exception:
                pass
        return snapshots

    # ── 内部：单条应用 ──
    def _apply_one(self, change: AssetChange) -> None:
        """将单条变更写入代码。"""
        asset = ASSETS_BY_KEY.get(change.asset_path.split(".")[-1])
        if not asset:
            # 尝试直接用 asset_path 中的 key
            for a in ASSETS_BY_KEY.values():
                if a.path == change.asset_path:
                    asset = a
                    break
        if not asset:
            raise KeyError(f"资产未注册: {change.asset_path}")

        if change.asset_path.startswith("FanqieRules."):
            self._write_fanqie_override(asset, change.proposed_value, change.asset_path)
            return

        if asset.asset_type in ("threshold", "config"):
            self._write_threshold(asset, change.proposed_value)
        elif asset.asset_type == "wordlist":
            self._write_wordlist(asset, change)
        elif asset.asset_type in ("prompt_template", "skill_file"):
            self._write_file(asset, change.proposed_value)
        else:
            raise ValueError(f"不支持的资产类型: {asset.asset_type}")

    def _write_fanqie_override(
        self,
        asset: AssetDef | None,
        value: Any,
        asset_path: str | None = None,
    ) -> None:
        """将番茄课程资产变更写入 fanqie_course_overrides.yaml。"""
        from core.fanqie_course import OVERRIDES_PATH

        path = asset_path or (asset.path if asset else None)
        if not path or not path.startswith("FanqieRules."):
            raise ValueError(f"非番茄课程资产路径: {path}")

        inner = path[len("FanqieRules.") :]
        keys = inner.split(".")

        # 情绪配比占位符统一写入 default_emotion_ratio，便于无 genre 场景生效
        if "<genre>" in keys:
            keys = ["pacing", "default_emotion_ratio", keys[-1]]

        overrides: dict[str, Any] = {}
        if OVERRIDES_PATH.exists():
            try:
                overrides = yaml.safe_load(
                    OVERRIDES_PATH.read_text(encoding="utf-8")
                ) or {}
            except Exception as exc:
                logger.warning("读取 fanqie_course_overrides.yaml 失败: %s", exc)
                overrides = {}
        if not isinstance(overrides, dict):
            overrides = {}

        overrides.setdefault("version", "1.0")
        current = overrides.setdefault("rules", {})
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = value

        OVERRIDES_PATH.write_text(
            yaml.safe_dump(overrides, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info(
            "番茄课程覆盖已写入 %s: %s = %s", OVERRIDES_PATH, path, value
        )

    def _write_threshold(self, asset: AssetDef, value: Any) -> None:
        """修改 ChapterValidator THRESHOLDS 等模块级字典。"""
        key = asset.key

        # THRESHOLDS 中的参数 → 同时写入 module dict + rule_overrides.json（跨进程持久）
        if key in (
            "min_words", "max_words", "max_ta_density", "max_redline",
            "max_forbidden_patterns", "max_sudden_count",
            "question_count_min", "reveal_count_max", "suspense_ending_min",
            "short_sentence_max", "max_consecutive_short", "long_sentence_min",
            "min_burstiness", "max_perplexity",
            "sensory_min_per_500", "precise_number_threshold",
        ):
            import core.chapter_validator as cv
            cv.THRESHOLDS[key] = value
            # 同时写入 rule_overrides.json（跨进程持久化）
            from core.outer_loop.rule_config import set_and_save
            config_key = f"THRESHOLDS.{key}"
            set_and_save(config_key, value)
            return

        # dialogue_ratio tuple → 同样双写
        if key in ("dialogue_ratio_min", "dialogue_ratio_max"):
            import core.chapter_validator as cv
            current = list(cv.THRESHOLDS.get("dialogue_ratio", (0.15, 0.55)))
            config_key = f"THRESHOLDS.{key}"
            if key == "dialogue_ratio_min":
                current[0] = value
            else:
                current[1] = value
            cv.THRESHOLDS["dialogue_ratio"] = tuple(current)
            from core.outer_loop.rule_config import set_and_save
            set_and_save(config_key, value)
            return

        # StyleRuleEngine / ChapterGoal / PipelineConfig → rule_overrides.json
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
            from core.outer_loop.rule_config import set_and_save
            config_key = config_key_map[key]
            set_and_save(config_key, value)
            logger.info("规则覆盖已写入 rule_overrides.json: %s = %s", config_key, value)
            return

        raise KeyError(f"未实现的阈值写入: {key}")

    def _write_wordlist(self, asset: AssetDef, change: AssetChange) -> None:
        """修改词表（追加/删除词条）。"""
        key = asset.key

        if key == "forbidden_words":
            from core.chapter_validator import BANNED_PATTERNS
            self._apply_list_change(BANNED_PATTERNS["禁用词"], change)
        elif key == "ai_ending":
            from core.chapter_validator import BANNED_PATTERNS
            self._apply_list_change(BANNED_PATTERNS["AI万能结尾"], change)
        elif key == "template_metaphors":
            from core.chapter_validator import BANNED_PATTERNS
            self._apply_list_change(BANNED_PATTERNS["模板比喻"], change)
        elif key == "ai_expressions":
            from core.chapter_validator import BANNED_PATTERNS
            self._apply_list_change(BANNED_PATTERNS["标志性AI表情"], change)
        elif key == "emotion_labels":
            from core.writing.style_rule_engine import StyleRuleEngine
            self._apply_list_change(StyleRuleEngine.EMOTION_LABELS, change)
        elif key == "stock_metaphors":
            from core.writing.style_rule_engine import StyleRuleEngine
            self._apply_list_change(StyleRuleEngine.STOCK_METAPHORS, change)
        elif key == "system_panel_words":
            from core.writing.style_rule_engine import StyleRuleEngine
            self._apply_list_change(StyleRuleEngine.SYSTEM_PANEL_WORDS, change)
        else:
            raise KeyError(f"未实现的词表写入: {key}")

    @staticmethod
    def _apply_list_change(target_list: list, change: AssetChange) -> None:
        """根据 change 对列表执行增/删操作。

        change.asset_type = "wordlist_add" → 追加
        change.asset_type = "wordlist_remove" → 删除
        change.proposed_value: 如果是 add → str(单个词)，remove → str(要删除的词)
        """
        if change.asset_type == "wordlist_add":
            word = change.proposed_value
            if word not in target_list:
                target_list.append(word)
        elif change.asset_type == "wordlist_remove":
            word = change.proposed_value
            if word in target_list:
                target_list.remove(word)
        else:
            raise ValueError(f"不支持的词表操作: {change.asset_type}")

    def _write_file(self, asset: AssetDef, content: str) -> None:
        """写入 prompt 模板 —— 保存到 rule_overrides.json 作为参考标记。

        prompt 模板的修改需要人工操作（改 Python 源码），外层回路不做自动写入。
        这里只记录：该 prompt 资产被提案修改过了。
        """
        from core.outer_loop.rule_config import set_and_save
        config_key = "prompt.{}".format(asset.key)
        set_and_save(config_key, {
            "modified": True,
            "modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "prompt 模板需人工修改源码。此记录仅标记回路曾提案修改此资产。",
        })
        logger.info("prompt 资产 %s 的修改建议已记录到 rule_overrides.json (需人工执行)", asset.key)

    # ── 快照 ──
    def _save_snapshot(self, label: str = "") -> str:
        """保存当前规则快照到 JSON 文件。"""
        from core.outer_loop.rule_reader import RuleReader

        reader = RuleReader()
        assets = reader.read_all()
        snapshot_id = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        data = {
            "snapshot_id": snapshot_id,
            "label": label,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "assets": assets,
        }
        filepath = SNAPSHOT_DIR / f"{snapshot_id}.json"
        filepath.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("快照已保存: %s (%d 项资产)", snapshot_id, len(assets))
        return snapshot_id

    def _rollback_to(self, snapshot_id: str) -> bool:
        """从 JSON 快照恢复规则。"""
        filepath = SNAPSHOT_DIR / f"{snapshot_id}.json"
        if not filepath.exists():
            logger.error("快照文件不存在: %s", filepath)
            return False

        data = json.loads(filepath.read_text(encoding="utf-8"))
        assets = data.get("assets", {})
        logger.warning("回滚到快照 %s (%d 项资产)", snapshot_id, len(assets))

        # 逐个恢复
        for key, value in assets.items():
            asset = ASSETS_BY_KEY.get(key)
            if not asset or value is None:
                continue
            try:
                if asset.asset_type in ("threshold", "config"):
                    self._write_threshold(asset, value)
                elif asset.asset_type == "wordlist":
                    # 词表完整替换
                    self._restore_wordlist(asset, value)
            except Exception as exc:
                logger.error("回滚 %s 失败: %s", key, exc)

        return True

    def _restore_wordlist(self, asset: AssetDef, value: list) -> None:
        """回滚词表到快照值。"""
        key = asset.key
        mapping = {
            "forbidden_words": ("core.chapter_validator", "BANNED_PATTERNS", "禁用词"),
            "ai_ending": ("core.chapter_validator", "BANNED_PATTERNS", "AI万能结尾"),
            "template_metaphors": ("core.chapter_validator", "BANNED_PATTERNS", "模板比喻"),
            "ai_expressions": ("core.chapter_validator", "BANNED_PATTERNS", "标志性AI表情"),
            "emotion_labels": None,  # 用属性方式
            "stock_metaphors": None,
            "system_panel_words": None,
        }
        if key in ("emotion_labels", "stock_metaphors", "system_panel_words"):
            from core.writing.style_rule_engine import StyleRuleEngine
            attr_map = {
                "emotion_labels": "EMOTION_LABELS",
                "stock_metaphors": "STOCK_METAPHORS",
                "system_panel_words": "SYSTEM_PANEL_WORDS",
            }
            setattr(StyleRuleEngine, attr_map[key], list(value))
        elif key in mapping and mapping[key]:
            mod_path, dict_name, list_key = mapping[key]
            import importlib
            mod = importlib.import_module(mod_path)
            d = getattr(mod, dict_name)
            d[list_key] = list(value)


# ── 模块级便捷函数 ──
def create_writer() -> RuleWriter:
    return RuleWriter()
