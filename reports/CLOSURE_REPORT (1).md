# Novel-OS 增强功能闭环修复报告

> 日期：2026-06-18  
> 背景：另一个 AI 已完成 `novel-style-db` 向量库、`StyleSkillRetriever`、增强版 `StyleRetrievalStep`、前端修复等工作，但部分增强未与流水线闭环。

---

## 一、当前状态

### 已完成的内容

| 模块 | 状态 | 说明 |
|------|------|------|
| `novel-style-db` 风格库 | ✅ | 33本小说，13个题材，位于 `.claude/skills/novel-style-db/` |
| `novel-style-guide` 风格指南 | ✅ | 5种风格详解，位于 `.claude/skills/novel-style-guide/` |
| `core/style_retriever.py` | ✅ | TF-IDF + FAISS 向量检索器 |
| `core/.style_index/` | ✅ | FAISS索引 + 元数据 + 向量化器 |
| `core/writing/steps/style_retrieval.py` | ✅ | 增强版，含场景推断 + 向量检索 |
| 前端修复 | ✅ | 页面滚动、选题持久化、分类树滚动 |
| `llm.yaml` 本地代理 | ✅ | 改为 `http://127.0.0.1:3456/v1` |

### 未闭环的内容

| 问题 | 原因 | 后果 |
|------|------|------|
| **Pipeline 未调用 StyleRetrievalStep** | `_default_steps()` 仍是7步 | 向量检索、真实小说参考完全不生效 |
| **字段注入不一致** | StyleRetrievalStep 写 `ctx.corrections["style_rules"]`，但 SceneWriter 读 `ctx.style_rules` | 即使调用 StyleRetrievalStep，内容也进不了 prompt |
| `context.py` 和 `StyleRetrievalStep` 重复生成风格规则 | 两个地方都在构建风格规则文本 | 可能重复注入或互相覆盖 |
| `llm.yaml` 代理配置可能不适用 | 默认 `127.0.0.1:3456` | 如果用户没启动代理，LLM 调用会失败 |

---

## 二、修复方案

### 总体思路

**单点负责 + Pipeline 闭环**：

```
context.py 不再生成 style_rules
        ↓
StyleRetrievalStep 统一负责：
  - 加载 core/style_guide/ 基础规则
  - 加载 .claude/skills/novel-style-guide/ 详细规则
  - 用 style_retriever.py 向量检索真实小说参考
  - 写入 ctx.style_rules
        ↓
SceneWriter / HookEngineer / DialogueTuner / Polish
  - 统一读取 ctx.style_rules
```

---

## 三、需要修改的文件

### 1. `core/writing/pipeline.py`

**修改**：`_default_steps()` 加回 `StyleRetrievalStep`

```python
@classmethod
def _default_steps(cls) -> list[PipelineStep]:
    """默认 8 阶 Steps。"""
    return [
        DirectorStep(),
        BeatPlannerStep(),
        StyleRetrievalStep(),  # 加回来：风格检索 + 向量参考
        SceneWriterStep(),
        HookEngineerStep(),
        DialogueTunerStep(),
        PolishStep(),
        AuditorStep(),
    ]
```

同时恢复 import：

```python
from core.writing.steps.style_retrieval import StyleRetrievalStep
```

### 2. `core/writing/steps/style_retrieval.py`

**修改**：`execute()` 方法末尾改为写入 `ctx.style_rules`

当前：

```python
ctx.corrections["style_rules"] = style_injection
```

改为：

```python
ctx.style_rules = style_injection
```

原因：SceneWriter 等 Step 读的是 `ctx.style_rules`。

### 3. `core/writing/context.py`

**修改**：`_build_style_rules()` 返回空字符串

```python
def _build_style_rules(self) -> str:
    """风格规则由 StyleRetrievalStep 运行时统一加载。"""
    return ""
```

原因：避免和 StyleRetrievalStep 重复生成，减少 prompt 冗余。

或者完全删除这个方法和 `style_rules=self._build_style_rules()` 调用，让 `style_rules` 默认为空字符串。

### 4. `config/llm.yaml`（二选一）

**方案A：使用本地代理**（如果用户已启动代理）

```yaml
api_key: sk-deepseek-proxy-local
base_url: http://127.0.0.1:3456/v1
```

**方案B：直连 DeepSeek 官方**（推荐，更简单）

```yaml
api_key: ${DEEPSEEK_API_KEY}
base_url: https://api.deepseek.com/v1
```

需要用户确认使用哪种。

---

## 四、修改后数据流

```
创建项目 → ChapterContext
                ↓
        ctx.style_rules = ""  （由 StyleRetrievalStep 填充）
                ↓
Pipeline:
Director → BeatPlanner → StyleRetrievalStep
                              ↓
                    1. 加载 core/style_guide/ 规则
                    2. 加载 .claude/skills/novel-style-guide/ 详细规则
                    3. 推断场景类型
                    4. style_retriever.py FAISS 检索 top-3 真实小说参考
                    5. 拼接成完整风格注入文本
                              ↓
                    ctx.style_rules = "【风格规则】+ 去AI味5条 + 同类小说参考..."
                              ↓
SceneWriter → HookEngineer → DialogueTuner → Polish
       ↓           ↓              ↓            ↓
  读取 ctx.style_rules 注入 prompt
```

---

## 五、验证步骤

### 1. Python 语法检查

```bash
cd e:/1/NoveOs-master/NoveOs-master/novel-os
python -m py_compile core/writing/pipeline.py
python -m py_compile core/writing/steps/style_retrieval.py
python -m py_compile core/writing/context.py
```

### 2. Pipeline 步骤检查

确认输出为8步：

```python
['Director', 'BeatPlanner', 'StyleRetrieval', 'SceneWriter', 'HookEngineer', 'DialogueTuner', 'Polish', 'Auditor']
```

### 3. 风格规则注入检查

运行一次单章写作测试，查看日志中：

```
[StyleRetrieval] 第 X 章 题材=XX → ...
```

并检查 prompt 日志中是否包含：

- `【风格规则】`
- `=== 去AI味核心规则 ===`
- `=== 同类小说风格参考 ===`

### 4. 向量索引可用性检查

```bash
cd e:/1/NoveOs-master/NoveOs-master/novel-os
python -m core.style_retriever --test
```

---

## 六、风险与注意事项

| 风险 | 说明 |
|------|------|
| Prompt 过长 | 向量检索参考可能让 prompt 增加 1000-2000 字，需注意 token 成本 |
| FAISS 索引过期 | `data/` 新增小说后需重建：`python -m core.style_retriever --build` |
| 本地代理可用性 | 如果用 `127.0.0.1:3456`，必须确保代理服务已启动 |
| StyleRetrievalStep 失败影响 | 如果该 Step 失败，`ctx.style_rules` 为空，后续 Step 仍能运行但无风格参考 |

---

## 七、建议执行顺序

1. **确认 `llm.yaml` 代理方案**（用户决定用本地代理还是官方 API）
2. **修改 `pipeline.py` 加回 StyleRetrievalStep**
3. **修改 `style_retrieval.py` 写入 `ctx.style_rules`**
4. **修改 `context.py` 不再预构建风格规则**
5. **运行验证步骤**

---

*状态：待执行修复*
