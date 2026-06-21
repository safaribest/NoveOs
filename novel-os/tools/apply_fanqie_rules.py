"""番茄课程规则工具 —— 诊断文本/项目并生成 prompt 注入。

用法：
    python tools/apply_fanqie_rules.py --diagnose-file chapters/ch001.txt --chapter 1 --genre 年代商战
    python tools/apply_fanqie_rules.py --diagnose-project D:/noveos/books/我的项目
    python tools/apply_fanqie_rules.py --apply-genre 年代商战
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 把项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.fanqie_course import load_fanqie_rules
from core.guards.reader_pull_guard import ReaderPullGuard
from core.guards.pacing_guard import PacingGuard
from core.writing.prompts import build_fanqie_injection


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_chapter_num(filename: str) -> int:
    patterns = [
        r"第\s*(\d+)\s*章",
        r"ch(?:apter)?[_\s]*(\d+)",
        r"(\d{3,4})",
    ]
    for pat in patterns:
        m = re.search(pat, filename, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 0


def _map_genre(genre: str) -> str:
    """简单映射，与 prompts.py 保持一致。"""
    from core.writing.prompts import map_genre_to_course_key
    return map_genre_to_course_key(genre)


def diagnose_file(filepath: str, chapter_num: int, genre: str) -> str:
    """诊断单个章节文件。"""
    path = Path(filepath)
    if not path.exists():
        return f"文件不存在: {path}"

    content = _read_text(path)
    if chapter_num <= 0:
        chapter_num = _parse_chapter_num(path.name) or 1

    rules = load_fanqie_rules()
    reader_guard = ReaderPullGuard()
    pacing_guard = PacingGuard()

    reader_result = reader_guard.run(content, {"chapter_num": chapter_num})
    pacing_result = pacing_guard.run(
        content,
        {"chapter_num": chapter_num, "genre": genre, "genre_key": _map_genre(genre)},
    )

    # 计算爽点密度
    beat_rules = rules.get_chapter_beat_rules()
    climax_keywords = beat_rules.get("climax_keywords", [])
    climax_count = sum(content.count(kw) for kw in climax_keywords)

    lines = []
    lines.append(f"# 番茄课程诊断报告：{path.name}")
    lines.append(f"- 章节号：{chapter_num}")
    lines.append(f"- 品类：{genre or '未指定'}")
    lines.append(f"- 字数：{len(content)} 字符")
    lines.append("")
    lines.append("## ReaderPullGuard 结果")
    lines.append(f"- 级别：{reader_result.level}")
    for issue in reader_result.metadata.get("issues", []):
        lines.append(f"- {issue}")
    if not reader_result.metadata.get("issues"):
        lines.append("- 无问题")

    lines.append("")
    lines.append("## PacingGuard 结果")
    lines.append(f"- 级别：{pacing_result.level}")
    for issue in pacing_result.metadata.get("issues", []):
        lines.append(f"- {issue}")
    if not pacing_result.metadata.get("issues"):
        lines.append("- 无问题")

    lines.append("")
    lines.append("## 爽点密度")
    lines.append(f"- 检测到 {climax_count} 处情绪爆点标记（关键词：{', '.join(climax_keywords[:5])}...）")
    min_climax = beat_rules.get("min_climax_per_chapter", 1)
    lines.append(f"- 建议每章 ≥{min_climax} 处")

    lines.append("")
    lines.append("## Prompt 注入建议")
    lines.append("将以下内容加入 writer prompt：")
    lines.append("```markdown")
    lines.append(build_fanqie_injection(chapter_num, genre))
    lines.append("```")

    return "\n".join(lines)


def diagnose_project(project_dir: str) -> str:
    """诊断项目 chapters 目录下的所有章节。"""
    project_path = Path(project_dir)
    chapters_dir = project_path / "chapters"
    if not chapters_dir.exists():
        return f"未找到 chapters 目录: {chapters_dir}"

    # 尝试读取 book.yaml 获取 genre
    genre = ""
    book_yaml = project_path / "book.yaml"
    if book_yaml.exists():
        import yaml
        try:
            cfg = yaml.safe_load(book_yaml.read_text(encoding="utf-8"))
            genre = cfg.get("genre", "")
        except Exception:
            pass

    files = sorted(chapters_dir.glob("*.txt")) + sorted(chapters_dir.glob("*.md"))
    if not files:
        return f"chapters 目录为空: {chapters_dir}"

    lines = []
    lines.append(f"# 项目番茄课程诊断报告：{project_path.name}")
    lines.append(f"- 品类：{genre or '未指定'}")
    lines.append(f"- 章节数：{len(files)}")
    lines.append("")

    opening_pass = 0
    ending_pass = 0
    climax_ok = 0
    total = len(files)

    reader_guard = ReaderPullGuard()
    beat_rules = load_fanqie_rules().get_chapter_beat_rules()
    climax_keywords = beat_rules.get("climax_keywords", [])
    min_climax = beat_rules.get("min_climax_per_chapter", 1)

    for fp in files:
        ch_num = _parse_chapter_num(fp.name) or 1
        content = _read_text(fp)
        reader_result = reader_guard.run(content, {"chapter_num": ch_num})
        issues = reader_result.metadata.get("issues", [])

        has_opening = not any("[开篇缺钩子]" in i for i in issues)
        has_ending = not any("[章节末缺钩子]" in i for i in issues)
        climax_count = sum(content.count(kw) for kw in climax_keywords)
        has_climax = climax_count >= min_climax

        if ch_num <= 3:
            opening_pass += 1 if has_opening else 0
        ending_pass += 1 if has_ending else 0
        climax_ok += 1 if has_climax else 0

        if ch_num <= 3:
            lines.append(f"## {fp.name}（第{ch_num}章）")
            for issue in issues:
                lines.append(f"- {issue}")

    lines.append("")
    lines.append("## 汇总")
    lines.append(f"- 前 3 章开篇钩子通过率：{opening_pass}/3")
    lines.append(f"- 全篇章末钩子通过率：{ending_pass}/{total}")
    lines.append(f"- 全章爽点密度达标率：{climax_ok}/{total}")

    return "\n".join(lines)


def apply_genre(genre: str) -> str:
    """输出某品类的 prompt 注入文本。"""
    return build_fanqie_injection(1, genre)


def main() -> int:
    parser = argparse.ArgumentParser(description="番茄课程规则诊断工具")
    parser.add_argument("--diagnose-file", help="诊断单个章节文件")
    parser.add_argument("--chapter", type=int, default=0, help="章节号（自动识别文件名）")
    parser.add_argument("--genre", default="", help="品类，如 年代商战/甜宠")
    parser.add_argument("--diagnose-project", help="诊断项目目录")
    parser.add_argument("--apply-genre", help="输出某品类的 prompt 注入")
    parser.add_argument("--output", help="输出到文件（否则 stdout）")

    args = parser.parse_args()

    if args.diagnose_file:
        result = diagnose_file(args.diagnose_file, args.chapter, args.genre)
    elif args.diagnose_project:
        result = diagnose_project(args.diagnose_project)
    elif args.apply_genre:
        result = apply_genre(args.apply_genre)
    else:
        parser.print_help()
        return 1

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"已保存到: {args.output}")
    else:
        print(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
