"""Novel-OS 批量写作器 —— Facade 层。

Phase 3 重构后，BatchWriter 职责缩减为：
1. 初始化（LLM、Validator、StateManager）
2. 构建 ChapterContext
3. 调用 WritingPipeline.execute
4. 保存结果 + 更新 StateManager

核心写作逻辑已迁移至 core.writing 域：
- Steps: core/writing/steps/*.py
- Pipeline: core/writing/pipeline.py
- Context: core/writing/context.py
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from core.config_loader import BookConfig
from core.content.metrics import count_chinese_chars
from core.content.sanitizer import Sanitizer
from core.content.title import extract_from_director, extract_from_content, strip_title_prefix
from core.event_bus import EventBus
from core.chapter_validator import ChapterValidator
from core.llm_client import LLMClient, LLMConfig
from core.platform_scorer import score_platform_adaptation, compute_genre_dna_match
from core.state_manager import StateManager
from core.post_write_validator import PostWriteValidator
from core.input_governor import InputGovernor
from core.anti_detect_reviser import AntiDetectReviser
from core.iwr_analyzer import analyze_chapter

from core.writing.context import ChapterContext, ChapterContextBuilder
from core.writing.output import WriteResult
from core.writing.pipeline import WritingPipeline, PipelineConfig

__all__ = ["BatchWriter", "WriteResult"]

logger = logging.getLogger("novel-os.batch_writer")


class BatchWriter:
    """配置驱动的批量章节写作器，支持断点续传。

    Phase 3 后，BatchWriter 是 WritingPipeline 的 Facade：
    - 保留初始化、保存、状态更新
    - 写作逻辑委托给 WritingPipeline
    """

    def __init__(
        self,
        book_config: BookConfig,
        state_manager: StateManager | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.cfg = book_config
        self.state = state_manager or StateManager(
            book_config.base_path / "world_state.db",
            project_id=book_config.base_path.name,
        )
        self._event_bus = event_bus
        self._sanitizer = Sanitizer()

        # project_id 启动校验
        self._validate_project_id()

        # 初始化 LLM 客户端
        def _build_llm_cfg(cfg_dict: dict[str, Any]) -> LLMConfig:
            return LLMConfig(
                model=cfg_dict.get("model", "deepseek-v4-pro"),
                api_key=cfg_dict.get("api_key", ""),
                api_base=cfg_dict.get("api_base", "https://api.deepseek.com/v1"),
                temperature=cfg_dict.get("temperature", 0.7),
                max_tokens=cfg_dict.get("max_tokens", 8000),
                timeout=cfg_dict.get("timeout", 300),
                reasoning_effort=cfg_dict.get("reasoning_effort", "high"),
                thinking_enabled=cfg_dict.get("thinking_enabled", False),
            )

        llm_cfg = book_config.llm
        fallback_cfg = book_config.llm_fallback
        agent_cfgs = getattr(book_config, "agent_llm", None)

        # ★ 合并内置模型选择策略与外部配置
        # 内置策略：SceneWriter/HookEngineer → thinking模式，其他 → 标准模式
        built_in_strategy = LLMClient.AGENT_MODEL_STRATEGY
        merged_agent_cfgs: dict[str, dict[str, Any]] = {}

        # 先应用内置策略（作为默认值）
        for agent_name, strategy in built_in_strategy.items():
            merged_agent_cfgs[agent_name] = dict(strategy)
            # 从主配置继承 api_key/api_base
            if llm_cfg:
                merged_agent_cfgs[agent_name].setdefault("api_key", llm_cfg.get("api_key", ""))
                merged_agent_cfgs[agent_name].setdefault("api_base", llm_cfg.get("api_base", "https://api.deepseek.com/v1"))

        # 再覆盖外部 agent_llm 配置（优先级更高）
        if agent_cfgs:
            for agent_name, agent_cfg in agent_cfgs.items():
                if agent_name not in merged_agent_cfgs:
                    merged_agent_cfgs[agent_name] = {}
                merged_agent_cfgs[agent_name].update(agent_cfg)

        if llm_cfg:
            # book.yaml 显式配置 → 优先使用
            primary = _build_llm_cfg(llm_cfg)
            fallback = _build_llm_cfg(fallback_cfg) if fallback_cfg else None
            self.llm = LLMClient(primary, fallback, agent_configs=merged_agent_cfgs)
        else:
            # 尝试从 llm.yaml（前端 LLM 设置页）加载
            try:
                from core.llm_settings_client import load_llm_settings
                settings = load_llm_settings()
                default_name = settings.get("default_provider", "")
                providers = settings.get("providers", {})
                if default_name and default_name in providers:
                    p = providers[default_name]
                    primary = LLMConfig(
                        model=p.get("model", "deepseek-v4-pro"),
                        api_key=p.get("api_key", ""),
                        api_base=p.get("base_url", "https://api.deepseek.com/v1"),
                        temperature=p.get("temperature", 0.7),
                        max_tokens=p.get("max_tokens", 8000),
                        timeout=p.get("timeout", 300),
                        thinking_enabled=p.get("thinking_enabled", False),
                        reasoning_effort=p.get("reasoning_effort", "high"),
                    )
                    # 加载 Agent 专属 Provider 分配
                    agent_providers = settings.get("agent_providers", {})
                    resolved_agent_cfgs: dict[str, dict[str, Any]] = {}
                    for agent_name, provider_name in agent_providers.items():
                        if provider_name in providers:
                            ap = providers[provider_name]
                            resolved_agent_cfgs[agent_name] = {
                                "model": ap.get("model"),
                                "api_key": ap.get("api_key"),
                                "api_base": ap.get("base_url"),
                                "temperature": ap.get("temperature", 0.7),
                                "max_tokens": ap.get("max_tokens", 8000),
                                "timeout": ap.get("timeout", 300),
                                "thinking_enabled": ap.get("thinking_enabled", False),
                                "reasoning_effort": ap.get("reasoning_effort", "high"),
                            }
                    # 合并：内置策略 → llm.yaml agent_providers → book.yaml agent_llm
                    merged_agent_cfgs = {**merged_agent_cfgs, **resolved_agent_cfgs}
                    if agent_cfgs:
                        for agent_name, agent_cfg in agent_cfgs.items():
                            if agent_name not in merged_agent_cfgs:
                                merged_agent_cfgs[agent_name] = {}
                            merged_agent_cfgs[agent_name].update(agent_cfg)
                    self.llm = LLMClient(primary, agent_configs=merged_agent_cfgs if merged_agent_cfgs else None)
                    logger.info("BatchWriter 从 llm.yaml 加载 LLM 配置: provider=%s, model=%s", default_name, primary.model)
                else:
                    self.llm = LLMClient(LLMConfig.from_env(), agent_configs=merged_agent_cfgs)
            except Exception:
                self.llm = LLMClient(LLMConfig.from_env(), agent_configs=merged_agent_cfgs)

        # 输入治理 + 反检测改写
        self.post_validator = PostWriteValidator()
        self.input_governor = InputGovernor(book_config, self.state)
        self.anti_detect = AntiDetectReviser()

        # ChapterValidator
        validator_thresholds = {
            "min_words": self.cfg.words_per_chapter - self.cfg.words_tolerance,
            "max_words": self.cfg.words_per_chapter + self.cfg.words_tolerance,
        }
        self.validator = ChapterValidator(thresholds=validator_thresholds)

        self.output_dir = book_config.base_path / book_config.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 流水线编排器
        self._pipeline = WritingPipeline(
            validator=self.validator,
            config=PipelineConfig(max_retries=self.cfg.max_retries),
            event_bus=self._event_bus,
            project_id=self.cfg.base_path.name,
            book_config=self.cfg,  # ★ 传入 book_config 让 ChapterGoal 动态计算字数目标
        )
        self._ctx_builder = ChapterContextBuilder(self.cfg, self.state, self.input_governor)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def write_chapter(self, chapter_num: int) -> WriteResult:
        """写单章入口：构建上下文 → 执行流水线 → 保存结果。"""
        logger.info("=" * 60)
        logger.info("BatchWriter 开始写作 第 %d 章", chapter_num)

        self._emit_agent_event("agent_call_start", chapter_num, "BatchWriter", "构建上下文")
        ctx = self._ctx_builder.build(chapter_num, self.llm)
        self._emit_agent_event("agent_call_complete", chapter_num, "BatchWriter", "上下文就绪")

        # 执行流水线
        pipeline_result = self._pipeline.execute(ctx)

        # 标题提取与剥离：标题保存到状态库，正文内不再保留
        director_title = extract_from_director(ctx.director_prompt, chapter_num)
        content, extracted_title = strip_title_prefix(
            chapter_num, pipeline_result.final_content
        )
        title = director_title or extracted_title or ""
        pipeline_result.final_content = content
        pipeline_result.word_count = count_chinese_chars(content)

        # 保存 + 更新状态
        if pipeline_result.success:
            saved_path = self.save_chapter(chapter_num, content)
            pipeline_result.saved_path = saved_path
            self._update_state_after_chapter(
                chapter_num,
                content,
                title=title,
                audit_report=pipeline_result.audit_report,
                gate_level=pipeline_result.gate_level,
            )
            logger.info("第 %d 章 完成，中文字数=%d，路径=%s", chapter_num, pipeline_result.word_count, saved_path)
        else:
            # BLOCK 也保存草稿
            if content.strip():
                draft_path = self.save_chapter(chapter_num, content)
                pipeline_result.saved_path = draft_path
                logger.info("第 %d 章 草稿已保存: %s", chapter_num, draft_path)

        return pipeline_result

    def write_range(self, start: int, end: int, resume: bool = False) -> list[WriteResult]:
        """批量写一定范围的章节。"""
        results: list[WriteResult] = []
        for num in range(start, end + 1):
            if resume and self._chapter_exists(num):
                existing_content = self._load_existing_chapter(num) or ""
                existing_wc = count_chinese_chars(existing_content)
                min_wc = self.cfg.words_per_chapter - self.cfg.words_tolerance
                if existing_wc < min_wc:
                    logger.warning("第 %d 章 已存在但字数不足（%d < %d），强制重写", num, existing_wc, min_wc)
                else:
                    logger.info("第 %d 章 已存在，跳过", num)
                    continue
            try:
                result = self.write_chapter(num)
                results.append(result)
            except Exception as exc:
                logger.exception("第 %d 章 流水线外层异常: %s", num, exc)
                results.append(
                    WriteResult(
                        chapter_num=num,
                        success=False,
                        final_content="",
                        word_count=0,
                        gate_level="BLOCKING",
                        attempts=0,
                    )
                )
        return results

    def save_chapter(self, chapter_num: int, content: str) -> Path:
        """保存章节正文到 output_dir，使用标准文件名 chapter_{num:03d}.md。"""
        content = self._sanitizer.sanitize(content)
        filename = f"chapter_{chapter_num:03d}.md"
        path = self.output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def set_outer_crew_feedback(
        self,
        retcons: list[str] | None = None,
        emotion_targets: list[dict[str, Any]] | None = None,
        priorities: list[str] | None = None,
    ) -> None:
        """从 Orchestrator 接收外层 CrewAI 反馈，注入后续章节上下文。"""
        self._ctx_builder.set_outer_crew_feedback(retcons, emotion_targets, priorities)
        logger.info(
            "BatchWriter 已接收外层反馈: retcons=%d, emotions=%d, priorities=%d",
            len(retcons) if retcons else 0,
            len(emotion_targets) if emotion_targets else 0,
            len(priorities) if priorities else 0,
        )

    # ------------------------------------------------------------------
    # 状态库查询
    # ------------------------------------------------------------------
    def _get_chapter_title(self, chapter_num: int) -> str:
        """获取章节标题。优先从 outline.title 读取，回退到 chapter_history。"""
        try:
            # outline 表的 title 是权威标题
            import sqlite3
            with sqlite3.connect(str(self.state.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT title FROM outline WHERE project_id = ? AND chapter = ?",
                    (self.state.project_id, chapter_num),
                ).fetchone()
                if row and row["title"]:
                    return row["title"]
        except Exception:
            pass
        try:
            return self.state.get_chapter_title(chapter_num)
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------
    def _validate_project_id(self) -> None:
        try:
            db_info = self.state.get_project_info()
            db_pid = db_info.get("project_id", "")
            cfg_pid = self.state.project_id
            if db_pid and db_pid != cfg_pid:
                logger.error(
                    "project_id 不匹配! 数据库=%s, 配置=%s. "
                    "这将导致 outline/character_states 查询返回空，全书脱离大纲写作。",
                    db_pid, cfg_pid,
                )
                raise ValueError(
                    f"project_id 不匹配: db='{db_pid}' vs cfg='{cfg_pid}'. "
                    f"请统一 book.yaml 的 project 字段与数据库 projects.project_id。"
                )
            if db_pid:
                logger.info("project_id 校验通过: %s", cfg_pid)
            else:
                logger.warning("数据库中无 projects 记录，自动初始化项目...")
                self.state.init_project(
                    project_id=cfg_pid,
                    name=self.cfg.project,
                    genre=self.cfg.genre,
                    platform=self.cfg.platform,
                    base_path=str(self.cfg.base_path),
                    total_chapters=self.cfg.chapters_target,
                )
                # 若 genre_dna 缺失也一并初始化
                if not self.state.get_genre_dna():
                    self.state.init_genre_dna(self.cfg.genre)
                logger.info("项目记录已创建: %s", cfg_pid)
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            logger.warning("project_id 启动校验异常: %s", exc)

    # ------------------------------------------------------------------
    # 文件系统
    # ------------------------------------------------------------------
    def _chapter_exists(self, chapter_num: int) -> bool:
        return (self.output_dir / f"chapter_{chapter_num:03d}.md").exists()

    def _load_existing_chapter(self, chapter_num: int) -> str:
        path = self.output_dir / f"chapter_{chapter_num:03d}.md"
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # 状态更新
    # ------------------------------------------------------------------
    def _update_state_after_chapter(
        self,
        chapter_num: int,
        content: str,
        title: str = "",
        audit_report: dict[str, Any] | None = None,
        gate_level: str = "",
    ) -> None:
        """章节写完后更新状态库（含 RAG 结构指标与审计结果）。"""
        summary = content[:200].replace("\n", " ") + "..."
        word_count = count_chinese_chars(content)
        self.state.update_after_chapter(
            chapter_num=chapter_num,
            summary=summary,
            word_count=word_count,
            mode="",
            title=title,
        )
        self.state.update_project_status(
            current_chapter=chapter_num,
            status="writing",
        )
        self._propagate_character_states(chapter_num)
        metrics = analyze_chapter(content)
        history = self.state.list_chapters()
        hist_word_counts = [h.get("word_count", 0) or 0 for h in history if h.get("word_count")]
        platform = score_platform_adaptation(metrics, hist_word_counts)
        genre_dna = self.state.get_genre_dna()
        dna_match = compute_genre_dna_match(metrics, genre_dna)
        metrics.update({
            "platform_score": platform.get("platform_score", 0),
            "platform_grade": platform.get("platform_grade", "C"),
            "genre_dna_match": dna_match if isinstance(dna_match, (int, float)) else dna_match.get("dna_match", 0.5),
        })
        clean_metrics = {}
        for k, v in metrics.items():
            if isinstance(v, (int, float, str, bool, type(None))):
                clean_metrics[k] = v
            elif isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    if isinstance(sub_v, (int, float, str, bool, type(None))):
                        clean_metrics[f"{k}_{sub_k}"] = sub_v
        quality_passed = gate_level != "BLOCKING" if gate_level else None
        self.state.update_chapter_metrics(
            chapter_num,
            clean_metrics,
            quality_passed=quality_passed,
            gate_level=gate_level or None,
            audit_report=audit_report,
        )
        nue_indicators = {
            "痛": 0.5, "血": 0.3, "死": 0.8, "杀": 0.7, "折": 0.4,
            "窒息": 0.9, "腐蚀": 0.7, "剥离": 0.6, "消退": 0.4,
            "绝望": 0.8, "窒息感": 0.9, "钝痛": 0.6, "撕裂": 0.7,
        }
        tian_indicators = {
            "笑": 0.5, "暖": 0.6, "光": 0.2, "甜": 0.8, "温柔": 0.5,
            "依赖": 0.4, "信任": 0.5, "安慰": 0.4,
        }
        shuang_indicators = {
            "赢": 0.8, "碾压": 0.9, "破": 0.5, "解": 0.3, "反击": 0.7,
            "挣脱": 0.6, "识破": 0.5,
        }
        nue = sum(content.count(w) * weight for w, weight in nue_indicators.items())
        tian = sum(content.count(w) * weight for w, weight in tian_indicators.items())
        shuang = sum(content.count(w) * weight for w, weight in shuang_indicators.items())
        total = nue + tian + shuang + 0.1
        emotion = {
            "nue": nue / total,
            "tian": tian / total,
            "shuang": shuang / total,
            "coord_x": 0.0,
            "coord_y": 0.0,
            "desc": f"IWR={metrics['iwr_score']}, Platform={platform['platform_grade']} (加权词袋回退)",
        }
        self.state.update_emotion_history(
            chapter_num=chapter_num,
            mode="auto",
            nue=emotion["nue"],
            tian=emotion["tian"],
            shuang=emotion["shuang"],
            coord_x=emotion.get("coord_x", 0.0),
            coord_y=emotion.get("coord_y", 0.0),
            desc=emotion.get("desc", ""),
        )

    def update_reader_pull_score(self, chapter_num: int, score: float) -> None:
        """更新章节的追读力分数（由 Orchestrator 计算后写入）。"""
        try:
            self.state.update_reader_pull_score(chapter_num, score)
        except Exception:
            logger.warning("更新第 %d 章追读力分数失败", chapter_num)

    def _propagate_character_states(self, chapter_num: int) -> None:
        """将上一章的角色状态复制到本章，保持跨章连续性。"""
        if chapter_num <= 0:
            return
        try:
            prev_chars = self.state.get_characters_by_chapter(chapter_num - 1)
            if not prev_chars and chapter_num > 1:
                for back in range(chapter_num - 2, -1, -1):
                    prev_chars = self.state.get_characters_by_chapter(back)
                    if prev_chars:
                        break
            if not prev_chars:
                logger.warning("第 %d 章 无可用角色状态可传播", chapter_num)
                return
            for char in prev_chars:
                self.state.update_character_state(
                    chapter=chapter_num,
                    character=char["name"],
                    location=char.get("location", ""),
                    emotional_state=char.get("emotional_state", ""),
                    known_secrets=char.get("known_secrets", ""),
                    unknown_secrets=char.get("unknown_secrets", ""),
                    abilities_active=char.get("abilities", ""),
                    dialog_fingerprint=char.get("dialog_fingerprint", ""),
                    body_language=char.get("body_language", ""),
                    physical_description=char.get("description", ""),
                )
            logger.info("第 %d 章 角色状态已传播: %d 人", chapter_num, len(prev_chars))
        except Exception as exc:
            logger.warning("传播角色状态到第 %d 章失败: %s", chapter_num, exc)

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def _emit_agent_event(self, event: str, chapter_num: int, agent: str, detail: str = "") -> None:
        if self._event_bus:
            self._event_bus.emit(
                event,
                {
                    "chapter_num": chapter_num,
                    "agent": agent,
                    "detail": detail,
                    "project_id": getattr(self.cfg, "base_path", Path(".")).name,
                },
            )
