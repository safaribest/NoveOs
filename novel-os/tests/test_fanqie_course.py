"""番茄课程规则集成测试。"""
from __future__ import annotations

import pytest

from core.fanqie_course import FanqieCourseRules, load_fanqie_rules
from core.guards.reader_pull_guard import ReaderPullGuard
from core.guards.pacing_guard import PacingGuard
from core.writing.prompts import build_fanqie_injection, map_genre_to_course_key


class TestFanqieCourseRules:
    """测试规则加载器。"""

    def test_load_default_rules(self):
        rules = load_fanqie_rules()
        opening = rules.get_opening_rules()
        assert opening["max_lead_in_words"] == 300
        assert 1 in opening["active_chapters"]

    def test_get_emotion_ratio_mapped(self):
        rules = load_fanqie_rules()
        ratio = rules.get_emotion_ratio("male_dushi_zhongsheng")
        assert ratio["shuang"] == 0.5
        assert ratio["tian"] == 0.2

    def test_get_emotion_ratio_default(self):
        rules = load_fanqie_rules()
        ratio = rules.get_emotion_ratio("unknown_genre")
        assert ratio["shuang"] == 0.35
        assert "tian" in ratio

    def test_override_merge(self, tmp_path):
        base_path = tmp_path / "base.yaml"
        override_path = tmp_path / "override.yaml"
        base_path.write_text(
            "version: '1.0'\nrules:\n  opening:\n    max_lead_in_words: 300\n",
            encoding="utf-8",
        )
        override_path.write_text(
            "version: '1.0'\nrules:\n  opening:\n    max_lead_in_words: 500\n",
            encoding="utf-8",
        )
        rules = FanqieCourseRules(rules_path=base_path, overrides_path=override_path)
        assert rules.get_opening_rules()["max_lead_in_words"] == 500


class TestGenreMapping:
    """测试品类映射。"""

    def test_known_genres(self):
        assert map_genre_to_course_key("年代商战") == "male_dushi_zhongsheng"
        assert map_genre_to_course_key("甜宠") == "female_xiandai_tianchong"
        assert map_genre_to_course_key("悬疑推理") == "male_xuanyi_tuili"

    def test_unknown_genre_fallback(self):
        assert map_genre_to_course_key("外星文明") == "default"


class TestReaderPullGuardFanqie:
    """测试 ReaderPullGuard 的番茄课程检测。"""

    def test_opening_hook_missing(self):
        guard = ReaderPullGuard()
        # 无冲突/悬念/转折的平缓开篇
        bad = "这个世界很大。主角出生在一个小村庄。他小时候很穷。他每天都很努力。"
        result = guard.run(bad, {"chapter_num": 1})
        assert any("[开篇缺钩子]" in issue for issue in result.metadata["issues"])

    def test_opening_hook_present(self):
        guard = ReaderPullGuard()
        good = "李强没想到，自己刚重生回来，就被人堵在巷子里。"
        result = guard.run(good, {"chapter_num": 1})
        assert not any("[开篇缺钩子]" in issue for issue in result.metadata["issues"])

    def test_opening_hook_only_for_first_three_chapters(self):
        guard = ReaderPullGuard()
        bad = "这个世界很大。主角出生在一个小村庄。他小时候很穷。"
        result = guard.run(bad, {"chapter_num": 4})
        assert not any("[开篇缺钩子]" in issue for issue in result.metadata["issues"])

    def test_ending_hook_missing(self):
        guard = ReaderPullGuard()
        # 长内容，结尾平缓
        bad = "他吃了饭。他睡了觉。他醒了过来。" * 100
        result = guard.run(bad, {"chapter_num": 1})
        assert any("[章节末缺钩子]" in issue for issue in result.metadata["issues"])

    def test_climax_density_low(self):
        guard = ReaderPullGuard()
        # 长内容，无爽点关键词
        bad = "他吃了饭。他睡了觉。他醒了过来。" * 100
        result = guard.run(bad, {"chapter_num": 1})
        assert any("[爽点不足]" in issue for issue in result.metadata["issues"])


class TestPacingGuardFanqie:
    """测试 PacingGuard 的番茄课程检测。"""

    def test_emotion_ratio_drift(self):
        guard = PacingGuard()
        # 年代商战文，但全文只有"爽"词
        content = "打脸！逆袭！碾压！震惊！终于！果然！"
        result = guard.run(
            content,
            {"chapter_num": 5, "genre": "年代商战", "genre_key": "male_dushi_zhongsheng"},
        )
        assert result.level in ("WARN", "INFO")

    def test_prompt_injection(self):
        """测试 prompt 注入内容。"""
        injection = build_fanqie_injection(1, "年代商战")
        assert "番茄官方·开篇铁律" in injection
        assert "番茄官方·章节节奏铁律" in injection
        assert "爽50%" in injection

        injection_late = build_fanqie_injection(10, "年代商战")
        assert "番茄官方·开篇铁律" not in injection_late
        assert "番茄官方·章节节奏铁律" in injection_late


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
