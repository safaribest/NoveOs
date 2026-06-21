from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from core.guards.registry import GuardRegistry
from core.writing.loop_controller import ChapterGoal, LoopController


@dataclass
class ValidationIssue:
    """单个校验问题。"""
    level: str          # "BLOCK" | "WARN" | "INFO"
    category: str       # "字数" | "他字密度" | "禁用词" | "对话" | "连续性" | "幻觉"
    message: str        # 人类可读描述
    detail: Any = None  # 额外数据（命中词列表、坐标等）


@dataclass
class ValidationResult:
    """统一校验结果。"""
    verdict: str                        # "PASS" | "WARN" | "BLOCK"
    issues: list[ValidationIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    auto_fix_text: str = ""             # 自动修复后的文本（禁用词替换等）
    repair_instruction: str = ""        # 如果需要人工介入，具体的修改指引


class ChapterValidator:
    """统一校验层。"""

    def __init__(
        self,
        extra_blacklist: dict[str, list[str]] | None = None,
        guard_registry: GuardRegistry | None = None,
        thresholds: dict[str, Any] | None = None,
        mandatory_terms: dict[str, dict] | None = None,
    ):
        self.thresholds = THRESHOLDS.copy()
        # 外层回路覆盖：读取 rule_overrides.json（如果存在）
        try:
            from core.outer_loop.rule_config import load_overrides
            overrides = load_overrides()
            for key, val in overrides.items():
                if key.startswith("THRESHOLDS."):
                    tk = key[len("THRESHOLDS."):]
                    # dialogue_ratio 是 tuple，特殊处理
                    if tk == "dialogue_ratio_min" or tk == "dialogue_ratio_max":
                        current = list(self.thresholds.get("dialogue_ratio", (0.15, 0.55)))
                        if tk == "dialogue_ratio_min":
                            current[0] = val
                        else:
                            current[1] = val
                        self.thresholds["dialogue_ratio"] = tuple(current)
                    else:
                        self.thresholds[tk] = val
        except Exception:
            pass  # 外层回路模块不可用时使用默认值
        if thresholds:
            self.thresholds.update(thresholds)
        self.banned = {k: v.copy() for k, v in BANNED_PATTERNS.items()}
        if extra_blacklist:
            for k, v in extra_blacklist.items():
                self.banned.setdefault(k, []).extend(v)
        self.guard_registry = guard_registry
        # 强制术语字典：优先使用传入的配置，fallback 到模块级 TERM_MANDATORY
        self.mandatory_terms = mandatory_terms if mandatory_terms is not None else TERM_MANDATORY
        self.loop_controller = LoopController(ChapterGoal())
        self._compile_regexes()

    def _compile_regexes(self):
        """预编译所有正则。"""
        self._re_banned: dict[str, re.Pattern] = {}
        for cat, words in self.banned.items():
            if words:
                escaped = [re.escape(w) for w in sorted(words, key=len, reverse=True)]
                self._re_banned[cat] = re.compile("|".join(escaped))

        # 特殊模式
        self._re_x_second = re.compile(r"看了(\d+)秒|沉默了(\d+)秒|等了(\d+)秒")
        self._re_parallel = re.compile(r"(.{3,15})。\1。\1。")
        self._re_english = re.compile(r"[a-zA-Z]{2,}")
        # 英文允许列表（品类特定术语，不视为 AI 残留）
        self._english_allowlist = {
            "HR", "KPI", "NULL", "PPT", "PC", "ID", "OK", "NO",
            "BGM", "CEO", "CTO", "VIP", "PDF", "OKR", "AI",
            "REVIEW", "Hz", "PS", "ERR", "LV", "XM", "SW",
            "GMT", "UTC", "AM", "PM", "DNA", "RNA", "API",
            "URL", "HTTP", "HTTPS", "SQL", "CPU", "GPU", "RAM",
            "APP", "iOS", "Android", "Java", "Python", "C++",
        }
        self._re_sensory = re.compile(
            r"(闻到|听见|触到|摸到|冰凉|温热|粗糙|滑腻|刺痛|麻木"
            r"|气味|声音|温度|触感|舌尖|鼻腔|耳膜|皮肤|指尖传来)"
        )
        # 检测精确数字铺陈环境（连续数字+量词/名词组合）
        self._re_precise_number = re.compile(
            r"(?:\d+\.?\d*|[一二两三四五六七八九十百千万亿零半]+)\s*"
            r"(?:个|颗|条|张|页|行|米|秒|分|度|次|种|份|件|只|把|本|支|块|片|粒|根|双|副|座|扇|层|步|颗|枚|具|头|匹|张|间|扇|艘|架|辆|台|部|套|滴|缕|丝|寸|尺|丈|里|亩|顷|吨|斤|两|克|千克|毫升|升|度|伏|瓦|赫兹|%)"
        )
        self._re_chinese = re.compile(r"[一-鿿]")
        self._re_ta = re.compile(r"[他她它]")
        self._re_question = re.compile(r"难道|究竟|怎么|会不会|为什么|什么|谁|哪里|为何|到底")
        self._re_reveal = re.compile(r"原来|终于|发现|明白|知道|看来|果然|竟然|突然|顿时")
        self._re_sudden = re.compile(r"突然")
        self._re_ending_hook = re.compile(r"[？?！!]|正要|就要|刚要|即将|不知道|不明白|然而|可是|难道|突然|等着|会怎样|不会吧|不可能")
        self._re_metaphor = re.compile(r"像.{1,10}一样|如同|仿佛|好似|犹如|宛如|好比|就像.{1,10}般")

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def validate(self, text: str, context: dict | None = None) -> ValidationResult:
        """执行全部校验，返回统一结果。

        Args:
            text: 章节正文
            context: 可选上下文，含 chapter_num / state_manager / core_event
        """
        ctx = context or {}
        issues: list[ValidationIssue] = []
        metrics: dict[str, Any] = {}

        # ── P0: 字数 ──
        metrics["word_count"] = self._count_chinese(text)
        wc = metrics["word_count"]
        if wc < self.thresholds["min_words"]:
            issues.append(ValidationIssue("BLOCK", "字数", f"字数不足: {wc} < {self.thresholds['min_words']}", wc))
        elif wc > self.thresholds["max_words"]:
            issues.append(ValidationIssue("BLOCK", "字数", f"字数超标: {wc} > {self.thresholds['max_words']}", wc))

        # ── P0: 他字密度 ──
        ta_count = len(self._re_ta.findall(text))
        metrics["ta_density"] = ta_count / max(wc, 1)
        if metrics["ta_density"] > self.thresholds["max_ta_density"]:
            issues.append(ValidationIssue("BLOCK", "他字密度",
                f"他字密度超标: {metrics['ta_density']:.1%} > {self.thresholds['max_ta_density']:.0%}",
                ta_count))

        # ── P0: 红线词 ──
        redline_hits = self._scan_category(text, "红线词")
        metrics["redline_hits"] = len(redline_hits)
        if metrics["redline_hits"] > self.thresholds["max_redline"]:
            issues.append(ValidationIssue("BLOCK", "红线词", f"红线词命中: {redline_hits}"))

        # ── P0: 强制术语命中 ──
        ch_num = ctx.get("chapter_num", 0)
        missing_terms = self._check_mandatory_terms(text, ch_num)
        metrics["mandatory_terms_hit"] = len(self.mandatory_terms) - len(missing_terms)
        metrics["mandatory_terms_miss"] = missing_terms
        if missing_terms:
            for term, cfg in missing_terms.items():
                level = cfg.get("severity", "WARN")
                issues.append(ValidationIssue(
                    level, "术语",
                    f"强制术语缺失: '{term}'（{cfg['category']}，第{cfg['first_chapter']}章起必须出现）",
                    term
                ))

        # ── P1: 禁用词 ──
        banned_hits: dict[str, list[str]] = {}
        for cat in ["禁用词", "AI万能结尾", "模板比喻", "标志性AI表情"]:
            hits = self._scan_category(text, cat)
            if hits:
                banned_hits[cat] = hits
        total_banned = sum(len(v) for v in banned_hits.values())
        metrics["banned_hits"] = total_banned
        metrics["banned_detail"] = banned_hits
        if total_banned > self.thresholds["max_forbidden_patterns"]:
            issues.append(ValidationIssue("WARN", "禁用词",
                f"禁用模式命中 {total_banned} 次（阈值 {self.thresholds['max_forbidden_patterns']}）",
                banned_hits))

        # ── P1: 精确数字铺陈 ──
        # 排除引号内内容（规则条文等允许精确数字）
        non_dialogue_text = re.sub(r'[""].*?[ ""]', '', text)
        pn_hits = self._re_precise_number.findall(non_dialogue_text)
        # 过滤剧情必需数字（楼层、时间、章节编号等）
        _story_essential = re.compile(
            r'(?:第?[一二两三四五六七八九十百千万亿\d]+\s*(?:分钟|秒|小时|天|章|楼|层|号|室))'
        )
        pn_hits_filtered = [h for h in pn_hits if not _story_essential.search(h[0] if isinstance(h, tuple) else h)]
        metrics["precise_number_count"] = len(pn_hits_filtered)
        pn_threshold = self.thresholds.get("precise_number_threshold", 8)
        if len(pn_hits_filtered) > pn_threshold:
            issues.append(ValidationIssue("WARN", "AI模式",
                f"环境/身体描写中精确数字+量词出现 {len(pn_hits_filtered)} 次（阈值{pn_threshold}），疑似AI量化铺陈。请改为身体体感描述（如'扎进肉里''震得牙根发酸'）。",
                pn_hits_filtered[:5]))

        # ── P1: X秒凝视 ──
        xsec_hits = self._re_x_second.findall(text)
        metrics["x_second_count"] = len(xsec_hits)
        if xsec_hits:
            issues.append(ValidationIssue("WARN", "AI模式", f"X秒凝视模式命中 {len(xsec_hits)} 次: {xsec_hits[:3]}"))

        # ── P1: 三连句式 ──
        parallel_hits = self._re_parallel.findall(text)
        metrics["parallel_count"] = len(parallel_hits)
        if parallel_hits:
            issues.append(ValidationIssue("WARN", "AI模式", f"三连句式命中 {len(parallel_hits)} 处"))

        # ── P1: 对话占比 ──
        dialogue_ratio = self._calc_dialogue_ratio(text)
        metrics["dialogue_ratio"] = dialogue_ratio
        lo, hi = self.thresholds["dialogue_ratio"]
        if not (lo <= dialogue_ratio <= hi):
            issues.append(ValidationIssue("WARN", "对话", f"对话占比 {dialogue_ratio:.1%} 不在 [{lo:.0%}, {hi:.0%}] 范围"))

        # ── P1: 句长结构 ──
        sentence_issues = self._check_sentence_length(text, metrics)
        issues.extend(sentence_issues)

        # ── P1: 统计指纹检查（困惑度 + 突发性） ──
        fingerprint_issues = self._check_statistical_fingerprint(text, metrics)
        issues.extend(fingerprint_issues)

        # ── P1: IWR 悬念结构 ──
        iwr_issues = self._check_iwr_structure(text, metrics)
        issues.extend(iwr_issues)

        # ── P1: "突然"专项计数 ──
        sudden_hits = self._re_sudden.findall(text)
        metrics["sudden_count"] = len(sudden_hits)
        max_sudden = self.thresholds.get("max_sudden_count", 3)
        if len(sudden_hits) > max_sudden:
            issues.append(ValidationIssue(
                "WARN", "禁用词",
                f"'突然'出现 {len(sudden_hits)} 次 > 阈值 {max_sudden} 次",
                sudden_hits[:5],
            ))

        # ── P1: 章末悬念收尾检查 ──
        last_100 = text[-200:]
        ending_hook_hits = self._re_ending_hook.findall(last_100)
        metrics["ending_hook_count"] = len(ending_hook_hits)
        suspense_min = max(self.thresholds.get("suspense_ending_min", 1), 1)  # ★ 强制至少1，防止被 rule_overrides 设为0导致检测失效
        if len(ending_hook_hits) < suspense_min:
            issues.append(ValidationIssue(
                "BLOCK", "章末钩子",
                f"章末未检测到悬念钩子（最后200字无问句/动作悬念/认知缺口），必须以未解问题/新危机/下一章诱惑收尾",
                last_100[-50:],
            ))

        # ── P1: 结尾结构同质化检测 ──
        ending_issues = self._check_ending_structure(text, ctx)
        issues.extend(ending_issues)

        # ── P1: 排版检查 ──
        paragraphs = [p for p in text.split('\n') if p.strip()]
        para_cn_counts = [len(self._re_chinese.findall(p)) for p in paragraphs]
        long_paras = [c for c in para_cn_counts if c > 80]
        metrics["paragraph_count"] = len(paragraphs)
        metrics["long_paragraph_count"] = len(long_paras)
        metrics["avg_para_length"] = round(sum(para_cn_counts) / max(len(para_cn_counts), 1), 1)
        if len(long_paras) > len(paragraphs) * 0.3 and len(paragraphs) > 5:
            issues.append(ValidationIssue(
                "WARN", "排版",
                f"{len(long_paras)}/{len(paragraphs)} 段落超过80字，密集排版可能影响移动端阅读，建议适度分段",
                {"avg": metrics["avg_para_length"]},
            ))

        # ── P1: 比喻检测 ──
        metaphor_hits = self._re_metaphor.findall(text)
        metrics["metaphor_count"] = len(metaphor_hits)
        if len(metaphor_hits) > 3:
            issues.append(ValidationIssue(
                "WARN", "AI模式",
                f"比喻/类比出现 {len(metaphor_hits)} 次 > 阈值3: {metaphor_hits[:5]}",
                metaphor_hits,
            ))

        # ── P1: 英文残留 ──
        eng_words = self._re_english.findall(text)
        eng_filtered = [w for w in eng_words if w not in self._english_allowlist]
        metrics["english_count"] = len(eng_filtered)
        if len(eng_filtered) > self.thresholds["max_english_words"]:
            issues.append(ValidationIssue("WARN", "英文残留",
                f"发现 {len(eng_filtered)} 个非术语英文词: {eng_filtered[:5]}"))

        # ── P1: 大纲遵循度 ──
        core_event = ctx.get("core_event", "")
        if core_event and not self._verify_core_event(text, core_event):
            issues.append(ValidationIssue("WARN", "大纲遵循", f"疑似遗漏核心事件: {core_event[:80]}"))

        # ── P1: 连续性（如果 StateManager 可用）─
        sm = ctx.get("state_manager")
        ch = ctx.get("chapter_num", 0)
        if sm and ch > 1:
            continuity = self._check_continuity(text, sm, ch)
            issues.extend(continuity)

        # ── P2: 感官密度 ─
        sensory_count = len(self._re_sensory.findall(text))
        metrics["sensory_count"] = sensory_count
        expected_sensory = max(1, wc // 500)
        if sensory_count < expected_sensory:
            issues.append(ValidationIssue("INFO", "感官密度",
                f"感官描写 {sensory_count} 处 < 预期 {expected_sensory} 处"))

        # ── 运行 GuardRegistry 中的插件化 Guard ──
        if self.guard_registry:
            guard_results = self.guard_registry.run_all(text, ctx, stop_on_blocking=False)
            for gr in guard_results:
                if gr.level == "PASS":
                    continue
                level = "BLOCK" if gr.level == "BLOCKING" else gr.level
                issues.append(ValidationIssue(level, gr.guard_id, gr.message, gr.metadata))

        # ── 判定 ──
        blocks = [i for i in issues if i.level == "BLOCK"]
        warns = [i for i in issues if i.level == "WARN"]
        info = [i for i in issues if i.level == "INFO"]

        if blocks:
            verdict = "BLOCK"
        elif warns:
            verdict = "WARN"
        else:
            verdict = "PASS"

        # ── 构建修复指令 ──
        repair = self._build_repair(blocks, warns, metrics)

        # ── 自动修复（禁用词替换） ──
        auto_fixed = self._auto_replace(text, banned_hits)

        return ValidationResult(
            verdict=verdict,
            issues=blocks + warns + info,
            metrics=metrics,
            auto_fix_text=auto_fixed,
            repair_instruction=repair,
        )

    def is_goal_met(self, text: str, dialogue_ratio: float | None = None) -> bool:
        """基于 Loop Engineering 的完成目标判定。"""
        return self.loop_controller.check(text, dialogue_ratio).passed

    def should_retry(self, result: ValidationResult, attempt: int, max_retries: int = 3) -> bool:
        """是否需要重试。"""
        return result.verdict == "BLOCK" and attempt < max_retries

    def build_retry_feedback(self, result: ValidationResult) -> str:
        """将校验失败转为注入 Writer 的修正指令。"""
        if result.verdict == "PASS":
            return ""
        lines = ["\n===== 质量校验反馈（请针对以下问题修改） ====="]
        for issue in result.issues:
            marker = "[阻塞]" if issue.level == "BLOCK" else "[警告]" if issue.level == "WARN" else "[提示]"
            lines.append(f"{marker} [{issue.category}] {issue.message}")
        if result.metrics.get("word_count"):
            lines.append(f"当前字数: {result.metrics['word_count']}")
        lines.append("请修改后重新输出完整章节。")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    @staticmethod
    def _count_chinese(text: str) -> int:
        return len(re.findall(r"[一-鿿]", text))

    def _check_mandatory_terms(self, text: str, chapter_num: int) -> dict[str, dict]:
        """检查强制术语是否命中。返回缺失的术语字典。"""
        missing = {}
        if chapter_num <= 0:
            return missing
        for term, cfg in self.mandatory_terms.items():
            if chapter_num >= cfg["first_chapter"] and term not in text:
                missing[term] = cfg
        return missing

    def _scan_category(self, text: str, category: str) -> list[str]:
        pat = self._re_banned.get(category)
        if not pat:
            return []
        return list(set(pat.findall(text)))

    @staticmethod
    def _calc_dialogue_ratio(text: str) -> float:
        """估算对话占比：有对话标记的段落 / 总段落。"""
        paragraphs = [p for p in text.split('\n') if p.strip()]
        if not paragraphs:
            return 0.0
        dial_paras = 0
        for p in paragraphs:
            if re.search(r'[\u201c\u201d\u2018\u2019""''「」『』]', p):
                dial_paras += 1
        return dial_paras / len(paragraphs)

    @staticmethod
    def _verify_core_event(text: str, core_event: str) -> bool:
        """检查核心事件关键词是否在正文中出现。

        过滤掉通用词（角色名、常见动词），只检查事件特异性词汇，
        提高阈值到 70% 以减少误报。
        """
        # 通用词过滤：这些词在每章都会出现，不能作为遵循度指标
        stopwords = {
            "林默", "苏晚", "张经理", "陈雨", "老周", "发现", "知道",
            "规则", "公司", "系统", "员工", "部门", "办公室", "工作",
            "时间", "时候", "开始", "已经", "进行", "需要", "必须",
            "没有", "不能", "可以", "还是", "但是", "因为", "所以",
            "一个", "什么", "怎么", "为什么", "如何", "哪里",
        }
        keywords = re.findall(r"[一-鿿]{2,}", core_event)
        keywords = [kw for kw in keywords if kw not in stopwords]
        if not keywords:
            return True
        match_count = sum(1 for kw in keywords if kw in text)
        return match_count >= len(keywords) * 0.70

    @staticmethod
    def _check_continuity(text: str, state_manager, chapter_num: int) -> list[ValidationIssue]:
        """跨章连续性检查（精简版）。"""
        issues: list[ValidationIssue] = []
        try:
            prev_chars = state_manager.list_characters(chapter_num - 1)
            curr_chars = state_manager.list_characters(chapter_num)
            for name, prev in prev_chars.items():
                curr = curr_chars.get(name)
                if not curr:
                    continue
                prev_loc = prev.get("location", "")
                curr_loc = curr.get("location", "")
                if prev_loc and curr_loc and prev_loc != curr_loc:
                    if curr_loc not in text and prev_loc not in text:
                        issues.append(ValidationIssue("WARN", "连续性",
                            f"人物'{name}'位置从'{prev_loc}'跳变到'{curr_loc}'，正文未提及"))
        except Exception:
            pass
        return issues

    def _check_sentence_length(self, text: str, metrics: dict[str, Any]) -> list[ValidationIssue]:
        """检查句长均值和连续短句，返回问题列表。"""
        issues: list[ValidationIssue] = []
        sentences = [s for s in re.split(r"[。！？…]+", text) if s.strip()]
        sent_lens = [
            len(re.findall(r"[一-鿿]", s))
            for s in sentences
            if len(re.findall(r"[一-鿿]", s)) > 0
        ]
        if not sent_lens:
            return issues

        avg_len = sum(sent_lens) / len(sent_lens)
        metrics["avg_sentence_length"] = round(avg_len, 1)

        if avg_len > 30:
            issues.append(ValidationIssue(
                "WARN", "句长",
                f"平均句长 {avg_len:.1f} 字 > 推荐上限 30 字，影响移动端可读性",
                avg_len,
            ))

        short_threshold = self.thresholds.get("short_sentence_max", 12)
        max_consec = self.thresholds.get("max_consecutive_short", 3)
        consecutive = 0
        max_consecutive = 0
        for length in sent_lens:
            if length <= short_threshold:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
        metrics["max_consecutive_short_sentences"] = max_consecutive

        if max_consecutive > max_consec:
            issues.append(ValidationIssue(
                "INFO", "句长",
                f"连续短句({short_threshold}字以内)最多 {max_consecutive} 句 > 阈值 {max_consec}",
                max_consecutive,
            ))

        long_min = self.thresholds.get("long_sentence_min", 25)
        paragraphs = [p for p in text.split("\n") if p.strip()]
        short_para_count = 0
        for para in paragraphs:
            para_sents = [s for s in re.split(r"[。！？…]+", para) if s.strip()]
            para_lens = [
                len(re.findall(r"[一-鿿]", s))
                for s in para_sents
                if len(re.findall(r"[一-鿿]", s)) > 0
            ]
            if para_lens and not any(l >= long_min for l in para_lens):
                short_para_count += 1
        metrics["paragraphs_without_long_sentence"] = short_para_count
        if short_para_count > 0:
            issues.append(ValidationIssue(
                "INFO", "句长",
                f"{short_para_count} 个段落未包含≥{long_min}字的长句",
                short_para_count,
            ))

        return issues

    def _check_iwr_structure(self, text: str, metrics: dict[str, Any]) -> list[ValidationIssue]:
        """检查悬念问句数量和揭示词数量，返回问题列表。"""
        issues: list[ValidationIssue] = []

        question_hits = self._re_question.findall(text)
        metrics["question_count"] = len(question_hits)

        reveal_hits = self._re_reveal.findall(text)
        metrics["reveal_count"] = len(reveal_hits)

        q_min = self.thresholds.get("question_count_min", 5)
        r_max = self.thresholds.get("reveal_count_max", 3)

        if len(question_hits) < q_min:
            issues.append(ValidationIssue(
                "WARN", "悬念结构",
                f"悬念问句 {len(question_hits)} 个 < 阈值 {q_min}，IWR不足导致追读力弱",
                question_hits,
            ))

        if len(reveal_hits) > r_max:
            issues.append(ValidationIssue(
                "WARN", "悬念结构",
                f"揭示词 {len(reveal_hits)} 个 > 阈值 {r_max}: {reveal_hits[:5]}，信息过度释放",
                reveal_hits,
            ))

        return issues

    def _check_ending_structure(self, text: str, ctx: dict) -> list[ValidationIssue]:
        """检测是否使用了'主角静止+物品特写+悬念'的AI万能结尾结构。"""
        issues: list[ValidationIssue] = []
        last_200 = text[-200:]

        # 检测模式：主角名 + 静止动词（站/坐/握/看/摸/抵/触/盯）+ 物品 + 疑问/悬念/省略
        static_pattern = re.compile(
            r'(?:林默|苏晚).{0,15}(?:站|坐|握|看|摸|抵|触|盯|望|盯|抵|靠).{0,25}'
            r'(?:工牌|照片|刀|门|血|黑暗|空白|碎裂|裂缝|倒计时|NULL|文件|纸|屏幕|光).{0,30}'
            r'[？?……]'
        )
        if static_pattern.search(last_200):
            issues.append(ValidationIssue(
                "WARN", "结尾结构",
                "检测到'主角静止+物品特写+悬念'结尾结构，连续使用会导致同质化AI味。建议轮换：动作悬念/对话未竟/认知崩塌/环境突变",
                last_200[-60:],
            ))

        # 检测"不是X，是Y"句式（全书禁用）
        not_x_but_y = re.compile(r'不是[^，。！？]{1,10}，?而是[^，。！？]{1,10}')
        nyb_hits = not_x_but_y.findall(text)
        if nyb_hits:
            issues.append(ValidationIssue(
                "WARN", "AI模式",
                f"'不是X，是Y'句式出现 {len(nyb_hits)} 次：{nyb_hits[:3]}。这是典型的AI结构化表达，请改为直接描述。",
                nyb_hits[:3],
            ))

        return issues

    def _auto_replace(self, text: str, banned_hits: dict[str, list[str]]) -> str:
        """自动替换禁用词为合适的替代词。"""
        # 禁用词 → 替代词映射
        replacement_map = {
            "缓缓": "慢慢",
            "微微": "稍",
            "淡淡": "轻",
            "轻轻": "轻",
            "默默": "无声",
            "悄然": "无声",
            "莫名": "不知为何",
            "忽然": "猛地",
            "竟然": "竟",
            "突然": "猛地",
            "与此同时": "同时",
            "果不其然": "果然",
            "不得不说": "必须说",
            "众所周知": "人人皆知",
            "就在这时": "此刻",
            "心中一凛": "心头一紧",
            "心头一震": "心头一紧",
            "下意识觉得": "直觉感到",
        }
        modified = text
        for cat, words in banned_hits.items():
            for word in words:
                if word in modified:
                    repl = replacement_map.get(word, f"[[{word}]]")
                    modified = modified.replace(word, repl)
        return modified

    def _build_repair(self, blocks: list, warns: list, metrics: dict) -> str:
        """构建修复指令。"""
        if not blocks and not warns:
            return ""
        lines = ["【ChapterValidator 修复指引】"]
        for b in blocks:
            lines.append(f"  🔴 {b.category}: {b.message}")
        for w in warns:
            lines.append(f"  🟡 {w.category}: {w.message}")
        if metrics.get("word_count", 0) < self.thresholds["min_words"]:
            lines.append("\n→ 字数不足：扩充场景描写或对话细节，而非重复已有内容。")
        if metrics.get("word_count", 0) > self.thresholds["max_words"]:
            lines.append("\n→ 字数超标：精简冗余叙述，合并重复信息。")
        return "\n".join(lines)

    def _check_statistical_fingerprint(self, text: str, metrics: dict[str, Any]) -> list[ValidationIssue]:
        """检查统计指纹指标（困惑度和突发性）。
    
        参考：GPTZero/Turnitin 通过 perplexity + burstiness 判断AI生成。
        - burstiness（突发性）：句长变异系数，人类写作高，AI写作低
        - perplexity（困惑度）：文本不可预测性，人类写作高，AI写作低
        """
        issues: list[ValidationIssue] = []
    
        from core.statistical_fingerprint_optimizer import StatisticalFingerprintOptimizer
    
        optimizer = StatisticalFingerprintOptimizer()
        fingerprint = optimizer.compute_metrics(text)
    
        metrics["perplexity_score"] = fingerprint.perplexity_score
        metrics["burstiness_score"] = fingerprint.burstiness_score
        metrics["sentence_length_cv"] = fingerprint.sentence_length_cv
        metrics["overall_human_score"] = fingerprint.overall_human_score
    
        # 突发性检查：低于阈值则警告（AI倾向低突发性）
        min_burstiness = self.thresholds.get("min_burstiness", 0.35)
        if fingerprint.burstiness_score < min_burstiness:
            issues.append(ValidationIssue(
                "WARN", "统计指纹",
                f"突发性(burstiness) {fingerprint.burstiness_score:.3f} < 阈值 {min_burstiness}，"
                f"句长过于均匀，疑似AI生成。建议：插入短句爆发+长句沉淀交替。",
                {"burstiness": fingerprint.burstiness_score, "cv": fingerprint.sentence_length_cv},
            ))
    
        # 困惑度检查：高于阈值则通过（perplexity越高越像人类，这里检查的是反向指标）
        # 实际上 perplexity_score 已经是0-1归一化，越高越像人类
        # 如果 perplexity 太低，说明文本过于"可预测"
        max_perplexity = self.thresholds.get("max_perplexity", 0.30)
        if fingerprint.perplexity_score < max_perplexity:
            issues.append(ValidationIssue(
                "WARN", "统计指纹",
                f"困惑度(perplexity) {fingerprint.perplexity_score:.3f} < 阈值 {max_perplexity}，"
                f"文本过于可预测，疑似AI生成。建议：替换常见词为低频词、打破固定句式。",
                {"perplexity": fingerprint.perplexity_score},
            ))
    
        return issues
"""
Novel-OS ChapterValidator —— 统一校验层。

合并了旧版 interceptor.py (230行) + quality_gates.py (157行) + 8 guards (~900行)。
总计 ~1300 行 → ~350 行。

设计原则：
  - 所有阈值在一个 dict 中定义，消除 10% vs 15% 这种冲突。
  - 所有规则扫描只跑一次。
  - 输出简洁：PASS / WARN / BLOCK + 具体问题 + 可操作建议。
"""



# ============================================================================
# ★ 强制术语字典 —— 默认空，避免把某个项目的术语强加给所有项目。
# 项目可通过 BookConfig 传入自己的 mandatory_terms 覆盖。
# ============================================================================
TERM_MANDATORY: dict[str, dict] = {}

# ============================================================================
# ★ 唯一阈值源 —— 所有硬指标在这里定义，不散落各处
# ============================================================================
THRESHOLDS = {
# P0 阻塞级
"min_words": 4050,               # ★ 对齐 book.yaml 4500-450（原1900，2026-06-20修复）
"max_words": 4950,               # ★ 对齐 book.yaml 4500+450（原2600）
"max_ta_density": 0.04,        # 收紧至4%，与 genre_dna 对齐，实际优质网文通常<4%
"max_redline": 0,              # 红线词 = 0 容忍
# P1 警告级
"max_forbidden_patterns": 3,    # 禁用模式命中 > 3 个
"dialogue_ratio": (0.15, 0.55),
"max_dash_count": 3,
"max_ellipsis_count": 2,
"max_english_words": 0,
# 新增：句长 / IWR 结构
"sentence_length_min": 15,
"iwr_target": 2.5,
"question_count_min": 3,
"reveal_count_max": 5,
"max_sudden_count": 3,
"suspense_ending_min": 1,
"short_sentence_max": 12,
"long_sentence_min": 25,
"max_consecutive_short": 8,
# 统计指纹阈值
"min_burstiness": 0.35,      # 突发性最低阈值，低于此值像AI
"max_perplexity": 0.30,      # 困惑度最高阈值（反向指标），高于此值像人类
# P2 信息级
"sensory_min_per_500": 1,      # 每 500 字至少 1 处非视觉感官
"precise_number_threshold": 8, # 精确数字+量词阈值
}

# ============================================================================
# ★ 唯一禁用词库 —— interceptor 的黑名单合并于此
# ============================================================================
BANNED_PATTERNS: dict[str, list[str]] = {
"红线词": [
    # 政治敏感词及平台违禁词（此处留空，由外部 JSON 注入）
],
"禁用词": [
    "缓缓", "微微", "淡淡", "轻轻", "默默", "悄然",
    "莫名", "忽然", "竟然", "突然", "殊不知",
    "与此同时", "果不其然", "不得不说", "众所周知",
    "就在这时", "心中一凛", "心头一震", "下意识觉得",
],
"AI万能结尾": [
    "他不知道的是", "然而事情并没有那么简单",
    "一切归于平静", "尘埃落定",
],
"模板比喻": [
    "像一把刀", "像一条蛇", "像铁板", "像灯泡", "像离水的鱼",
    "像提线木偶", "像蜡像", "像木偶", "像纸片", "像瓷器",
    "像被加热的蜡像", "像离弦的箭", "像断了线的风筝",
],
"标志性AI表情": [
    "嘴角微微上扬", "眼眸中闪过一丝", "眼底浮现", "眸色幽深",
],
"X秒凝视模式": [
    # 用正则匹配：看了(\d+)秒
],
}

