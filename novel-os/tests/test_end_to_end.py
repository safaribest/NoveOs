"""Novel-OS 端到端集成测试。

使用《重生七八：老娘要搞钱》的简化数据，验证核心流程。
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from core.config_loader import BookConfig
from core.state_manager import StateManager


class TestEndToEnd(unittest.TestCase):
    """端到端测试：从大纲初始化 → 状态查询 → JSON 导出。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp_dir = Path(tempfile.mkdtemp(prefix="novel-os-test-"))
        cls.db_path = cls.tmp_dir / "test_world_state.db"

    @classmethod
    def tearDownClass(cls) -> None:
        # 清理临时文件
        import shutil
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def setUp(self) -> None:
        self.state = StateManager(self.db_path)
        self.outline = {
            "meta": {
                "project": "重生七八：老娘要搞钱",
                "platform": "fanqie_novel",
                "genre": "era_biz",
                "chapters_target": 5,
            },
            "characters": {
                "protagonist_female": {
                    "name": "沈若楠",
                    "a_track": {
                        "identity": "重生者，18岁外表59岁灵魂",
                        "ability": "前世商业经验",
                    },
                    "b_track": {"essence": "害怕被遗忘的女孩"},
                }
            },
            "world": {
                "locks": [
                    "1978年11月不能用改革开放",
                    "空间只能储物",
                ],
                "key_items": [
                    {"name": "翡翠戒指", "initial_location": "左手中指", "initial_state": "激活"}
                ],
            },
            "plot": {
                "debts": [
                    {"id": "D1", "bury_chapter": 1, "collect_chapter": 3, "content": "拒婚如何善后"}
                ],
                "foreshadowing": [
                    {
                        "id": "F1",
                        "bury_chapter": 1,
                        "collect_chapter": "3/10",
                        "content": "王建国不能生",
                    }
                ],
                "chapter_beats": [
                    {
                        "chapter": 1,
                        "mode": "紧",
                        "beat_1": {"plot": "拒婚"},
                        "beat_4": {"cliffhanger": True},
                    }
                ],
            },
        }

    def test_01_init_from_outline(self) -> None:
        """测试：从大纲初始化后，各表是否有数据。"""
        self.state.init_from_outline(self.outline)

        # 验证人物状态
        char_state = self.state.get_character_state(0, "沈若楠")
        self.assertEqual(char_state.get("character_name"), "沈若楠")

        # 验证道具状态
        # item_states 查询需通过底层或新增方法；这里直接导出视图验证
        export_path = self.tmp_dir / "view.json"
        self.state.export_json_view(export_path)
        view = json.loads(export_path.read_text(encoding="utf-8"))

        self.assertIn("沈若楠", view["characters"])
        self.assertIn("翡翠戒指", view["items"])
        self.assertEqual(len(view["debts"]), 1)
        self.assertEqual(len(view["foreshadowing"]), 1)

    def test_02_get_active_debts(self) -> None:
        """测试：get_active_debts(3) 应返回 D1。"""
        self.state.init_from_outline(self.outline)
        debts = self.state.get_active_debts(3)
        self.assertEqual(len(debts), 1)
        self.assertEqual(debts[0]["debt_id"], "D1")
        self.assertEqual(debts[0]["content"], "拒婚如何善后")

    def test_03_get_active_foreshadowing(self) -> None:
        """测试：get_active_foreshadowing 应返回 F1。"""
        self.state.init_from_outline(self.outline)
        fss = self.state.get_active_foreshadowing(3)
        self.assertEqual(len(fss), 1)
        self.assertEqual(fss[0]["fs_id"], "F1")

    def test_04_export_json_view(self) -> None:
        """测试：export_json_view 生成有效 JSON。"""
        self.state.init_from_outline(self.outline)
        export_path = self.tmp_dir / "view2.json"
        self.state.export_json_view(export_path)

        self.assertTrue(export_path.exists())
        data = json.loads(export_path.read_text(encoding="utf-8"))
        self.assertIn("exported_at", data)
        self.assertIn("characters", data)
        self.assertIn("items", data)
        self.assertIn("debts", data)
        self.assertIn("foreshadowing", data)
        self.assertIn("chapter_history", data)

    def test_05_chapter_history(self) -> None:
        """测试：update_after_chapter 后 chapter_history 有记录。"""
        self.state.init_from_outline(self.outline)
        self.state.update_after_chapter(
            chapter_num=1, summary="沈若楠拒婚，冲突爆发", word_count=4500, mode="紧"
        )
        export_path = self.tmp_dir / "view3.json"
        self.state.export_json_view(export_path)
        data = json.loads(export_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["chapter_history"]), 1)
        self.assertEqual(data["chapter_history"][0]["chapter"], 1)
        self.assertEqual(data["chapter_history"][0]["word_count"], 4500)

    def test_06_character_update(self) -> None:
        """测试：update_character_state 增量更新。"""
        self.state.init_from_outline(self.outline)
        self.state.update_character_state(
            1, "沈若楠", location="公社大院", emotional_state="愤怒"
        )
        state = self.state.get_character_state(1, "沈若楠")
        self.assertEqual(state.get("location"), "公社大院")
        self.assertEqual(state.get("emotional_state"), "愤怒")

    def test_07_snapshot_and_rollback(self) -> None:
        """测试：快照创建与回滚。"""
        self.state.init_from_outline(self.outline)
        snap_data = {"test": "snapshot_1"}
        self.state.create_snapshot(1, "test", snap_data)
        rolled = self.state.rollback_to_snapshot(1, "test")
        self.assertEqual(rolled, snap_data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
