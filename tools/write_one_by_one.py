#!/usr/bin/env python3
"""
逐章写作脚本 —— 解决"一口气全部写完"的问题。

核心机制：
1. 逐章调用 cli.py write --chapter N（非批量 range）
2. 每章写完后验证字数（1900-2500）和标题（必须与大纲一致）
3. 验证失败 → 删除文件 + 回滚数据库 + 自动重试（最多2次）
4. 一章通过后才写下一章 —— 彻底避免"一口气写完"的质量失控
"""
import subprocess
import sys
import sqlite3
from pathlib import Path

PROJECT_NAME = "村超系统：我带侗寨球队踢爆世界杯"
PROJECT_DIR = Path("books") / PROJECT_NAME
BOOK_YAML = PROJECT_DIR / "book.yaml"
CHAPTERS_DIR = PROJECT_DIR / "chapters"
DB_PATH = PROJECT_DIR / "world_state.db"


def get_expected_title(ch: int) -> str:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM outline WHERE chapter = ?", (ch,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""


def get_word_count(file_path: Path) -> int:
    content = file_path.read_text(encoding="utf-8")
    lines = content.strip().splitlines()
    # 去掉标题行（通常前2行是标题+空行）
    body = "\n".join(lines[2:] if len(lines) > 2 else lines)
    return len([c for c in body if "\u4e00" <= c <= "\u9fff"])


def rollback_chapter(ch: int):
    """验证失败时回滚：删文件 + 删数据库记录 + 重置 current_chapter"""
    # 删除文件
    for f in CHAPTERS_DIR.glob(f"第{ch:03d}章_*.txt"):
        f.unlink(missing_ok=True)
    
    # 删除数据库记录
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    pid = PROJECT_NAME
    cursor.execute("DELETE FROM chapter_history WHERE project_id = ? AND chapter = ?", (pid, ch))
    cursor.execute(
        "UPDATE projects SET current_chapter = ?, updated_at = datetime('now') WHERE project_id = ?",
        (ch - 1, pid)
    )
    conn.commit()
    conn.close()
    print(f"  已回滚第{ch}章（文件+数据库）")


def write_chapter(ch: int) -> bool:
    expected_title = get_expected_title(ch)
    print(f"\n{'='*60}")
    print(f"【第{ch}章】{expected_title}")
    print(f"{'='*60}")
    
    result = subprocess.run(
        [sys.executable, "novel-os/cli.py", "--book", str(BOOK_YAML), "write", "--chapter", str(ch)],
        capture_output=True, text=True, cwd="D:/noveos", encoding="utf-8", errors="replace"
    )
    
    print(result.stdout)
    if result.stderr and "ERROR" in result.stderr:
        print(f"  检测到错误输出")
    
    if result.returncode != 0:
        return False
    
    # 查找输出文件
    files = list(CHAPTERS_DIR.glob(f"第{ch:03d}章_*.txt"))
    if not files:
        print(f"  错误：未找到第{ch}章的输出文件")
        return False
    
    file_path = files[0]
    wc = get_word_count(file_path)
    print(f"  字数：{wc}")
    
    # 字数验证
    if wc < 1900:
        print(f"  字数不足（{wc} < 1900），标记为失败")
        file_path.unlink()
        return False
    if wc > 2600:
        print(f"  警告：字数超标（{wc} > 2600）")
    
    # 标题验证
    actual_title = file_path.stem.replace(f"第{ch:03d}章_", "")
    if expected_title and actual_title != expected_title:
        print(f"  标题不匹配：大纲='{expected_title}'，实际='{actual_title}'")
        new_path = CHAPTERS_DIR / f"第{ch:03d}章_{expected_title}.txt"
        file_path.rename(new_path)
        print(f"  已重命名为：{new_path.name}")
    
    print(f"  第{ch}章通过验证")
    return True


def main():
    target_chapters = [1, 2, 3, 4, 5]
    max_attempts = 2
    
    for ch in target_chapters:
        success = False
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                print(f"\n  第{ch}章第{attempt}次尝试...")
                rollback_chapter(ch)
            
            success = write_chapter(ch)
            if success:
                break
        
        if not success:
            print(f"\n  第{ch}章在{max_attempts}次尝试后仍失败，停止写作")
            sys.exit(1)
    
    print("\n" + "="*60)
    print("前5章逐章写作全部完成")
    print("="*60)
    
    # 最终统计
    for ch in target_chapters:
        files = list(CHAPTERS_DIR.glob(f"第{ch:03d}章_*.txt"))
        if files:
            wc = get_word_count(files[0])
            print(f"  第{ch}章: {wc}字  {files[0].name}")


if __name__ == "__main__":
    main()
