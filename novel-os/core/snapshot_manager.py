"""Novel-OS 快照管理器 —— 细粒度版本控制与回滚。

对 StateManager 的快照功能做高层封装，支持：
- 写前自动快照（pre-write）
- 写后确认快照（post-write）
- 按标签回滚（rollback）
- 差异对比（diff）
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.state_manager import StateManager


@dataclass
class SnapshotMeta:
    """快照元信息。"""
    id: int
    chapter: int
    snapshot_type: str
    created_at: datetime


class SnapshotManager:
    """快照管理高层 API。"""

    def __init__(self, state_manager: StateManager) -> None:
        self.state = state_manager

    def pre_write(self, chapter: int) -> SnapshotMeta:
        """写章节前自动打快照，标签为 'pre_write'。"""
        data = self._export_current_state()
        self.state.create_snapshot(chapter, "pre_write", data)
        # 获取刚插入的快照元信息（简化：直接返回模拟 meta）
        return SnapshotMeta(id=0, chapter=chapter, snapshot_type="pre_write", created_at=datetime.now())

    def post_write(self, chapter: int, chapter_content: str, audit_report: dict[str, Any]) -> SnapshotMeta:
        """写章节后确认快照，标签为 'post_write'。"""
        data = {
            "state": self._export_current_state(),
            "content_preview": chapter_content[:500],
            "audit": audit_report,
        }
        self.state.create_snapshot(chapter, "post_write", data)
        return SnapshotMeta(id=0, chapter=chapter, snapshot_type="post_write", created_at=datetime.now())

    def rollback(self, chapter: int, snapshot_type: str = "pre_write") -> dict[str, Any]:
        """回滚到指定章节的最新快照。"""
        return self.state.rollback_to_snapshot(chapter, snapshot_type)

    def diff(self, chapter: int, type_a: str, type_b: str) -> dict[str, Any]:
        """对比同一章节的两种快照差异（简化版）。"""
        snap_a = self.state.rollback_to_snapshot(chapter, type_a)
        snap_b = self.state.rollback_to_snapshot(chapter, type_b)
        return {
            "chapter": chapter,
            "type_a": type_a,
            "type_b": type_b,
            "keys_only_in_a": list(set(snap_a.keys()) - set(snap_b.keys())),
            "keys_only_in_b": list(set(snap_b.keys()) - set(snap_a.keys())),
        }

    def _export_current_state(self) -> dict[str, Any]:
        """导出当前全部 SQLite 状态为字典。"""
        # 复用 StateManager 的 JSON 视图逻辑
        tmp_path = Path("__tmp_snapshot.json")
        self.state.export_json_view(tmp_path)
        data = json.loads(tmp_path.read_text(encoding="utf-8"))
        tmp_path.unlink(missing_ok=True)
        return data
