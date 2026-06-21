import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.main import orchestrator

# 字数统计：优先使用 core 实现，缺失时回退兜底
try:
    from core.content.metrics import count_chinese_chars
except Exception:

    def count_chinese_chars(text: str) -> int:
        return len([c for c in text if "\u4e00" <= c <= "\u9fff"])


router = APIRouter()


class SaveContentRequest(BaseModel):
    content: str


def _find_chapter_path(base_path: Path, chapter_num: int) -> Path | None:
    """查找章节文件路径。

    只保留标准格式 chapter_{num:03d}.md；同时兼容旧格式 第{num}章_*.txt 用于迁移。
    """
    output_dir = base_path / "chapters"
    if not output_dir.exists():
        return None

    # 1. 标准格式
    standard_path = output_dir / f"chapter_{chapter_num:03d}.md"
    if standard_path.exists():
        return standard_path

    # 2. 旧格式兼容（迁移用）
    for f in output_dir.iterdir():
        if not f.is_file():
            continue
        if f.name.startswith(f"第{chapter_num:03d}章") and f.name.endswith(".txt"):
            return f
    return None


@router.get("/projects/{project_id}/chapters")
async def list_chapters(project_id: str):
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    state = orchestrator.get_state_manager(project_id)
    if not state:
        raise HTTPException(status_code=404, detail="状态库不可用")

    base_path = Path(status["base_path"])
    chapters_dir = base_path / "chapters"

    chapters = []
    # 1. 优先从 state_manager 读取章节元数据
    state_chapters = state.list_chapters()
    state_chapter_map = {ch["chapter"]: ch for ch in state_chapters}

    # 2. 扫描 chapters 目录下的标准格式文件
    if chapters_dir.exists():
        for file_path in chapters_dir.iterdir():
            if not file_path.is_file():
                continue

            # 只识别 chapter_001.md 格式
            match = re.match(r"chapter_(\d+)\.md$", file_path.name)
            if not match:
                continue

            chapter_num = int(match.group(1))
            state_ch = state_chapter_map.get(chapter_num, {})
            word_count = state_ch.get("word_count")
            if word_count is None:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    word_count = count_chinese_chars(content)
                except Exception:
                    word_count = 0

            chapters.append(
                {
                    "chapter_num": chapter_num,
                    "title": state_ch.get("title"),
                    "summary": state_ch.get("summary"),
                    "word_count": word_count,
                    "mode": state_ch.get("mode"),
                    "created_at": state_ch.get("created_at"),
                    "filename": file_path.name,
                }
            )

    # 3. 补充 state 中有但文件未扫描到的章节
    existing_nums = {ch["chapter_num"] for ch in chapters}
    for ch in state_chapters:
        num = ch["chapter"]
        if num not in existing_nums:
            chapters.append(
                {
                    "chapter_num": num,
                    "title": ch.get("title"),
                    "summary": ch.get("summary"),
                    "word_count": ch.get("word_count", 0),
                    "mode": ch.get("mode"),
                    "created_at": ch.get("created_at"),
                    "filename": None,
                }
            )

    chapters.sort(key=lambda x: x["chapter_num"])
    return {"code": 200, "data": chapters}


@router.get("/projects/{project_id}/chapters/{chapter_num}")
async def get_chapter(project_id: str, chapter_num: int):
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    state = orchestrator.get_state_manager(project_id)
    if not state:
        raise HTTPException(status_code=404, detail="状态库不可用")

    # 从 state_manager 读取章节元数据
    chapters = state.list_chapters()
    for ch in chapters:
        if ch["chapter"] == chapter_num:
            return {"code": 200, "data": ch}
    return {"code": 200, "data": {}}


@router.get("/projects/{project_id}/chapters/{chapter_num}/content")
async def get_chapter_content(project_id: str, chapter_num: int):
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    base_path = Path(status["base_path"])
    path = _find_chapter_path(base_path, chapter_num)
    content = path.read_text(encoding="utf-8") if path else ""
    return {"code": 200, "data": {"content": content}}


@router.put("/projects/{project_id}/chapters/{chapter_num}/content")
async def save_chapter_content(
    project_id: str, chapter_num: int, req: SaveContentRequest
):
    if chapter_num <= 0:
        raise HTTPException(status_code=422, detail="章节号必须大于 0")

    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    base_path = Path(status["base_path"])
    chapters_dir = base_path / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    # 保存统一使用标准格式，读取才兼容旧格式
    path = chapters_dir / f"chapter_{chapter_num:03d}.md"

    path.write_text(req.content, encoding="utf-8")

    word_count = count_chinese_chars(req.content)

    # 同步更新 state_manager 中的字数统计
    state = orchestrator.get_state_manager(project_id)
    if state:
        try:
            existing = next(
                (ch for ch in state.list_chapters() if ch.get("chapter") == chapter_num),
                None,
            )
            state.update_after_chapter(
                chapter_num=chapter_num,
                summary=existing.get("summary", "") if existing else "",
                word_count=word_count,
                mode=existing.get("mode", "") if existing else "",
                title=existing.get("title", "") if existing else "",
            )
        except Exception:
            pass

    return {
        "code": 200,
        "data": {
            "saved": True,
            "path": str(path),
            "word_count": word_count,
        },
    }


@router.get("/projects/{project_id}/chapters/{chapter_num}/quality")
async def get_chapter_quality_gate(project_id: str, chapter_num: int):
    """返回单章质量门禁面板所需的真实审计维度与聚合分。"""
    status = orchestrator.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail="项目不存在")

    state = orchestrator.get_state_manager(project_id)
    if not state:
        raise HTTPException(status_code=404, detail="状态库不可用")

    rows = state.get_chapter_metrics(chapter_num)
    metrics = rows[0] if rows else {}
    genre_dna = state.get_genre_dna()
    dimensions, aggregate = _compute_quality_gate(metrics, genre_dna)

    return {
        "code": 200,
        "data": {
            "chapter_num": chapter_num,
            "reader_pull_score": metrics.get("reader_pull_score"),
            "quality_passed": metrics.get("quality_passed"),
            "gate_level": metrics.get("gate_level"),
            "aggregate_score": aggregate,
            "dimensions": dimensions,
        },
    }


def _compute_quality_gate(
    metrics: dict, genre_dna: dict
) -> tuple[list[dict[str, int | None]], int | None]:
    """根据章节真实指标计算质量门禁五维分数。

    五维定义：
    - 情节完整性：基于 genre_dna_match / platform_score
    - 文笔流畅度：基于平均句长与品类 DNA 目标句长的偏离
    - 人设一致性：暂以门禁等级推导（PASS/WARN/BLOCK），无历史数据时占位
    - 爽点密度：基于微张力振荡次数 oscillations
    - 合规质检：基于 quality_passed / 禁用词命中
    """
    if not metrics:
        return [
            {"label": "情节完整性", "value": None},
            {"label": "文笔流畅度", "value": None},
            {"label": "人设一致性", "value": None},
            {"label": "爽点密度", "value": None},
            {"label": "合规质检", "value": None},
        ], None

    # 1. 情节完整性：优先使用 DNA 匹配度，回退平台适配分
    dna_match = metrics.get("genre_dna_match")
    platform_score = metrics.get("platform_score")
    raw_plot = dna_match if isinstance(dna_match, (int, float)) else platform_score
    plot_integrity = (
        int(round(max(0.0, min(1.0, float(raw_plot))) * 100))
        if isinstance(raw_plot, (int, float)) and raw_plot is not None
        else None
    )

    # 2. 文笔流畅度：句长越接近 DNA 目标越高分
    sentence_length = metrics.get("sentence_length")
    target_sent_len = genre_dna.get("target_sent_len") if genre_dna else None
    if isinstance(sentence_length, (int, float)) and sentence_length:
        target = target_sent_len or 25
        deviation = abs(float(sentence_length) - target) / target
        language_fluency = int(round(max(0.0, min(1.0, 1.0 - deviation) * 100)))
    else:
        language_fluency = None

    # 3. 人设一致性：直接测量数据尚缺，以门禁等级推导
    gate_level = metrics.get("gate_level")
    if gate_level == "PASS":
        character_consistency = 95
    elif gate_level == "WARN":
        character_consistency = 80
    elif gate_level == "BLOCKING":
        character_consistency = 55
    else:
        character_consistency = 85

    # 4. 爽点密度：基于微张力振荡次数
    oscillations = metrics.get("oscillations")
    if isinstance(oscillations, (int, float)) and oscillations is not None:
        cool_point_density = int(round(max(0.0, min(100.0, 60 + float(oscillations) * 4))))
    else:
        cool_point_density = None

    # 5. 合规质检：基于 quality_passed / 禁用词
    quality_passed = metrics.get("quality_passed")
    audit_report = metrics.get("audit_report") or {}
    forbidden_count = len(audit_report.get("forbidden_words", []))
    if quality_passed is True:
        compliance_score = 100
    elif quality_passed is False:
        compliance_score = max(0, 100 - forbidden_count * 10)
    else:
        compliance_score = None

    dimensions = [
        {"label": "情节完整性", "value": plot_integrity},
        {"label": "文笔流畅度", "value": language_fluency},
        {"label": "人设一致性", "value": character_consistency},
        {"label": "爽点密度", "value": cool_point_density},
        {"label": "合规质检", "value": compliance_score},
    ]

    valid_values = [d["value"] for d in dimensions if isinstance(d["value"], int)]
    aggregate = int(round(sum(valid_values) / len(valid_values))) if valid_values else None
    return dimensions, aggregate
