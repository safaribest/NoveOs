#!/usr/bin/env python3
"""
全自动持续写作系统 v2.1

设计目标：
- 持续：从第1章写到第200章，无人值守
- 全自动：质量检查、失败重试、批量审阅全部自动化
- 高效：预算控制在10-20元（约0.05-0.10元/章）
- 有限容忍：每章最多3次重试，仍不达标标记为"待精修"并继续

v2.1 改进：
- 修复子进程误判：增加 stdout/stderr 日志、文件生成兜底、超时控制
- 子进程调用使用项目根目录作为 cwd，并显式设置 PYTHONPATH
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════
PROJECT_NAME = "村超系统：我带侗寨球队踢爆世界杯"
PROJECT_DIR = Path("books") / PROJECT_NAME
BOOK_YAML = PROJECT_DIR / "book.yaml"
CHAPTERS_DIR = PROJECT_DIR / "chapters"
LOG_FILE = Path("logs/auto_write.log")
SUBPROCESS_LOG = Path("logs/auto_write_subprocess.log")

MAX_RETRIES = 3          # 每章最大重试次数
TARGET_START = 1         # 起始章节
TARGET_END = 200         # 结束章节
_FORCE_START: int | None = None  # 命令行 --start 覆盖值
BATCH_REVIEW_EVERY = 5   # 每5章批量审阅
COOLDOWN_SECONDS = 8     # 每章冷却（避免API限流）
MIN_WORDS = 1900         # 字数下限
MAX_WORDS = 2600         # 字数上限
SUBPROCESS_TIMEOUT = 600 # 单章子进程超时（秒）

ROOT_DIR = Path("D:/noveos")
CLI_PATH = ROOT_DIR / "novel-os" / "cli.py"

# 禁用词表（从 book_data.py 的 RULES 提取）
FORBIDDEN_WORDS = [
    "首先", "其次", "最后", "综上所述", "值得注意的是", "说白了",
    "过了一会儿", "不久之后", "几天后", "数月后", "数年后",
    "愤怒", "绝望", "兴奋", "悲伤", "开心",
    "反越位", "肋部穿插", "高位逼抢",  # 足球专业术语
]

# ═══════════════════════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════════════════════

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_subprocess(ch: int, attempt: int, returncode: int, stdout: str, stderr: str):
    """记录子进程完整输出，便于排查误判。"""
    SUBPROCESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SUBPROCESS_LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"第{ch}章 | 第{attempt}次 | returncode={returncode} | {datetime.now()}\n")
        f.write(f"--- STDOUT ---\n{stdout}\n")
        f.write(f"--- STDERR ---\n{stderr}\n")


# ═══════════════════════════════════════════════════════════
# 本地质量检查（零API成本）
# ═══════════════════════════════════════════════════════════

def get_word_count(file_path: Path) -> int:
    """计算中文字数（去除标题行）"""
    content = file_path.read_text(encoding="utf-8")
    lines = content.strip().splitlines()
    # 去掉前2行（标题+空行）
    body = "\n".join(lines[2:] if len(lines) > 2 else lines)
    return len([c for c in body if "\u4e00" <= c <= "\u9fff"])


def check_chapter(ch: int) -> dict:
    """本地检查：字数 + 禁用词 + 文件存在性"""
    files = list(CHAPTERS_DIR.glob(f"第{ch:03d}章_*.txt"))
    if not files:
        return {"ok": False, "reason": "文件未生成", "word_count": 0, "violations": []}

    # 如果存在多个文件，取最新修改的
    file_path = max(files, key=lambda p: p.stat().st_mtime)
    content = file_path.read_text(encoding="utf-8")
    wc = get_word_count(file_path)

    # 禁用词检查
    violations = [w for w in FORBIDDEN_WORDS if w in content]

    issues = []
    if wc < MIN_WORDS:
        issues.append(f"字数不足({wc})")
    if wc > MAX_WORDS:
        issues.append(f"字数超标({wc})")
    if violations:
        issues.append(f"禁用词{len(violations)}处")

    return {
        "ok": len(issues) == 0,
        "reason": "; ".join(issues) if issues else "通过",
        "word_count": wc,
        "violations": violations,
        "file": file_path,
    }


# ═══════════════════════════════════════════════════════════
# 批量审阅（每5章，本地规则）
# ═══════════════════════════════════════════════════════════

def review_batch(chapters: list[int]) -> dict:
    """审阅最近N章，返回是否通过及建议"""
    wcs = []
    for ch in chapters:
        files = list(CHAPTERS_DIR.glob(f"第{ch:03d}章_*.txt"))
        if files:
            wcs.append(get_word_count(max(files, key=lambda p: p.stat().st_mtime)))

    if not wcs:
        return {"ok": True, "issues": [], "suggestion": ""}

    issues = []
    avg_wc = sum(wcs) / len(wcs)
    max_diff = max(wcs) - min(wcs)

    if max_diff > 600:
        issues.append(f"字数波动过大({min(wcs)}-{max(wcs)})")
    if avg_wc < 2000:
        issues.append(f"平均字数偏低({avg_wc:.0f})")

    # 检查是否有连续失败章
    failed_chapters = [ch for ch in chapters if not check_chapter(ch)["ok"]]
    if len(failed_chapters) >= 2:
        issues.append(f"连续{len(failed_chapters)}章未达标")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "suggestion": "建议调整Writer温度或提示词以稳定字数" if issues else "",
        "stats": {"avg": avg_wc, "min": min(wcs), "max": max(wcs)},
    }


# ═══════════════════════════════════════════════════════════
# 核心：写一章
# ═══════════════════════════════════════════════════════════

def write_chapter(ch: int, attempt: int = 1) -> bool:
    """调用 cli.py 写单章，返回是否应继续检查文件。"""
    env = os.environ.copy()
    # 确保子进程能找到项目模块
    env["PYTHONPATH"] = str(ROOT_DIR / "novel-os") + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        sys.executable,
        str(CLI_PATH),
        "--book", str(BOOK_YAML),
        "write", "--chapter", str(ch),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(ROOT_DIR),
            encoding="utf-8",
            errors="replace",
            timeout=SUBPROCESS_TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        log_subprocess(ch, attempt, -1, exc.stdout or "", exc.stderr or "")
        log(f"  子进程超时（>{SUBPROCESS_TIMEOUT}秒）")
        return False
    except Exception as exc:
        log_subprocess(ch, attempt, -1, "", str(exc))
        log(f"  子进程异常：{exc}")
        return False

    log_subprocess(ch, attempt, result.returncode, result.stdout, result.stderr)

    # v2.1 关键修复：即使 returncode != 0，也要检查文件是否实际生成
    # 因为 cli.py 可能打印了 WARNING（exit 0）或某些非致命错误（exit 1）但文件已写出
    if result.returncode != 0:
        # 记录关键错误信息到主日志
        err_summary = (result.stderr or result.stdout or "").strip()[:200]
        log(f"  cli.py returncode={result.returncode}， stderr/stdout: {err_summary}")

    return True


def rollback_chapter(ch: int):
    """删除文件，用于重试前清理"""
    for f in CHAPTERS_DIR.glob(f"第{ch:03d}章_*.txt"):
        f.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════
# 主循环
# ═══════════════════════════════════════════════════════════

def main():
    # 自动检测已有章节，从下一个开始（若未强制指定起始）
    existing = sorted([int(f.stem[1:4]) for f in CHAPTERS_DIR.glob("第*.txt") if f.stem[1:4].isdigit()])
    if _FORCE_START is not None:
        actual_start = _FORCE_START
    else:
        actual_start = (existing[-1] + 1) if existing else TARGET_START

    log("=" * 60)
    log("全自动持续写作系统 v2.1 启动")
    log(f"已检测到{len(existing)}章，从第{actual_start}章继续")
    log(f"目标：第{actual_start}-{TARGET_END}章")
    log(f"策略：每章最多{MAX_RETRIES}次重试，每{BATCH_REVIEW_EVERY}章批量审阅")
    log(f"预算：10-20元（复用现有Pipeline，本地规则替代LLM审计）")
    log("=" * 60)

    stats = {"success": 0, "retry": 0, "failed": 0}
    start_time = time.time()

    for ch in range(actual_start, TARGET_END + 1):
        log(f"\n{'─' * 40}")
        log(f"第{ch}章")

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                log(f"  第{attempt}次尝试...")
                stats["retry"] += 1
                rollback_chapter(ch)
                time.sleep(3)

            # 调用 cli.py
            if not write_chapter(ch, attempt):
                # 子进程自身出错（超时/异常）
                continue

            # 本地质量检查（v2.1：这是成功与否的最终标准）
            check = check_chapter(ch)
            if check["ok"]:
                log(f"  通过 | {check['word_count']}字 | {check['file'].name}")
                success = True
                stats["success"] += 1
                break
            else:
                log(f"  未通过 | {check['reason']} | {check['word_count']}字")
                if attempt == MAX_RETRIES:
                    log(f"  已达最大重试次数，标记为【待精修】")
                    stats["failed"] += 1

        # 冷却
        time.sleep(COOLDOWN_SECONDS)

        # 批量审阅
        if ch % BATCH_REVIEW_EVERY == 0:
            recent = list(range(ch - BATCH_REVIEW_EVERY + 1, ch + 1))
            log(f"\n  >>> 批量审阅 第{recent[0]}-{recent[-1]}章")
            review = review_batch(recent)
            st = review["stats"]
            log(f"      字数: avg={st['avg']:.0f} min={st['min']} max={st['max']}")
            if review["ok"]:
                log(f"      审阅通过")
            else:
                log(f"      发现问题: {review['issues']}")
                log(f"      建议: {review['suggestion']}")

    # 结算
    elapsed = time.time() - start_time
    log("\n" + "=" * 60)
    log("写作完成")
    log(f"统计: 成功{stats['success']}章 | 重试{stats['retry']}次 | 待精修{stats['failed']}章")
    log(f"耗时: {elapsed/60:.1f}分钟 ({elapsed/3600:.2f}小时)")
    log(f"预估成本: 约2-5元（取决于重试次数）")
    log("=" * 60)


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="全自动持续写作系统 v2.1")
    parser.add_argument("--start", type=int, default=None, help="起始章节（默认自动检测）")
    parser.add_argument("--end", type=int, default=TARGET_END, help=f"结束章节（默认{TARGET_END}）")
    parser.add_argument("--limit", type=int, default=None, help="最多写N章后停止")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.start is not None:
        _FORCE_START = args.start
        TARGET_START = args.start
    if args.end is not None:
        TARGET_END = args.end
    if args.limit is not None:
        start = _FORCE_START if _FORCE_START is not None else TARGET_START
        TARGET_END = start + args.limit - 1
    main()
