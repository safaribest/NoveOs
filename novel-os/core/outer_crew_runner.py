"""Novel-OS 外层巡检运行器 —— 战略层质量巡检。

职责：
  - 每 5 章：Novel Architect（全书架构师）+ Continuity Inspector（跨章一致性巡检）
  - 每 10 章：Pacing Analyst（节奏分析师）
  - 发现 🔴 矛盾时：Retcon Manager（回溯修正师）

设计约束：
  - 直接从 book.yaml 加载配置 + LLMClient 调用
  - 失败隔离：外层 Agent 失败不阻塞内层写作
  - 上下文裁剪：只注入 Agent 需要的信息，避免 prompt 爆炸
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config_loader import BookConfig
from core.llm_client import LLMClient
from core.state_manager import StateManager

logger = logging.getLogger("novel-os.outer_crew")


# ============================================================================
# 结构化输出类型
# ============================================================================

@dataclass
class ArchitectureReview:
    """Novel Architect 输出。"""

    health_grade: str = ""           # A-F
    deviations: list[dict] = field(default_factory=list)
    inactive_characters: list[str] = field(default_factory=list)
    stale_foreshadowing: list[str] = field(default_factory=list)
    next_5_priorities: list[str] = field(default_factory=list)
    raw_report: str = ""


@dataclass
class ContinuityIssue:
    """单条矛盾记录。"""

    severity: str = ""       # 🔴 🟡
    prev_chapter: int = 0
    curr_chapter: int = 0
    description: str = ""
    suggestion: str = ""


@dataclass
class ContinuityReport:
    """Continuity Inspector 输出。"""

    issues: list[ContinuityIssue] = field(default_factory=list)
    has_critical: bool = False
    raw_report: str = ""


@dataclass
class PacingReport:
    """Pacing Analyst 输出。"""

    emotion_curve: str = ""
    rhythm_diagnosis: str = ""
    hook_rotation: list[str] = field(default_factory=list)
    word_trend: str = ""
    next_10_suggestions: list[str] = field(default_factory=list)
    raw_report: str = ""


@dataclass
class RetconAction:
    """单条回溯修正动作。"""

    strategy: str = ""       # A/B/C/D
    contradiction: str = ""
    fix_text: str = ""


@dataclass
class RetconPlan:
    """Retcon Manager 输出。"""

    actions: list[RetconAction] = field(default_factory=list)
    raw_report: str = ""


# ============================================================================
# 外层 CrewAI 运行器
# ============================================================================

class OuterCrewRunner:
    """外层战略巡检运行器。

    从 book.yaml 和 StateManager 加载配置与上下文，
    调用 LLM 执行 4 个外层 Agent，返回结构化报告。
    """

    def __init__(
        self,
        book_config: BookConfig,
        state_manager: StateManager,
        llm_client: LLMClient,
    ) -> None:
        self.cfg = book_config
        self.state = state_manager
        self.llm = llm_client

        # 外层巡检配置：检查 book.yaml 是否配置了外层 Agent
        self._available = "novel_architect" in self.cfg.agent_query
        if not self._available:
            logger.info("book.yaml 未配置外层巡检 Agent（novel_architect），外层巡检已禁用")

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """外层配置是否可用。"""
        return self._available

    def run_architecture_review(self, chapter_num: int) -> ArchitectureReview:
        """运行 Novel Architect —— 全书架构巡检。"""
        if not self._available:
            return ArchitectureReview()

        try:
            system = self._build_system_prompt("novel_architect")
            context = self._build_architecture_context(chapter_num)
            user = self._build_task_prompt("architecture_review", chapter_num, context)

            logger.info("[外层] Novel Architect 巡检第 %d 章节点", chapter_num)
            raw = self.llm.call(system, user, temperature=0.1, max_tokens=4000)
            return self._parse_architecture_review(raw)
        except Exception as exc:
            logger.exception("[外层] Novel Architect 失败: %s", exc)
            return ArchitectureReview(raw_report=f"ERROR: {exc}")

    def run_continuity_check(self, chapter_num: int) -> ContinuityReport:
        """运行 Continuity Inspector —— 跨章一致性巡检。"""
        if not self._available:
            return ContinuityReport()

        try:
            system = self._build_system_prompt("continuity_inspector")
            context = self._build_continuity_context(chapter_num)
            user = self._build_task_prompt("continuity_check", chapter_num, context)

            logger.info("[外层] Continuity Inspector 巡检第 %d 章节点", chapter_num)
            raw = self.llm.call(system, user, temperature=0.0, max_tokens=4000)
            return self._parse_continuity_report(raw)
        except Exception as exc:
            logger.exception("[外层] Continuity Inspector 失败: %s", exc)
            return ContinuityReport(raw_report=f"ERROR: {exc}")

    def run_pacing_analysis(self, chapter_num: int) -> PacingReport:
        """运行 Pacing Analyst —— 节奏分析。"""
        if not self._available:
            return PacingReport()

        try:
            system = self._build_system_prompt("pacing_analyst")
            context = self._build_pacing_context(chapter_num)
            user = self._build_task_prompt("pacing_analysis", chapter_num, context)

            logger.info("[外层] Pacing Analyst 分析第 %d 章节点", chapter_num)
            raw = self.llm.call(system, user, temperature=0.1, max_tokens=4000)
            return self._parse_pacing_report(raw)
        except Exception as exc:
            logger.exception("[外层] Pacing Analyst 失败: %s", exc)
            return PacingReport(raw_report=f"ERROR: {exc}")

    def run_retcon_fix(
        self, issues: list[ContinuityIssue], chapter_num: int
    ) -> RetconPlan:
        """运行 Retcon Manager —— 回溯修正。"""
        if not self._available or not issues:
            return RetconPlan()

        try:
            system = self._build_system_prompt("retcon_manager")
            context = self._build_retcon_context(issues, chapter_num)
            user = self._build_task_prompt("retcon_fix", chapter_num, context)

            logger.info("[外层] Retcon Manager 处理 %d 条矛盾", len(issues))
            raw = self.llm.call(system, user, temperature=0.1, max_tokens=4000)
            return self._parse_retcon_plan(raw)
        except Exception as exc:
            logger.exception("[外层] Retcon Manager 失败: %s", exc)
            return RetconPlan(raw_report=f"ERROR: {exc}")

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def _build_system_prompt(self, agent_type: str) -> str:
        """构建 system prompt。直接从 book.yaml agent_query 读取。"""
        query_cfg = self.cfg.agent_query.get(agent_type, {})
        role = query_cfg.get("role", agent_type)
        goal = query_cfg.get("goal", "")

        parts = [f"你是 {role}。"]
        if goal:
            parts.append(f"你的目标是：{goal}")
        return "\n\n".join(parts)

    def _build_task_prompt(
        self, task_type: str, chapter_num: int, context: dict[str, Any]
    ) -> str:
        """从 book.yaml 查询 Task 配置，构建 user prompt。"""
        query_cfg = self.cfg.agent_query.get(task_type, {})
        desc = query_cfg.get("description", "")
        expected = query_cfg.get("expected_output", "")

        # 替换模板变量
        desc = desc.replace("{chapter_number}", str(chapter_num))
        desc = desc.replace("{chapter}", str(chapter_num))
        for key, val in context.items():
            placeholder = "{" + key + "}"
            if placeholder in desc:
                desc = desc.replace(placeholder, str(val)[:8000])

        parts = [desc] if desc else []
        if expected:
            parts.append(f"\n[预期输出格式]\n{expected}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 上下文构建（从 StateManager 取数据）
    # ------------------------------------------------------------------

    def _build_architecture_context(self, chapter_num: int) -> dict[str, str]:
        """Novel Architect 上下文：大纲 + 最近5章摘要 + 人物 + 伏笔。"""
        ctx: dict[str, str] = {}

        # 全书大纲摘要
        outline = self.state.list_outline()
        ctx["outline_summary"] = self._format_outline_summary(outline)

        # 最近 5 章摘要
        history = self.state.list_chapters()
        recent = [h for h in history if h.get("chapter", 0) <= chapter_num][-5:]
        ctx["chapter_history"] = self._format_chapter_history(recent)

        # 人物状态
        characters = self.state.list_characters()
        ctx["character_states"] = self._format_characters(characters)

        # 未回收伏笔
        foreshadowing = self.state.list_foreshadowing()
        pending = [f for f in foreshadowing if f.get("status") == "active"]
        ctx["pending_foreshadowing"] = self._format_foreshadowing(pending)

        return ctx

    def _build_continuity_context(self, chapter_num: int) -> dict[str, str]:
        """Continuity Inspector 上下文：最近5章全文 + 人物快照 + 关键事实。"""
        ctx: dict[str, str] = {}

        # 最近 5 章全文（从文件读取）
        recent_texts = self._load_recent_chapter_texts(chapter_num, count=5)
        ctx["recent_chapters"] = recent_texts

        # 人物-设定-物品对照表
        characters = self.state.list_characters()
        ctx["consistency_snapshot"] = self._format_characters(characters)

        # 关键事实（从 consistency_rules 提取）
        rules = self.state.list_rules()
        ctx["key_facts"] = self._format_rules(rules)

        return ctx

    def _build_pacing_context(self, chapter_num: int) -> dict[str, str]:
        """Pacing Analyst 上下文：最近10章情绪 + 钩子 + 字数。"""
        ctx: dict[str, str] = {}

        # 最近 10 章情绪坐标
        emotions = self.state.get_emotion_history()
        recent_emotions = [e for e in emotions if e.get("chapter", 0) <= chapter_num][-10:]
        ctx["emotion_coordinates"] = self._format_emotions(recent_emotions)

        # 最近 10 章字数
        history = self.state.list_chapters()
        recent_history = [h for h in history if h.get("chapter", 0) <= chapter_num][-10:]
        ctx["word_counts"] = self._format_word_counts(recent_history)

        # 钩子类型和开头类型（简化：从 chapter_history 的 summary 推断）
        ctx["hook_types"] = "（钩子类型由 Agent 自行从章节结尾推断）"
        ctx["opening_types"] = "（开头类型由 Agent 自行从章节开头推断）"

        return ctx

    def _build_retcon_context(
        self, issues: list[ContinuityIssue], chapter_num: int
    ) -> dict[str, str]:
        """Retcon Manager 上下文：致命矛盾列表 + 涉及章节。"""
        ctx: dict[str, str] = {}

        # 致命矛盾列表
        critical = [i for i in issues if i.severity == "🔴"]
        ctx["critical_issues"] = self._format_continuity_issues(critical)

        # 涉及的前文章节
        affected_chapters = list(set(i.prev_chapter for i in critical))
        affected_texts = []
        for ch in affected_chapters:
            text = self._load_chapter_text(ch)
            if text:
                affected_texts.append(f"### 第{ch}章\n{text[:1000]}")
        ctx["affected_chapters"] = "\n\n".join(affected_texts) if affected_texts else "(无)"

        ctx["chapter_number"] = str(chapter_num)
        return ctx

    # ------------------------------------------------------------------
    # 数据格式化辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _format_outline_summary(outline: list[dict]) -> str:
        lines = ["## 全书大纲"]
        for o in outline[:20]:  # 最多 20 章，避免过长
            lines.append(
                f"- 第{o.get('chapter', '?')}章 [{o.get('arc', '')}]: "
                f"{o.get('core_event', '')} | 钩子:{o.get('chapter_hook', '')[:30]}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_chapter_history(history: list[dict]) -> str:
        lines = ["## 最近章节摘要"]
        for h in history:
            lines.append(
                f"- 第{h.get('chapter', '?')}章 [{h.get('title') or '无标题'}]: "
                f"{(h.get('summary') or '')[:100]} | 字数:{h.get('word_count', 0)}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_characters(characters: list[dict]) -> str:
        lines = ["## 人物状态"]
        for c in characters:
            lines.append(
                f"- {c.get('character_name', '未知')}："
                f"位置={c.get('location', '未知')}，"
                f"情绪={c.get('emotional_state', '未知')}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_foreshadowing(foreshadowing: list[dict]) -> str:
        lines = ["## 未回收伏笔"]
        for f in foreshadowing[:10]:
            lines.append(
                f"- [{f.get('fs_id', '?')}] 第{f.get('bury_chapter', '?')}章埋入: "
                f"{f.get('content', '')[:50]}... (计划第{f.get('collect_chapter', '?')}章回收)"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_rules(rules: list[dict]) -> str:
        lines = ["## 关键设定/规则"]
        for r in rules:
            lines.append(f"- [{r.get('rule_type', '')}] {r.get('rule_content', '')}")
        return "\n".join(lines)

    @staticmethod
    def _format_emotions(emotions: list[dict]) -> str:
        lines = ["## 情绪坐标历史"]
        for e in emotions:
            lines.append(
                f"- 第{e.get('chapter', '?')}章: "
                f"虐{e.get('nue_density', 0):.2f} "
                f"甜{e.get('tian_density', 0):.2f} "
                f"爽{e.get('shuang_density', 0):.2f} "
                f"({e.get('desc', '')})"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_word_counts(history: list[dict]) -> str:
        lines = ["## 字数趋势"]
        for h in history:
            lines.append(f"- 第{h.get('chapter', '?')}章: {h.get('word_count', 0)} 字")
        return "\n".join(lines)

    @staticmethod
    def _format_continuity_issues(issues: list[ContinuityIssue]) -> str:
        lines = ["## 致命矛盾列表"]
        for i in issues:
            lines.append(
                f"- [{i.severity}] 第{i.prev_chapter}章 vs 第{i.curr_chapter}: {i.description}\n"
                f"  建议: {i.suggestion}"
            )
        return "\n".join(lines)

    def _load_recent_chapter_texts(self, chapter_num: int, count: int = 5) -> str:
        """从文件加载最近 N 章的全文。"""
        output_dir = self.cfg.base_path / self.cfg.output_dir
        if not output_dir.exists():
            return "(无章节文件)"

        texts = []
        for ch in range(max(1, chapter_num - count + 1), chapter_num + 1):
            text = self._load_chapter_text(ch)
            if text:
                # 每章最多取 2000 字，避免 prompt 爆炸
                preview = text[:2000] + ("\n..." if len(text) > 2000 else "")
                texts.append(f"### 第{ch}章\n{preview}")

        return "\n\n".join(texts) if texts else "(无章节文件)"

    def _load_chapter_text(self, chapter_num: int) -> str:
        """加载单章全文。"""
        output_dir = self.cfg.base_path / self.cfg.output_dir
        if not output_dir.exists():
            return ""

        # 匹配文件名：第{num:03d}章_*_正文.txt
        pattern = f"第{chapter_num:03d}章_*_正文.txt"
        files = list(output_dir.glob(pattern))
        if files:
            return files[0].read_text(encoding="utf-8")
        return ""

    # ------------------------------------------------------------------
    # 报告解析（从 Markdown 提取结构化数据）
    # ------------------------------------------------------------------

    def _parse_architecture_review(self, raw: str) -> ArchitectureReview:
        """解析 Novel Architect 的 Markdown 报告。"""
        review = ArchitectureReview(raw_report=raw)

        # 提取健康度评分
        grade_match = re.search(r"健康度评分[：:]\s*([A-F][+-]?)", raw, re.IGNORECASE)
        if grade_match:
            review.health_grade = grade_match.group(1).upper()

        # 提取偏离清单
        for m in re.finditer(r"[\-\*]\s*(.+?)(?=\n[\-\*]|\n#{1,6}\s|\Z)", raw, re.DOTALL):
            text = m.group(1).strip()
            if "偏离" in text or "偏离" in raw[max(0, m.start() - 50):m.start()]:
                review.deviations.append({"text": text[:200]})

        # 提取角色活跃度提醒
        for line in raw.splitlines():
            if "连续" in line and "章未出场" in line:
                review.inactive_characters.append(line.strip()[:100])

        # 提取过期伏笔
        for line in raw.splitlines():
            if "超过" in line and "章" in line and "回收" in line:
                review.stale_foreshadowing.append(line.strip()[:100])

        # 提取下 5 章优先级
        in_priorities = False
        for line in raw.splitlines():
            if "优先级" in line or "下 5 章" in line:
                in_priorities = True
            if in_priorities and (line.startswith("-") or line.startswith("*")):
                review.next_5_priorities.append(line.strip()[2:][:150])
            if in_priorities and line.startswith("#") and "优先级" not in line:
                in_priorities = False

        return review

    def _parse_continuity_report(self, raw: str) -> ContinuityReport:
        """解析 Continuity Inspector 的 Markdown 报告。"""
        report = ContinuityReport(raw_report=raw)

        # 提取矛盾条目
        for m in re.finditer(
            r"[\-\*]\s*(.+?)(?=\n[\-\*]|\n#{1,6}\s|\Z)", raw, re.DOTALL
        ):
            text = m.group(1).strip()
            severity = "🟡"
            if "🔴" in text or "致命" in text:
                severity = "🔴"
                report.has_critical = True

            # 尝试提取章号
            ch_match = re.search(r"第(\d+)章", text)
            prev_ch = int(ch_match.group(1)) if ch_match else 0

            report.issues.append(
                ContinuityIssue(
                    severity=severity,
                    prev_chapter=prev_ch,
                    description=text[:300],
                    suggestion="",
                )
            )

        return report

    def _parse_pacing_report(self, raw: str) -> PacingReport:
        """解析 Pacing Analyst 的 Markdown 报告。"""
        report = PacingReport(raw_report=raw)

        # 提取情绪曲线 ASCII 图
        curve_match = re.search(r"```\n?(.*?)```", raw, re.DOTALL)
        if curve_match:
            report.emotion_curve = curve_match.group(1).strip()[:500]

        # 提取节奏诊断
        for line in raw.splitlines():
            if any(k in line for k in ["健康", "疲劳", "单调", "预警"]):
                report.rhythm_diagnosis = line.strip()[:200]
                break

        # 提取下 10 章建议
        in_suggestions = False
        for line in raw.splitlines():
            if "下 10 章" in line or "建议" in line:
                in_suggestions = True
            if in_suggestions and (line.startswith("-") or line.startswith("*")):
                report.next_10_suggestions.append(line.strip()[2:][:150])
            if in_suggestions and line.startswith("#") and "建议" not in line:
                in_suggestions = False

        return report

    def _parse_retcon_plan(self, raw: str) -> RetconPlan:
        """解析 Retcon Manager 的 Markdown 报告。"""
        plan = RetconPlan(raw_report=raw)

        # 按策略分块提取
        strategies = {
            "策略 A": "A",
            "策略A": "A",
            "策略 B": "B",
            "策略B": "B",
            "策略 C": "C",
            "策略C": "C",
            "策略 D": "D",
            "策略D": "D",
        }

        for marker, strategy_code in strategies.items():
            if marker in raw:
                # 提取该策略后的文案
                start = raw.find(marker)
                end = raw.find("策略", start + 1)
                if end == -1:
                    end = len(raw)
                block = raw[start:end].strip()

                plan.actions.append(
                    RetconAction(
                        strategy=strategy_code,
                        contradiction="",
                        fix_text=block[:1000],
                    )
                )

        return plan

    # ------------------------------------------------------------------
    # 报告持久化
    # ------------------------------------------------------------------

    def save_report(
        self, chapter_num: int, agent_type: str, report: str, findings: dict | None = None
    ) -> None:
        """将外层报告存入 StateManager 的 outer_crew_reports 表。"""
        try:
            with self.state._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS outer_crew_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        chapter INTEGER NOT NULL,
                        agent_type TEXT NOT NULL,
                        report TEXT NOT NULL,
                        findings TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO outer_crew_reports
                    (project_id, chapter, agent_type, report, findings)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.state.project_id,
                        chapter_num,
                        agent_type,
                        report,
                        json.dumps(findings, ensure_ascii=False) if findings else None,
                    ),
                )
        except Exception as exc:
            logger.warning("保存外层报告失败: %s", exc)
