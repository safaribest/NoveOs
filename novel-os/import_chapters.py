#!/usr/bin/env python3
"""批量导入已有章节文件到 world_state.db 的 chapter_history 表。

扫描 chapters/ 目录下的 第XXX章_标题_正文.txt 文件，
自动提取章节号、标题、字数、摘要，写入数据库。

用法:
    python import_chapters.py --book D:/noveos/books/新书名称/book.yaml

可选:
    --dry-run   只打印，不写入
    --force     强制覆盖已存在的记录
"""
from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
from pathlib import Path

from core.config_loader import BookConfig

logger = logging.getLogger("novel-os.import_chapters")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

CHAPTER_PATTERN = re.compile(r"第\s*(\d+)\s*章\s*[：:_]*(.+?)\s*\.txt")


def extract_chapter_info(file_path: Path) -> dict | None:
    """从文件名和正文提取章节信息。"""
    match = CHAPTER_PATTERN.match(file_path.name)
    if not match:
        return None

    chapter_num = int(match.group(1))
    title_from_filename = match.group(2).strip()

    content = file_path.read_text(encoding="utf-8").strip()
    if not content:
        logger.warning("文件为空: %s", file_path.name)
        return None

    # 统计中文字数
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", content))

    # 提取摘要：前200字（不含标题行）
    lines = content.splitlines()
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("第") and "章" not in stripped[:10]:
            body_start = i
            break

    body_text = "\n".join(lines[body_start:])
    summary = body_text[:200].replace("\n", " ") + "..."

    # 尝试从正文第一行提取更准确的标题
    title = title_from_filename
    if lines and ("章" in lines[0] or "：" in lines[0]):
        first_line = lines[0].strip()
        if "：" in first_line:
            parts = first_line.split("：", 1)
            if len(parts) == 2:
                title = parts[1].strip()

    return {
        "chapter": chapter_num,
        "title": title,
        "word_count": chinese_chars,
        "summary": summary,
        "content": content,
    }


def import_chapters(db_path: Path, project_id: str, chapters_dir: Path, force: bool = False, dry_run: bool = False):
    """扫描目录并导入章节。"""
    if not chapters_dir.exists():
        logger.error("目录不存在: %s", chapters_dir)
        return 1

    files = sorted(chapters_dir.glob("第*章*.txt"))
    if not files:
        logger.warning("未找到章节文件: %s", chapters_dir)
        return 0

    logger.info("发现 %d 个章节文件", len(files))

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 兼容：如果 chapter_history 没有 title 列，添加它
    cursor.execute("PRAGMA table_info(chapter_history)")
    columns = [row[1] for row in cursor.fetchall()]
    if "title" not in columns:
        cursor.execute("ALTER TABLE chapter_history ADD COLUMN title TEXT")
        conn.commit()
        logger.info("已为 chapter_history 表添加 title 列")

    imported = 0
    skipped = 0

    for file_path in files:
        info = extract_chapter_info(file_path)
        if not info:
            logger.warning("无法解析文件名: %s", file_path.name)
            continue

        # 检查是否已存在
        cursor.execute(
            "SELECT title, word_count FROM chapter_history WHERE project_id=? AND chapter=?",
            (project_id, info["chapter"]),
        )
        row = cursor.fetchone()

        if row and not force:
            logger.info("第 %d 章 已存在 (title=%s, words=%s)，跳过。使用 --force 覆盖",
                        info["chapter"], row[0], row[1])
            skipped += 1
            continue

        if dry_run:
            print(f"[DRY-RUN] 第{info['chapter']:03d}章 | {info['title']} | {info['word_count']}字 | {info['summary'][:50]}")
            imported += 1
            continue

        # 优先使用 outline 中的权威标题
        cursor.execute(
            "SELECT title FROM outline WHERE project_id = ? AND chapter = ?",
            (project_id, info["chapter"]),
        )
        row = cursor.fetchone()
        canonical_title = row[0] if row and row[0] else info["title"]

        cursor.execute(
            """INSERT OR REPLACE INTO chapter_history
               (project_id, chapter, summary, word_count, mode, title, created_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (project_id, info["chapter"], info["summary"], info["word_count"], "", canonical_title),
        )
        logger.info("导入 第 %d 章: %s (%d字)", info["chapter"], canonical_title, info["word_count"])
        imported += 1

    conn.commit()
    conn.close()

    logger.info("完成: 导入 %d 章, 跳过 %d 章", imported, skipped)
    return 0


def main():
    parser = argparse.ArgumentParser(description="批量导入已有章节到数据库")
    parser.add_argument("--book", required=True, help="book.yaml 路径")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的记录")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写入")
    args = parser.parse_args()

    cfg = BookConfig.from_yaml(args.book)
    project_id = cfg.base_path.name
    db_path = cfg.base_path / "world_state.db"
    chapters_dir = cfg.base_path / cfg.output_dir

    return import_chapters(db_path, project_id, chapters_dir, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
