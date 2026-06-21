#!/usr/bin/env python3
"""Novel-OS 单本小说压测脚本。

用法:
    python stress_test.py --book book.yaml --start 12 --end 40

输出:
    - stress_report.json  (详细数据)
    - stress_summary.md   (可读报告)
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.batch_writer import BatchWriter, WriteResult
from core.config_loader import BookConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("novel-os.stress")


@dataclass
class ChapterMetrics:
    chapter_num: int
    success: bool
    word_count: int
    gate_level: str
    attempts: int
    elapsed_sec: float
    saved_path: str | None = None
    error: str | None = None


@dataclass
class StressReport:
    book: str
    model: str
    start_chapter: int
    end_chapter: int
    total_chapters: int
    success_count: int
    fail_count: int
    avg_word_count: float
    min_word_count: int
    max_word_count: int
    avg_elapsed_sec: float
    min_elapsed_sec: float
    max_elapsed_sec: float
    total_elapsed_min: float
    pass_rate: float
    gate_pass: int
    gate_warn: int
    gate_block: int
    avg_attempts: float
    chapters: list[ChapterMetrics] = field(default_factory=list)


def run_stress(book_path: str, start: int, end: int) -> StressReport:
    cfg = BookConfig.from_yaml(book_path)
    writer = BatchWriter(cfg)

    chapters: list[ChapterMetrics] = []
    t0_global = time.time()

    for num in range(start, end + 1):
        t0 = time.time()
        logger.info("=" * 60)
        logger.info("[压测] 第 %d/%d 章", num, end)

        try:
            result = writer.write_chapter(num)
            elapsed = time.time() - t0
            chapters.append(
                ChapterMetrics(
                    chapter_num=result.chapter_num,
                    success=result.success,
                    word_count=result.word_count,
                    gate_level=result.gate_level,
                    attempts=result.attempts,
                    elapsed_sec=round(elapsed, 1),
                    saved_path=str(result.saved_path) if result.saved_path else None,
                )
            )
            status = "PASS" if result.success else "FAIL"
            logger.info(
                "[压测] 第 %d 章 %s | 字数=%d | 质量门=%s | 尝试=%d | 耗时=%.1fs",
                num, status, result.word_count, result.gate_level,
                result.attempts, elapsed,
            )
        except Exception as exc:
            elapsed = time.time() - t0
            chapters.append(
                ChapterMetrics(
                    chapter_num=num,
                    success=False,
                    word_count=0,
                    gate_level="ERROR",
                    attempts=0,
                    elapsed_sec=round(elapsed, 1),
                    error=str(exc),
                )
            )
            logger.error("[压测] 第 %d 章 异常: %s", num, exc)

    total_elapsed = time.time() - t0_global
    success_chapters = [c for c in chapters if c.success]
    fail_chapters = [c for c in chapters if not c.success]

    word_counts = [c.word_count for c in success_chapters]
    elapsed_secs = [c.elapsed_sec for c in chapters]
    attempts = [c.attempts for c in chapters]

    gate_pass = sum(1 for c in success_chapters if c.gate_level == "PASS")
    gate_warn = sum(1 for c in success_chapters if c.gate_level == "WARN")
    gate_block = sum(1 for c in fail_chapters if c.gate_level == "BLOCKING")

    return StressReport(
        book=cfg.project,
        model=cfg.llm.get("model", "unknown"),
        start_chapter=start,
        end_chapter=end,
        total_chapters=len(chapters),
        success_count=len(success_chapters),
        fail_count=len(fail_chapters),
        avg_word_count=round(statistics.mean(word_counts), 1) if word_counts else 0,
        min_word_count=min(word_counts) if word_counts else 0,
        max_word_count=max(word_counts) if word_counts else 0,
        avg_elapsed_sec=round(statistics.mean(elapsed_secs), 1) if elapsed_secs else 0,
        min_elapsed_sec=min(elapsed_secs) if elapsed_secs else 0,
        max_elapsed_sec=max(elapsed_secs) if elapsed_secs else 0,
        total_elapsed_min=round(total_elapsed / 60, 1),
        pass_rate=round(len(success_chapters) / len(chapters) * 100, 1) if chapters else 0,
        gate_pass=gate_pass,
        gate_warn=gate_warn,
        gate_block=gate_block,
        avg_attempts=round(statistics.mean(attempts), 1) if attempts else 0,
        chapters=chapters,
    )


def save_report(report: StressReport, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = output_dir / "stress_report.json"
    json_path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Markdown 摘要
    md = f"""# Novel-OS 压测报告

## 概览

- **项目**: {report.book}
- **模型**: {report.model}
- **章节范围**: {report.start_chapter} - {report.end_chapter}
- **总耗时**: {report.total_elapsed_min} 分钟
- **成功率**: {report.pass_rate}% ({report.success_count}/{report.total_chapters})

## 字数统计

| 指标 | 数值 |
|------|------|
| 平均字数 | {report.avg_word_count} |
| 最小字数 | {report.min_word_count} |
| 最大字数 | {report.max_word_count} |

## 耗时统计

| 指标 | 数值 |
|------|------|
| 平均耗时 | {report.avg_elapsed_sec} 秒 |
| 最小耗时 | {report.min_elapsed_sec} 秒 |
| 最大耗时 | {report.max_elapsed_sec} 秒 |

## 质量门分布

- PASS: {report.gate_pass}
- WARN: {report.gate_warn}
- BLOCKING: {report.gate_block}

## 平均重试次数

{report.avg_attempts}

## 失败章节

"""
    for c in report.chapters:
        if not c.success:
            md += f"- 第 {c.chapter_num} 章: {c.gate_level}"
            if c.error:
                md += f" ({c.error})"
            md += "\n"

    md_path = output_dir / "stress_summary.md"
    md_path.write_text(md, encoding="utf-8")

    logger.info("压测报告已保存: %s, %s", json_path, md_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--output", default="output/stress")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Novel-OS 压测启动")
    logger.info("范围: %d-%d", args.start, args.end)
    logger.info("=" * 60)

    report = run_stress(args.book, args.start, args.end)
    save_report(report, Path(args.output))

    logger.info("=" * 60)
    logger.info("压测完成")
    logger.info("成功率: %s%% | 平均字数: %s | 总耗时: %s 分钟",
                report.pass_rate, report.avg_word_count, report.total_elapsed_min)
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
