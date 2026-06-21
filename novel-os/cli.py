#!/usr/bin/env python3
"""Novel-OS 命令行入口。

用法示例:
    python cli.py init --book book.yaml
    python cli.py write --book book.yaml --chapter 1
    python cli.py write --book book.yaml --range 1:10 --resume
    python cli.py state --book book.yaml --export world_state.json
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# 自动加载项目根目录的 .env 文件
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    with open(_ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key = _key.strip()
                _val = _val.strip().strip('"').strip("'")
                os.environ[_key] = _val

from core.batch_writer import BatchWriter
from core.config_loader import BookConfig
from core.orchestrator import Orchestrator
from core.state_manager import StateManager

# 强制 UTF-8 编码，避免 Windows 终端中文乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("novel-os.cli")


def cmd_init(args: argparse.Namespace) -> int:
    """初始化项目状态库。"""
    cfg = BookConfig.from_yaml(args.book)
    project_id = cfg.base_path.name
    db_path = cfg.base_path / "world_state.db"

    # 方式1: 从 book_data.py 数据文件初始化（推荐）
    if args.data:
        import subprocess
        init_script = Path(__file__).parent / "init_book.py"
        cmd = [
            sys.executable, str(init_script),
            "--book", str(args.book),
            "--data", str(args.data),
        ]
        if args.dry_run:
            cmd.append("--dry-run")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            return result.returncode

    # 方式2: 从旧版 JSON 大纲初始化（兼容）
    elif args.outline:
        state = StateManager(db_path, project_id=project_id)
        import json
        outline = json.loads(Path(args.outline).read_text(encoding="utf-8"))
        state.init_from_outline(outline)
        state.init_genre_dna(cfg.genre)
        logger.info("已从大纲初始化状态库，债务=%d 伏笔=%d",
                    len(outline.get("plot", {}).get("debts", [])),
                    len(outline.get("plot", {}).get("foreshadowing", [])))
    else:
        # 仅创建空数据库 schema
        from init_book import init_database, init_project_record
        import sqlite3
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_database(db_path, project_id)
        conn = sqlite3.connect(str(db_path))
        init_project_record(conn, project_id, cfg.project, cfg.genre, cfg.platform, str(cfg.base_path))
        conn.close()
        state = StateManager(db_path, project_id=project_id)
        state.init_genre_dna(cfg.genre)
        logger.info("空状态库已初始化: %s", db_path)

    # 可选: 导入已有章节文件
    if args.import_chapters:
        import subprocess
        import_script = Path(__file__).parent / "import_chapters.py"
        cmd = [
            sys.executable, str(import_script),
            "--book", str(args.book),
        ]
        if args.force:
            cmd.append("--force")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            return result.returncode

    return 0


def cmd_write(args: argparse.Namespace) -> int:
    """执行写作。"""
    cfg = BookConfig.from_yaml(args.book)
    project_id = cfg.base_path.name
    db_path = cfg.base_path / "world_state.db"

    # 启动前完整性校验（防止 genre_dna / term_dict 缺失导致无限重试）
    state = StateManager(db_path, project_id)
    # ★ 修复（2026-06-20）：必须先 init_project 否则 init_genre_dna 外键约束失败
    if not state.get_project_info():
        logger.info("初始化项目: %s", project_id)
        state.init_project(
            project_id,
            cfg.project,
            cfg.genre,
            cfg.platform,
            str(cfg.base_path),
            cfg.chapters_target,
        )
    if not state.get_genre_dna():
        logger.warning("genre_dna 缺失，自动补初始化...")
        state.init_genre_dna(cfg.genre)
    if not state.get_term_dict():
        logger.warning("term_dict 为空，建议从大纲提取术语后重新初始化")

    writer = BatchWriter(cfg)

    if args.chapter is not None:
        result = writer.write_chapter(args.chapter)
        print(f"第 {result.chapter_num} 章: success={result.success}, level={result.gate_level}")
        return 0 if result.success else 1

    if args.range:
        start, end = map(int, args.range.split(":"))
        results = writer.write_range(start, end, resume=args.resume)
        success_count = sum(1 for r in results if r.success)
        print(f"完成: {success_count}/{len(results)} 章成功")
        return 0 if success_count == len(results) else 1

    print("请指定 --chapter 或 --range")
    return 2


def cmd_state(args: argparse.Namespace) -> int:
    """状态库操作。"""
    cfg = BookConfig.from_yaml(args.book)
    state = StateManager(cfg.base_path / "world_state.db")

    if args.export:
        out = Path(args.export)
        state.export_json_view(out)
        logger.info("状态已导出: %s", out)
        return 0

    if args.rollback:
        chapter, snap_type = args.rollback.split(",")
        data = state.rollback_to_snapshot(int(chapter), snap_type)
        print(data)
        return 0

    print("请指定 --export 或 --rollback")
    return 2


def cmd_pipeline(args: argparse.Namespace) -> int:
    """通过 Orchestrator 双层调度批量写作（支持暂停/恢复/外层巡检）。"""
    cfg = BookConfig.from_yaml(args.book)
    project_id = cfg.base_path.name

    orch = Orchestrator()
    orch.register_project(project_id, cfg)

    if args.range:
        start, end = map(int, args.range.split(":"))
    else:
        print("请指定 --range（如 1:30）")
        return 2

    pipeline_id = orch.start_pipeline(
        project_id, (start, end), resume=args.resume
    )
    print(f"Pipeline 已启动: {pipeline_id}")
    print(f"项目: {project_id}, 章节范围: {start}-{end}")

    # 等待完成（阻塞轮询）
    try:
        import time
        while True:
            status = orch.get_project_status(project_id)
            if not status:
                print("项目状态丢失，终止等待")
                return 1
            if status["status"] in ("completed", "error", "paused"):
                print(f"\nPipeline 结束: status={status['status']}, chapter={status['current_chapter']}")
                stats = orch.get_global_stats()
                print(f"全局统计: {stats}")
                return 0 if status["status"] == "completed" else 1
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n收到中断信号，暂停 Pipeline...")
        orch.pause_pipeline(project_id)
        print(f"已暂停在章节 {orch.get_project_status(project_id)['current_chapter']}")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="novel-os",
        description="Novel-OS: AI 长篇小说写作系统",
    )
    parser.add_argument("--book", required=True, help="book.yaml 路径")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="初始化状态库")
    p_init.add_argument("--outline", help="[兼容旧版] 大纲 JSON 路径")
    p_init.add_argument("--data", help="[推荐] 数据文件路径 (book_data.py)，包含 OUTLINE/CHARACTERS/DEBTS 等")
    p_init.add_argument("--import-chapters", action="store_true", help="同时导入 chapters/ 目录下已有的章节文件")
    p_init.add_argument("--force", action="store_true", help="覆盖已存在的章节记录（配合 --import-chapters）")
    p_init.add_argument("--dry-run", action="store_true", help="只打印，不写入数据库")
    p_init.set_defaults(func=cmd_init)

    # write
    p_write = sub.add_parser("write", help="写作章节")
    p_write.add_argument("--chapter", type=int, help="单章编号")
    p_write.add_argument("--range", help="范围，如 1:10")
    p_write.add_argument("--resume", action="store_true", help="断点续传")
    p_write.set_defaults(func=cmd_write)

    # state
    p_state = sub.add_parser("state", help="状态库操作")
    p_state.add_argument("--export", help="导出 JSON 视图路径")
    p_state.add_argument("--rollback", help="回滚快照，格式: chapter,type")
    p_state.set_defaults(func=cmd_state)

    # pipeline（通过 Orchestrator 双层调度）
    p_pipeline = sub.add_parser("pipeline", help="通过 Orchestrator 双层调度批量写作（支持暂停/恢复/外层巡检）")
    p_pipeline.add_argument("--range", help="范围，如 1:30")
    p_pipeline.add_argument("--resume", action="store_true", help="断点续传")
    p_pipeline.set_defaults(func=cmd_pipeline)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
