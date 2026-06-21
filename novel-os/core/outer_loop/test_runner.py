"""TestRunner —— 在测试章节集上运行流水线并收集审计数据。

职责:
1. 找到测试章节（已存在的 .md 或 .txt 文件）
2. 逐章跑 WritingPipeline
3. 收集每章完整 AuditRecord
4. 产出 AuditBatch
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from core.fanqie_course import load_fanqie_rules
from core.outer_loop.models import AuditBatch, AuditRecord

logger = logging.getLogger("novel-os.outer_loop.test_runner")


class TestRunner:
    """测试集运行器。"""

    def __init__(
        self,
        chapters_dir: str | Path,
        project_id: str = "",
        book_config_path: str = "",
        pipeline=None,  # WritingPipeline 实例
    ) -> None:
        self.chapters_dir = Path(chapters_dir)
        self.project_id = project_id
        self.book_config_path = book_config_path
        self._pipeline = pipeline
        self._fanqie_rules = load_fanqie_rules()

    def run(self, chapter_range: tuple[int, int] | None = None) -> AuditBatch:
        """跑测试集，返回 AuditBatch。

        Args:
            chapter_range: (start, end) 要测试的章节范围。None 表示自动发现。

        修复说明（2026-06-20）：
        每次 run 前重新加载番茄规则，确保 RuleWriter 修改的 overrides 生效。
        原实现在 __init__ 时加载一次 _fanqie_rules，多轮之间不更新，
        导致 Step6 验证测试用的还是旧规则 → 指标必然 UNCHANGED。
        """
        # ★ 修复：每次 run 前刷新番茄规则（读取最新 overrides）
        try:
            self._fanqie_rules = load_fanqie_rules()
        except Exception as exc:
            logger.warning("[TestRunner] 刷新番茄规则失败: %s", exc)

        chapter_files = self._discover_chapters(chapter_range)
        if not chapter_files:
            raise FileNotFoundError(f"未找到测试章节: {self.chapters_dir}")

        logger.info("[TestRunner] 发现 %d 章测试数据", len(chapter_files))

        batch = AuditBatch(
            source="test_run",
            run_id=f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            run_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        for ch_num, filepath in sorted(chapter_files):
            t0 = time.time()
            try:
                content = self._read_chapter(filepath)
                record = self._audit_chapter(ch_num, content)
                record.pipeline_time_ms = round((time.time() - t0) * 1000)
                batch.records.append(record)
                logger.info(
                    "[TestRunner] 第 %d 章 审计完成: score=%.3f, %s",
                    ch_num, record.rule_score_total, record.validator_verdict,
                )
            except Exception as exc:
                logger.error("[TestRunner] 第 %d 章 审计失败: %s", ch_num, exc)
                batch.records.append(AuditRecord(
                    chapter_num=ch_num,
                    validator_verdict="ERROR",
                    metadata={"error": str(exc)},
                ))

        logger.info(
            "[TestRunner] 批次完成: %d/%d 章, avg_score=%.3f, pass_rate=%.1f%%",
            len([r for r in batch.records if r.validator_verdict != "ERROR"]),
            len(batch.records),
            batch.avg_rule_score,
            batch.pass_rate * 100,
        )
        return batch

    # ── 章节发现 ──
    def _discover_chapters(
        self, chapter_range: tuple[int, int] | None
    ) -> list[tuple[int, Path]]:
        """发现测试章节文件。支持 .md / .txt 格式。"""
        files: list[tuple[int, Path]] = []

        for pattern in ("*.md", "*.txt"):
            for fp in sorted(self.chapters_dir.glob(pattern)):
                ch_num = self._parse_chapter_num(fp.stem)
                if ch_num is None:
                    continue
                if chapter_range:
                    if chapter_range[0] <= ch_num <= chapter_range[1]:
                        files.append((ch_num, fp))
                else:
                    files.append((ch_num, fp))

        return files

    @staticmethod
    def _parse_chapter_num(filename: str) -> int | None:
        """从文件名解析章节号。支持 '第001章' 'ch001' 'chapter_001' 等。"""
        patterns = [
            r"第\s*(\d+)\s*章",
            r"ch(?:apter)?[_\s]*(\d+)",
            r"(\d{3,4})",
        ]
        for pat in patterns:
            m = re.search(pat, filename, re.IGNORECASE)
            if m:
                return int(m.group(1))
        return None

    @staticmethod
    def _read_chapter(filepath: Path) -> str:
        """读取章节文件内容。"""
        return filepath.read_text(encoding="utf-8")

    # ── 审计 ──
    def _audit_chapter(self, ch_num: int, content: str) -> AuditRecord:
        """对单章执行完整审计（ChapterValidator + StyleRuleEngine + 统计指纹）。"""
        record = AuditRecord(chapter_num=ch_num)

        # 1. 字数
        cn_chars = re.findall(r"[一-鿿]", content)
        record.word_count = len(cn_chars)

        # 2. 他字密度
        ta_count = content.count("他") + content.count("她") + content.count("它")
        record.ta_density = ta_count / max(record.word_count, 1)
        record.ta_count = ta_count

        # 3. StyleRuleEngine
        from core.writing.style_rule_engine import StyleRuleEngine

        engine = StyleRuleEngine()
        score_result = engine.score(content)
        record.rule_score_total = score_result["score"]["total"]
        record.rule_score_breakdown = score_result["score"]
        record.rule_issue_count = score_result["issue_count"]
        record.cn_number_density = score_result.get("cn_number_density", 0)
        record.not_x_but_y_count = score_result["breakdown"].get("not_x_but_y", 0)
        record.xiang_count = score_result["breakdown"].get("xiang", 0)
        record.emotion_label_count = score_result["breakdown"].get("emotion_label", 0)
        record.precise_number_count = score_result["breakdown"].get("precise_number", 0)

        # 4. ChapterValidator
        from core.chapter_validator import ChapterValidator

        validator = ChapterValidator()
        val_result = validator.validate(content, {"chapter_num": ch_num})
        record.validator_verdict = val_result.verdict
        record.validator_issues = [
            {"level": i.level, "category": i.category, "message": i.message}
            for i in val_result.issues
        ]
        record.blocked = val_result.verdict == "BLOCK"

        # 5. 禁用词命中
        from core.chapter_validator import BANNED_PATTERNS

        for cat in ["禁用词", "AI万能结尾", "模板比喻", "标志性AI表情"]:
            pat_words = BANNED_PATTERNS.get(cat, [])
            hits = [w for w in pat_words if w in content]
            if hits:
                record.banned_hits[cat] = hits
        record.banned_total = sum(len(v) for v in record.banned_hits.values())

        # 6. 对话占比
        record.dialogue_ratio = self._calc_dialogue_ratio(content)

        # 7. 句长
        sentences = [s for s in re.split(r"[。！？…]+", content) if s.strip()]
        sent_lens = [len(re.findall(r"[一-鿿]", s)) for s in sentences if re.findall(r"[一-鿿]", s)]
        record.avg_sentence_length = round(sum(sent_lens) / max(len(sent_lens), 1), 1) if sent_lens else 0

        # 8. 段长
        paragraphs = [p for p in content.split("\n") if p.strip()]
        para_lens = [len(re.findall(r"[一-鿿]", p)) for p in paragraphs]
        record.avg_para_length = round(sum(para_lens) / max(len(para_lens), 1), 1) if para_lens else 0

        # 9. 统计指纹
        from core.statistical_fingerprint_optimizer import StatisticalFingerprintOptimizer

        optimizer = StatisticalFingerprintOptimizer()
        fingerprint = optimizer.compute_metrics(content)
        record.burstiness = fingerprint.burstiness_score
        record.perplexity = fingerprint.perplexity_score
        record.sentence_length_cv = fingerprint.sentence_length_cv
        record.overall_human_score = fingerprint.overall_human_score

        # 10. IWR / 悬念
        from core.iwr_analyzer import analyze_chapter

        iwr = analyze_chapter(content)
        record.iwr_score = iwr.get("iwr_score", 0)

        # 11. 章末钩子
        tail = content[-200:]
        record.ending_hook = bool(re.search(r"[？?]|正要|就要|刚要|即将|不知道|不明白|然而|可是|但$", tail))

        # 12. "突然"计数
        record.sudden_count = len(re.findall(r"突然", content))

        # 13. 感官密度
        record.sensory_count = len(re.findall(
            r"(闻到|听见|触到|摸到|冰凉|温热|粗糙|滑腻|刺痛|麻木"
            r"|气味|声音|温度|触感|舌尖|鼻腔|耳膜|皮肤|指尖传来)",
            content,
        ))

        # 14. 番茄课程指标
        record.fanqie_opening_hook = self._check_opening_hook(content)
        record.fanqie_opening_hook_position = self._opening_hook_position(content)
        record.fanqie_climax_count = self._count_climax_markers(content)
        record.fanqie_ending_hook = self._check_ending_hook(content)
        record.fanqie_emotion_ratio = self._estimate_emotion_ratio(content)
        record.fanqie_course_score = self._calc_fanqie_score(record)

        return record

    # ── 番茄课程辅助方法 ──
    def _check_opening_hook(self, content: str) -> bool:
        opening_rules = self._fanqie_rules.get_opening_rules()
        max_lead_in = opening_rules.get("max_lead_in_words", 300)
        hook_markers = opening_rules.get("hook_markers", [])
        prefix = self._take_n_cn_chars(content, max_lead_in)
        return any(marker in prefix for marker in hook_markers)

    def _opening_hook_position(self, content: str) -> int:
        opening_rules = self._fanqie_rules.get_opening_rules()
        max_lead_in = opening_rules.get("max_lead_in_words", 300)
        hook_markers = opening_rules.get("hook_markers", [])
        prefix = self._take_n_cn_chars(content, max_lead_in)
        positions = [content.find(marker) for marker in hook_markers if marker in prefix]
        return min(positions) if positions else 0

    def _count_climax_markers(self, content: str) -> int:
        """统计爽点标记数（按段落去重，避免同一段重复出现同一关键词被多次计数）。

        修复说明（2026-06-20）：
        原实现 sum(content.count(kw)) 按全文累加，同一段落中"终于...终于"会计2次。
        现改为按段落计数：每段中每个关键词最多计1次，避免段落内重复刷分。
        """
        chapter_beat = self._fanqie_rules.get_chapter_beat_rules()
        climax_keywords = chapter_beat.get("climax_keywords", [])
        paragraphs = [p for p in content.split("\n") if p.strip()]
        total = 0
        for para in paragraphs:
            for kw in climax_keywords:
                if kw in para:
                    total += 1
                    break  # 每段每个关键词最多计1次
        return total

    def _check_ending_hook(self, content: str) -> bool:
        chapter_beat = self._fanqie_rules.get_chapter_beat_rules()
        zone = chapter_beat.get("ending_hook_zone", 200)
        ending_markers = chapter_beat.get("ending_hook_markers", [])
        tail = self._take_last_n_cn_chars(content, zone)
        return any(marker in tail for marker in ending_markers)

    def _estimate_emotion_ratio(self, content: str) -> dict[str, float]:
        pacing = self._fanqie_rules.get_pacing_rules()
        emotion_keywords = pacing.get("emotion_keywords", {})
        counts: dict[str, int] = {}
        for category, keywords in emotion_keywords.items():
            counts[category] = sum(content.count(kw) for kw in keywords)
        total = sum(counts.values())
        if total == 0:
            return {category: 0.0 for category in counts}
        return {category: round(cnt / total, 4) for category, cnt in counts.items()}

    def _calc_fanqie_score(self, record: AuditRecord) -> float:
        score = 0.0
        if record.fanqie_opening_hook or record.chapter_num > 3:
            score += 0.25
        if record.fanqie_ending_hook:
            score += 0.25
        if record.fanqie_climax_count >= 1:
            score += 0.25
        if record.fanqie_emotion_ratio:
            target = self._fanqie_rules.get_emotion_ratio("")
            l1 = sum(
                abs(record.fanqie_emotion_ratio.get(k, 0.0) - target.get(k, 0.0))
                for k in target
            )
            similarity = max(0.0, 1.0 - l1 / 2.0)
            score += 0.25 * similarity
        return round(score, 4)

    @staticmethod
    def _take_n_cn_chars(content: str, n: int) -> str:
        count = 0
        cut = 0
        for i, ch in enumerate(content):
            if "\u4e00" <= ch <= "\u9fff":
                count += 1
            if count >= n:
                cut = i + 1
                break
        return content[:cut]

    @staticmethod
    def _take_last_n_cn_chars(content: str, n: int) -> str:
        count = 0
        start = 0
        for i in range(len(content) - 1, -1, -1):
            ch = content[i]
            if "\u4e00" <= ch <= "\u9fff":
                count += 1
            if count >= n:
                start = i
                break
        return content[start:]

    @staticmethod
    def _calc_dialogue_ratio(text: str) -> float:
        """估算对话占比。"""
        paragraphs = [p for p in text.split("\n") if p.strip()]
        if not paragraphs:
            return 0.0
        dial_paras = sum(
            1 for p in paragraphs
            if re.search(r'[“”‘’""''「」『』]', p)
        )
        return dial_paras / len(paragraphs)

    # ── 批量审计 JSON 导出 ──
    def export_audit_json(self, batch: AuditBatch, output_dir: str | Path) -> Path:
        """将审计批次导出为 JSON 文件，供 Analyzer 使用。"""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        filepath = out / f"audit_{batch.run_id}.json"
        data = {
            "run_id": batch.run_id,
            "run_at": batch.run_at,
            "source": batch.source,
            "summary": {
                "avg_rule_score": batch.avg_rule_score,
                "block_count": batch.block_count,
                "pass_rate": batch.pass_rate,
                "chapters": len(batch.records),
            },
            "records": [r.to_dict() for r in batch.records],
        }
        filepath.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("[TestRunner] 审计数据已导出: %s", filepath)
        return filepath
