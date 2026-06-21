"""LexiconInjector —— 辞林约束注入器。

把 scene_lexicon.yaml 和 dialog_taboo.yaml 从"后处理规则"变成"生成前约束"：
- 根据章节大纲自动匹配场景类型与情绪子类
- 抽取 2-4 个具体词条
- 抽取本章涉及角色的对话红线与词汇地址
- 生成可直接注入 Director / SceneWriter prompt 的文本
"""

from __future__ import annotations

import logging
import random
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("novel-os.lexicon_injector")

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_SCENE_LEXICON_PATH = _TEMPLATES_DIR / "scene_lexicon.yaml"
_DIALOG_TABOO_PATH = _TEMPLATES_DIR / "dialog_taboo.yaml"


class LexiconInjector:
    """辞林注入器。"""

    def __init__(self, scene_lexicon_path: Path | str | None = None, dialog_taboo_path: Path | str | None = None) -> None:
        self.scene_lexicon_path = Path(scene_lexicon_path) if scene_lexicon_path else _SCENE_LEXICON_PATH
        self.dialog_taboo_path = Path(dialog_taboo_path) if dialog_taboo_path else _DIALOG_TABOO_PATH
        self._scene_data: dict[str, Any] | None = None
        self._dialog_data: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------
    def _load_scene_lexicon(self) -> dict[str, Any]:
        if self._scene_data is None:
            try:
                text = self.scene_lexicon_path.read_text(encoding="utf-8")
                merged = self._parse_scene_lexicon(text)
                self._scene_data = merged
            except Exception as exc:
                logger.warning("加载场景辞林失败: %s", exc)
                self._scene_data = {"scene_types": [], "emotion_subtypes": [], "universal_lexicon": [], "usage_rules": {}}
        return self._scene_data

    @staticmethod
    def _parse_scene_lexicon(text: str) -> dict[str, Any]:
        """解析场景辞林 YAML。

        由于 emotion_subtypes 在文件内按 ## 2.x 分块重复出现，
        需要特殊处理：按 `## 2.x` 分块，每块解析为一个 subtype 组。
        """
        merged: dict[str, Any] = {"scene_types": [], "emotion_subtypes": [], "universal_lexicon": [], "usage_rules": {}}

        # 先加载全局文档获取 scene_types / universal_lexicon / usage_rules
        docs = list(yaml.safe_load_all(text))
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if "scene_types" in doc:
                merged["scene_types"] = doc["scene_types"]
            if "universal_lexicon" in doc:
                merged["universal_lexicon"] = doc["universal_lexicon"]
            if "usage_rules" in doc:
                merged["usage_rules"].update(doc["usage_rules"])

        # 按 ## 2.x 分块解析 emotion_subtypes
        # 正则：匹配 "## 2.x 场景类型名" 直到下一个 "## 2.x" 或 "# 3." 或文件结束
        blocks = re.split(r"\n(?=##\s+2\.\d+\s+)", text)
        for block in blocks:
            block = block.strip()
            header_match = re.match(r"##\s+2\.\d+\s+(\S+)", block)
            if not header_match:
                continue
            scene_type = header_match.group(1).strip()

            # 只解析该块中的 emotion_subtypes
            # 由于块中可能还有子标题，我们提取 emotion_subtypes: 到下一个 ## 或 --- 之间的内容
            subtype_text = LexiconInjector._extract_emotion_subtypes_block(block)
            if subtype_text:
                try:
                    parsed = yaml.safe_load(subtype_text)
                    if isinstance(parsed, dict) and "emotion_subtypes" in parsed:
                        for st in parsed["emotion_subtypes"]:
                            if isinstance(st, dict):
                                st["_scene_type"] = scene_type
                                merged["emotion_subtypes"].append(st)
                except Exception as exc:
                    logger.warning("解析场景块失败 [%s]: %s", scene_type, exc)

        return merged

    @staticmethod
    def _extract_emotion_subtypes_block(block: str) -> str:
        """从 ## 2.x 块中提取 emotion_subtypes YAML 文本。"""
        lines = block.split("\n")
        start_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("emotion_subtypes:"):
                start_idx = i
                break
        if start_idx is None:
            return ""

        # 收集缩进 >= start_line_indent 的行，直到遇到同层级的新键
        start_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
        collected = [lines[start_idx]]
        for line in lines[start_idx + 1 :]:
            stripped = line.strip()
            if not stripped:
                collected.append(line)
                continue
            indent = len(line) - len(line.lstrip())
            # 遇到新的同层键（如 ## 2.x 或 # 3.）停止
            if stripped.startswith("##") or stripped.startswith("# 3.") or stripped.startswith("---"):
                break
            # 遇到新的顶层键（缩进 <= start_indent 且不是列表项）停止
            if indent <= start_indent and not stripped.startswith("-"):
                break
            collected.append(line)

        return "\n".join(collected)

    def _load_dialog_taboo(self) -> dict[str, Any]:
        if self._dialog_data is None:
            try:
                docs = list(yaml.safe_load_all(self.dialog_taboo_path.read_text(encoding="utf-8")))
                merged: dict[str, Any] = {"characters": [], "cross_character_taboo": [], "usage_rules": {}}
                for doc in docs:
                    if not isinstance(doc, dict):
                        continue
                    if "character" in doc:
                        merged["characters"].append(doc)
                    if "cross_character_taboo" in doc:
                        merged["cross_character_taboo"] = doc["cross_character_taboo"]
                    if "usage_rules" in doc:
                        merged["usage_rules"].update(doc["usage_rules"])
                self._dialog_data = merged
            except Exception as exc:
                logger.warning("加载对话红线失败: %s", exc)
                self._dialog_data = {"characters": [], "cross_character_taboo": [], "usage_rules": {}}
        return self._dialog_data

    # ------------------------------------------------------------------
    # 场景类型匹配
    # ------------------------------------------------------------------
    def match_scene_type(
        self,
        outline: dict[str, str],
        chapter_num: int,
        prev_summary: str = "",
    ) -> list[str]:
        """根据大纲文本匹配最可能的场景类型。返回 1-2 个候选类型。"""
        lexicon = self._load_scene_lexicon()
        scene_types = lexicon.get("scene_types", [])
        if not scene_types:
            return []

        text_pool = " ".join([
            outline.get("arc", ""),
            outline.get("core_event", ""),
            outline.get("face_slap_method", ""),
            outline.get("chapter_hook", ""),
            outline.get("title", ""),
            prev_summary,
        ])

        scores: dict[str, int] = {}
        for st in scene_types:
            scores[st] = self._scene_type_score(st, text_pool)

        # 取前 2 名，且分数 > 0
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [st for st, score in ranked if score > 0][:2]

    @staticmethod
    def _scene_type_score(scene_type: str, text: str) -> int:
        """简单关键词匹配打分。"""
        score = 0
        text_lower = text.lower()

        # 类型名本身出现
        if scene_type in text:
            score += 5

        # 关键词映射
        keywords = {
            "解约/告别": ["解约", "离队", "开除", "告别", "离开", "退队", "合同"],
            "返乡/归家": ["回村", "返乡", "归家", "回寨", "到家", "侗寨", "榕江"],
            "系统觉醒": ["系统", "觉醒", "绑定", "激活", "血脉", "侗神瞳", "铜鼓"],
            "初次训练": ["训练", "练习", "练球", "基本功", "体能", "对抗"],
            "村超比赛": ["村超", "比赛", "联赛", "决赛", "对手", "裁判", "进球"],
            "直播弹幕互动": ["直播", "弹幕", "观众", "网友", "在线", "平台"],
            "侗族仪式": ["仪式", "萨玛", "铜鼓", "祭祀", "侗族", "鼓楼", "长老"],
            "伤病发作": ["伤病", "膝盖", "旧伤", "疼痛", "骨折", "复发", "队医"],
            "碾压/打脸": ["打脸", "碾压", "震惊", "反转", "反击", "嘲讽"],
            "危机/绝境": ["危机", "绝境", "困境", "围堵", "失败", "濒临"],
            "回忆闪回": ["回忆", "闪回", "当年", "曾经", "小时候", "过去"],
            "夜色独坐": ["夜色", "独坐", "独处", "深夜", "一个人", "窗前"],
        }
        for kw in keywords.get(scene_type, []):
            if kw in text_lower:
                score += 2
        return score

    # ------------------------------------------------------------------
    # 词条抽取
    # ------------------------------------------------------------------
    def pick_lexicon_entries(
        self,
        scene_types: list[str],
        count_per_scene: int = 2,
        seed: int | None = None,
    ) -> list[dict[str, str]]:
        """从匹配的场景类型中抽取词条。"""
        lexicon = self._load_scene_lexicon()
        rng = random.Random(seed)
        picked: list[dict[str, str]] = []
        used_words: set[str] = set()

        # 按场景类型分组的子类
        emotion_map = self._build_emotion_map(lexicon)

        for st in scene_types:
            subtypes = emotion_map.get(st, [])
            if not subtypes:
                continue
            subtype = rng.choice(subtypes) if len(subtypes) > 1 else subtypes[0]
            entries = subtype.get("lexicon_entries", [])
            candidates = [e for e in entries if isinstance(e, dict) and e.get("word", "") not in used_words]
            if not candidates:
                candidates = [e for e in entries if isinstance(e, dict)]
            if not candidates:
                continue
            selected = rng.sample(candidates, min(count_per_scene, len(candidates)))
            for e in selected:
                word = e.get("word", "")
                if word:
                    used_words.add(word)
                picked.append({
                    "scene_type": st,
                    "emotion_subtype": subtype.get("name", ""),
                    "word": word,
                    "context": str(e.get("context", "")).replace("\n", " ").strip(),
                    "taboo": str(e.get("taboo", "") or "").replace("\n", " ").strip(),
                })

        return picked

    def _build_emotion_map(self, lexicon: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """把 emotion_subtypes 按 _scene_type 分组。"""
        result: dict[str, list[dict[str, Any]]] = {}
        for subtype in lexicon.get("emotion_subtypes", []):
            if not isinstance(subtype, dict):
                continue
            st = subtype.get("_scene_type", "")
            if st:
                result.setdefault(st, []).append(subtype)
        return result

    # ------------------------------------------------------------------
    # 角色对话约束
    # ------------------------------------------------------------------
    def pick_character_constraints(
        self,
        character_names: list[str],
    ) -> list[dict[str, Any]]:
        """抽取指定角色的对话红线与词汇地址。"""
        dialog_data = self._load_dialog_taboo()
        results = []
        for doc in dialog_data.get("characters", []):
            char = doc.get("character", "")
            if not char or char not in character_names:
                continue
            results.append({
                "character": char,
                "persona_summary": doc.get("persona_summary", ""),
                "lexicon_address": doc.get("lexicon_address", []),
                "taboo": doc.get("taboo", []),
            })
        return results

    # ------------------------------------------------------------------
    # 注入文本生成
    # ------------------------------------------------------------------
    def build_injection_text(
        self,
        outline: dict[str, str],
        chapter_num: int,
        character_names: list[str],
        prev_summary: str = "",
        seed: int | None = None,
    ) -> str:
        """生成可注入 prompt 的辞林约束文本。"""
        scene_types = self.match_scene_type(outline, chapter_num, prev_summary)
        entries = self.pick_lexicon_entries(scene_types, count_per_scene=2, seed=seed) if scene_types else []
        char_constraints = self.pick_character_constraints(character_names)

        parts = ["\n【辞林写作约束——本章必须遵守】\n"]

        # 1. 场景类型
        if scene_types:
            parts.append(f"本章场景类型：{' + '.join(scene_types)}")
            parts.append("请从对应场景的情绪子类中选取最贴合本章的 1-2 个，并在描写中自然呈现。")

        # 2. 必选词条
        if entries:
            parts.append("\n【本章必选词条——必须自然嵌入正文，禁止改写为更'漂亮'的版本】")
            for i, e in enumerate(entries, 1):
                parts.append(
                    f"{i}. 「{e['word']}」\n"
                    f"   用途：{e['context']}\n"
                    f"   红线：{e['taboo'] or '无'}"
                )

        # 3. 通用词条限制
        parts.append("\n【通用词条限制】")
        parts.append("- 「又」字表达重复/宿命感，本章最多使用 2 次")
        parts.append("- 「声音」必须带来源或质感，禁止孤立出现")
        parts.append("- 「没有」必须承载具体缺位（空间/能力/情感）")

        # 4. 角色红线
        if char_constraints:
            parts.append("\n【角色对话红线——命中则整句重写，禁止仅替换同义词】")
            for cc in char_constraints:
                parts.append(f"\n■ {cc['character']}")
                if cc.get("persona_summary"):
                    parts.append(f"  人设：{cc['persona_summary']}")
                if cc.get("taboo"):
                    taboo_words = [str(t.get("word", "")) for t in cc["taboo"] if isinstance(t, dict)]
                    if taboo_words:
                        parts.append(f"  绝对禁用词：{'、'.join(taboo_words)}")
                if cc.get("lexicon_address"):
                    parts.append("  情境词汇地址（该角色在这些情境下只能说这类话）：")
                    for la in cc["lexicon_address"]:
                        if not isinstance(la, dict):
                            continue
                        vocab = [str(v) for v in la.get("vocabulary", [])]
                        if vocab:
                            parts.append(f"    - {la.get('situation', '')}：{' / '.join(vocab[:3])}")

        # 5. 跨角色通用红线
        cross_taboo = self._load_dialog_taboo().get("cross_character_taboo", [])
        cross_words = [str(t.get("word", "")) for t in cross_taboo if isinstance(t, dict)]
        if cross_words:
            parts.append("\n【跨角色通用红线——任何角色台词禁用】")
            parts.append("、".join(cross_words + ["其实", "说白了", "归根结底", "值得注意的是"]))

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 轻量工具：判断文本是否命中红线
    # ------------------------------------------------------------------
    @staticmethod
    def check_red_lines(text: str, taboo_words: list[str]) -> list[tuple[str, str]]:
        """返回命中红线的 (词, 所在行)。"""
        hits = []
        for line in text.split("\n"):
            for word in taboo_words:
                if word and word in line:
                    hits.append((word, line.strip()))
        return hits
