# Novel-OS 重构迁移指南

> 配合 `REFACTOR-PLAN.md` 使用。本文档给出每一步的具体操作命令和代码迁移示例。

---

## 准备工作

```bash
cd novel-os

# 1. 创建特性分支（必须用分支，方便回退）
git checkout -b refactor/v2.0

# 2. 备份当前核心文件（一旦重构出问题，5 秒回退）
cp core/batch_writer.py core/batch_writer.py.bak
cp core/state_manager.py core/state_manager.py.bak
cp core/orchestrator.py core/orchestrator.py.bak

# 3. 确认当前能跑通（基准线）
python cli.py --book book.yaml write --chapter 1
```

**原则**：每 Phase 结束后必须跑通 `write --chapter 1`，否则不进入下一 Phase。

---

## Phase 1：内容域提取（Day 1-2）

### Step 1.1 创建目录

```bash
mkdir -p core/content
mkdir -p core/writing/steps
mkdir -p core/state/repositories
mkdir -p core/validation
mkdir -p infrastructure
mkdir -p tests/fixtures
touch core/content/__init__.py
touch core/writing/__init__.py
touch core/writing/steps/__init__.py
touch core/state/__init__.py
touch core/state/repositories/__init__.py
touch core/validation/__init__.py
touch infrastructure/__init__.py
```

### Step 1.2 迁移文本指标

**原代码位置**：`batch_writer.py` 中的 `_count_chinese_chars`（第 962 行）

**操作**：
1. 创建 `core/content/metrics.py`，把 `_count_chinese_chars` 迁移为 `count_chinese_chars`
2. 在 `batch_writer.py` 顶部添加 `from core.content.metrics import count_chinese_chars`
3. 删除 `batch_writer.py` 中的 `_count_chinese_chars` 方法

**验证**：
```bash
python -c "from core.content.metrics import count_chinese_chars; print(count_chinese_chars('测试中文字数'))"
# 期望输出: 6
```

### Step 1.3 迁移文本清洗

**原代码位置**：`batch_writer.py` 中的 `_sanitize_content`（第 536 行，~40 行逻辑）

**操作**：
1. 创建 `core/content/sanitizer.py`
2. 把 `_sanitize_content` 的逻辑搬过去，包装为 `Sanitizer` 类
3. 在 `batch_writer.py` 中：
   ```python
   from core.content.sanitizer import Sanitizer
   # __init__ 中
   self._sanitizer = Sanitizer()
   # save_chapter 中
   content = self._sanitizer.sanitize(content)
   ```
4. 删除 `_sanitize_content`、`_replace_english_terms`、`_limit_sudden`

### Step 1.4 迁移标题处理

**原代码位置**：`batch_writer.py` 中的 `_extract_title`、`_ensure_title_prefix`、`_extract_title_from_director`、`_save_chapter_title`

**操作**：
1. 创建 `core/content/title.py`
2. 迁移上述 4 个方法为纯函数
3. 在 `batch_writer.py` 中替换调用

### Step 1.5 写测试

```bash
# 创建 tests/unit/test_content.py
pytest tests/unit/test_content.py -v
```

**Phase 1 验收**：
- [ ] `batch_writer.py` 行数减少 > 200 行
- [ ] `python cli.py --book book.yaml write --chapter 1` 正常输出
- [ ] `pytest tests/unit/test_content.py` 通过

---

## Phase 2：状态域拆分（Day 3-5）

### Step 2.1 创建领域模型

创建 `core/state/models.py`，定义 dataclass：
- `ProjectInfo`
- `CharacterState`
- `ChapterOutline`
- `Debt`
- `Foreshadowing`
- `ChapterHistory`
- `ItemState`

### Step 2.2 创建 Repository 基类

创建 `core/state/repositories/base.py`：
- `BaseRepository`
- `UnitOfWork`

### Step 2.3 逐个迁移表

以 `character_states` 为例：

**原代码**（`state_manager.py` 中分散的多处）：
```python
# 查询人物状态
conn.execute(
    "SELECT * FROM character_states WHERE project_id=? AND character_name=? ORDER BY chapter DESC LIMIT 1",
    (self.project_id, name)
)
```

**新代码**：
```python
# core/state/repositories/character.py
class CharacterRepository(BaseRepository):
    def get_latest(self, character_name: str) -> CharacterState | None:
        row = self._fetchone("SELECT * FROM character_states WHERE project_id=? AND character_name=? ORDER BY chapter DESC LIMIT 1",
                             (self._project_id, character_name))
        return self._row_to_model(row) if row else None
```

**兼容层修改**（`state_manager.py`）：
```python
# 在 StateManager.__init__ 中
self._character_repo = CharacterRepository(self._connect(), self.project_id)

# 替换原来的直接 SQL
def get_character_latest(self, name: str) -> dict | None:
    state = self._character_repo.get_latest(name)
    return state.__dict__ if state else None
```

> **关键**：`StateManager` 的**对外接口不变**，内部调用 Repository。这样现有代码不 break。

### Step 2.4 迁移顺序

按依赖复杂度从低到高：
1. `projects` → `ProjectRepository`（最简单，无依赖）
2. `character_states` → `CharacterRepository`
3. `item_states` → `ItemRepository`
4. `debts` → `DebtRepository`
5. `foreshadowing` → `ForeshadowingRepository`
6. `chapter_history` + `chapter_snapshots` → `ChapterRepository`
7. `cast_schedule` → `CastRepository`

### Step 2.5 写测试

```python
# tests/unit/test_repositories.py
from core.state.unit_of_work import UnitOfWork
from core.state.models import CharacterState

def test_character_repository(tmp_path):
    db = tmp_path / "test.db"
    with UnitOfWork(db, "test_project") as uow:
        uow.characters.save(1, CharacterState(name="张三", chapter=1, location="北京"))
        result = uow.characters.get_latest("张三")
        assert result.location == "北京"
```

**Phase 2 验收**：
- [ ] `StateManager` 所有现有方法仍可用
- [ ] `pytest tests/unit/test_repositories.py` 通过
- [ ] 初始化一本书 + 写一章无 regression

---

## Phase 3：写作域拆分（Day 6-9）

这是最复杂的 Phase，**必须在分支上做，随时可回退**。

### Step 3.1 定义 Step 基类

创建 `core/writing/steps/base.py`：
```python
class PipelineStep(ABC):
    name: str = ""
    @abstractmethod
    def execute(self, ctx: ChapterContext) -> StepResult: ...
```

### Step 3.2 定义 ChapterContext

创建 `core/writing/context.py`，把 `_build_chapter_context` 的逻辑搬过来。

### Step 3.3 逐个迁移 Agent 调用

以 `Director` 为例：

**原代码**（`batch_writer.py` 第 1218 行 `_call_director`）：
```python
def _call_director(self, chapter_num: int, context: dict[str, Any]) -> str:
    system = self._build_system_prompt("director")
    user = self._build_task_user_prompt("director", chapter_num)
    result = self.llm.call_for_agent("director", system, user)
    return result
```

**新代码**（`core/writing/steps/director.py`）：
```python
class DirectorStep(PipelineStep):
    name = "Director"
    def execute(self, ctx: ChapterContext) -> StepResult:
        system = self._build_system(ctx)
        user = self._build_user(ctx)
        result = ctx.llm.complete(system, user)
        ctx.director_prompt = result
        return StepResult(content=result)
```

### Step 3.4 重写 Pipeline 编排

创建 `core/writing/pipeline.py`，把 `_write_full_pipeline` 的主循环搬过来：

```python
class WritingPipeline:
    def execute(self, ctx: ChapterContext) -> WriteResult:
        for step in self._steps:
            result = step.execute(ctx)
            content = result.content
        # ... 校验 ... 重试 ...
```

### Step 3.5 改造 BatchWriter 为 Facade

```python
# batch_writer.py（精简后）
class BatchWriter:
    def __init__(self, book_config, ...):
        self._pipeline = WritingPipeline(...)
        self._ctx_builder = ChapterContextBuilder(...)
    
    def write_chapter(self, chapter_num: int) -> WriteResult:
        ctx = self._ctx_builder.build(chapter_num)
        return self._pipeline.execute(ctx)
```

**Phase 3 验收**：
- [ ] `batch_writer.py` 行数 < 500
- [ ] 每个 Step 可以用 Fake LLM 独立测试
- [ ] 写 3 章无 regression

---

## Phase 4：校验域整理（Day 10-11）

### Step 4.1 统一校验接口

```python
# core/validation/models.py
class Validator(ABC):
    @abstractmethod
    def validate(self, content: str, ctx: ValidationContext) -> ValidationResult: ...
```

### Step 4.2 改造现有校验器

把 `ChapterValidator` 改造为：
```python
class ChapterValidator(Validator):
    def validate(self, content: str, ctx: ValidationContext) -> ValidationResult:
        # 原有逻辑，但接口统一
```

### Step 4.3 组装校验链

```python
chain = ValidationChain([
    WordCountValidator(),
    TaDensityValidator(),
    ForbiddenWordValidator(),
    IWRValidator(),
    PlatformDNAValidator(),
])
```

**Phase 4 验收**：
- [ ] `batch_writer` 不再直接引用 `ChapterValidator` 内部类
- [ ] 触发一次 BLOCK 场景，修正逻辑正常

---

## Phase 5：清理与测试（Day 12-14）

### Step 5.1 删除死代码

```bash
# 确认无引用后删除 batch_writer.py 中的旧方法
grep -n "_call_director\|_call_beat_planner\|_call_scene_writer" core/batch_writer.py
# 应该只剩 import 或不再出现
```

### Step 5.2 修复测试

```python
# tests/test_guard_registry.py
# 如果 InterceptorGuard 已不存在，删除或替换为新的 Guard 测试
```

### Step 5.3 写集成测试

```python
# tests/integration/test_pipeline.py
from tests.fixtures.fake_llm import FakeLLMService
from core.writing.pipeline import WritingPipeline

def test_pipeline_with_fake_llm():
    fake = FakeLLMService()
    fake.when(system_contains="Director").then_return("【标题】第1章：测试\n核心事件：主角醒来")
    fake.when(system_contains="SceneWriter").then_return("第1章：测试\n\n主角醒来了。天亮了。")
    
    pipeline = WritingPipeline(llm=fake)
    result = pipeline.execute(build_test_context())
    
    assert result.success
    assert result.word_count > 0
    assert fake.get_call_count() >= 2
```

### Step 5.4 最终验证

```bash
# 1. 全部测试通过
pytest tests/ -q

# 2. 端到端验证
python cli.py --book book.yaml write --range 1:3

# 3. 行数检查
wc -l core/batch_writer.py core/state_manager.py
# 期望：batch_writer < 300, state_manager < 200
```

**Phase 5 验收**：
- [ ] `pytest tests/` 全部通过
- [ ] 核心文件行数达标
- [ ] 写一本测试书（5章）通过

---

## 回退策略

如果任何 Phase 出现问题，**不要硬修**，直接回退：

```bash
# 回退单个文件
git checkout core/batch_writer.py.bak core/batch_writer.py

# 回退整个分支
git checkout main
git branch -D refactor/v2.0
```

---

## 常见问题

### Q: 迁移期间代码不能运行怎么办？

**A**: 每 Phase 都是增量迁移，旧代码和新代码共存。例如 Phase 2 中 `StateManager` 保留为兼容层，所有现有调用点不变。只有全部测试通过后，才删除旧方法。

### Q: 新写的 Repository 性能不如原来一个 SQL 查询怎么办？

**A**: Repository 封装的是**单表 CRUD**。复杂的跨表查询（如"查询某章涉及的所有人物+债务+伏笔"）应该在 Service 层或 ContextBuilder 中写原生 SQL，而不是强行拆成 3 次查询。

### Q: 团队成员看不懂新架构怎么办？

**A**: 新架构的规则很简单：
- 想改 Agent 行为 → 找 `core/writing/steps/xxx.py`
- 想改数据库查询 → 找 `core/state/repositories/xxx.py`
- 想改校验规则 → 找 `core/validation/xxx.py`
- 不要碰 `batch_writer.py`（它已经是壳了）
