"""ProjectFactory 单元测试。"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from core.project_factory import ProjectFactory


class TestProjectFactory(unittest.TestCase):
    """验证项目创建时 chapters_target 推导逻辑。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp_dir = Path(tempfile.mkdtemp(prefix="novel-os-project-factory-test-"))

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _build_outline(self, chapter_count: int, chapters_target: int | None = None) -> dict:
        outline = {
            "genre": "都市",
            "platform": "起点",
            "words_per_chapter": 2200,
            "outline": [
                {"chapter": i + 1, "arc": f"arc_{i + 1}", "core_event": f"event_{i + 1}"}
                for i in range(chapter_count)
            ],
        }
        if chapters_target is not None:
            outline["chapters_target"] = chapters_target
        return outline

    def test_chapters_target_derived_from_outline_length(self) -> None:
        """当 outline 未提供 chapters_target 时，应按实际章节数推导。"""
        factory = ProjectFactory(base_path=self.tmp_dir)
        outline = self._build_outline(30)

        result = factory.create_from_outline(title="测试三十章", outline=outline)

        book_yaml = Path(result["base_path"]) / "book.yaml"
        config = yaml.safe_load(book_yaml.read_text(encoding="utf-8"))
        self.assertEqual(config["chapters_target"], 30)
        self.assertEqual(config["total_words_target"], 30 * 2200)

    def test_explicit_chapters_target_preserved(self) -> None:
        """当 outline 显式提供 chapters_target 时，应保留该值。"""
        factory = ProjectFactory(base_path=self.tmp_dir)
        outline = self._build_outline(30, chapters_target=50)

        result = factory.create_from_outline(title="测试显式章数", outline=outline)

        book_yaml = Path(result["base_path"]) / "book.yaml"
        config = yaml.safe_load(book_yaml.read_text(encoding="utf-8"))
        self.assertEqual(config["chapters_target"], 50)

    def test_zero_chapters_target_derived_from_outline_length(self) -> None:
        """当 chapters_target 为 0 时，应回退到实际章节数。"""
        factory = ProjectFactory(base_path=self.tmp_dir)
        outline = self._build_outline(30, chapters_target=0)

        result = factory.create_from_outline(title="测试零章数", outline=outline)

        book_yaml = Path(result["base_path"]) / "book.yaml"
        config = yaml.safe_load(book_yaml.read_text(encoding="utf-8"))
        self.assertEqual(config["chapters_target"], 30)

    def test_user_explicit_chapters_target_override(self) -> None:
        """显式传入的 chapters_target 应覆盖 outline 中的值。"""
        factory = ProjectFactory(base_path=self.tmp_dir)
        outline = self._build_outline(30, chapters_target=200)

        result = factory.create_from_outline(
            title="测试用户覆盖章数", outline=outline, chapters_target=50
        )

        book_yaml = Path(result["base_path"]) / "book.yaml"
        config = yaml.safe_load(book_yaml.read_text(encoding="utf-8"))
        self.assertEqual(config["chapters_target"], 50)
        self.assertEqual(config["words_per_chapter"], 2200)
        self.assertEqual(config["total_words_target"], 50 * 2200)

    def test_user_explicit_words_per_chapter_override(self) -> None:
        """显式传入的 words_per_chapter 应覆盖 outline 中的值。"""
        factory = ProjectFactory(base_path=self.tmp_dir)
        outline = self._build_outline(30, chapters_target=30)
        outline["words_per_chapter"] = 2200

        result = factory.create_from_outline(
            title="测试用户覆盖字数", outline=outline, words_per_chapter=3000
        )

        book_yaml = Path(result["base_path"]) / "book.yaml"
        config = yaml.safe_load(book_yaml.read_text(encoding="utf-8"))
        self.assertEqual(config["chapters_target"], 30)
        self.assertEqual(config["words_per_chapter"], 3000)
        self.assertEqual(config["total_words_target"], 30 * 3000)


if __name__ == "__main__":
    unittest.main()
