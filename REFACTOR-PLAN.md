# Novel-OS 重构方案 v1.0

> **目标**：在不引入任何外部框架的前提下，将 `batch_writer.py`（1972 行）和 `state_manager.py`（1174 行）拆分为职责单一的模块，使 Novel-OS 从"脚本集合"进化为"可维护的领域系统"。
>
> **周期**：2 周（分 5 个 Phase，每 Phase 2-3 天）
>
> **风险**：低。不更换技术栈，不改动数据库 Schema，不改动前端接口。

---

## 一、当前架构诊断

### 1.1 核心问题

| 文件 | 行数 | 类数 | 问题 |
|------|------|------|------|
| `core/batch_writer.py` | 1972 | 2 | God Class，10 阶流水线 + 文本清洗 + 标题提取 + 字数统计 + 保存逻辑全塞在一个类里 |
| `core/state_manager.py` | 1174 | 1 | God Class，12 张表的 CRUD + Schema 迁移 + 业务查询全在一个类里 |
| `core/orchestrator.py` | 712 | 2 | 项目生命周期 + 线程池 + 全局 DB + 事件总线 + 外层 Crew 调度 |
| `core/chapter_validator.py` | 681 | ~5 | 相对独立，但和 `batch_writer` 有双向依赖 |

### 1.2 依赖关系图（简化）

```
batch_writer ──→ state_manager ──→ sqlite
      │               ↑
      ├────→ chapter_validator ──┤
      │               │
      ├────→ llm_client ─────────┤
      │               │
      └────→ orchestrator ←──────┘
```

**问题**：`batch_writer` 是中心节点，所有模块都直接或间接依赖它。改一行 `batch_writer`，可能触发连锁反应。

### 1.3 测试现状

- 7 个测试文件，其中 `test_guard_registry.py` 因模块不存在而 **ImportError**
- 没有单元测试覆盖 `batch_writer` 的核心流水线
- 没有 Mock LLM 调用，所有测试如果跑了会消耗真实 API Token

---

## 二、目标架构：四层模型

```
┌─────────────────────────────────────────────────────────────┐
│  接口层 (API + CLI)                                         │
│  FastAPI Routers / cli.py                                   │
├─────────────────────────────────────────────────────────────┤
│  应用层 (Application)                                       │
│  Orchestrator / ProjectService / WritingService             │
├─────────────────────────────────────────────────────────────┤
│  领域层 (Domain)                                            │
│  ├─ writing/     写作流水线 (Steps + Pipeline)               │
│  ├─ validation/  质量门禁 (Validator + Guards)               │
│  ├─ state/       状态管理 (Repositories + UoW)               │
│  ├─ content/     文本处理 (Sanitizer + Metrics + Title)      │
│  └─ orchestration/ 调度 (Events + Scheduler)                │
├─────────────────────────────────────────────────────────────┤
│  基础设施层 (Infrastructure)                                │
│  LLMClient / PromptBuilder / ConfigLoader / EventBus        │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 目录结构

```
novel-os/
├── core/                          # 领域层
│   ├── writing/
│   │   ├── pipeline.py            # 流水线编排 (~150 行)
│   │   ├── context.py             # 章节上下文构建 (~100 行)
│   │   ├── output.py              # WriteResult / 输出处理 (~50 行)
│   │   └── steps/
│   │       ├── base.py            # PipelineStep 基类 (~40 行)
│   │       ├── director.py        # (~80 行)
│   │       ├── beat_planner.py    # (~60 行)
│   │       ├── scene_writer.py    # (~120 行)
│   │       ├── hook_engineer.py   # (~80 行)
│   │       ├── dialogue_tuner.py  # (~80 行)
│   │       ├── polish.py          # (~60 行)
│   │       ├── auditor.py         # (~60 行)
│   │       ├── expander.py        # (~50 行)
│   │       └── spot_fix.py        # (~60 行)
│   │
│   ├── validation/
│   │   ├── models.py              # ValidationResult / Issue / Metric
│   │   ├── chapter_validator.py   # (迁移现有，精简接口)
│   │   ├── post_validator.py      # (迁移现有)
│   │   ├── anti_detect.py         # (迁移现有)
│   │   └── guards/                # (迁移现有)
│   │
│   ├── state/
│   │   ├── models.py              # 领域模型 dataclasses
│   │   ├── unit_of_work.py        # 事务管理
│   │   └── repositories/
│   │       ├── base.py            # Repository 基类 + 接口
│   │       ├── project.py         # projects 表
│   │       ├── character.py       # character_states 表
│   │       ├── chapter.py         # chapter_history + chapter_snapshots
│   │       ├── debt.py            # debts 表
│   │       ├── foreshadowing.py   # foreshadowing 表
│   │       ├── item.py            # item_states 表
│   │       └── cast.py            # cast_schedule 表
│   │
│   ├── content/
│   │   ├── metrics.py             # 字数 / 他字密度 / 句长统计
│   │   ├── sanitizer.py           # 文本清洗 (原 _sanitize_content)
│   │   ├── title.py               # 标题提取 / 验证 / 插入
│   │   └── formatter.py           # 段落拆分 / 格式化
│   │
│   └── orchestration/
│       ├── models.py              # ProjectRuntime dataclass
│       ├── events.py              # 事件类型定义
│       └── scheduler.py           # 任务调度抽象
│
├── infrastructure/                # 基础设施层
│   ├── llm.py                     # LLMClient (精简接口)
│   ├── prompts.py                 # PromptBuilder
│   ├── config.py                  # BookConfig / 配置加载
│   ├── event_bus.py               # EventBus (现有，微调)
│   └── persistence.py             # SQLite 连接池 / 上下文管理
│
├── api/                           # 接口层 (现有，逐步迁移)
├── plugins/                       # 插件 (现有，不变)
├── platforms/                     # 平台规则 (现有，不变)
├── tests/
│   ├── unit/                      # 单元测试 (每个领域模块独立)
│   ├── integration/               # 集成测试 (端到端流水线)
│   └── fixtures/                  # Mock 数据 / Fake LLM
├── cli.py                         # 命令行入口
└── pyproject.toml
```

---

## 三、关键设计决策

### 3.1 写作流水线：Step 模式

每个 Agent 调用封装为独立的 `PipelineStep`，统一接口：

```python
class PipelineStep(ABC):
    name: str
    
    @abstractmethod
    def execute(self, ctx: ChapterContext) -> StepResult:
        """执行本步骤，返回结果或抛出 StepFailure"""
        ...
    
    def fallback(self, ctx: ChapterContext, error: StepFailure) -> str | None:
        """失败时的回退策略，返回修正指令或 None（交给上层重试）"""
        return None
```

**为什么不用函数而用类？**
- 每个 Step 需要持有自己的配置（temperature、max_tokens、system prompt 模板）
- 需要状态（如 `Director` 第一次生成后重试时复用）
- 需要独立的日志和事件发射

### 3.2 状态管理：Repository 模式

按表拆分，每个 Repository 只负责一张表的 CRUD：

```python
class BaseRepository(ABC):
    def __init__(self, conn: sqlite3.Connection, project_id: str): ...

class CharacterRepository(BaseRepository):
    def get_latest(self, character_name: str) -> CharacterState | None: ...
    def save(self, chapter: int, state: CharacterState) -> None: ...
    def get_all_at_chapter(self, chapter: int) -> list[CharacterState]: ...
```

**兼容策略**：旧的 `StateManager` 暂时保留，内部调用新的 Repositories，逐步迁移。

### 3.3 内容处理：纯函数优先

文本清洗、字数统计、标题提取等操作**无状态、无副作用**，全部设计为纯函数：

```python
# core/content/metrics.py
def count_chinese_chars(text: str) -> int: ...
def ta_density(text: str) -> float: ...
def sentence_length_avg(text: str) -> float: ...

# core/content/sanitizer.py  
def sanitize(text: str, rules: SanitizerRules) -> str: ...
```

### 3.4 校验域：策略模式

质量门禁统一为 `Validator` 接口：

```python
class Validator(ABC):
    @abstractmethod
    def validate(self, content: str, context: ValidationContext) -> ValidationResult: ...

class ChapterValidator(Validator): ...      # 字数 / 他字密度 / 禁用词
class PostWriteValidator(Validator): ...    # 零成本预检
class AntiDetectValidator(Validator): ...   # AI 痕迹检测
```

---

## 四、数据流重构

### 4.1 当前数据流（混乱）

```
Orchestrator → BatchWriter.write_chapter()
                    ↓
              [直接操作 state_manager 查询]
                    ↓
              [直接调用 llm_client]
                    ↓
              [直接修改 corrections 字典]
                    ↓
              [直接保存文件]
                    ↓
              [直接更新 state_manager]
```

### 4.2 目标数据流（清晰）

```
Orchestrator → WritingService.write_chapter(num)
                    ↓
              ChapterContextBuilder.build(num) ──→ State Repositories
                    ↓
              WritingPipeline.execute(ctx)
                    ↓
              ├─ DirectorStep ──→ LLM Service
              ├─ BeatPlannerStep ──→ LLM Service
              ├─ SceneWriterStep ──→ LLM Service
              ├─ HookEngineerStep ──→ LLM Service (条件)
              ├─ DialogueTunerStep ──→ LLM Service (条件)
              ├─ PolishStep ──→ LLM Service (条件)
              ├─ AuditorStep ──→ LLM Service
              └─ ValidationChain ──→ Validators
                    ↓
              ContentService.save(ctx, result) ──→ FileSystem
                    ↓
              StateService.update(ctx, result) ──→ State Repositories
                    ↓
              EventBus.emit(CHAPTER_COMPLETE)
```

**关键变化**：
1. `BatchWriter` 不再直接操作数据库和文件系统，通过 Service 层委托
2. 每个 Step 只接收 `ChapterContext`，不直接访问 `StateManager`
3. 校验逻辑统一走 `ValidationChain`，不散落在流水线各处

---

## 五、Phase-by-Phase 实施计划

### Phase 1: 基础设施 + 内容域（第 1-2 天）

**目标**：建立最独立的模块，零风险验证新架构。

**任务清单**：
- [ ] 创建 `core/content/` 目录
- [ ] 提取 `metrics.py`：字数统计、他字密度、句长、对话占比
- [ ] 提取 `sanitizer.py`：文本清洗（从 `_sanitize_content` 迁移）
- [ ] 提取 `title.py`：标题提取/验证/插入（从 `_extract_title` / `_ensure_title_prefix` 迁移）
- [ ] 提取 `formatter.py`：段落拆分（从 `_split_long_paragraphs` 迁移）
- [ ] 为每个模块写单元测试（纯函数，容易测）
- [ ] 在 `batch_writer.py` 中用新模块替换旧方法（import 替换）

**验收标准**：
- `pytest core/content/` 全部通过
- `batch_writer.py` 行数减少 ~300 行
- 端到端写一章验证无 regression

### Phase 2: 状态域拆分（第 3-5 天）

**目标**：把 `state_manager.py` 从 1174 行拆为 8 个 Repository + 1 个 UoW。

**任务清单**：
- [ ] 创建 `core/state/models.py`，定义 `CharacterState`、`Debt`、`Foreshadowing` 等 dataclass
- [ ] 创建 `core/state/repositories/base.py`，定义 `BaseRepository`
- [ ] 逐个迁移表：
  - `projects` → `ProjectRepository`
  - `character_states` → `CharacterRepository`
  - `debts` → `DebtRepository`
  - `foreshadowing` → `ForeshadowingRepository`
  - `chapter_history` + `chapter_snapshots` → `ChapterRepository`
  - `item_states` → `ItemRepository`
  - `cast_schedule` → `CastRepository`
- [ ] 创建 `core/state/unit_of_work.py`，管理事务边界
- [ ] **兼容层**：修改 `StateManager`，内部调用 Repositories，保持对外接口不变

**验收标准**：
- `StateManager` 所有方法仍然可用（现有测试/代码不 break）
- 新增 `pytest core/state/` 单元测试，覆盖每个 Repository
- 端到端初始化一本书 + 写一章无 regression

### Phase 3: 写作域拆分（第 6-9 天）

**目标**：把 `batch_writer.py` 的 10 阶流水线拆为独立的 Steps。

**任务清单**：
- [ ] 创建 `core/writing/steps/base.py`，定义 `PipelineStep` 基类
- [ ] 创建 `core/writing/context.py`，定义 `ChapterContext` dataclass
- [ ] 逐个迁移 Agent 调用：
  - `_call_director` → `DirectorStep`
  - `_call_beat_planner` → `BeatPlannerStep`
  - `_call_scene_writer` → `SceneWriterStep`
  - `_call_hook_engineer` → `HookEngineerStep`
  - `_call_dialogue_tuner` → `DialogueTunerStep`
  - `_call_polish` → `PolishStep`
  - `_call_auditor` → `AuditorStep`
  - `_call_expander` → `ExpanderStep`
  - `_call_spot_fix` → `SpotFixStep`
- [ ] 创建 `core/writing/pipeline.py`，实现 `WritingPipeline` 编排逻辑
- [ ] 创建 `core/writing/output.py`，定义 `WriteResult`
- [ ] 重写 `batch_writer.py`：保留 `BatchWriter` 类名，内部委托给 `WritingPipeline`

**验收标准**：
- `batch_writer.py` 行数 < 500 行
- 每个 Step 独立可测（用 Fake LLM）
- 端到端写 3 章无 regression

### Phase 4: 校验域整理（第 10-11 天）

**目标**：统一校验接口，消除 `batch_writer` 和 `validator` 的双向依赖。

**任务清单**：
- [ ] 创建 `core/validation/models.py`，统一 `ValidationResult` / `ValidationIssue`
- [ ] 重构 `ChapterValidator`，实现 `Validator` 接口
- [ ] 重构 `PostWriteValidator`，实现 `Validator` 接口
- [ ] 重构 `AntiDetectReviser`，拆分为 `AntiDetectValidator` + `AntiDetectReviser`
- [ ] 创建 `core/validation/chain.py`，实现 `ValidationChain`（按顺序执行多个 Validator）
- [ ] 在 `WritingPipeline` 中集成 `ValidationChain`

**验收标准**：
- `batch_writer` 不再直接引用 `ChapterValidator` 内部类
- 校验器可独立测试（传入文本即可，不需要 StateManager）
- 端到端触发一次 BLOCK 场景，验证修正逻辑正常

### Phase 5: 调度层 + 集成测试（第 12-14 天）

**目标**：整理 Orchestrator，补全测试，删除旧代码。

**任务清单**：
- [ ] 重构 `orchestrator.py`，提取 `ProjectService` 和 `WritingService`
- [ ] 删除 `batch_writer.py` 中被替换的旧方法（确认无引用后删除）
- [ ] 删除 `state_manager.py` 中被迁移的旧方法（确认无引用后删除）
- [ ] 修复 `tests/test_guard_registry.py` 的 ImportError
- [ ] 为 `WritingPipeline` 写集成测试（用 Fake LLM，不消耗 Token）
- [ ] 为 `Orchestrator` 写集成测试（多项目注册/调度）
- [ ] 更新 `pyproject.toml` 的测试配置

**验收标准**：
- `pytest tests/` 全部通过
- `batch_writer.py` 最终行数 < 300 行（或完全删除，由 `WritingPipeline` 替代）
- `state_manager.py` 最终行数 < 200 行（或作为兼容 facade 保留）
- 写一本测试书（5 章）端到端通过

---

## 六、接口契约

### 6.1 PipelineStep 基类

```python
@dataclass
class StepResult:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    skip_subsequent: bool = False  # 如 HookEngineer 跳过则后续也跳过

@dataclass
class StepFailure(Exception):
    step_name: str
    reason: str
    correction_hint: str = ""
    retryable: bool = True

class PipelineStep(ABC):
    name: str = ""
    
    @abstractmethod
    def execute(self, ctx: ChapterContext) -> StepResult:
        ...
    
    def fallback(self, ctx: ChapterContext, failure: StepFailure) -> str | None:
        return failure.correction_hint or None
```

### 6.2 ChapterContext

```python
@dataclass
class ChapterContext:
    chapter_num: int
    project_id: str
    book_config: BookConfig
    
    # 由 ContextBuilder 填充的查询结果
    outline: ChapterOutline
    prev_summary: str
    character_states: list[CharacterState]
    consistency_rules: list[str]
    debts: list[Debt]
    foreshadowing: list[Foreshadowing]
    
    # 流水线中间状态
    director_prompt: str = ""
    beat_plan: str = ""
    corrections: dict[str, str] = field(default_factory=dict)
    
    # 运行时依赖（通过依赖注入，不直接实例化）
    llm: LLMService = field(repr=False)
    state: StateService = field(repr=False)
```

### 6.3 Repository 基类

```python
class BaseRepository:
    def __init__(self, conn: sqlite3.Connection, project_id: str):
        self._conn = conn
        self._project_id = project_id
    
    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

class UnitOfWork:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
    
    def __enter__(self):
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA foreign_keys = ON")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()
    
    @property
    def characters(self) -> CharacterRepository:
        return CharacterRepository(self._conn, self._project_id)
    
    # ... 其他 repositories
```

### 6.4 Validator 接口

```python
@dataclass
class ValidationContext:
    chapter_num: int
    word_count: int
    outline: ChapterOutline | None = None

class Validator(ABC):
    @abstractmethod
    def validate(self, content: str, ctx: ValidationContext) -> ValidationResult: ...

class ValidationChain:
    def __init__(self, validators: list[Validator]):
        self._validators = validators
    
    def validate(self, content: str, ctx: ValidationContext) -> ValidationResult:
        all_issues = []
        for v in self._validators:
            result = v.validate(content, ctx)
            all_issues.extend(result.issues)
        # 合并结果...
        return ValidationResult(issues=all_issues)
```

---

## 七、风险与回退策略

| 风险 | 概率 | 影响 | 回退策略 |
|------|------|------|----------|
| Phase 3 拆 Step 时引入 Bug | 中 | 高 | 保留原 `batch_writer.py` 为 `batch_writer_legacy.py`，发现问题立即切换 |
| Repository 拆分后性能下降（多次查询） | 低 | 中 | 在 UoW 层增加查询缓存，或合并高频查询 |
| 测试覆盖不足导致 regression | 中 | 高 | 每 Phase 必须端到端验证（写 3 章真章）才能进入下一 Phase |
| 前端 API 因后端结构调整 break | 低 | 高 | API Router 层保持不变，只改 core 内部实现 |
| 时间不够，14 天做不完 | 高 | 中 | 按 Phase 优先级执行，Phase 3（写作域）必须完成，Phase 5 可延后 |

---

## 八、验收检查清单

重构完成后的 Novel-OS 应该满足：

- [ ] `core/` 下没有超过 300 行的文件（除测试外）
- [ ] `pytest tests/` 全部通过，且包含 Fake LLM 的集成测试
- [ ] 新增一本小说的流程（init → import → write 5 章）能在 30 分钟内跑完
- [ ] 修改一个 Agent 的 Prompt 不需要读超过 100 行代码
- [ ] 新增一个 Validator（如"禁止连续 3 章无感情线"）只需新建一个类并注册到 Chain
- [ ] 新增一个 Repository（如"战斗记录表"）只需继承 `BaseRepository`

---

*方案设计完成。下一步：按 Phase 1 开始执行，或根据反馈调整架构设计。*
