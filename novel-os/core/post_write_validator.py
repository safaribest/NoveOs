"""PostWriteValidator —— 零 LLM 成本的确定性预检层。

对标 InkOS Post-Write Validator：
- 11 条规则，全部正则/计数，不调用任何 LLM
- 命中 error 级问题立即触发 spot-fix，不进入 Auditor
- 运行时间 < 100ms
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PostValidationIssue:
    rule: str
    level: str  # "ERROR" | "WARN"
    message: str
    detail: Any = None


@dataclass
class PostValidationResult:
    verdict: str  # "PASS" | "SPOT_FIX"
    issues: list[PostValidationIssue] = field(default_factory=list)
    fix_instruction: str = ""


class PostWriteValidator:
    """11 条确定性规则（对标 InkOS）。"""

    # 禁用模式
    BANNED_PATTERNS = ["不是……?而是……?"]
    # 过渡词密度限制（每 3000 字最多 1 次）
    TRANSITION_WORDS = ["仿佛", "忽然", "竟然", "不禁", "宛如", "猛地", "居然", "终究"]
    # 高疲劳词
    FATIGUE_WORDS = ["缓缓", "微微", "淡淡", "轻轻", "默默", "悄然"]
    # 元叙事/作者说教
    METANARRATIVE = ["显然", "不言而喻", "众所周知", "不难看出", "值得注意的是", "综上所述", "总而言之"]
    # 分析报告术语
    REPORT_TERMS = ["核心动机", "信息落差", "情感弧线", "叙事节奏", "人物弧光", "戏剧张力", "认知缺口"]
    # 集体反应 cliché
    COLLECTIVE_RE = re.compile(r"(?:全场|众人|所有人|大家|群臣|满朝).{0,6}(?:震惊|哗然|倒吸|骇然|色变|鸦雀无声|寂静|沸腾)")
    # 公式化转折
    FORMULAIC_RE = re.compile(r"虽然.*但是.*却.*|明明.*却.*|已经.*却.*|不是.*而是.*")

    def __init__(self, thresholds: dict[str, Any] | None = None):
        self.t = thresholds or {}
        self.max_dash = self.t.get("max_dash_count", 3)
        self.max_fatigue = self.t.get("max_fatigue_per_word", 1)
        self.max_consecutive_le = self.t.get("max_consecutive_le", 3)
        self.paragraph_std_min = self.t.get("paragraph_std_min", 5)
        self.max_long_paras = self.t.get("max_long_paragraphs", 1)

    def validate(self, text: str) -> PostValidationResult:
        issues: list[PostValidationIssue] = []
        cn_chars = len(re.findall(r"[一-鿿]", text))
        if cn_chars == 0:
            cn_chars = len(text)

        # Rule 1: 禁用模式（不是…而是…）
        for pat in self.BANNED_PATTERNS:
            matches = re.findall(pat, text)
            if matches:
                issues.append(PostValidationIssue("banned_pattern", "ERROR", f"禁用模式命中 {len(matches)} 处", matches[:3]))

        # Rule 2: 长破折号
        dash_count = text.count("——")
        if dash_count > self.max_dash:
            issues.append(PostValidationIssue("em_dash", "WARN", f"长破折号 {dash_count} 处 > 限值 {self.max_dash}"))

        # Rule 3: 过渡词密度
        limit = max(1, cn_chars // 3000)
        for word in self.TRANSITION_WORDS:
            count = text.count(word)
            if count > limit:
                issues.append(PostValidationIssue("transition_density", "ERROR", f"过渡词'{word}'出现 {count} 次 > 限值 {limit}", {"word": word, "count": count, "limit": limit}))

        # Rule 4: 高疲劳词
        for word in self.FATIGUE_WORDS:
            count = text.count(word)
            if count > self.max_fatigue:
                issues.append(PostValidationIssue("fatigue_word", "ERROR", f"高疲劳词'{word}'出现 {count} 次", {"word": word, "count": count}))

        # Rule 5: 元叙事
        for word in self.METANARRATIVE:
            if word in text:
                issues.append(PostValidationIssue("metanarrative", "ERROR", f"元叙事词'{word}'", {"word": word}))

        # Rule 6: 分析报告术语
        for term in self.REPORT_TERMS:
            if term in text:
                issues.append(PostValidationIssue("report_terminology", "ERROR", f"分析报告术语'{term}'入正文", {"term": term}))

        # Rule 7: 集体反应 cliché
        collective = self.COLLECTIVE_RE.findall(text)
        if collective:
            issues.append(PostValidationIssue("collective_reaction", "ERROR", f"集体反应 cliché {len(collective)} 处", collective[:3]))

        # Rule 8: 连续"了"句
        sentences = [s for s in re.split(r"[。！？…；]+", text) if s.strip()]
        consecutive = 0
        max_le = 0
        for s in sentences:
            if "了" in s:
                consecutive += 1
                max_le = max(max_le, consecutive)
                if consecutive > self.max_consecutive_le:
                    issues.append(PostValidationIssue("consecutive_le", "ERROR", f"连续 {consecutive} 句含'了'", {"count": consecutive}))
                    break
            else:
                consecutive = 0
        if max_le <= self.max_consecutive_le and max_le >= 2:
            issues.append(PostValidationIssue("consecutive_le", "WARN", f"连续 {max_le} 句含'了'（接近上限）", {"count": max_le}))

        # Rule 9: 段落等长检测
        paragraphs = [p for p in text.split("\n") if p.strip()]
        para_lens = [len(re.findall(r"[一-鿿]", p)) for p in paragraphs]
        if len(para_lens) >= 5:
            mean_len = sum(para_lens) / len(para_lens)
            variance = sum((x - mean_len) ** 2 for x in para_lens) / len(para_lens)
            std = variance ** 0.5
            if std < self.paragraph_std_min:
                issues.append(PostValidationIssue("paragraph_uniformity", "ERROR", f"段落过于均匀（标准差={std:.1f}），疑似 AI", {"std": round(std, 1)}))

        # Rule 10: 超长段落
        long_paras = [l for l in para_lens if l > 300]
        if len(long_paras) > self.max_long_paras:
            issues.append(PostValidationIssue("long_paragraph", "WARN", f"超长段落 {len(long_paras)} 处（>300字）", {"count": len(long_paras)}))

        # Rule 11: 公式化转折
        formulaic = self.FORMULAIC_RE.findall(text)
        if len(formulaic) > 2:
            issues.append(PostValidationIssue("formulaic_transition", "ERROR", f"公式化转折 {len(formulaic)} 处", {"count": len(formulaic)}))

        if issues:
            instruction = self._build_fix_instructions(issues)
            return PostValidationResult("SPOT_FIX", issues, instruction)
        return PostValidationResult("PASS")

    def _build_fix_instructions(self, issues: list[PostValidationIssue]) -> str:
        lines = ["【零成本预检未通过——请按以下指令修正】"]
        for issue in issues:
            rule = issue.rule
            if rule == "banned_pattern":
                lines.append(f"- 删除'不是…而是…'结构（命中 {issue.detail} 处），改为直接陈述或动作描写。")
            elif rule == "em_dash":
                lines.append(f"- 删除长破折号'——'（{issue.detail} 处），改为句号或逗号。")
            elif rule == "transition_density":
                d = issue.detail or {}
                lines.append(f"- 过渡词'{d.get('word')}'出现 {d.get('count')} 次 > 限值 {d.get('limit')}。请删除或用动作替代。")
            elif rule == "fatigue_word":
                d = issue.detail or {}
                lines.append(f"- 高疲劳词'{d.get('word')}'出现 {d.get('count')} 次。请替换为具体动作或感官描写。")
            elif rule == "metanarrative":
                lines.append(f"- 删除元叙事词'{issue.detail.get('word')}'，改为角色动作或环境反应。")
            elif rule == "report_terminology":
                lines.append(f"- 删除分析报告术语'{issue.detail.get('term')}'，禁止方法论词汇入正文。")
            elif rule == "collective_reaction":
                lines.append(f"- 删除集体反应 cliché（{issue.detail} 处），改为 2-3 个具体个体的差异化反应。")
            elif rule == "consecutive_le":
                lines.append(f"- 连续{issue.detail.get('count')}句含'了'，请合并或用其他句式替代（每3句最多1句含'了'）。")
            elif rule == "paragraph_uniformity":
                lines.append(f"- 段落长度过于均匀（标准差={issue.detail.get('std')}），请故意打乱：长段50字→短段12字→中段30字。")
            elif rule == "long_paragraph":
                lines.append(f"- 超长段落 {issue.detail.get('count')} 处（>300字），请拆分为 15-25 字/段。")
            elif rule == "formulaic_transition":
                lines.append(f"- 公式化转折 {issue.detail.get('count')} 处，请改为因果链动作描写。")
        return "\n".join(lines)
