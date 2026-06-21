# Novel-OS - AI 长篇小说写作系统

Novel-OS 是一个基于 LLM 的多 Agent 协作长篇小说写作系统。支持多类型、多项目并行写作，内置质量门禁、去 AI 味拦截器、追读力评分和状态追踪。

> **已验证**：单章 4500 字、120 章+ 规模的自动化长篇小说写作能力。

---

## 系统架构

```
Novel-OS/
├── novel-os/               # 后端核心（Python + SQLite）
│   ├── core/               # 核心引擎
│   │   ├── batch_writer.py # 5 阶批量写作流水线
│   │   ├── llm_client.py   # LLM 客户端（DeepSeek/Moonshot/SiliconFlow）
│   │   ├── state_manager.py# SQLite 跨章状态库
│   │   ├── quality_gates.py# 质量门禁系统
│   │   └── interceptor.py  # 去 AI 味拦截器
│   ├── api/                # FastAPI + WebSocket 接口
│   ├── cli.py              # 命令行入口
│   ├── init_book.py        # 新书数据库初始化
│   ├── import_chapters.py  # 已有章节批量导入
│   └── book.yaml           # 示例配置文件
│
├── books/                  # 小说项目目录
│   └── [你的项目]/          # 每个小说独立目录
│       ├── book.yaml       # 项目配置
│       ├── book_data.py    # 创作数据（大纲/人设/规则/伏笔）
│       └── chapters/       # 生成的章节正文
│
├── tools/                  # 辅助工具
├── docs/                   # 文档
└── _模板_新书配置/          # 新书启动模板
```

---

## 快速开始

### 1. 环境准备

```bash
# 要求 Python 3.10+
python --version

# 安装依赖
pip install pyyaml litellm openai

# 或使用项目内的 pyproject.toml
pip install -e ./novel-os
```

### 2. 配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 API Key
# 支持：DeepSeek、Moonshot、SiliconFlow 等 OpenAI 兼容接口
```

`.env` 示例：
```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_API_BASE=https://api.deepseek.com/v1
OPENAI_API_KEY_FALLBACK=sk-your-backup-key
LLM_MODEL=deepseek-chat
```

### 3. 创建新小说

**Step 1：创建项目目录**
```bash
mkdir -p D:/noveos/books/我的新书
```

**Step 2：准备创作数据**
```bash
# 复制模板
cp _模板_新书配置/【模板】新书-book_data.py D:/noveos/books/我的新书/book_data.py

# 在 book_data.py 中填写：
# - OUTLINE: 每章大纲（核心事件、打脸方式、钩子）
# - CHARACTERS: 人物双轨表（秘密、对话指纹、肢体语言）
# - DEBTS / FORESHADOWING: 债务和伏笔时间表
# - RULES: 写作硬规则（人设/设定/节奏约束）
# - SKILLS: 技能树（每章解锁什么新能力）
```

**Step 3：创建 book.yaml**

参考 `novel-os/book.yaml` 创建你的项目配置，关键字段：
```yaml
project: 我的新书
platform: fanqie_novel  # 或 qimao, etc.
genre: era_biz            # 类型标签
total_words_target: 800000
chapters_target: 240
words_per_chapter: 4500
base_path: "D:/noveos/books/我的新书"
output_dir: "chapters"
llm:
  model: Pro/moonshotai/Kimi-K2.5  # 或 deepseek-chat
  api_key: "${OPENAI_API_KEY}"
  api_base: https://api.siliconflow.cn/v1
  temperature: 1.0
writing:
  words_per_chapter: 4500
  tolerance: 450
  max_retries: 3
  batch_size: 5
```

**Step 4：初始化数据库**
```bash
cd D:/noveos/novel-os
python cli.py --book D:/noveos/books/我的新书/book.yaml init \
  --data D:/noveos/books/我的新书/book_data.py
```

**Step 5：导入种子章节（前 3 章建议人工写）**
```bash
# 将人工写好的前3章保存为：chapters/第001章_标题_正文.txt
python cli.py --book D:/noveos/books/我的新书/book.yaml init --import-chapters --force
```

**Step 6：启动流水线**
```bash
# 从第4章开始写，写到第30章
python cli.py --book D:/noveos/books/我的新书/book.yaml write --range 4:30 --resume

# 使用启动脚本（Windows）
D:/noveos/start_auto_write.bat
```

每章约 5-6 分钟，30 章约 3 小时。

---

## 核心概念

### 5 阶写作流水线

| Agent | 职责 | 触发条件 |
|-------|------|----------|
| **Director** | 读取大纲+人设+规则，生成本章任务卡（含标题） | 每章必跑 |
| **Writer** | 按任务卡写初稿，严格遵循字数铁律 | 每章必跑 |
| **DeAI Interceptor** | 扫描 AI 味（他字密度、禁用词、句式破坏） | 每章必跑 |
| **Polish** | 润色去 AI 味，提升画面感 | 每3章1次 + 有拦截问题时强制 |
| **Auditor** | 审计字数/他字密度/禁用词/情绪一致性 | 每章必跑 |

### 质量门禁

- **字数**：4500 ± 450 字（中文字符）
- **他字密度**：≤ 8%
- **禁用词**：禁止"然而/不得不说/众所周知/突然/竟然/原来/与此同时"
- **BLOCKING**：字数不足/超标、严重违规 → 触发重试或 Expander 扩写

### 三层回路架构

Novel-OS 采用 **三层回路** 工程架构，将网文写作从"单次生成"提升为"持续优化的自动化生产线"：

| 层级 | 名称 | 职责 | 实现 |
|------|------|------|------|
| **第一层** | 知识注入层 | 番茄官方 222 节创作课提炼为可执行规则，注入每一章 | `fanqie_writer_courses/` → `core/rule_config.py` |
| **第二层** | 内层回路 | 导演→写手→去AI味→审计，一章自动跑完 5 道工序 | `core/batch_writer.py` 5 阶流水线 |
| **第三层** | **外层回路** | AI 自己跑测试→发现规则盲区→提优化方案→等审批→自动应用。规则越跑越准 | `core/outer_loop/` |

### 外层回路（Outer Loop）

外层回路是系统的"自我进化"机制——不是写完就完了，而是 **每轮写作后自动诊断规则质量**：

```
写作产出 → 规则审计 → 盲区发现 → 优化提案 → 人工审批 → 自动应用 → 下一轮更准
```

**核心组件**（`novel-os/core/outer_loop/`）：

| 组件 | 文件 | 功能 |
|------|------|------|
| **RuleReader** | `rule_reader.py` | 读取当前生效的规则集，含缓存与版本管理 |
| **TestRunner** | `test_runner.py` | 对最近 N 章执行全量规则打分 |
| **Analyzer** | `analyzer.py` | 代码+LLM 双阶段分析：阈值误校准、规则盲区、误报 |
| **Proposer** | `proposer.py` | 对发现的问题生成优化提案，含风险评级 |
| **Approval** | `approval.py` | 人工审批界面，支持批量通过/驳回 |
| **RuleWriter** | `rule_writer.py` | 通过审批的规则自动写入，生成快照 |
| **Comparer** | `comparer.py` | 规则变更前后效果对比，防 Goodhart 效应 |
| **Convergence** | `convergence.py` | 收敛检测——连续 N 轮无改进则暂停 |

**规则快照**（`.rule_snapshots/`）：每次规则变更自动存档，支持回滚和变更追溯。

**巡检 Agent**（`outer_crew/`），每 5-10 章触发一次：

| Agent | 职责 |
|-------|------|
| **架构师** | 对照大纲检查最近 N 章产出，确保主线同步推进 |
| **一致性巡检员** | 人物位置/资产/时间线/年代细节自洽检查 |
| **节奏分析师** | 商战/感情/日常三条线配比、爽点密度、字数趋势 |
| **回溯修正师** | 致命矛盾生成修正方案，优先软修正 |

> 详细设计见 [外层回路设计报告](reports/外层回路设计报告_LoopEngineering_20260619.md)

### 状态库（world_state.db）

| 表 | 用途 |
|----|------|
| `outline` | 每章详细规划（核心事件、打脸、护妻、钩子） |
| `character_states` | 人物状态（位置、情绪、秘密、对话指纹） |
| `debts` | 悬念/秘密的埋收时间表 |
| `foreshadowing` | 伏笔的埋收时间表 |
| `consistency_rules` | 写作硬规则 |
| `skill_tree` | 技能解锁时间表 |
| `chapter_history` | 已写章节摘要、字数、标题 |

---

## 目录说明

### 不应提交到版本控制的内容（已在 .gitignore）

- `books/*/chapters/` —— 生成的章节正文
- `books/*/world_state.db*` —— 运行时生成的 SQLite 数据库
- `logs/prompts/` —— 历史 Prompt 日志（体积大）
- `*.log`, `*.pid` —— 日志和进程文件
- `__pycache__/` —— Python 缓存
- `.env` —— 环境变量（含 API Key）

### 关键源码文件

| 文件 | 说明 |
|------|------|
| `novel-os/core/batch_writer.py` | 批量写作器，5 阶流水线核心 |
| `novel-os/core/llm_client.py` | LLM 客户端，支持多种 API |
| `novel-os/core/state_manager.py` | SQLite 状态库管理 |
| `novel-os/core/quality_gates.py` | 质量门禁系统 |
| `novel-os/core/interceptor.py` | 去 AI 味拦截器 |
| `novel-os/cli.py` | 命令行入口（init/write/state） |
| `novel-os/init_book.py` | 新书数据库初始化 |
| `novel-os/import_chapters.py` | 已有章节批量导入 |

---

## 技术栈

- **后端**：Python 3.10+ + FastAPI + SQLite + OpenAI SDK / LiteLLM
- **LLM 支持**：DeepSeek、Moonshot、SiliconFlow 等 OpenAI 兼容接口
- **数据库**：SQLite（world_state.db）
- **依赖管理**：pyproject.toml（PEP 621）

---

## License

MIT

---

## AI 一键部署提示

如果你是使用 AI 助手部署此项目，请将以下内容交给你的 AI：

```
请帮我部署 Novel-OS 小说写作系统：

1. 要求 Python 3.10+
2. 安装依赖：pip install pyyaml litellm openai
3. 复制 .env.example 为 .env，填入你的 API Key（支持 DeepSeek/Moonshot/SiliconFlow）
4. 创建项目目录：mkdir -p D:/noveos/books/我的新书
5. 复制模板：cp _模板_新书配置/【模板】新书-book_data.py books/我的新书/book_data.py
6. 在 book_data.py 中填写大纲、人设、规则等创作数据
7. 参考 novel-os/book.yaml 创建项目配置
8. 初始化数据库：cd novel-os && python cli.py --book ../books/我的新书/book.yaml init --data ../books/我的新书/book_data.py
9. 导入前3章种子（人工写好后放 chapters/目录，然后 init --import-chapters）
10. 启动写作：python cli.py --book ../books/我的新书/book.yaml write --range 4:30 --resume
```
