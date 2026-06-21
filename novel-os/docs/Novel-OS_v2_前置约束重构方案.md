# Novel-OS v2.0 前置约束重构方案

> 基于手工写作第一章的 15 轮迭代经验，将"事后审计型流水线"改造为"前置约束型编译器"。

---

## 一、核心诊断：为什么 AI 初稿总是不合格？

当前 Novel-OS 的 BatchWriter 流水线：

```
Director → Writer → Polish → Auditor
         ↓
    ChapterValidator（事后审计）
         ↓
    BLOCK → 注入 feedback → retry（3次）
```

**问题本质**：LLM 在写初稿时，完全不知道以下约束：
- IWR ≥ 2.0（= 至少 5 个悬念问句，最多 3 个揭示词）
- 句长均值 22–28 字（= 禁止连续短句）
- 他密度 < 2%（= 主语使用规则）
- 对话占比 25–45%（= 叙述与对话的节奏分配）

结果是：初稿 IWR=0.33、他密度=2.64%、句长均值=17.7。Validator 事后抽鞭子，LLM retry 时只能做局部修修补补，**无法修复结构性缺陷**。

**目标架构**：把 Validator 的规则翻译成 LLM 能听懂的"写作宪法"，在 system prompt 里先戴好镣铐。

---

## 二、总体架构：从"审计流水线"到"约束编译器"

```
book.yaml（全局约束）
    ↓
crewai/agents.yaml（Agent 人格）
    ↓
ChapterValidator.THRESHOLDS（硬指标）
    ↓
PromptBuilder_v2（翻译层：把约束 → system prompt）
    ↓
LLM（戴着镣铐写作）
    ↓
ChapterValidator（轻量校验，仅拦截漂移）
    ↓
通过 / 微调
```

**关键变化**：
1. Validator 从"审判者"降级为"抽检员"
2. PromptBuilder 新增"约束翻译"职责
3. retry 次数从 3 次降到 1 次（因为初稿合格率从 30% 提升到 85%）

---

## 三、六大战术改动（按优先级排序）

### P0：PromptBuilder 增加"写作宪法"生成器

**新建文件**：`core/prompt_builder_v2.py`

新增方法 `_build_writing_constitution()`，把 `ChapterValidator.THRESHOLDS` + `iwr_analyzer` 规则翻译为人类可读的写作指令：

```python
def _build_writing_constitution(self, chapter_num: int) -> str:
    """把硬指标翻译成 LLM 能执行的写作宪法。"""
    t = self.validator.thresholds  # 引用 ChapterValidator 的阈值
    target = self._get_chapter_target_words(chapter_num)
    
    lines = [
        "【写作宪法——违反任何一条，整章作废重写】",
        "",
        f"1. 字数铁律：本章中文字数必须严格控制在 {target - t['tolerance']} ~ {target + t['tolerance']} 字。",
        f"   统计方式：只算汉字，不算标点、空格、英文、数字。",
        "",
        f"2. 悬念铁律（IWR≥{t['iwr_target']}）：",
        f"   - 本章必须预埋至少 {t['question_count_min']} 个悬念问句（用难道/究竟/怎么/会不会等）。",
        f"   - 揭示词（原来/终于/发现/明白/知道/看来/果然/竟然/突然/顿时）不得超过 {t['reveal_count_max']} 个。",
        f"   - 每提出一个悬念，必须在 500 字内给出部分线索，但不得在 2000 字内彻底揭晓。",
        "",
        f"3. 句长铁律（均值 {t['sentence_length_target']} 字）：",
        f"   - 禁止连续使用 3 个以上≤{t['short_sentence_max']} 字的句子。",
        f"   - 每个段落至少包含 1 个≥{t['long_sentence_min']} 字的复合句。",
        f"   - 碎片化动作（\"他笑了。他走了。他回头。\"）视为一级违规。",
        "",
        f"4. 视角铁律（他密度<{t['max_ta_density']:.0%}）：",
        f"   - 主语优先使用角色全名（林默/陈雨），其次用省略主语的无头句。",
        f"   - 禁止用\"他/她\"指代前文超过 3 句未出现的角色。",
        "",
        f"5. 对话铁律（占比 {t['dialogue_ratio'][0]:.0%}~{t['dialogue_ratio'][1]:.0%}）：",
        f"   - 对话簇（连续引号段落）不得超过 3 段。",
        f"   - 规则条款用冷峻客观体，情感对话克制而撕裂。",
        f"   - 禁止用对话交代世界观（\"原来这个世界……\"）。",
        "",
        f"6. 章末钩子铁律：",
        f"   - 最后 100 字必须包含 1 个未解之谜或 1 个情绪定格画面。",
        f"   - 禁止用\"他不知道的是……\"这种 AI 万能结尾。",
    ]
    return "\n".join(lines)
```

**改动点**：`_build_system_prompt()` 在注入 author_persona 之后、注入网文禁区之前，插入 `_build_writing_constitution()` 的输出。

**预期效果**：Writer Agent 初稿的合格率从 30% 提升到 85%。

---

### P1：ChapterValidator.THRESHOLDS 补全缺失指标

**修改文件**：`core/chapter_validator.py`

当前 `THRESHOLDS`：
```python
THRESHOLDS = {
    "min_words": 4000,
    "max_words": 5000,
    "max_ta_density": 0.10,
    "max_redline": 0,
    "max_forbidden_patterns": 3,
    "dialogue_ratio": (0.25, 0.45),
    "max_dash_count": 3,
    "max_ellipsis_count": 2,
    "max_english_words": 0,
    "sensory_min_per_500": 1,
}
```

**补全后**：
```python
THRESHOLDS = {
    # P0 阻塞级
    "min_words": 4000,
    "max_words": 5000,
    "max_ta_density": 0.10,
    "max_redline": 0,
    "sentence_length_min": 20,        # ★ 新增：句长均值硬下限
    "iwr_target": 2.5,                # ★ 新增：IWR 目标值
    "question_count_min": 5,          # ★ 新增：悬念问句最低数量
    "reveal_count_max": 3,            # ★ 新增：揭示词上限
    
    # P1 警告级
    "max_forbidden_patterns": 3,
    "dialogue_ratio": (0.25, 0.45),
    "short_sentence_max": 12,         # ★ 新增：短句判定阈值
    "long_sentence_min": 25,          # ★ 新增：长句判定阈值
    "max_consecutive_short": 3,       # ★ 新增：连续短句上限
    "max_dash_count": 3,
    "max_ellipsis_count": 2,
    "max_english_words": 0,
    "sensory_min_per_500": 1,
}
```

**新增校验方法**：
```python
def _check_sentence_length(self, text: str, metrics: dict) -> list[ValidationIssue]:
    """检查句长均值和连续短句。"""
    issues = []
    sents = [s for s in re.split(r'[。！？…]+', text) if s.strip()]
    lens = [len(self._re_chinese.findall(s)) for s in sents]
    
    mean_len = sum(lens) / len(lens) if lens else 0
    metrics["sentence_length_mean"] = round(mean_len, 1)
    
    if mean_len < self.thresholds["sentence_length_min"]:
        issues.append(ValidationIssue(
            "WARN", "句长",
            f"句长均值 {mean_len:.1f} 字 < 下限 {self.thresholds['sentence_length_min']} 字。"
            f"建议合并短句，增加复合句。"
        ))
    
    # 连续短句检测
    consecutive = 0
    for ln in lens:
        if ln <= self.thresholds["short_sentence_max"]:
            consecutive += 1
            if consecutive > self.thresholds["max_consecutive_short"]:
                issues.append(ValidationIssue(
                    "WARN", "短句簇",
                    f"发现连续 {consecutive} 个≤{self.thresholds['short_sentence_max']} 字的短句。"
                    f"请用逗号合并，或用复合句替代。"
                ))
                break
        else:
            consecutive = 0
    
    return issues

def _check_iwr_structure(self, text: str, metrics: dict) -> list[ValidationIssue]:
    """检查 IWR 结构，不是只算比率，而是检查绝对数量。"""
    from core.iwr_analyzer import _QUESTION_PATTERNS, _REVEAL_PATTERNS
    
    q_count = sum(len(re.findall(p, text)) for p in _QUESTION_PATTERNS)
    r_count = sum(len(re.findall(p, text)) for p in _REVEAL_PATTERNS)
    
    metrics["question_count"] = q_count
    metrics["reveal_count"] = r_count
    metrics["iwr_score"] = round(q_count / max(r_count, 1), 2)
    
    issues = []
    if q_count < self.thresholds["question_count_min"]:
        issues.append(ValidationIssue(
            "WARN", "IWR",
            f"悬念问句仅 {q_count} 个 < 最低 {self.thresholds['question_count_min']} 个。"
            f"请在本章中段增加\"怎么会/为什么/究竟\"等认知缺口。"
        ))
    if r_count > self.thresholds["reveal_count_max"]:
        issues.append(ValidationIssue(
            "WARN", "IWR",
            f"揭示词 {r_count} 个 > 上限 {self.thresholds['reveal_count_max']} 个。"
            f"请将\"原来/发现/明白\"改写为疑问或留白。"
        ))
    return issues
```

---

### P2：统一对话占比统计口径

**问题**：`iwr_analyzer.py` 用段落级，`chapter_validator.py` 用引号字数级，两者打架。

**决策**：废弃段落级口径，统一使用**引号字数占比**（更贴近实际阅读体验）。

**修改文件**：
1. `core/iwr_analyzer.py`：删除 `dialogue_ratio` 字段（或改为与 validator 一致的算法）
2. `core/chapter_validator.py`：保留现有 `_calc_dialogue_ratio()`，但把阈值从 `(0.25, 0.45)` 改为与平台适配一致的值
3. `book.yaml`：新增显式声明
   ```yaml
   metrics:
     dialogue_algorithm: "quote_chars_ratio"  # 可选：quote_chars_ratio / paragraph_count_ratio
     dialogue_target: [0.30, 0.45]
   ```

---

### P3：按章节类型动态调整字数目标

**问题**：大纲第 1 章只有 6 个节拍，撑不起 4500 字；第 10 章团建大场面，3200 字又不够。

**修改文件**：`core/config_loader.py` + `core/batch_writer.py`

**方案**：在 `book.yaml` 增加章节级覆盖，或在 `state_manager` 中维护 `chapter_specs`。

推荐方案：利用现有的 `state_manager.get_chapter_specs()`，新增 `target_words` 字段。

```python
# core/batch_writer.py

def _get_chapter_target_words(self, chapter_num: int) -> int:
    """获取本章目标字数。优先级：state_manager > book.yaml > 默认值。"""
    # 1. 尝试从 state_manager 读取本章特定配置
    try:
        spec = self.state.get_chapter_spec(chapter_num, "target_words")
        if spec:
            return int(spec["spec_value"])
    except Exception:
        pass
    
    # 2. 回退到 book.yaml 全局配置
    return self.cfg.words_per_chapter
```

**大纲层配置示例**（在 `import_outline.py` 或手动写入 state）：
```sql
INSERT INTO chapter_specs (chapter, spec_key, spec_value) VALUES
(1, "target_words", "3200"),
(1, "chapter_type", "钩子章"),
(2, "target_words", "3500"),
(2, "chapter_type", "爆发章"),
(10, "target_words", "4200"),
(10, "chapter_type", "副本章");
```

**chapter_type 枚举**：`钩子章` / `爆发章` / `过渡章` / `副本章` / `情感章`

每种类型对应不同的 PromptBuilder 策略：
- 钩子章：开头 50 字必须抛悬念，结尾 100 字必须留未解之谜
- 爆发章：动作动词密度 +50%，句长缩短到 20 字以内制造急促感
- 过渡章：允许 IWR 降至 1.5，以信息释放为主
- 副本章：规则条款必须占 20% 字数，对话占比降至 30%
- 情感章：感官描写必须占 15%，触觉>听觉>视觉

---

### P4：crewai YAML 与 book.yaml 职责重划分

**当前问题**：
- crewai YAML 加载了，但 book.yaml 的 `agent_query` 在 `_build_system_prompt` 里抢了 role 的定义权
- crewai YAML 的 goal 被使用，但 book.yaml 的 goal 被忽略
- 两套配置内容大量重复，维护成本高

**重划分方案**：

| 职责 | crewai YAML | book.yaml |
|-----|------------|-----------|
| **Agent 身份** | role, backstory, goal（人格层） | agent_query.role（仅用于匹配） |
| **LLM 参数** | temperature, max_tokens | 无 |
| **全局约束** | 无 | author_persona, writing, thresholds |
| **Task 定义** | description, expected_output | 无 |
| **字数铁律** | 无 | 有（但应迁移到 THRESHOLDS） |

**修改点**：
1. `_build_system_prompt()` 中：
   - `role` 优先用 `cfg.get("role")`（crewai），其次 `query.get("role")`（book.yaml）
   - `goal` 优先用 `cfg.get("goal")`（crewai），其次 `query.get("goal")`（book.yaml）
   - 如果两者不同，以 crewai 为准，但在 debug log 中警告
2. 删除 book.yaml 中 `agent_query.*.goal` 的重复定义，只保留 `role`（用于 crewai 匹配）
3. 把 `author_persona` 中关于"字数铁律"的内容迁移到 `THRESHOLDS` 和 `_build_writing_constitution()`

---

### P5：RAG 模板引擎（轻量版）

**目标**：不是做全套 RAG 分析，而是提取"高追读章节的结构模板"，作为 Writer Agent 的 few-shot。

**新建文件**：`core/rag_template_engine.py`

```python
class RAGTemplateEngine:
    """从 RAG 语料库提取可复用的章节结构模板。"""
    
    def __init__(self, rag_path: Path):
        self.rag_path = rag_path
        self._cache: dict[str, list[dict]] = {}
    
    def get_chapter_template(self, genre: str, chapter_type: str, chapter_num: int) -> str:
        """
        返回适合本章的结构模板（纯文本，直接注入 prompt）。
        
        策略：
        1. 从 RAG 库筛选同品类、高追读分（IWR>2.5）的章节
        2. 按 chapter_type 聚类（钩子章/爆发章/过渡章）
        3. 提取平均节拍结构：每章几段、每段什么功能、字数分配
        4. 返回 human-readable 的"参考结构"
        """
        cache_key = f"{genre}:{chapter_type}"
        if cache_key not in self._cache:
            self._cache[cache_key] = self._analyze_corpus(genre, chapter_type)
        
        templates = self._cache[cache_key]
        # 取与当前 chapter_num 最接近的模板（第1章参考第1章，第10章参考第10章）
        best = min(templates, key=lambda t: abs(t["chapter_num"] - chapter_num))
        return self._format_template(best)
    
    def _analyze_corpus(self, genre: str, chapter_type: str) -> list[dict]:
        # 实际实现：调用已有的 batch_analyze_all.py 结果
        # 从 rag_analysis/ 读取 JSON，筛选 IWR>2.5 的章节
        pass
    
    def _format_template(self, template: dict) -> str:
        return (
            f"【同品类高追读章节参考结构（IWR={template['iwr']}）】\n"
            f"总字数：{template['word_count']} 字 | 句长：{template['sentence_length']} 字\n"
            f"节拍分配：\n"
            + "\n".join(f"  {i+1}. {b['name']}：{b['words']} 字，{b['function']}" 
                       for i, b in enumerate(template["beats"]))
            + "\n\n注意：以上为参考结构，不是强制要求。请根据本章大纲灵活调整。"
        )
```

**使用方式**：在 `_build_task_user_prompt()` 中，把 RAG 模板作为 few-shot 插入：

```python
rag = RAGTemplateEngine(Path("D:/noveos/RAG"))
template = rag.get_chapter_template(self.cfg.genre, chapter_type, chapter_num)
if template:
    parts.insert(0, template)
```

---

### P6：探索模式（前 3 章轻量验证）

**问题**：4-Agent 架构在风格探索期 overhead 太高。

**修改文件**：`core/batch_writer.py` + `book.yaml`

**book.yaml 新增**：
```yaml
exploration_mode:
  enabled: true
  until_chapter: 3
  agents: ["writer", "auditor"]  # 只保留 Writer + Auditor
  skip_polish: true
  skip_director: true
```

**BatchWriter 逻辑**：
```python
def write_chapter(self, chapter_num: int) -> WriteResult:
    if self.cfg.exploration_mode.get("enabled") and chapter_num <= self.cfg.exploration_mode.get("until_chapter", 3):
        return self._write_exploration_mode(chapter_num)
    else:
        return self._write_full_pipeline(chapter_num)

def _write_exploration_mode(self, chapter_num: int) -> WriteResult:
    """轻量模式：Writer → Validator → 内循环微调（最多2轮）。"""
    content = self._call_writer_agent(chapter_num)
    
    for attempt in range(2):
        result = self.validator.validate(content, {"chapter_num": chapter_num})
        if result.verdict == "PASS":
            break
        
        # 把 validator 反馈直接注入 writer 的 context，内循环重写
        feedback = self.validator.build_retry_feedback(result)
        content = self._call_writer_agent(chapter_num, feedback=feedback)
    
    return WriteResult(...)
```

**预期效果**：探索期单章耗时从 60–90 秒降到 15–25 秒，token 消耗降低 60%。

---

## 四、实施路线图

| 阶段 | 内容 | 预计工时 | 交付物 |
|-----|------|---------|--------|
| **Phase 1** | PromptBuilder_v2 + 写作宪法 | 4h | `prompt_builder_v2.py` |
| **Phase 2** | ChapterValidator 补全句长/IWR | 2h | 更新 `chapter_validator.py` |
| **Phase 3** | 统一对话占比口径 | 1h | 更新 `iwr_analyzer.py` |
| **Phase 4** | 动态字数 + chapter_type | 3h | 更新 `config_loader.py`, `batch_writer.py` |
| **Phase 5** | crewai/book.yaml 职责重划分 | 2h | 更新 `book.yaml`, `_build_system_prompt()` |
| **Phase 6** | 探索模式 | 2h | 更新 `batch_writer.py` |
| **Phase 7** | RAG 模板引擎（可选） | 4h | `rag_template_engine.py` |

**总工时**：18h（不含 Phase 7 为 14h）

---

## 五、验证标准

重构完成后，用第一章做回归测试：

| 指标 | 当前基线 | 目标 |
|-----|---------|------|
| 初稿合格率（无需 retry） | ~30% | **≥80%** |
| 平均 retry 次数 | 2.5 | **≤0.5** |
| 单章耗时 | 60–90s | **≤30s**（探索期） |
| IWR | 0.33（人工） | **≥2.0**（AI 初稿） |
| 句长均值 | 17.7（人工初稿） | **22–28**（AI 初稿） |
| 他密度 | 2.64%（人工初稿） | **<1.5%**（AI 初稿） |

---

## 六、一句话总结

> 不要给 AI 更多自由，要把 validator 的规则提前翻译成 AI 能听懂的"宪法"。**让 LLM 戴着镣铐跳舞，而不是跳完再给它戴手铐。**
