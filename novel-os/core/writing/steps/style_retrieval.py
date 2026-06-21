"""StyleRetrieval Step —— 风格检索步骤。

在 Director + BeatPlanner 之后执行，根据当前题材检索风格规则和示例，
注入到 ChapterContext 中供后续 Steps 使用。

职责：
1. 根据当前题材（genre）选择对应风格库
2. 检索风格规则（句长/对话/情绪等约束）
3. 检索 novel-style-db 真实小说参考（技法+片段+语汇）
4. 检索经典片段示例（相似场景）
5. 将规则和示例存储到 ctx 供 SceneWriter/HookEngineer 使用
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.writing.context import ChapterContext
from core.writing.steps.base import PipelineStep, StepResult

logger = logging.getLogger("novel-os.steps.style_retrieval")


class StyleRetrievalStep(PipelineStep):
    """风格检索步骤——在规划后注入风格规则。"""

    name = "StyleRetrieval"

    # 风格库根目录（项目内路径）
    _PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
    STYLE_GUIDE_DIR = Path(__file__).parent.parent.parent / "style_guide"

    # Novel-OS 风格参考库（book-to-skill 处理 data/ 35 本小说产出）
    NOVEL_DB_DIR = _PROJECT_ROOT / ".claude" / "skills" / "novel-style-db"

    # Novel-OS 风格指南（多风格小说样本 → book-to-skill）
    NOVEL_GUIDE_DIR = _PROJECT_ROOT / ".claude" / "skills" / "novel-style-guide"

    # 题材映射：book_config.genre → 风格库名称
    GENRE_MAP = {
        "都市": "urban_rebirth",
        "都市重生": "urban_rebirth",
        "现言": "romance",
        "言情": "romance",
        "古言": "romance",
        "玄幻": "fantasy",
        "仙侠": "fantasy",
        "武侠": "fantasy",
        "悬疑": "suspense",
        "恐怖": "suspense",
        "盗墓": "suspense",
        "系统": "system",
        "系统流": "system",
        "科幻": "system",
        "网游": "system",
        "穿越": "urban_rebirth",
        "历史": "urban_rebirth",
        "军事": "suspense",
        "竞技": "system",
    }

    def execute(self, ctx: ChapterContext) -> StepResult:
        genre = ctx.book_config.genre or "general"
        style_key = self.GENRE_MAP.get(genre, "general")

        # 1. 加载风格规则
        rules = self._load_style_rules(style_key)

        # 2. 加载经典片段示例
        examples = self._load_examples(style_key)

        # 3. 推断场景类型 + 用向量检索匹配小说参考
        scene_type, scene_description = self._infer_scene(ctx)
        novel_refs = self._retrieve_novel_refs(genre, scene_type, scene_description)

        # 3.5. 加载番茄写作课指导（按场景+品类匹配）
        fanqie_guide = self._load_fanqie_guide(genre, scene_type, ctx)

        # 4. 加载项目级声音资产
        project_voice = self._load_project_voice_assets(ctx)

        # 5. 写入 ctx.style_rules，供后续 Steps 读取
        style_injection = self._build_style_injection(rules, examples, novel_refs, genre)
        if fanqie_guide:
            style_injection = style_injection + "\n\n" + fanqie_guide
        if project_voice:
            style_injection = project_voice + "\n\n" + style_injection
        ctx.style_rules = style_injection

        novel_count = len(novel_refs.split("### 参考：")) - 1 if novel_refs else 0
        logger.info(
            "[StyleRetrieval] 第 %d 章 题材=%s 场景=%s → 风格库=%s，规则 %d 条，示例 %d 个，小说参考 %d 本",
            ctx.chapter_num, genre, scene_type, style_key,
            len(rules.get("rules", [])), len(examples), novel_count
        )

        return StepResult(
            content="",
            metadata={
                "style_key": style_key,
                "rules_count": len(rules.get("rules", [])),
                "examples_count": len(examples),
                "novel_refs_count": novel_count,
            }
        )

    def _load_style_rules(self, style_key: str) -> dict:
        """加载风格规则。"""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "style_rules",
                self.STYLE_GUIDE_DIR / "style_rules.py"
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "StyleRules"):
                    return module.StyleRules.GENRE_PROFILES.get(style_key, {})
        except Exception as exc:
            logger.warning("[StyleRetrieval] 加载 style_rules.py 失败: %s", exc)

        return {
            "rules": [
                "用细节代替概括",
                "用动作代替状态",
                "用对话推动剧情",
                "用环境暗示情绪",
                "用生理反应代替心理描写",
            ]
        }

    def _load_examples(self, style_key: str) -> list[str]:
        """加载经典片段示例。"""
        example_file = self.STYLE_GUIDE_DIR / "examples" / f"{style_key}.md"
        if not example_file.exists():
            return []

        try:
            content = example_file.read_text(encoding="utf-8")
            examples = re.findall(r"```\n(.*?)\n```", content, re.DOTALL)
            return examples[:3]
        except Exception as exc:
            logger.warning("[StyleRetrieval] 加载示例失败: %s", exc)
            return []

    # ── novel-style-db 向量检索集成 ──

    def _infer_scene(self, ctx: ChapterContext) -> tuple[str, str]:
        """从当前章节大纲推断场景类型和描述。"""
        outline = ctx.outline
        scene_type = "综合"
        description = ""

        if outline:
            core_event = getattr(outline, "core_event", "") or ""
            title = getattr(outline, "title", "") or ""
            chapter_hook = getattr(outline, "chapter_hook", "") or ""
            combined = f"{title} {core_event} {chapter_hook}"

            # 按关键词推断场景类型
            if any(kw in combined for kw in ["战斗", "武", "比试", "打", "对决", "击杀", "拼杀", "搏", "擂",
                                               "战", "袭", "攻", "剑", "拳", "掌", "刀"]):
                scene_type = "战斗"
            elif any(kw in combined for kw in ["对话", "谈判", "交谈", "质问", "揭秘", "坦白", "诉说",
                                                "提议", "商议", "问", "答"]):
                scene_type = "对话"
            elif any(kw in combined for kw in ["愤怒", "悲伤", "恐惧", "绝望", "哭泣", "泪", "怒", "恨",
                                                "高兴", "激动", "情感"]):
                scene_type = "情绪"
            elif any(kw in combined for kw in ["环境", "场景", "氛围", "夜", "雨", "风", "雪", "晨", "暮",
                                                "街", "巷", "山", "水", "屋", "房"]):
                scene_type = "描写"
            elif any(kw in combined for kw in ["修炼", "升级", "突破", "觉醒", "解锁", "领悟", "习得",
                                                "突破", "进阶", "魂", "境", "系统"]):
                scene_type = "设定"

            description = f"{title} {core_event} {chapter_hook}"

        return scene_type, description[:200]

    def _retrieve_novel_refs(self, genre: str, scene_type: str, description: str) -> str:
        """用向量检索匹配的小说技法+片段。"""
        # 优先使用 FAISS 向量检索
        try:
            from core.style_retriever import StyleSkillRetriever
            retriever = StyleSkillRetriever()
            if retriever.is_available:
                result = retriever.query_for_prompt(
                    genre=genre,
                    scene_type=scene_type,
                    scene_description=description,
                    top_k=3,
                    max_chars=1500,
                )
                if result:
                    logger.info("[StyleRetrieval] 向量检索命中 %d 条",
                                len(result.split("### 参考：")) - 1 if "### 参考：" in result else 1)
                    return result
        except Exception as exc:
            logger.warning("[StyleRetrieval] 向量检索失败: %s，回退到全量加载", exc)

        # 回退：全量加载同品类小说
        return self._load_novel_db_references(genre)

    def _load_novel_db_references(self, genre: str) -> str:
        """从 novel-style-db 加载该品类真实小说的技法+片段+语汇。"""
        genre_dir = self.NOVEL_DB_DIR / genre
        if not genre_dir.exists():
            logger.debug("[StyleRetrieval] novel-style-db 无 '%s' 品类目录", genre)
            return ""

        parts = []
        for novel_dir in sorted(genre_dir.iterdir()):
            if not novel_dir.is_dir():
                continue
            skill_md = novel_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
            except Exception:
                continue

            novel_name = novel_dir.name
            techniques = self._extract_section(content, "## 核心技法", "## 代表性片段")
            techniques = self._trim_techniques(techniques, max_items=3)

            excerpts = self._extract_section(content, "## 代表性片段", "## 语汇特征")
            excerpts = self._trim_excerpts(excerpts, max_items=2)

            vocab_section = self._extract_section(content, "## 语汇特征", "## 适用场景")
            dialogue_tags = self._extract_dialogue_tags(vocab_section)

            if not techniques:
                continue

            block = f"\n### 参考：《{novel_name}》\n"
            if techniques:
                block += f"{techniques}\n"
            if excerpts:
                block += f"{excerpts}\n"
            if dialogue_tags:
                block += f"- 对话标签：{dialogue_tags}\n"

            parts.append(block)

        return "".join(parts) if parts else ""

    def _extract_section(self, content: str, start_heading: str, end_heading: str) -> str:
        """提取 Markdown 中两个 ## 标题之间的内容。"""
        start_pat = re.escape(start_heading)
        end_pat = re.escape(end_heading)
        pattern = rf"{start_pat}\s*\n(.*?)(?=\n{end_pat}|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _trim_techniques(self, text: str, max_items: int = 3) -> str:
        """截取前 N 条技法，控制在 800 字内。"""
        items = re.split(r"\n(?=###?\s+\d+[\.\s])", text)
        trimmed = []
        total_chars = 0
        for item in items:
            if not item.strip():
                continue
            if len(trimmed) >= max_items:
                break
            short = item[:250]
            if len(item) > 250:
                short = short.rsplit("\n", 1)[0] + "…"
            trimmed.append(short)
            total_chars += len(short)
            if total_chars > 800:
                break
        return "\n".join(trimmed)

    def _trim_excerpts(self, text: str, max_items: int = 2) -> str:
        """截取前 N 个代表性片段，每段控制在 150 字内。"""
        fragments = re.split(r"\n(?=###\s+片段\d+)", text)
        trimmed = []
        for frag in fragments:
            if not frag.strip():
                continue
            if len(trimmed) >= max_items:
                break
            lines = frag.split("\n")
            header = ""
            quotes = []
            for line in lines:
                if line.startswith("###"):
                    header = line
                elif line.startswith(">"):
                    q = line[:150]
                    quotes.append(q)
                    if sum(len(q) for q in quotes) > 300:
                        break
            if quotes:
                trimmed.append(f"{header}\n" + "\n".join(quotes[:2]))
        return "\n".join(trimmed)

    def _extract_dialogue_tags(self, vocab_section: str) -> str:
        """从语汇特征中提取对话标签行。"""
        match = re.search(r"(?:对话标签|对话标签偏好)[：:]\s*(.+?)(?:\n|$)", vocab_section)
        if match:
            return match.group(1).strip()[:120]
        tags = re.findall(r"[-•]\s*(?:对话标签|标签)[：:]*\s*(.+)", vocab_section)
        if tags:
            return tags[0][:120]
        return ""

    # ── 番茄写作课注入 ──
    # 场景→课程映射: 写不同场景时加载对应的官方写作指南
    FANQIE_SCENE_MAP = {
        "战斗": ["ch03-conflict", "ch04-xuanhuan"],
        "对话": ["ch02-characters", "ch03-conflict"],
        "情绪": ["ch02-characters", "ch07-masters"],
        "描写": ["ch01-opening", "ch04-xuanhuan"],
        "设定": ["ch01-opening", "ch08-beginners"],
        "综合": ["ch01-opening", "ch03-conflict"],
    }
    # 品类→课程映射
    FANQIE_GENRE_MAP = {
        "玄幻": ["ch04-xuanhuan"],
        "仙侠": ["ch04-xuanhuan"],
        "都市": ["ch05-urban-romance"],
        "现言": ["ch05-urban-romance"],
        "言情": ["ch05-urban-romance"],
        "古言": ["ch05-urban-romance"],
        "悬疑": ["ch06-suspense"],
        "恐怖": ["ch06-suspense"],
        "穿越": ["ch06-suspense"],
        "历史": ["ch06-suspense"],
    }

    # fanqie-courses 技能库的 chapters 目录
    _FANQIE_CHAPTERS_DIR = Path(__file__).parent.parent.parent.parent.parent / ".claude" / "skills" / "fanqie-courses" / "chapters"

    def _load_fanqie_guide(self, genre: str, scene_type: str, ctx) -> str:
        """根据场景类型和品类，从番茄写作课技能库加载对应的写作指南。"""
        # 合集: 场景匹配 + 品类匹配（去重）
        chapter_keys: list[str] = []
        for key in self.FANQIE_SCENE_MAP.get(scene_type, ["ch01-opening"]):
            if key not in chapter_keys:
                chapter_keys.append(key)
        for key in self.FANQIE_GENRE_MAP.get(genre, []):
            if key not in chapter_keys:
                chapter_keys.append(key)

        # 始终加载新手速查（通用规则）
        if "ch08-beginners" not in chapter_keys:
            chapter_keys.append("ch08-beginners")

        if not chapter_keys:
            return ""

        parts: list[str] = []
        loaded = 0
        for key in chapter_keys[:3]:  # 最多3个文件，控制prompt长度
            filepath = self._FANQIE_CHAPTERS_DIR / (key + ".md")
            if not filepath.exists():
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
                # 截断到1500字以内
                if len(content) > 1500:
                    content = content[:1500].rsplit("\n", 1)[0] + "\n..."
                parts.append(content)
                loaded += 1
            except Exception:
                pass

        if parts:
            logger.info(
                "[StyleRetrieval] 番茄写作课: 场景=%s 品类=%s → %d 文件",
                scene_type, genre, loaded,
            )

        return "\n\n---\n\n".join(parts)

    def _load_project_voice_assets(self, ctx: ChapterContext) -> str:
        """加载项目级的 voice_examples.md 和 voice_cards.md。"""
        parts = []
        base_path = getattr(ctx.book_config, "base_path", None)
        if not base_path:
            return ""

        voice_examples = Path(base_path) / "voice_examples.md"
        if voice_examples.exists():
            try:
                text = voice_examples.read_text(encoding="utf-8")
                # 截断到 2500 字以内，避免 prompt 过长
                if len(text) > 2500:
                    text = text[:2500].rsplit("\n\n", 1)[0] + "\n\n..."
                parts.append("【项目级声音示例——必须模仿的目标风格】\n" + text)
            except Exception as exc:
                logger.warning("[StyleRetrieval] 加载 voice_examples.md 失败: %s", exc)

        voice_cards = Path(base_path) / "voice_cards.md"
        if voice_cards.exists():
            try:
                text = voice_cards.read_text(encoding="utf-8")
                if len(text) > 2000:
                    text = text[:2000].rsplit("\n\n", 1)[0] + "\n\n..."
                parts.append("【人物声线卡——对话必须贴合各自声线】\n" + text)
            except Exception as exc:
                logger.warning("[StyleRetrieval] 加载 voice_cards.md 失败: %s", exc)

        return "\n\n".join(parts)

    def _build_style_injection(self, rules: dict, examples: list[str], novel_refs: str, genre: str) -> str:
        """构建风格注入文本。"""
        lines = [f"\n【风格规则——{genre}】"]

        if rules:
            lines.append("\n=== 风格约束 ===")
            if "sentence_length" in rules:
                sl = rules["sentence_length"]
                lines.append(f"- 句长：均值{sl.get('mean', '?')}字，变异系数{sl.get('cv', '?')}")
            if "paragraph_length" in rules:
                pl = rules["paragraph_length"]
                lines.append(f"- 段落：均值{pl.get('mean', '?')}句，最长{pl.get('max', '?')}句")
            if "dialogue_ratio" in rules:
                lines.append(f"- 对话占比：{rules['dialogue_ratio']:.0%}")
            if "dialogue_tags" in rules:
                lines.append(f"- 对话标签偏好：{', '.join(rules['dialogue_tags'][:5])}")
            if "opening_pattern" in rules:
                lines.append(f"- 开篇模式：{rules['opening_pattern']}")
            if "emotion_expression" in rules:
                lines.append(f"- 情绪表达：{rules['emotion_expression']}")

        lines.append("\n=== 去AI味核心规则 ===")
        lines.append("1. 用细节代替概括：禁止'他很累/很高兴'，改为具体动作+生理反应")
        lines.append("2. 用动作代替状态：禁止'他拒绝了/逃跑了'，改为连续动作描写")
        lines.append("3. 用对话推动剧情：禁止'他的朋友提醒他'，改为直接对话")
        lines.append("4. 用环境暗示情绪：禁止'他很孤独'，改为环境细节描写")
        lines.append("5. 用生理反应代替心理：禁止'他很紧张'，改为喉咙鼓动/嘴唇干燥/手脚发凉")

        if novel_refs:
            lines.append("\n=== 同类小说风格参考（真实作品） ===")
            lines.append(novel_refs)

        if examples:
            lines.append("\n=== 风格示例 ===")
            for i, ex in enumerate(examples, 1):
                lines.append(f"\n示例{i}：")
                lines.append(ex[:300] + "..." if len(ex) > 300 else ex)

        return "\n".join(lines)
