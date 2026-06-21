# Novel-OS V1.0

> 多类型、多项目的 AI 长篇小说写作系统

## 特性

- **配置驱动**：每本书独立 `book.yaml`，零代码切换项目
- **SQLite 状态中心**：替代 JSON，解决并发与版本控制问题
- **质量门自动拦截**：字数、红线词、他字密度硬指标自动阻断 + 修复
- **插件化类型系统**：年代文/甜宠/玄幻等类型通过插件加载不同规则
- **断点续传**：批量写作时自动跳过已存在章节
- **快照回滚**：写崩了随时回退到任意历史版本

## 快速开始

### 1. 环境准备

```bash
# Python >= 3.10
pip install pyyaml

# 设置环境变量（指向你的小说根目录和 CrewAI Studio 数据库）
export NOVEL_BASE_PATH=/path/to/your/novels
export CREWAI_STUDIO_PATH=/path/to/crewai/studio
```

### 2. 创建 book.yaml

```bash
cp book.yaml.example mybook.yaml
# 编辑 mybook.yaml，修改书名、Agent 角色名等
```

### 3. 初始化状态库

```bash
python cli.py init --book mybook.yaml
```

如需从大纲 JSON 初始化（含人物、道具、债务、伏笔）：

```bash
python cli.py init --book mybook.yaml --outline outline.json
```

### 4. 写作

单章：
```bash
python cli.py write --book mybook.yaml --chapter 1
```

批量（支持断点续传）：
```bash
python cli.py write --book mybook.yaml --range 1:10 --resume
```

### 5. 查看状态

```bash
# 导出 JSON 视图
python cli.py state --book mybook.yaml --export world_view.json

# 回滚快照
python cli.py state --book mybook.yaml --rollback 5,pre_write
```

## 项目结构

```
novel-os/
├── cli.py                  # 命令行入口
├── core/                   # 核心引擎
│   ├── config_loader.py    # 配置解析
│   ├── state_manager.py    # SQLite 状态中心
│   ├── crewai_connector.py # CrewAI Agent/Task 查询
│   ├── quality_gates.py    # 质量拦截
│   ├── batch_writer.py     # 写作流水线
│   └── snapshot_manager.py # 快照与回滚
├── plugins/                # 类型插件
│   ├── base.py             # 插件基类
│   ├── plugin_loader.py    # 动态加载器
│   └── era_biz/            # 年代商战插件示例
│       └── plugin.yaml
├── platforms/              # 平台规则
│   ├── fanqie.yaml         # 番茄小说
│   └── qimao.yaml          # 七猫小说
├── templates/              # 配置模板
│   ├── config_base.md      # Jinja2 配置表模板
│   └── world_state_schema.sql
└── tests/
    └── test_end_to_end.py  # 集成测试
```

## 接入 LLM

当前 `batch_writer.py` 中的 Agent 调用为 **Mock 桩**，需替换为真实调用：

**方式一：LiteLLM（推荐）**
```python
import litellm
response = litellm.completion(model="gpt-4", messages=[...])
```

**方式二：CrewAI SDK**
直接使用 `crewai_connector.py` 查询到的 Agent ID / Task ID 调用 CrewAI Studio 接口。

**方式三：OpenAI SDK / Claude / 其他**
在 `_call_director` / `_call_writer` / `_call_polish` / `_call_auditor` 中替换为你的 SDK 调用。

## 开发插件

1. 在 `plugins/` 下新建目录，如 `plugins/xianxia/`
2. 创建 `plugin.yaml`（纯配置模式）或 `plugin.py`（Python 类模式）
3. 在 `book.yaml` 中设置 `plugin_id: xianxia`

## 测试

```bash
python -m pytest tests/test_end_to_end.py -v
```

## 路线图

- [x] 核心状态管理（SQLite）
- [x] 质量门拦截
- [x] 插件系统骨架
- [x] CLI 入口
- [ ] LiteLLM / CrewAI 真实接入
- [ ] 多线程/异步批量写作
- [ ] Web UI 状态面板
- [ ] 自动发布到平台
