"""Phase 2 Prompt 注入层临时验收测试。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

from core.config_loader import BookConfig
from core.writing.prompts import build_task_user_prompt, map_genre_to_course_key


def make_book(genre: str) -> BookConfig:
    base = Path(tempfile.mkdtemp(prefix="novel_os_phase2_test_"))
    os.environ["NOVEL_BASE_PATH"] = str(base)
    project_dir = base / "test_book"
    project_dir.mkdir(parents=True, exist_ok=True)
    book_path = project_dir / "book.yaml"
    data = {
        "project": "Phase2Test",
        "platform": "fanqie_novel",
        "genre": genre,
        "target_tier": "A",
        "total_words_target": 100000,
        "chapters_target": 100,
        "words_per_chapter": 4500,
        "base_path": str(project_dir),
        "output_dir": "chapters",
        "agent_query": {
            "writer": {
                "role": "测试写手",
                "description": "创作第{chapter_number}章正文。",
                "expected_output": "章节正文",
            },
            "director": {
                "role": "测试导演",
                "description": "检查第{chapter_number}章。",
                "expected_output": "审阅意见",
            },
        },
        "writing": {"tolerance": 450},
    }
    book_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return BookConfig.from_yaml(book_path)


def main() -> None:
    cfg = make_book("年代商战")
    prompt1 = build_task_user_prompt(cfg, "writer", 1)
    assert "番茄官方" in prompt1, "writer 第1章应出现番茄官方标识"
    assert "【番茄官方·开篇铁律（第1章）】" in prompt1, "writer 第1章应注入开篇铁律"
    assert "前 300 字必须让主角出场" in prompt1, "应读取 max_lead_in_words"
    assert "禁止大段世界观铺陈、群像缓慢登场、抒情回忆" in prompt1, "应读取 forbidden_patterns"
    assert "【番茄官方·章节节奏铁律】" in prompt1, "应注入章节节奏铁律"
    assert "章节最后 200 字" in prompt1, "应读取 ending_hook_zone"
    assert "对话占比控制在 25%-45%" in prompt1, "应读取 dialogue ratio_range"
    assert "本章及后续章节建议情绪配比：爽50% / 甜20% / 平20% / 虐10%" in prompt1, "年代商战情绪配比错误"

    prompt10 = build_task_user_prompt(cfg, "writer", 10)
    assert "番茄官方" in prompt10, "writer 第10章仍应出现番茄官方标识"
    assert "【番茄官方·开篇铁律" not in prompt10, "writer 第10章不应注入开篇铁律"
    assert "【番茄官方·章节节奏铁律】" in prompt10, "writer 第10章仍应注入章节节奏铁律"

    prompt_dir = build_task_user_prompt(cfg, "director", 1)
    assert "番茄官方" not in prompt_dir, "非 writer agent 不应注入番茄规则"

    cfg2 = make_book("甜宠")
    prompt_sweet = build_task_user_prompt(cfg2, "writer", 1)
    assert "本章及后续章节建议情绪配比：爽25% / 甜55% / 平15% / 虐5%" in prompt_sweet, "甜宠情绪配比错误"

    cfg3 = make_book("未知品类")
    prompt_default = build_task_user_prompt(cfg3, "writer", 1)
    assert "本章及后续章节建议情绪配比：爽35% / 甜25% / 平25% / 虐15%" in prompt_default, "未知 genre 应使用默认情绪配比"

    assert map_genre_to_course_key("都市异能") == "male_dushi_yineng"
    assert map_genre_to_course_key("不存在") == "default"

    print("[PASS] Phase 2 prompt 注入层验收测试全部通过")
    print("\n--- 第1章注入片段示例 ---")
    start = prompt1.find("【番茄官方·开篇铁律")
    print(prompt1[start : start + 700])


if __name__ == "__main__":
    main()
