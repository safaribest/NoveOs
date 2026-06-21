#!/usr/bin/env python3
"""全面检查前端状态和 API 可用性"""
import json
import urllib.request
from pathlib import Path

BASE = "http://localhost:3000"
PROJECT = "村超系统：我带侗寨球队踢爆世界杯"

def fetch(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

def check():
    report = ["=" * 50, "前端全面检查报告", "=" * 50]

    # 1. 首页
    try:
        with urllib.request.urlopen(f"{BASE}/", timeout=5) as r:
            html = r.read().decode("utf-8")
            ok = "墨斋 — Novel-OS" in html
            report.append(f"\n[首页] {'OK' if ok else 'FAIL'} 标题: {'墨斋 - Novel-OS' if ok else '不匹配'}")
    except Exception as e:
        report.append(f"\n[首页] FAIL 无法访问: {e}")
        return "\n".join(report)

    # 2. 项目列表
    projects = fetch(f"{BASE}/local-api/projects")
    if "error" in projects:
        report.append(f"[项目列表] FAIL {projects['error']}")
    else:
        data = projects.get("data", [])
        report.append(f"[项目列表] OK 共{len(data)}个项目")
        for p in data:
            report.append(f"  - {p['project_id']}: {p['total_chapters']}章 ({p['status']})")

    # 3. 章节列表
    chapters = fetch(f"{BASE}/local-api/projects/{urllib.parse.quote(PROJECT)}/chapters")
    if "error" in chapters:
        report.append(f"[章节列表] FAIL {chapters['error']}")
    else:
        data = chapters.get("data", [])
        report.append(f"[章节列表] OK 共{len(data)}章")
        for ch in data[:5]:
            report.append(f"  第{ch['chapter_num']}章: {ch['word_count']}字  {ch['title']}")
        if len(data) > 5:
            report.append(f"  ... 还有{len(data)-5}章")

    # 4. 单章内容
    if data:
        ch1 = data[0]
        content = fetch(f"{BASE}/local-api/projects/{urllib.parse.quote(PROJECT)}/chapters/{ch1['chapter_num']}")
        if "error" in content:
            report.append(f"[单章内容] FAIL {content['error']}")
        else:
            cdata = content.get("data", {})
            text = cdata.get("content", "")[:100]
            report.append(f"[单章内容] OK 第{ch1['chapter_num']}章, 内容预览: {text[:80]}...")

    # 5. 检查自动写作进度（文件系统）
    chapters_dir = Path(f"books/{PROJECT}/chapters")
    files = sorted(chapters_dir.glob("第*.txt")) if chapters_dir.exists() else []
    report.append(f"\n[写作进度] 文件系统共{len(files)}个章节文件")
    for f in files[:5]:
        wc = len([c for c in f.read_text(encoding="utf-8") if "\u4e00" <= c <= "\u9fff"])
        report.append(f"  {f.name}: {wc}字")

    # 6. 检查后台任务日志
    log_file = Path("logs/auto_write.log")
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        report.append(f"\n[自动写作日志] 共{len(lines)}行")
        for line in lines[-5:]:
            report.append(f"  {line}")
    else:
        report.append(f"\n[自动写作日志] 暂无日志文件")

    report.append("\n" + "=" * 50)
    output = "\n".join(report)
    Path("logs/frontend_check_report.txt").write_text(output, encoding="utf-8")
    print(output)

if __name__ == "__main__":
    import urllib.parse
    check()
