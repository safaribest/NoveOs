# Novel-OS 优化与修改报告

> 日期：2026-06-18  
> 项目：E:\1\NoveOs-master\NoveOs-master

---

## 一、风格参考库：novel-style-db（Layer 1.5）

### 做了什么

用 book-to-skill 思路，将 `data/` 目录下 35 本网文小说的写作风格提取为结构化技能文件。

### 产出

```
.claude/skills/novel-style-db/
├── 军事/(2)  历史/(3)  恐怖/(3)  武侠/(3)  玄幻/(3)
├── 科幻/(2)  穿越/(2)  竞技/(3)  网游/(1)  美文/(3)
├── 腹黑/(3)  言情/(2)  都市/(3)
└── 共 33 本, 13 品类

每本包含:
  SKILL.md      — 风格DNA + 核心技法 + 代表性片段 + 语汇特征 + 适用场景
  patterns.md   — 写作技法模式
  glossary.md   — 特色词汇/表达方式
```

### 关键决策

- 用 TF-IDF + FAISS 而非 sentence-transformers，避免下载 ~2GB 模型依赖
- 每品类 2-3 本参考，每个 SKILL.md 8-12KB
- 路径从全局 `~/.claude/skills/` 移到项目内 `.claude/skills/`

---

## 二、向量检索器：StyleSkillRetriever（Layer 2）

### 做了什么

将 33 本小说 SKILL.md 解析为 445 个风格片段，按场景类型分类（战斗/对话/描写/情绪/设定/综合），构建 TF-IDF + FAISS 向量索引。

### 产出

```
novel-os/core/
├── style_retriever.py          ← StyleSkillRetriever 检索类
└── .style_index/
    ├── style_index.faiss       ← FAISS 索引 (445 vectors, dim=1024)
    ├── style_metadata.json     ← 片段元数据
    └── vectorizer.pkl          ← TF-IDF 向量化器
```

### 效果

| 查询 | 结果 |
|------|------|
| 玄幻 + 战斗 + "主角施展武技" | 《斗罗大陆》动作肢解 (score=1.30) + 《血狱魔帝》以弱胜强循环 (1.05) |
| 都市 + 情绪 + "主角感到愤怒" | 《都市逍遥神》围观群众反应 (0.97) + 《致命交易》省略号断句法 (0.89) |
| 言情 + 对话 + "男女主对话" | 《指缝间的幸福》青梅竹马示爱 (0.98) |

### 运行方式

```
首次构建: python -m core.style_retriever --build
测试检索: python -m core.style_retriever --test
```

---

## 三、StyleRetrievalStep 集成

### 改动文件

[style_retrieval.py](novel-os/core/writing/steps/style_retrieval.py)

### 改动内容

| 改动前 | 改动后 |
|--------|--------|
| 只从 `style_guide/` 加载 5 种固定规则 | 增加了 novel-style-db 真实小说参考 |
| 无场景区分，同品类全部注入 | 从大纲推断场景类型，向量检索匹配片段 |
| 注入 prompt ~1500 字符 | 精准检索 ~1000 字符，相关性更高 |
| 全品类加载 ~2500 字符 | 按场景检索 ~1000 字符 |

### 新增方法

- `_infer_scene(ctx)` — 从章节大纲的 core_event/title/chapter_hook 推断当前章场景类型
- `_retrieve_novel_refs(genre, scene_type, description)` — 向量检索优先，不可用时回退全量加载

### 场景推断逻辑

从大纲关键词推断 5 种场景类型：

| 场景类型 | 触发关键词 |
|---------|-----------|
| 战斗 | 对决、比试、击杀、剑、拳、掌、袭 |
| 对话 | 谈判、质问、揭秘、坦白、问、答 |
| 情绪 | 愤怒、悲伤、恐惧、哭泣、泪、恨 |
| 描写 | 环境、氛围、夜、雨、风、雪、晨 |
| 设定 | 修炼、突破、觉醒、解锁、魂、境 |

---

## 四、LLM 配置修复

### 问题 1：API 认证失败 (401)

**根因**：`llm.yaml` 中 API key 写的是 `${DEEPSEEK_API_KEY}` 占位符，代码未展开环境变量。

**修复**：

1. [llm_settings_client.py](novel-os/core/llm_settings_client.py) — `_get_provider_config()` 增加 `_expand_env()` 函数，自动展开 `${VAR}` 引用
2. [llm.yaml](novel-os/config/llm.yaml) — 改用本地代理 `http://127.0.0.1:3456/v1`，绕过 API key 问题

### 问题 2：前端代理端口不匹配

**根因**：Vite 配置代理到端口 8001，手动启动了后端在 8000。

**修复**：后端改为启动在 8001 端口。

---

## 五、前端修复

### 1. 页面无法滚动

**根因**：[app-shell.tsx](novel-os/frontend/src/components/layout/app-shell.tsx) 内容容器设了 `overflow-hidden`。

**修复**：改为 `overflow-y-auto`。

### 2. 刷新后选题丢失

**根因**：选题结果只存组件 state，刷新后重新触发 LLM 生成。

**修复**：[topics-page.tsx](novel-os/frontend/src/pages/create/topics-page.tsx)
- 选题结果写入 localStorage（key: `novel-os:topics-draft`）
- 挂载时从 localStorage 恢复
- 已有数据时跳过重新生成和轮询

### 3. 分类树无滚动

**根因**：[category-page.tsx](novel-os/frontend/src/pages/create/category-page.tsx) 左右面板无 overflow 控制。

**修复**：左侧分类树和右侧叶子分类增加 `max-h + overflow-y-auto`。

---

## 六、项目目录整理

### 做了什么

| 操作 | 从 | 到 |
|------|----|----|
| 技能数据迁移 | `~/.claude/skills/novel-style-db/` | `.claude/skills/novel-style-db/` |
| 技能数据迁移 | `~/.claude/skills/novel-style-guide/` | `.claude/skills/novel-style-guide/` |
| 技能数据迁移 | `~/.claude/skills/多风格小说样本/` | `.claude/skills/多风格小说样本/` |
| 技能数据迁移 | `~/.claude/skills/斗罗大陆/` | `.claude/skills/斗罗大陆/` |
| 技能数据迁移 | `~/.claude/skills/网文创作资料/` | `.claude/skills/网文创作资料/` |
| 项目数据迁移 | `~/.claude/skills/月租300块99条禁忌/` | `books/月租300块99条禁忌/` |

全局 `~/.claude/skills/` 只保留 `book-to-skill`（通用工具）。

### 代码路径更新

- `style_retrieval.py`：`NOVEL_DB_DIR` 和 `NOVEL_GUIDE_DIR` 改为项目内路径
- `style_rules.py` 路径修复（之前多了一层 `core/`）

---

## 七、新增/修改文件清单

### 新增文件 (4)

| 文件 | 大小 | 说明 |
|------|------|------|
| `novel-os/core/style_retriever.py` | ~10KB | TF-IDF + FAISS 向量检索器 |
| `novel-os/core/.style_index/style_index.faiss` | - | FAISS 索引 |
| `novel-os/core/.style_index/style_metadata.json` | - | 片段元数据 |
| `novel-os/core/.style_index/vectorizer.pkl` | - | TF-IDF 向量化器 |

### 修改文件 (8)

| 文件 | 改动 |
|------|------|
| `novel-os/core/writing/steps/style_retrieval.py` | 集成向量检索 + 场景推断 |
| `novel-os/core/writing/context.py` | 风格规则加载改为项目路径 |
| `novel-os/core/llm_settings_client.py` | 环境变量展开 + import os |
| `novel-os/config/llm.yaml` | API 改为本地代理 |
| `novel-os/frontend/src/components/layout/app-shell.tsx` | overflow-hidden → auto |
| `novel-os/frontend/src/pages/create/topics-page.tsx` | localStorage 持久化 |
| `novel-os/frontend/src/pages/create/category-page.tsx` | 面板滚动 |

### 新增数据 (100+ 文件)

| 目录 | 文件数 | 说明 |
|------|--------|------|
| `.claude/skills/novel-style-db/` | 99+ | 33 本 × 3 文件 |
| `.claude/skills/novel-style-guide/` | 8 | 5种风格 + 配套文件 |
| `.claude/skills/多风格小说样本/` | - | 迁移 |
| `.claude/skills/斗罗大陆/` | 4 | 迁移 |
| `.claude/skills/网文创作资料/` | 4 | 迁移 |
| `books/月租300块99条禁忌/` | 29 | 迁移 |

### 新增 Python 依赖 (2)

| 包 | 版本 | 用途 |
|----|------|------|
| `faiss-cpu` | 1.14.3 | FAISS 向量索引 |
| `scikit-learn` | 1.9.0 | TF-IDF 向量化 |

---

## 八、当前写作流水线效果

### 数据流

```
StyleRetrievalStep.execute()
  │
  ├─ _infer_scene(ctx)
  │   └─ 大纲 core_event + title + chapter_hook
  │      → 推断场景类型 (战斗/对话/情绪/描写/设定/综合)
  │
  ├─ _retrieve_novel_refs(genre, scene_type, description)
  │   ├─ 优先: StyleSkillRetriever.query_for_prompt()
  │   │   → FAISS 向量检索 → top-3 匹配片段
  │   └─ 回退: _load_novel_db_references(genre)
  │       → 全量加载同品类小说
  │
  └─ _build_style_injection()
      → 拼接规则 + 去AI味5条 + 检索结果 → ctx.corrections["style_rules"]
      → SceneWriter prompt 中注入
```

### 注入内容示例（玄幻 + 战斗场景）

```
=== 去AI味核心规则 ===
1. 用细节代替概括...
2. 用动作代替状态...
...

=== 同类小说风格参考（真实作品）===

### 参考：《斗罗大陆》（玄幻·战斗·相似度1.30）
动作流程微观肢解式描写——
任何武技被拆解为极其细微的物理流程。"以腿带腰，以腰带背，以背带臂"
——配合"从XX发力，经过XX到XX"的固定句式。

### 参考：《血狱魔帝》（玄幻·战斗·相似度1.05）
"以弱胜强"标准战循环——
主角劣势遭遇→对手轻视→隐藏底牌→关键时刻爆发→一招逆转。
```

---

## 九、未完成事项

| 事项 | 状态 | 说明 |
|------|------|------|
| sentence-transformers 语义模型 | 未安装 | 当前用 TF-IDF，语义理解不如神经网络模型 |
| novel-style-db 缺 1 本 | 网游/网游之情缘江湖 (89KB) | API 连接失败，文件很小，影响可忽略 |
| S-style-db 增量更新 | 未做 | `data/` 新增小说后需手动重建索引 |
| 写作流线线端到端测试 | 待验证 | 前后端已就绪，创建项目后可测试 |

---

## 十、运行方式

```bash
# 构建向量索引（首次或数据更新后）
cd novel-os
python -m core.style_retriever --build

# 后端
python -X utf8 -m uvicorn api.main:app --host 127.0.0.1 --port 8001

# 前端
cd frontend && npm run dev

# 写作测试
python cli.py --book <book.yaml> write --chapter 1
```
