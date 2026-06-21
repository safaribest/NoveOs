"""PacingGuard —— 节奏检测。

检测连续多章同模式（爽→爽→爽无起伏）、情绪曲线单调、情绪配比偏离。
"""
from __future__ import annotations

from core.fanqie_course import load_fanqie_rules
from core.guards.base import BaseGuard, GuardResult


class PacingGuard(BaseGuard):
    """检测节奏：连续多章同模式、情绪曲线单调、情绪配比偏离。"""

    guard_id = "pacing"
    description = "节奏检测：检测连续多章同模式、情绪曲线单调、情绪配比偏离"
    default_level = "INFO"

    _GENRE_KEY_MAP: dict[str, str] = {
        "古代穿越": "female_gudai_chuanyue",
        "古代": "female_gudai_chuanyue",
        "宫斗": "female_gudai_gongdou",
        "宅斗": "female_gudai_gongdou",
        "都市重生": "male_dushi_zhongsheng",
        "重生": "male_dushi_zhongsheng",
        "都市": "male_dushi_zhongsheng",
        "都市异能": "male_dushi_yineng",
        "异能": "male_dushi_yineng",
        "玄幻": "male_xuanhuan_dongfang",
        "东方玄幻": "male_xuanhuan_dongfang",
        "异世": "male_xuanhuan_yishi",
        "异世大陆": "male_xuanhuan_yishi",
        "悬疑": "male_xuanyi_tuili",
        "推理": "male_xuanyi_tuili",
        "末世": "male_kehuan_moshi",
        "甜宠": "female_xiandai_tianchong",
        "现代甜宠": "female_xiandai_tianchong",
        "虐恋": "female_xiandai_nuelian",
        "现代虐恋": "female_xiandai_nuelian",
    }

    _EMOTION_LABEL: dict[str, str] = {
        "shuang": "爽",
        "tian": "甜",
        "nue": "虐",
        "ping": "平",
    }

    _EMOTION_ADVICE: dict[str, str] = {
        "shuang": "增加打脸/逆袭情节",
        "tian": "增加暧昧/互动情节",
        "nue": "增加冲突/误会/失去情节",
        "ping": "增加冲突/悬念推进",
    }

    def __init__(self) -> None:
        self._fanqie_rules = load_fanqie_rules()
        # 用于跟踪情绪配比偏离的跨章连续性（Guard 实例通常按章节复用）
        self._emotion_ratio_history: list[dict] = []

    def _resolve_genre_key(self, context: dict) -> str | None:
        """从 context 解析品类 key，失败返回 None。"""
        genre_key = context.get("genre_key")
        if genre_key:
            return genre_key
        genre = context.get("genre", "")
        if not genre:
            return None
        for key, mapped in self._GENRE_KEY_MAP.items():
            if key in genre:
                return mapped
        return None

    def _check_emotion_ratio(self, content: str, context: dict) -> list[str]:
        """检测本章主导情绪是否与目标品类的情绪配比一致。"""
        genre_key = self._resolve_genre_key(context)
        if not genre_key:
            return []

        pacing = self._fanqie_rules.get_pacing_rules()
        emotion_keywords = pacing.get("emotion_keywords", {})
        if not emotion_keywords:
            return []

        counts: dict[str, int] = {}
        for emotion, keywords in emotion_keywords.items():
            counts[emotion] = sum(content.count(kw) for kw in keywords)

        total = sum(counts.values())
        if total == 0:
            return []

        actual: dict[str, float] = {emotion: count / total for emotion, count in counts.items()}
        target_ratio = self._fanqie_rules.get_emotion_ratio(genre_key)

        # 兼容 keywords 中可能只出现部分情绪的情况
        for key in target_ratio:
            actual.setdefault(key, 0.0)

        deviation_threshold = pacing.get("emotion_deviation_threshold", 0.15)
        chapter_num = context.get("chapter_num", len(self._emotion_ratio_history) + 1)

        # 记录本章实际配比，用于后续连续偏离/连续主导判断
        current_dominant = max(actual, key=actual.get)
        self._emotion_ratio_history.append({
            "chapter": chapter_num,
            "ratios": actual,
            "dominant": current_dominant,
        })

        issues: list[str] = []

        # 1. 单章最大偏离
        max_deviation_emotion = max(
            target_ratio,
            key=lambda e: abs(actual[e] - target_ratio[e]),
        )
        deviation = actual[max_deviation_emotion] - target_ratio[max_deviation_emotion]
        if abs(deviation) > deviation_threshold:
            label = self._EMOTION_LABEL.get(max_deviation_emotion, max_deviation_emotion)
            actual_pct = round(actual[max_deviation_emotion] * 100)
            target_pct = round(target_ratio[max_deviation_emotion] * 100)
            advice = self._EMOTION_ADVICE.get(max_deviation_emotion, "调整情节配比")
            direction = "高于" if deviation > 0 else "低于"
            issues.append(
                f"[情绪配比偏离] {label}情绪占比 {actual_pct}%，目标 {target_pct}%，"
                f"{direction}目标 {abs(actual_pct - target_pct)}%，建议{advice}"
            )

        # 2. 连续 3 章同一情绪主导
        max_streak = pacing.get("max_same_emotion_streak", 3)
        if len(self._emotion_ratio_history) >= max_streak:
            recent = self._emotion_ratio_history[-max_streak:]
            dominants = [entry["dominant"] for entry in recent]
            if len(set(dominants)) == 1 and dominants[0] != "ping":
                label = self._EMOTION_LABEL.get(dominants[0], dominants[0])
                issues.append(
                    f"[情绪配比偏离] {label}情绪连续{max_streak}章主导，"
                    f"建议引入其他情绪转折以丰富节奏"
                )

        return issues

    def run(self, content: str, context: dict) -> GuardResult:
        chapter_num = context.get("chapter_num", 0)
        ratio_issues = self._check_emotion_ratio(content, context)

        state = context.get("state_manager")
        if (not state or chapter_num < 3) and not ratio_issues:
            return GuardResult(
                guard_id=self.guard_id, level="PASS",
                message="章节数不足，跳过节奏检测", metadata={},
            )

        issues: list[str] = list(ratio_issues)
        metadata: dict = {}

        if state and chapter_num >= 3:
            # 1. 检测连续3章同一主导情绪
            history = state.get_emotion_history()
            if len(history) >= 3:
                recent = history[-3:]
                # 找出每章主导情绪
                dominant_emotions = []
                for h in recent:
                    nue = h.get("nue", 0)
                    tian = h.get("tian", 0)
                    shuang = h.get("shuang", 0)
                    if shuang > nue and shuang > tian:
                        dominant_emotions.append("爽")
                    elif nue > tian and nue > shuang:
                        dominant_emotions.append("虐")
                    elif tian > nue and tian > shuang:
                        dominant_emotions.append("甜")
                    else:
                        dominant_emotions.append("平")

                if len(set(dominant_emotions)) == 1 and dominant_emotions[0] != "平":
                    issues.append(
                        f"[情绪单调] 最近3章均为'{dominant_emotions[0]}'模式，缺少情绪起伏"
                    )
                metadata["recent_dominant"] = dominant_emotions

        # 2. 检测本章内部节奏：高潮位置
        # 简化：检测高潮词在文中的分布
        climax_words = ["终于", "果然", "果然如此", "果然不出所料", "反转", "逆转",
                        "爆发", "爆发出来", "炸裂", "震惊", "震撼", "不可思议"]
        climax_positions = []
        for word in climax_words:
            idx = content.find(word)
            if idx >= 0:
                climax_positions.append(idx / max(len(content), 1))
        if climax_positions:
            avg_pos = sum(climax_positions) / len(climax_positions)
            metadata["climax_avg_position"] = round(avg_pos, 3)
            if avg_pos < 0.3:
                issues.append("[高潮前置] 高潮/反转集中在文章前30%，后文可能乏力")
            elif avg_pos > 0.85:
                issues.append("[高潮后置] 高潮/反转集中在文章末尾85%后，前文可能拖沓")

        # 3. 检测节奏单一：本章缺乏情绪转折
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if len(paragraphs) >= 5:
            # 检测是否有明显的情绪转折标记
            turn_markers = ["但", "却", "然而", "没想到", "突然", "反转", "原来",
                           "不料", "谁知", "岂料", "岂知"]
            turn_count = sum(content.count(m) for m in turn_markers)
            metadata["turn_count"] = turn_count
            if turn_count == 0:
                issues.append("[无转折] 本章缺少情绪/情节转折，平铺直叙")
            elif turn_count >= 8:
                issues.append(f"[转折过多] 本章有{turn_count}处转折，节奏可能过于跳跃")

        if issues:
            # 番茄课程新增检测默认 WARN；原有单条问题保持 INFO
            has_ratio_issue = any("[情绪配比偏离]" in i for i in issues)
            level = "WARN" if has_ratio_issue or len(issues) >= 2 else "INFO"
            return GuardResult(
                guard_id=self.guard_id,
                level=level,
                message=f"发现 {len(issues)} 处节奏问题",
                metadata={"issues": issues, **metadata},
            )
        return GuardResult(
            guard_id=self.guard_id,
            level="PASS",
            message="节奏检测通过",
            metadata=metadata,
        )
