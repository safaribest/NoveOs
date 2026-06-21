"""状态域领域模型 —— 纯数据结构，无业务逻辑。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ProjectInfo:
    project_id: str
    name: str
    genre: str
    platform: str
    base_path: str
    total_chapters: int
    status: str = "pending"
    current_chapter: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ChapterOutline:
    """单章大纲。"""

    chapter: int
    arc: str = ""
    core_event: str = ""
    face_slap_target: str = ""
    face_slap_method: str = ""
    husband_moment: str = ""
    chapter_hook: str = ""
    emotion_ratio: str = ""
    skill_unlocked: str = ""
    questions: str = ""
    reveal_at: int | None = None
    beat_pattern: str = ""


@dataclass
class CharacterState:
    """人物状态。"""

    name: str
    chapter: int
    location: str = ""
    emotional_state: str = ""
    known_secrets: str = ""
    unknown_secrets: str = ""
    abilities_active: str = ""
    abilities_locked: str = ""
    dialog_fingerprint: str = ""
    body_language: str = ""
    physical_description: str = ""


@dataclass
class Debt:
    """悬念债务。"""

    debt_id: str
    type: str
    content: str
    bury_chapter: int
    collect_chapter: int | None = None
    status: str = "active"  # active / collected / abandoned


@dataclass
class Foreshadowing:
    """伏笔。"""

    fs_id: str
    content: str
    bury_chapter: int
    collect_chapter: str = ""
    type: str = ""
    status: str = "active"


@dataclass
class ChapterHistory:
    """已写章节记录。"""

    chapter: int
    title: str = ""
    summary: str = ""
    word_count: int = 0
    mode: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ItemState:
    """道具/关键物品状态。"""

    item_name: str
    chapter: int
    location: str = ""
    state: str = ""
    rule: str = ""
    state_history: str = ""


@dataclass
class CastSchedule:
    """配角出场调度。"""

    character_name: str
    chapter: int
    must_appear: bool = False
    role_evolution: str = ""
    dialog_fingerprint: str = ""
    physical_description: str = ""


@dataclass
class RuntimeLog:
    """运行日志。"""

    log_id: str
    level: str
    agent: str
    message: str
    chapter_num: int | None = None
    metadata: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class EmotionHistory:
    """情感坐标历史。"""

    chapter: int
    mode: str = ""
    nue_density: float = 0.0
    tian_density: float = 0.0
    shuang_density: float = 0.0
    coordinate_x: float = 0.0
    coordinate_y: float = 0.0
    desc: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ConsistencyRule:
    """跨章一致性约束。"""

    rule_type: str
    rule_content: str
    enforcement_level: str = "hard"  # hard / soft / info


@dataclass
class ChapterSnapshot:
    """章节快照。"""

    id: int
    chapter: int
    snapshot_type: str
    snapshot_data: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
