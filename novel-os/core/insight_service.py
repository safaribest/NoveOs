"""洞察服务：基于 LLM 生成网文选题和大纲。"""

from __future__ import annotations

import json
import json5
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.llm_settings_client import LLMProviderError, LLMSettingsClient

logger = logging.getLogger("novel-os.insight")

DEFAULT_CATEGORIES_PATH = Path(__file__).resolve().parent.parent / "config" / "genres.json"
JSON_DEBUG_PATH = Path(__file__).resolve().parent.parent / "logs" / "json_debug.txt"


@dataclass
class Topic:
    """选题。"""

    id: str
    title: str
    hook: str
    slap_points: list[str] = field(default_factory=list)
    target_reader: str = ""
    risks: list[str] = field(default_factory=list)
    why_now: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "hook": self.hook,
            "slap_points": self.slap_points,
            "target_reader": self.target_reader,
            "risks": self.risks,
            "why_now": self.why_now,
        }


@dataclass
class GeneratePreferences:
    """选题生成偏好。"""

    platform: str = "起点"
    style: str = ""
    chapters_target: int = 200
    words_per_chapter: int = 2200
    extra_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "style": self.style,
            "chapters_target": self.chapters_target,
            "words_per_chapter": self.words_per_chapter,
            "extra_notes": self.extra_notes,
        }


class InsightService:
    """洞察服务。"""

    def __init__(
        self,
        provider_name: str | None = None,
        categories_path: Path | str | None = None,
    ):
        self.llm = LLMSettingsClient()
        self.provider_name = provider_name
        self.categories_path = Path(categories_path or DEFAULT_CATEGORIES_PATH)
        self._categories: list[dict[str, Any]] | None = None

    def load_categories(self) -> list[dict[str, Any]]:
        """加载分类树。"""
        if self._categories is not None:
            return self._categories

        if not self.categories_path.exists():
            logger.warning("分类配置文件不存在: %s", self.categories_path)
            self._categories = []
            return self._categories

        try:
            import json as _json

            with self.categories_path.open("r", encoding="utf-8") as f:
                data = _json.load(f)
            self._categories = data.get("categories", [])
        except Exception as exc:  # noqa: BLE001
            logger.error("加载分类配置失败: %s", exc)
            self._categories = []

        return self._categories

    def find_category(self, category_id: str) -> dict[str, Any] | None:
        """根据 ID 查找分类（支持三级）。"""

        def search(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
            for node in nodes:
                if node.get("id") == category_id:
                    return node
                if "children" in node:
                    found = search(node["children"])
                    if found:
                        return found
            return None

        return search(self.load_categories())

    def get_category_path(self, category_id: str) -> list[dict[str, Any]]:
        """获取分类路径（从根到叶子）。"""
        path: list[dict[str, Any]] = []

        def dfs(
            nodes: list[dict[str, Any]],
            current: list[dict[str, Any]],
        ) -> bool:
            for node in nodes:
                new_path = current + [node]
                if node.get("id") == category_id:
                    path.extend(new_path)
                    return True
                if "children" in node and dfs(node["children"], new_path):
                    return True
            return False

        dfs(self.load_categories(), [])
        return path

    def build_topic_prompt(
        self,
        category: dict[str, Any],
        preferences: GeneratePreferences,
    ) -> str:
        """构建选题生成 Prompt。"""
        genre = category.get("genre", category.get("name", "网文"))
        tags = ", ".join(category.get("tags", []))

        style_hint = f"风格偏好：{preferences.style}\n" if preferences.style else ""
        notes_hint = f"额外要求：{preferences.extra_notes}\n" if preferences.extra_notes else ""

        return f"""你是一位资深网文编辑和爆款选题专家。请针对以下分类，生成 8-10 个有爆款潜力的长篇网文选题。

【分类信息】
类型：{genre}
标签：{tags}
目标平台：{preferences.platform}
目标篇幅：{preferences.chapters_target} 章，约 {preferences.words_per_chapter} 字/章
{style_hint}{notes_hint}
【选题要求】
1. 每个选题必须包含：标题、一句话卖点、核心爽点（3-5 个）、目标读者画像、风险红线、为什么现在能火
2. 标题要有网文感，避免文艺腔
3. 避开同质化严重的老梗，优先近 1-2 年有热度的新梗/新设定
4. 核心爽点要具体，避免"打脸""逆袭"这种空泛词
5. 风险红线要指出这个题材容易写崩的地方

【输出格式】
先输出一段 200 字以内的整体趋势判断，然后在 Markdown 代码块中输出以下 JSON 数组：

```json
[
  {{
    "id": "topic_1",
    "title": "选题标题",
    "hook": "一句话卖点，30字以内",
    "slap_points": ["爽点1", "爽点2", "爽点3"],
    "target_reader": "目标读者画像",
    "risks": ["风险1", "风险2"],
    "why_now": "当前热度理由，50字以内"
  }}
]
```

【重要约束】
1. JSON 必须放在 ```json ... ``` 代码块中
2. JSON 字符串中不能包含真实换行符或制表符，如需换行请用空格替代
3. 字符串中的双引号必须正确转义
4. 不要在 JSON 代码块之外再输出另一个 JSON
5. 确保输出是合法的 JSON，可以直接被 Python json.loads 解析"""

    def _extract_json(self, text: str) -> list[dict[str, Any]]:
        """从 LLM 输出中提取 JSON 数组，带修复逻辑。"""
        # 优先匹配 ```json ... ```
        code_block = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if code_block:
            json_str = code_block.group(1)
        else:
            # 匹配最后一个 [ ... ]
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if not match:
                raise ValueError("未在输出中找到 JSON 数组")
            json_str = match.group(0)

        # 清理 JSON 字符串中的非法控制字符
        json_str = self._sanitize_json_string(json_str)

        data = self._parse_json_robust(json_str, text, expect_type=list)
        return data

    def _sanitize_json_string(self, json_str: str) -> str:
        """清理 JSON 字符串中的非法控制字符。"""
        # 移除所有 C0 控制字符（0x00-0x1F），仅保留常见空白字符的字符形式
        result = []
        for char in json_str:
            code = ord(char)
            if code < 0x20 and char not in "\n\t\r":
                continue
            result.append(char)
        return "".join(result)

    def _fix_json(self, json_str: str) -> str:
        """尝试修复常见 JSON 格式问题。"""
        fixed = json_str

        # 1. 把真实空白字符替换为空格（控制字符 sanitize 后残余）
        fixed = re.sub(r"[\n\r\t\x0b\x0c]+", " ", fixed)

        # 2. 中文双引号 -> 英文双引号
        fixed = fixed.replace("\"", '"').replace("\"", '"')

        # 3. 单引号 -> 双引号（简单情况）
        fixed = re.sub(r"(?<!\\)'", '"', fixed)

        # 4. 移除对象和数组中的 trailing commas
        fixed = re.sub(r",(\s*[}\]])", r"\1", fixed)

        # 5. 修复缺少逗号的对象/数组分隔：} { -> }, { 和 ] [ -> ], [
        fixed = re.sub(r"}(\s*){", r"},\1{", fixed)
        fixed = re.sub(r"](\s*)\[", r"],\1[", fixed)

        # 6. 修复对象内部键值对之间缺少逗号
        # 值后紧跟下一个键名（双引号开头）
        fixed = re.sub(
            r'("\s*:\s*(?:"(?:[^"\\]|\\.)*"|\[[^\]]*\]|\{[^}]*\}|\d+(?:\.\d+)?|true|false|null))\s+"',
            r'\1,"',
            fixed,
        )
        # 值后紧跟下一个键名（单引号开头，已替换为双引号）
        fixed = re.sub(
            r"('\\s*:\\s*(?:'(?:[^'\\\\]|\\\\.)*'|\\[[^\\]]*\\]|\\{[^}]*\\}|\\d+(?:\\.\\d+)?|true|false|null))\\s+'",
            r"\1,'",
            fixed,
        )

        # 7. 修复数组元素之间缺少逗号："] [" 或 "} {" 形式已在上面处理，
        #    但数组元素是字符串时："a" "b" -> "a","b"
        fixed = re.sub(
            r'("(?:[^"\\]|\\.)*")\s+("(?:[^"\\]|\\.)*")',
            r'\1,\2',
            fixed,
        )

        # 8. 修复对象/数组结束后紧接下一个键/值缺少逗号
        # 例如: } "key" -> }, "key" 或 ] "val" -> ], "val"
        fixed = re.sub(r'}(\s+)(")', r'},\1\2', fixed)
        fixed = re.sub(r"](\s+)(')", r"],\1\2", fixed)

        # 9. 去除首尾空白
        fixed = fixed.strip()

        return fixed

    def _recover_truncated_json(self, json_str: str) -> str | None:
        """尝试修复被截断的 JSON（常见于 LLM 输出超长被切断）。"""
        s = json_str.rstrip()
        if not s:
            return None

        # 1. 关闭未闭合的字符串
        in_string = False
        escaped = False
        for i, ch in enumerate(s):
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
        if in_string:
            s += '"'

        # 2. 用栈关闭未闭合的 [ 和 { （注意跳过字符串内）
        stack: list[str] = []
        in_string = False
        escaped = False
        for ch in s:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in ("[", "{"):
                stack.append(ch)
            elif ch == "]":
                if stack and stack[-1] == "[":
                    stack.pop()
            elif ch == "}":
                if stack and stack[-1] == "{":
                    stack.pop()

        # 3. 如果末尾是一个还没写完的对象（{...），且整体在数组里，尝试删掉这个残缺对象并关闭数组
        if stack == ["[", "{"]:
            # 找到数组中最后一个完整对象后的位置（},
            last_close = -1
            in_string = False
            escaped = False
            for i, ch in enumerate(s):
                if escaped:
                    escaped = False
                    continue
                if ch == "\\":
                    escaped = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "}":
                    # 检查后面是否是 , 或 ] 或空白，避免是对象内部的 }
                    j = i + 1
                    while j < len(s) and s[j] in " \t\n\r,":
                        j += 1
                    if j >= len(s) or s[j] in "{]":
                        last_close = i
            if last_close >= 0:
                s = s[: last_close + 1] + "]"
                stack.clear()
            else:
                # 数组里没有任何完整对象，返回空数组
                return "[]"
        else:
            # 4. 通用补全
            while stack:
                opener = stack.pop()
                s += "]" if opener == "[" else "}"

        return s

    def _parse_json_robust(
        self,
        json_str: str,
        original_text: str = "",
        expect_type: type | None = None,
    ) -> Any:
        """强力解析 JSON，先标准解析，再修复，再截断恢复，最后回退到 json5。"""
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.warning("JSON 初次解析失败，尝试修复: %s", exc)

        fixed = self._fix_json(json_str)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError as exc2:
            logger.warning("JSON 修复后仍失败，尝试截断恢复: %s", exc2)

        recovered = self._recover_truncated_json(fixed)
        if recovered is not None:
            try:
                return json.loads(recovered)
            except json.JSONDecodeError as exc3:
                logger.warning("JSON 截断恢复后仍失败，尝试 json5: %s", exc3)
        else:
            logger.warning("JSON 截断恢复无法处理，尝试 json5")

        try:
            data = json5.loads(fixed)
        except Exception as exc3:  # noqa: BLE001
            # 保存调试信息
            try:
                JSON_DEBUG_PATH.write_text(
                    f"=== 原始文本 ===\n{original_text}\n\n"
                    f"=== 提取的 JSON ===\n{json_str}\n\n"
                    f"=== 修复后 ===\n{fixed}\n\n"
                    f"=== 错误 ===\n{exc3}",
                    encoding="utf-8",
                )
            except Exception:
                pass
            raise ValueError(f"JSON 解析失败: {exc3}") from exc3

        if expect_type is not None and not isinstance(data, expect_type):
            raise ValueError(f"JSON 类型不匹配，期望 {expect_type.__name__}")

        return data

    def _parse_topics(self, data: list[dict[str, Any]]) -> list[Topic]:
        """解析选题列表。"""
        topics = []
        for i, item in enumerate(data, 1):
            topic = Topic(
                id=item.get("id") or f"topic_{i}_{uuid.uuid4().hex[:8]}",
                title=item.get("title", "未命名选题"),
                hook=item.get("hook", ""),
                slap_points=item.get("slap_points", []) or [],
                target_reader=item.get("target_reader", ""),
                risks=item.get("risks", []) or [],
                why_now=item.get("why_now", ""),
            )
            topics.append(topic)
        return topics

    # ═══════════════════════════════════════════════════════════════════════
    # 大纲生成
    # ═══════════════════════════════════════════════════════════════════════

    def build_outline_prompt(
        self,
        topic: dict[str, Any],
        category: dict[str, Any],
        preferences: GenerateOutlinePreferences,
    ) -> str:
        """构建大纲生成 Prompt。"""
        genre = category.get("genre", category.get("name", "网文"))
        tags = ", ".join(category.get("tags", []))
        title = topic.get("title", "未命名选题")
        hook = topic.get("hook", "")
        slap_points = "\n".join(f"- {p}" for p in topic.get("slap_points", []))
        target_reader = topic.get("target_reader", "")
        risks = "\n".join(f"- {r}" for r in topic.get("risks", []))

        style_hint = f"风格偏好：{preferences.style}\n" if preferences.style else ""
        notes_hint = f"额外要求：{preferences.extra_notes}\n" if preferences.extra_notes else ""

        ct = preferences.chapters_target
        if ct <= 10:
            volume_guidance = f"设计 1-2 卷，每卷包含若干章节，卷范围必须严格在 1-{ct} 之间"
            example_range = f"1-{min(ct, 5)}"
        elif ct <= 30:
            volume_guidance = f"设计 1-3 卷，每卷范围必须严格在 1-{ct} 之间"
            example_range = f"1-{min(ct, 15)}"
        else:
            volume_guidance = "设计合理的卷数（建议每卷 10-30 章），每卷包含：卷号、标题、章节范围、主题、卷高潮"
            example_range = "1-30"

        return f"""你是一位资深网文策划，擅长设计长篇网文的完整大纲。请基于以下选题，生成一份 {preferences.chapters_target} 章的详细大纲。

【选题信息】
标题：{title}
卖点：{hook}
目标读者：{target_reader}
分类：{genre}
标签：{tags}
目标平台：{preferences.platform}
目标篇幅：{preferences.chapters_target} 章，约 {preferences.words_per_chapter} 字/章
{style_hint}{notes_hint}
【核心爽点】
{slap_points}

【风险红线】
{risks}

【输出要求】
1. {volume_guidance}，每卷有明确的主题和卷高潮，且卷范围不得超过总章数 {preferences.chapters_target}
2. 每章必须包含：章节号、标题、所属卷、核心事件、打脸目标、打脸方式、男主高光时刻、章节钩子、情绪比例、解锁技能
3. 设计 3-5 个主要角色，简介和弧光各15字以内
4. 设计 5-8 个债务/伏笔，content 20字以内
5. 设计 2-3 条世界观/系统规则
6. 设计 3-5 个技能/金手指，description 15字以内
7. 先输出 300 字以内的整体结构说明
8. 卷范围必须严格落在 1-{preferences.chapters_target} 之间，禁止出现超出总章数的范围

【输出格式】
必须在 Markdown 代码块中输出以下 JSON（JSON 字符串中不要包含真实换行符或制表符）：

```json
{{
  "summary": "整体结构说明",
  "volumes": [
    {{"index": 1, "title": "卷标题", "range": "{example_range}", "theme": "卷主题", "climax": "卷高潮"}}
  ],
  "outline": [
    {{
      "chapter": 1,
      "title": "章节标题",
      "arc": "所属卷标题",
      "core_event": "核心事件，30字以内",
      "face_slap_target": "打脸目标，10字以内",
      "face_slap_method": "打脸方式，15字以内",
      "husband_moment": "男主高光，15字以内",
      "chapter_hook": "章节钩子，15字以内",
      "emotion_ratio": "爽:虐:甜 比例，如 7:2:1",
      "skill_unlocked": "本章解锁的技能，无则留空"
    }}
  ],
  "characters": [
    {{"name": "角色名", "role": "主角/反派/女主/队友", "brief": "简介", "arc": "人物弧光", "tags": ["标签1", "标签2"]}}
  ],
  "debts": [
    {{"debt_id": "d1", "type": "债务", "content": "伏笔内容", "bury_chapter": 5, "collect_chapter": 50}}
  ],
  "foreshadowing": [
    {{"debt_id": "f1", "type": "伏笔", "content": "伏笔内容", "bury_chapter": 10, "collect_chapter": 80}}
  ],
  "rules": ["规则1", "规则2"],
  "skills": [
    {{"name": "技能名", "chapter": 3, "description": "技能效果"}}
  ]
}}
```

请确保 JSON 格式正确，可以被程序直接解析。"""

    def build_outline_structure_prompt(
        self,
        topic: dict[str, Any],
        category: dict[str, Any],
        preferences: GenerateOutlinePreferences,
    ) -> str:
        """构建大纲整体结构 Prompt：只生成卷规划、角色、债务、规则、技能。"""
        genre = category.get("genre", category.get("name", "网文"))
        tags = ", ".join(category.get("tags", []))
        title = topic.get("title", "未命名选题")
        hook = topic.get("hook", "")
        slap_points = "\n".join(f"- {p}" for p in topic.get("slap_points", []))
        target_reader = topic.get("target_reader", "")
        risks = "\n".join(f"- {r}" for r in topic.get("risks", []))

        style_hint = f"风格偏好：{preferences.style}\n" if preferences.style else ""
        notes_hint = f"额外要求：{preferences.extra_notes}\n" if preferences.extra_notes else ""

        ct = preferences.chapters_target
        if ct <= 10:
            volume_guidance = f"设计 1-2 卷，每卷包含若干章节，卷范围必须严格在 1-{ct} 之间"
            example_range = f"1-{min(ct, 5)}"
        elif ct <= 30:
            volume_guidance = f"设计 1-3 卷，每卷范围必须严格在 1-{ct} 之间"
            example_range = f"1-{min(ct, 15)}"
        else:
            volume_guidance = "设计合理的卷数（建议每卷 10-30 章），每卷包含：卷号、标题、章节范围、主题、卷高潮"
            example_range = "1-30"

        return f"""你是一位资深网文策划。请基于以下选题，先设计一份 {preferences.chapters_target} 章小说的整体结构，**不需要输出每章详细内容**。

【选题信息】
标题：{title}
卖点：{hook}
目标读者：{target_reader}
分类：{genre}
标签：{tags}
目标平台：{preferences.platform}
目标篇幅：{preferences.chapters_target} 章，约 {preferences.words_per_chapter} 字/章
{style_hint}{notes_hint}
【核心爽点】
{slap_points}

【风险红线】
{risks}

【输出要求】
1. {volume_guidance}，每卷包含：卷号、标题、章节范围、主题、卷高潮，且卷范围不得超过总章数 {preferences.chapters_target}
2. 设计 3-5 个主要角色，简介和弧光各 15 字以内
3. 设计 5-8 个债务/伏笔，content 20 字以内，埋下/回收章节合理
4. 设计 2-3 条世界观/系统规则
5. 设计 3-5 个技能/金手指，description 15 字以内
6. 输出 300 字以内的整体结构说明
7. 卷范围必须严格落在 1-{preferences.chapters_target} 之间，禁止出现超出总章数的范围

【输出格式】
必须在 Markdown 代码块中输出以下 JSON：

```json
{{
  "summary": "整体结构说明",
  "volumes": [
    {{"index": 1, "title": "卷标题", "range": "{example_range}", "theme": "卷主题", "climax": "卷高潮"}}
  ],
  "characters": [
    {{"name": "角色名", "role": "主角/反派/女主/队友", "brief": "简介", "arc": "人物弧光", "tags": ["标签1"]}}
  ],
  "debts": [
    {{"debt_id": "d1", "type": "债务", "content": "伏笔内容", "bury_chapter": 5, "collect_chapter": 20}}
  ],
  "foreshadowing": [
    {{"debt_id": "f1", "type": "伏笔", "content": "伏笔内容", "bury_chapter": 10, "collect_chapter": 40}}
  ],
  "rules": ["规则1", "规则2"],
  "skills": [
    {{"name": "技能名", "chapter": 3, "description": "技能效果"}}
  ]
}}
```

请确保 JSON 格式正确，可以被程序直接解析。"""

    def build_volume_outline_prompt(
        self,
        topic: dict[str, Any],
        category: dict[str, Any],
        preferences: GenerateOutlinePreferences,
        volume: dict[str, Any],
        characters: list[dict[str, Any]],
        rules: list[str],
        skills: list[dict[str, Any]],
        debts: list[dict[str, Any]],
    ) -> str:
        """构建单卷章节大纲 Prompt。"""
        genre = category.get("genre", category.get("name", "网文"))
        title = topic.get("title", "未命名选题")
        hook = topic.get("hook", "")
        slap_points = "\n".join(f"- {p}" for p in topic.get("slap_points", []))
        style_hint = f"风格偏好：{preferences.style}\n" if preferences.style else ""
        notes_hint = f"额外要求：{preferences.extra_notes}\n" if preferences.extra_notes else ""

        volume_range = volume.get("range", "1-15")
        volume_title = volume.get("title", "未命名卷")
        volume_theme = volume.get("theme", "")
        volume_climax = volume.get("climax", "")

        characters_str = "\n".join(
            f"- {c.get('name')}（{c.get('role', '')}）：{c.get('brief', '')}" for c in characters
        )
        rules_str = "\n".join(f"- {r}" for r in rules)
        skills_str = "\n".join(
            f"- {s.get('name')}（{s.get('chapter')}章解锁）：{s.get('description', '')}" for s in skills
        )
        debts_str = "\n".join(
            f"- {d.get('debt_id')}（{d.get('type')}，{d.get('bury_chapter')}章埋下，{d.get('collect_chapter')}章回收）：{d.get('content', '')}"
            for d in debts
        )

        return f"""你是一位资深网文策划。请基于以下选题和整体结构，生成**第 {volume_range} 章**的详细章节大纲。

【选题信息】
标题：{title}
卖点：{hook}
分类：{genre}
目标平台：{preferences.platform}
目标篇幅：{preferences.chapters_target} 章，约 {preferences.words_per_chapter} 字/章
{style_hint}{notes_hint}
【核心爽点】
{slap_points}

【本卷信息】
卷标题：{volume_title}
章节范围：{volume_range}
卷主题：{volume_theme}
卷高潮：{volume_climax}

【已有设定】
主要角色：
{characters_str}

世界观/系统规则：
{rules_str}

技能/金手指：
{skills_str}

债务/伏笔：
{debts_str}

【输出要求】
1. 只为本卷范围（{volume_range}）内的章节生成详细大纲
2. 每章包含：章节号、标题、所属卷、核心事件、打脸目标、打脸方式、男主高光时刻、章节钩子、情绪比例、解锁技能
3. 章节号必须严格对应范围
4. 注意埋设/回收已有债务伏笔，必要时新增本卷内的临时伏笔

【输出格式】
必须在 Markdown 代码块中输出以下 JSON：

```json
{{
  "outline": [
    {{
      "chapter": 1,
      "title": "章节标题",
      "arc": "{volume_title}",
      "core_event": "核心事件，30字以内",
      "face_slap_target": "打脸目标，10字以内",
      "face_slap_method": "打脸方式，15字以内",
      "husband_moment": "男主高光，15字以内",
      "chapter_hook": "章节钩子，15字以内",
      "emotion_ratio": "爽:虐:甜 比例，如 7:2:1",
      "skill_unlocked": "本章解锁的技能，无则留空"
    }}
  ]
}}
```

请确保 JSON 格式正确，可以被程序直接解析。"""

    def _split_volume_ranges(self, chapters_target: int, volumes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """如果 LLM 没有返回合理卷规划，按每卷最多 15 章自动拆分。"""
        if volumes and all(v.get("range") for v in volumes):
            return volumes
        per_volume = 15
        volumes = []
        start = 1
        while start <= chapters_target:
            end = min(start + per_volume - 1, chapters_target)
            volumes.append({"index": len(volumes) + 1, "title": f"第{len(volumes)+1}卷", "range": f"{start}-{end}", "theme": "", "climax": ""})
            start = end + 1
        return volumes

    def _parse_outline(self, data: dict[str, Any]) -> OutlineResult:
        """解析大纲结果。"""
        outline = []
        for item in data.get("outline", []):
            outline.append(
                OutlineChapter(
                    chapter=int(item.get("chapter", 0)),
                    title=item.get("title", "未命名章节"),
                    arc=item.get("arc", ""),
                    core_event=item.get("core_event", ""),
                    face_slap_target=item.get("face_slap_target", ""),
                    face_slap_method=item.get("face_slap_method", ""),
                    husband_moment=item.get("husband_moment", ""),
                    chapter_hook=item.get("chapter_hook", ""),
                    emotion_ratio=item.get("emotion_ratio", "5:3:2"),
                    skill_unlocked=item.get("skill_unlocked", ""),
                )
            )

        characters = []
        for item in data.get("characters", []):
            characters.append(
                OutlineCharacter(
                    name=item.get("name", "未命名"),
                    role=item.get("role", ""),
                    brief=item.get("brief", ""),
                    arc=item.get("arc", ""),
                    tags=item.get("tags", []) or [],
                )
            )

        debts = []
        for item in data.get("debts", []):
            debts.append(
                OutlineDebt(
                    debt_id=item.get("debt_id", f"d_{uuid.uuid4().hex[:6]}"),
                    type=item.get("type", "债务"),
                    content=item.get("content", ""),
                    bury_chapter=int(item.get("bury_chapter", 1)),
                    collect_chapter=int(item.get("collect_chapter", 1)),
                )
            )

        foreshadowing = []
        for item in data.get("foreshadowing", []):
            foreshadowing.append(
                OutlineDebt(
                    debt_id=item.get("debt_id", f"f_{uuid.uuid4().hex[:6]}"),
                    type=item.get("type", "伏笔"),
                    content=item.get("content", ""),
                    bury_chapter=int(item.get("bury_chapter", 1)),
                    collect_chapter=int(item.get("collect_chapter", 1)),
                )
            )

        return OutlineResult(
            topic_title=data.get("topic_title", ""),
            topic_hook=data.get("topic_hook", ""),
            genre=data.get("genre", ""),
            platform=data.get("platform", ""),
            chapters_target=data.get("chapters_target", 200),
            words_per_chapter=data.get("words_per_chapter", 2200),
            volumes=data.get("volumes", []),
            outline=outline,
            characters=characters,
            debts=debts,
            foreshadowing=foreshadowing,
            rules=data.get("rules", []),
            skills=data.get("skills", []),
            summary=data.get("summary", ""),
        )

    def generate_outline(
        self,
        topic: dict[str, Any],
        category_id: str,
        preferences: GenerateOutlinePreferences | None = None,
    ) -> OutlineResult:
        """生成大纲。<=30 章一次性生成，>30 章分卷拼接。"""
        prefs = preferences or GenerateOutlinePreferences()
        category = self.find_category(category_id)
        if not category:
            raise ValueError(f"分类不存在: {category_id}")

        logger.info("开始为选题 '%s' 生成大纲（目标 %d 章）", topic.get("title", "未命名"), prefs.chapters_target)

        if prefs.chapters_target <= 30:
            return self._generate_outline_single(topic, category, prefs)

        return self._generate_outline_multi_volume(topic, category, prefs)

    def _generate_outline_single(
        self,
        topic: dict[str, Any],
        category: dict[str, Any],
        prefs: GenerateOutlinePreferences,
    ) -> OutlineResult:
        """一次性生成完整大纲。"""
        prompt = self.build_outline_prompt(topic, category, prefs)
        content = self._call_llm(prompt, max_tokens=16384)
        data = self._extract_json_object(content)
        result = self._parse_outline(data)
        return result

    def _generate_outline_multi_volume(
        self,
        topic: dict[str, Any],
        category: dict[str, Any],
        prefs: GenerateOutlinePreferences,
    ) -> OutlineResult:
        """分卷生成大纲并拼接。"""
        # 1. 生成整体结构
        structure_prompt = self.build_outline_structure_prompt(topic, category, prefs)
        structure_content = self._call_llm(structure_prompt, max_tokens=16384)
        structure_data = self._extract_json_object(structure_content)

        # 解析结构（使用 _parse_outline 解析，outline 字段可能为空）
        structure = self._parse_outline(structure_data)
        volumes = self._split_volume_ranges(prefs.chapters_target, structure.volumes)

        logger.info("开始分卷生成，共 %d 卷", len(volumes))

        # 2. 逐卷生成章节
        all_outline: list[OutlineChapter] = []
        character_dicts = [c.to_dict() for c in structure.characters]
        debt_dicts = [d.to_dict() for d in structure.debts + structure.foreshadowing]
        for volume in volumes:
            volume_prompt = self.build_volume_outline_prompt(
                topic, category, prefs, volume,
                character_dicts,
                structure.rules,
                structure.skills,
                debt_dicts,
            )
            volume_content = self._call_llm(volume_prompt, max_tokens=16384)
            volume_data = self._extract_json_object(volume_content)
            volume_result = self._parse_outline(volume_data)
            all_outline.extend(volume_result.outline)
            logger.info("第 %s 卷生成完成，%d 章", volume.get("range"), len(volume_result.outline))

        # 3. 合并结果
        result = structure
        result.outline = sorted(all_outline, key=lambda x: x.chapter)
        result.chapters_target = prefs.chapters_target

        return result

    def _call_llm(self, prompt: str, max_tokens: int = 16384) -> str:
        """调用 LLM 并返回内容。"""
        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                provider_name=self.provider_name,
                temperature=0.8,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except LLMProviderError as exc:
            logger.error("LLM 调用失败: %s", exc)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM 调用失败: %s", exc)
            raise RuntimeError(f"LLM 调用失败: {exc}") from exc

    def _extract_json_object(self, content: str) -> dict[str, Any]:
        """从 LLM 输出中提取 JSON 对象。"""
        code_block = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if code_block:
            json_str = code_block.group(1)
        else:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                raise ValueError("未在输出中找到 JSON 对象")
            json_str = match.group(0)

        json_str = self._sanitize_json_string(json_str)
        return self._parse_json_robust(json_str, content, expect_type=dict)
        return result

    def generate_topics(
        self,
        category_id: str,
        preferences: GeneratePreferences | None = None,
    ) -> list[Topic]:
        """生成选题。"""
        prefs = preferences or GeneratePreferences()
        category = self.find_category(category_id)
        if not category:
            raise ValueError(f"分类不存在: {category_id}")

        prompt = self.build_topic_prompt(category, prefs)
        logger.info("开始为分类 %s 生成选题", category_id)

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                provider_name=self.provider_name,
                temperature=0.9,
                max_tokens=12000,
            )
            content = response.choices[0].message.content or ""
        except LLMProviderError as exc:
            logger.error("生成选题失败: %s", exc)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("生成选题失败: %s", exc)
            raise RuntimeError(f"生成选题失败: {exc}") from exc

        try:
            data = self._extract_json(content)
            topics = self._parse_topics(data)
        except ValueError as exc:
            logger.error("解析选题失败: %s\n原始输出: %s", exc, content[:500])
            raise RuntimeError(f"解析选题失败: {exc}") from exc

        logger.info("成功生成 %d 个选题", len(topics))
        return topics


# ═══════════════════════════════════════════════════════════════════════════
# 大纲生成
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class OutlineChapter:
    """大纲章节。"""

    chapter: int
    title: str
    arc: str
    core_event: str
    face_slap_target: str
    face_slap_method: str
    husband_moment: str
    chapter_hook: str
    emotion_ratio: str
    skill_unlocked: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter": self.chapter,
            "title": self.title,
            "arc": self.arc,
            "core_event": self.core_event,
            "face_slap_target": self.face_slap_target,
            "face_slap_method": self.face_slap_method,
            "husband_moment": self.husband_moment,
            "chapter_hook": self.chapter_hook,
            "emotion_ratio": self.emotion_ratio,
            "skill_unlocked": self.skill_unlocked,
        }


@dataclass
class OutlineCharacter:
    """人设。"""

    name: str
    role: str
    brief: str
    arc: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "brief": self.brief,
            "arc": self.arc,
            "tags": self.tags,
        }


@dataclass
class OutlineDebt:
    """债务/伏笔。"""

    debt_id: str
    type: str
    content: str
    bury_chapter: int
    collect_chapter: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "debt_id": self.debt_id,
            "type": self.type,
            "content": self.content,
            "bury_chapter": self.bury_chapter,
            "collect_chapter": self.collect_chapter,
        }


@dataclass
class OutlineResult:
    """大纲生成结果。"""

    topic_title: str
    topic_hook: str
    genre: str
    platform: str
    chapters_target: int
    words_per_chapter: int
    volumes: list[dict[str, Any]]
    outline: list[OutlineChapter]
    characters: list[OutlineCharacter]
    debts: list[OutlineDebt]
    foreshadowing: list[OutlineDebt]
    rules: list[str]
    skills: list[dict[str, Any]]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_title": self.topic_title,
            "topic_hook": self.topic_hook,
            "genre": self.genre,
            "platform": self.platform,
            "chapters_target": self.chapters_target,
            "words_per_chapter": self.words_per_chapter,
            "volumes": self.volumes,
            "outline": [o.to_dict() for o in self.outline],
            "characters": [c.to_dict() for c in self.characters],
            "debts": [d.to_dict() for d in self.debts],
            "foreshadowing": [f.to_dict() for f in self.foreshadowing],
            "rules": self.rules,
            "skills": self.skills,
            "summary": self.summary,
        }


class GenerateOutlinePreferences:
    """大纲生成偏好。"""

    def __init__(
        self,
        platform: str = "起点",
        style: str = "",
        chapters_target: int = 200,
        words_per_chapter: int = 2200,
        extra_notes: str = "",
    ):
        self.platform = platform
        self.style = style
        self.chapters_target = chapters_target
        self.words_per_chapter = words_per_chapter
        self.extra_notes = extra_notes


