# Novel-OS 外层回路设计报告：基于 Loop Engineering 的去AI味规则自动优化引擎

> 日期：2026-06-19  
> 方法论来源：Loop Engineering（环路工程）  
> 核心原则：管理学 > 工程学——定义可验证目标、边界和反馈机制，让AI系统自主持续运行

---

## 一、执行摘要

本报告提出 Novel-OS **外层回路**（Outer Loop）的完整设计与实现——基于 Loop Engineering 思想的去AI味规则自动优化引擎。

**现状问题**：Novel-OS 已经具备了成熟的**内层回路**（章节写作→审计→修正→重试），但规则本身（阈值、禁用词表、prompt模板）仍需人工调试。每次换品类、换模型、开新书，都要重新摸索——这是"操作工"模式。

**解决方案**：外层回路将"优化规则"这件事也自动化——AI自动跑测试、发现规则盲区、生成优化提案、等你审批、自动应用、验证效果、收敛自动停止。你从"操作工"变成"厂长"。

**核心数据**：
- 外层回路单轮成本 ≈ $0.02（≈8.5K tokens），若关闭LLM深度分析则为 $0
- 一次完整优化（3轮到收敛）≈ $0.05 + 5分钟人工审批
- 规则收敛后，内层回路每章重试次数预计从3次降到1-2次，100章可节省约450K tokens

---

## 二、系统现状观察

### 2.1 已有资产

Novel-OS 当前的去AI味体系已经相当完善：

| 层次 | 组件 | 位置 | 成熟度 |
|------|------|------|--------|
| 硬规则引擎 | StyleRuleEngine（8类检测） | `core/writing/style_rule_engine.py` | ✅ 可用 |
| 多Agent审查 | StyleCriticStep（Pattern/Repetition/Voice三审） | `core/writing/steps/style_critic.py` | ✅ 可用 |
| 统一校验 | ChapterValidator（30+指标） | `core/chapter_validator.py` | ✅ 可用 |
| 质量门禁 | QualityGates（BLOCKING/WARN/PASS） | `core/quality_gates.py` | ✅ 可用 |
| 反检测改写 | AntiDetectReviser（辞林过滤+指纹优化） | `core/anti_detect_reviser.py` | ⚠️ 已关闭 |
| 风格检索 | StyleRetrievalStep（33本参考小说+向量检索） | `core/writing/steps/style_retrieval.py` | ✅ 可用 |
| 风格指南 | novel-style-guide（5条去AI味核心规则） | `.claude/skills/novel-style-guide/` | ✅ 可用 |
| 风格参考库 | novel-style-db（33本×3文件） | `.claude/skills/novel-style-db/` | ✅ 可用 |
| 写作流水线 | WritingPipeline（10阶Steps） | `core/writing/pipeline.py` | ✅ 可用 |
| 回路控制器 | LoopController（目标检查+护栏） | `core/writing/loop_controller.py` | ✅ 可用 |
| Prompt模板 | SceneWriter DNA / 各Agent system prompt | `core/writing/prompts.py` | ✅ 可用 |

### 2.2 诊断发现

经过对代码和 v3 测试数据的分析，发现以下系统性问题：

**问题 1：规则参数缺乏数据支撑**
- `max_ta_density = 0.04`——这个4%哪来的？实际人类网文均值约5-6%。v3测试中平均他字密度可能已经高于阈值，导致大量"假阳性"WARN
- `min_burstiness = 0.35`——这个0.35是基于什么数据定的？没有基线测试
- 30+阈值参数中，大部分是"拍脑袋"或"从某个项目继承"的

**问题 2：禁用词表存在盲区和误杀**
- v3测试发现"心里一沉"出现17次未在禁用词表中——典型的AI情绪标签盲区
- "轻轻"在对话中高频出现但每次都被标记——典型的误杀
- 禁用词表来自人工积累，没有系统性验证过"命中率 vs 误报率"

**问题 3：指标间存在隐性冲突**
- 对话占比上限（55%）和长句最低阈值（25字）天然冲突——对话章节短句多
- 段落长度警告和"去AI碎片化"目标可能反向——过于碎片化的文本正是AI特征之一
- Validator 的某些约束在"去AI味"和"保持品质"之间形成跷跷板

**问题 4：系统是"事后纠正"架构**
- StyleCritic 在倒数第三步才介入，前面所有步骤都在为"有AI味"的初稿做扩展
- 一旦StyleCritic修订幅度过大，可能破坏Hook/Dialogue已经调好的结构
- "生成→审查→修复→再审查"的链路过长，每章额外消耗3-4次LLM调用

### 2.3 前期改造回顾

此前 agent 完成的 v3 改造解决了部分问题：

| 改造项 | 效果 | 局限性 |
|--------|------|--------|
| 关闭 AntiDetectReviser | 避免碎片化反效果 | 治标——代码还在，未来可能被误开 |
| 放宽段落阈值 30→80字 | 减少无效警告 | 单一调整，未系统校准所有阈值 |
| 新增 StyleCriticStep | 有效压降AI味评分 | 是后置修补——前置Prompt仍未根治 |
| 重写 SceneWriter DNA | 从17条负面清单→10条正面铁律 | 缺少正例和具体句法模板 |
| 新增 StyleRuleEngine | 硬规则兜底 | 参数硬编码，阈值未经数据校准 |

**本质问题**：这些改造是"人分析→人改"的一次性模式。下次换模型、换品类、开新书，又要重新来一遍。

---

## 三、外层回路设计

### 3.1 Loop Engineering 五组件映射

| Loop Engineering 组件 | Novel-OS 实现 | 说明 |
|----------------------|---------------|------|
| **心跳（定时任务）** | `OuterLoopRunner` + 手动触发 / cron | 新书启动时跑一次，或每月定期巡检 |
| **工作树隔离** | `.rule_snapshots/` 快照系统 | 每轮迭代前保存完整规则快照，支持一键回滚 |
| **知识体系** | `audit_history` + `rule_change_log` | 每次测试审计数据入库，每次变更原因和效果留痕 |
| **连接器** | `RuleReader` / `RuleWriter` | 统一读写 THRESHOLDS、BANNED_PATTERNS 等所有参数 |
| **子Agent（做查分离）** | Analyzer → Proposer → (审批) → Tester → Comparer | 分析、提案、测试、对比各司其职 |

### 3.2 七步骤回路

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ╔═══════════════════════════════════════════════════════════════╗  │
│  ║  STEP 1: 测试集运行 (TestRunner)               成本: 0 tokens  ║  │
│  ║  读取已有章节 .md/.txt 文件 → 纯Python静态审计                 ║  │
│  ║  采集20+指标: 字数/他字密度/AI味评分/禁用词/统计指纹...        ║  │
│  ║  不使用LLM——ChapterValidator + StyleRuleEngine + 正则          ║  │
│  ╚═══════════════════════════════════════════════════════════════╝  │
│                              ↓                                      │
│  ╔═══════════════════════════════════════════════════════════════╗  │
│  ║  STEP 2: 分析器 (Analyzer)                    成本: 0-5K tokens║  │
│  ║  阶段A (代码): 统计预分析——阈值校准/盲区/误报/相关性          ║  │
│  ║  阶段B (LLM): 深度分析——跨章趋势/异常值/隐蔽冲突 (可选)      ║  │
│  ║  输出: AnalysisFinding 列表 (含置信度)                        ║  │
│  ╚═══════════════════════════════════════════════════════════════╝  │
│                              ↓                                      │
│  ╔═══════════════════════════════════════════════════════════════╗  │
│  ║  STEP 3: 提案器 (Proposer)                    成本: 0-3.5K    ║  │
│  ║  将每条发现转化为具体的 AssetChange 提案                       ║  │
│  ║  每条提案: from值 → to值 + 理由 + 古德哈特风险评估            ║  │
│  ║  LLM补充: 对代码无法覆盖的复杂情况生成额外提案 (可选)         ║  │
│  ╚═══════════════════════════════════════════════════════════════╝  │
│                              ↓                                      │
│  ╔═══════════════════════════════════════════════════════════════╗  │
│  ║  STEP 4: 人类审批 (ApprovalNode)              成本: 你的5分钟  ║  │
│  ║  展示: 每条提案 from→to + 理由 + 风险评级                     ║  │
│  ║  操作: 全部批准 / 逐条批准/拒绝 / 修改参数后批准              ║  │
│  ║  你在回路中的唯一参与点                                       ║  │
│  ╚═══════════════════════════════════════════════════════════════╝  │
│                              ↓                                      │
│  ╔═══════════════════════════════════════════════════════════════╗  │
│  ║  STEP 5: 应用变更 (RuleWriter)                成本: 0 tokens  ║  │
│  ║  保存规则快照 (.rule_snapshots/snapshot_*.json)               ║  │
│  ║  应用批准的提案: 修改 THRESHOLDS/BANNED_PATTERNS/等           ║  │
│  ║  失败自动回滚                                                  ║  │
│  ╚═══════════════════════════════════════════════════════════════╝  │
│                              ↓                                      │
│  ╔═══════════════════════════════════════════════════════════════╗  │
│  ║  STEP 6: 验证测试 (TestRunner again)          成本: 0 tokens  ║  │
│  ║  用新规则再次静态审计同样的章节                                ║  │
│  ║  产出第二轮 AuditBatch                                         ║  │
│  ╚═══════════════════════════════════════════════════════════════╝  │
│                              ↓                                      │
│  ╔═══════════════════════════════════════════════════════════════╗  │
│  ║  STEP 7: 对比 + 收敛判定 (Comparer + Convergence) 成本: 0     ║  │
│  ║  逐指标 before/after 对比 → 改善/恶化/持平                    ║  │
│  ║  古德哈特预警: 某指标改善但另一指标恶化                        ║  │
│  ║  收敛判定: >90%参数连续3轮变动<1% → 自动停止                  ║  │
│  ║  未收敛 → 回到 STEP 2，携带新一轮基线                         ║  │
│  ╚═══════════════════════════════════════════════════════════════╝  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 可优化的生产资料清单

外层回路管理的 35 项资产，按类型分类：

**A. 结构化阈值参数（28项，代码直接读写）**

| 类别 | 数量 | 典型参数 |
|------|------|---------|
| P0 BLOCKING | 4项 | min_words, max_words, max_ta_density, max_redline |
| P1 WARNING | 15项 | max_forbidden_patterns, dialogue_ratio, burstiness, perplexity, max_sudden_count, 等 |
| P2 INFO | 2项 | sensory_min_per_500, precise_number_threshold |
| Pipeline | 2项 | max_retries, polish_interval |
| StyleRuleEngine | 4项 | max_not_x_but_y, max_xiang, max_cn_numbers, max_repetition |
| ChapterGoal | 4项 | goal_word_min/max, goal_max_rule_score, goal_max_cn_number_density |

**B. 词表资产（7项，支持增删词条）**

| 词表 | 当前规模 | 位置 |
|------|---------|------|
| 禁用词 | 19词 | `chapter_validator.py:BANNED_PATTERNS` |
| AI万能结尾 | 4词 | `chapter_validator.py:BANNED_PATTERNS` |
| 模板比喻 | 13词 | `chapter_validator.py:BANNED_PATTERNS` |
| 标志性AI表情 | 4词 | `chapter_validator.py:BANNED_PATTERNS` |
| 情绪标签 | 50词 | `style_rule_engine.py:StyleRuleEngine.EMOTION_LABELS` |
| 公共库存比喻 | 6词 | `style_rule_engine.py:StyleRuleEngine.STOCK_METAPHORS` |
| 系统面板词 | 6词 | `style_rule_engine.py:StyleRuleEngine.SYSTEM_PANEL_WORDS` |

### 3.4 收敛条件

外层回路在以下条件全部满足时自动停止：

1. **参数稳定性**：超过90%的被监测参数（13个核心参数）连续3轮变动 < 1%
2. **无新增盲区**：本轮未发现新的BLOCKING级别的模式
3. **无古德哈特预警**：无指标出现"一个变好但另一个变差"的跷跷板效应

收敛后生成报告 → 你最终拍板"接受"或"追加一轮定向优化"。

---

## 四、成本分析

### 4.1 外层回路 vs 内层回路

外层回路和内层回路的成本结构完全不同：

| | 内层回路（写一章） | 外层回路（优化规则/轮） |
|---|---|---|
| **LLM调用** | 8-10次 | 0-2次（可选） |
| **Token消耗** | ~16K | ~8.5K（含LLM）或 0（纯代码） |
| **费用估算** | ~$0.03-0.04 | ~$0.02 或 $0 |
| **耗时** | 5-6分钟 | 1-2分钟（代码）或 3-5分钟（含LLM） |
| **人工参与** | 0（全自动） | 5分钟审批 |

### 4.2 外层回路为何这么便宜

**关键设计决策：TestRunner 做的是"静态审计"，不是"重新跑流水线"。**

TestRunner 读取已有的 `.md`/`.txt` 章节文件（这些文件是内层流水线已经产出的），然后用纯 Python 代码计算20+指标：
- `ChapterValidator.validate()` → 纯正则+计数
- `StyleRuleEngine.score()` → 纯正则+计数
- `StatisticalFingerprintOptimizer.compute_metrics()` → 纯统计算法

**全程不调一次 LLM。** LLM 只在 Step 2（分析器）和 Step 3（提案器）中作为**可选增强**使用。

### 4.3 完整运行成本

**启动一次外层回路（修仙模拟器，1-10章，假设3轮到收敛）：**

| 步骤 | 每轮 tokens | 3轮合计 | 费用 |
|------|------------|---------|------|
| TestRunner 静态审计 ×2 | 0 | 0 | $0 |
| Analyzer 代码分析 | 0 | 0 | $0 |
| Analyzer LLM深度分析 | ~5K | ~15K | ~$0.03 |
| Proposer 代码转化 | 0 | 0 | $0 |
| Proposer LLM补充 | ~3.5K | ~10K | ~$0.02 |
| 人类审批 | — | 3×5分钟 | 你的时间 |
| RuleWriter 快照+应用 | 0 | 0 | $0 |
| Comparer + Convergence | 0 | 0 | $0 |
| **总计** | **~8.5K/轮** | **~25K** | **~$0.05** |

若不需要 LLM 深度分析（代码分析已足够）：3轮总计 **$0**。

### 4.4 成本对比：有 vs 没有外层回路

```
场景：写一本 100 章的小说

┌────────────────────────────────────────────────────────────┐
│ 没有外层回路                                                │
│                                                            │
│ 规则未优化 → 每章平均重试3次                                 │
│ 100章 × 16K tokens + 额外200次重试 × 3K tokens              │
│ = 2,200K tokens ≈ $4-5                                     │
│                                                            │
│ 人工调参时间: 全年100+小时                                   │
│ 规则一致性: 依赖个人经验，不可复制                            │
│ 跨品类迁移: 从头摸索                                         │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ 有外层回路                                                  │
│                                                            │
│ 新书启动: 外层回路 3轮 ≈ $0.05 (+ LLM深度分析)              │
│ 规则优化后 → 每章平均重试降到1-2次                           │
│ 100章 × 16K + 额外50次重试 × 3K                             │
│ = 1,750K tokens ≈ $3-4                                     │
│                                                            │
│ 省下: ~450K tokens ≈ $1 + 99小时人工                        │
│ 规则变更可追溯: rule_change_log                             │
│ 跨品类迁移: 1轮外层回路适配                                  │
└────────────────────────────────────────────────────────────┘
```

**外层回路不是成本——是省成本的投入。** 花不到一毛钱跑一次优化，每100章省一刀（$1）和无数人工。

### 4.5 成本控制机制

回路内置三道成本闸门：

1. **渐进测试集**：第1轮只跑3章验证方向，方向对了才扩到10章全跑。避免方向错了还花时间跑全量
2. **审批断点**：Step 4 是人类审批节点。提案不靠谱直接拒掉，不会浪费后续验证测试
3. **收敛自动停**：3轮参数稳定即停止，不会无限循环（max_rounds 硬上限兜底）

---

## 五、与现有系统的配合

### 5.1 数据流关系

```
内层流水线 (已有的 → 另一个Agent优化过)
│
│  产出: chapters/*.md 章节文件
│
├──→ 外层回路 Step 1 TestRunner
│    │
│    │  读取章节文本
│    │  调用 ChapterValidator(StyleRuleEngine(StatisticalFingerprint))
│    │  产出: AuditBatch (纯计算, 0 tokens)
│    │
│    ├──→ Step 2 Analyzer → 发现模式
│    ├──→ Step 3 Proposer → 生成提案
│    ├──→ Step 4 你审批
│    ├──→ Step 5 RuleWriter → 修改 THRESHOLDS/BANNED_PATTERNS/等
│    ├──→ Step 6 TestRunner → 用新规则重测
│    └──→ Step 7 Comparer + Convergence → 报告
│              │
│              ├── 收敛 → 结束, 规则冻结
│              └── 未收敛 → 回到 Step 2
│
└──→ 内层流水线 (下次写作时使用优化后的规则)
```

### 5.2 外层回路读取的资产（与 v3 改造的关系）

| 资产 | v3 改造后的值 | 外层回路如何读取 |
|------|-------------|----------------|
| `THRESHOLDS.max_ta_density` | 0.04 | `RuleReader` → `chapter_validator.THRESHOLDS` |
| `THRESHOLDS.min_burstiness` | 0.35 | 同上 |
| `BANNED_PATTERNS.禁用词` | 19词 | `RuleReader` → `chapter_validator.BANNED_PATTERNS` |
| `StyleRuleEngine.EMOTION_LABELS` | 50词 | `RuleReader` → `StyleRuleEngine.EMOTION_LABELS` |
| `PipelineConfig.enable_anti_detect` | False | `RuleReader` → `PipelineConfig` |
| SceneWriter DNA | 10条正面铁律 | 待实现（prompt_template 类型资产） |

### 5.3 外层回路不做什么

- ❌ 不重新跑流水线（不调 Writer/Auditor/Polish 等 LLM 步骤）
- ❌ 不修改情节、大纲、人物设定
- ❌ 不替代人工对章节内容的判断
- ❌ 不自动发布或部署

---

## 六、实现状态

### 6.1 已完成

```
novel-os/core/outer_loop/          ← 新增模块
├── __init__.py             50行   模块入口
├── models.py              271行   7个核心数据结构
├── assets_index.py        334行   35项资产注册表
├── rule_reader.py         189行   统一读取当前规则
├── rule_writer.py         308行   应用变更 + 快照/回滚
├── test_runner.py         255行   测试集运行 + 20项指标
├── analyzer.py            339行   代码+LLM双阶段分析
├── proposer.py            368行   发现→提案转化
├── comparer.py            213行   before/after对比
├── convergence.py         174行   收敛判定
├── approval.py            208行   终端交互审批 + JSON模式
└── runner.py              338行   7步骤主编排器 + CLI
                         ─────
                 12文件  3047行
```

已验证：
- ✅ 12/12 文件 Python 语法检查通过
- ✅ 所有模块导入成功
- ✅ RuleReader 正确读取全部 35 项资产当前值
- ✅ 快照/回滚机制就绪
- ✅ CLI 入口可用：`python -m core.outer_loop.runner`

### 6.2 待完成

| 优先级 | 事项 | 说明 |
|--------|------|------|
| P0 | 产出1-10章v3测试数据 | 内层流水线先跑完，回路才有测试集可读 |
| P0 | 跑通第一轮演示 | 自动审批模式验证回路能转起来 |
| P1 | 规则写入的 monkey-patch 改为 config-file 方式 | 当前对 StyleRuleEngine/ChapterGoal 使用 monkey-patch，需更稳健的方式 |
| P1 | LLM 客户端注入 | 将项目现有的 `llm_client.py` 正确注入 Analyzer/Proposer |
| P2 | prompt_template 类型资产的读写 | 当前只支持 threshold/wordlist/config，prompt模板待实现 |
| P2 | 跨品类迁移验证 | 玄幻规则在言情品类上的迁移效果 |
| P3 | 收敛历史可视化 | 参数趋势图、规则变更时间线 |

---

## 七、使用方式

### 7.1 新书启动

```bash
# 1. 先让内层流水线写1-10章（使用当前规则）
python cli.py --book <book.yaml> write --range 1:10

# 2. 启动外层回路优化规则
cd novel-os
python -m core.outer_loop.runner \
  --chapters-dir "<book_path>/chapters" \
  --chapter-range 1-10 \
  --rounds 5

# 3. 按提示逐条审批提案
# 4. 收敛后，用优化后的规则继续写11-100章
```

### 7.2 换模型适配

```bash
# 模型从 DeepSeek v4 升级到 v5 后
python -m core.outer_loop.runner \
  --chapters-dir "<book_path>/chapters" \
  --chapter-range 1-5 \
  --rounds 3
# → 自动校准提示工程参数到新模型
```

### 7.3 定期巡检

```bash
# 每50章或每月跑一次诊断（只分析不修改）
python -m core.outer_loop.runner \
  --chapters-dir "<book_path>/chapters" \
  --rounds 1
# → 只看分析报告，不批准任何提案
```

---

## 八、商用价值

### 8.1 短期（单书写作）

- 新书启动时 3 轮外层回路帮规则适配该书的品类和风格
- 减少内层重试次数，每 100 章节省约 450K tokens（≈$1）
- 规则变更可追溯，方便复盘和交接

### 8.2 中期（系统产品化）

- 多品类支持：外层回路让同一套系统能自动适配玄幻/都市/言情/悬疑
- 换模型无痛：LLM API 升级后跑一次外层回路即可校准
- 降低人工依赖：不再需要"懂规则调参的人"长期维护

### 8.3 长期（平台化）

- 作者提供 3 章样本 → 外层回路自动适配作者风格 → 产出定制规则引擎
- 不同作者的不同规则库可以比较和迁移
- 规则优化经验积累 → 冷启动新品类时不再是"从零开始"

---

## 九、关键设计原则

1. **人类定义目标，AI 执行循环** — 你审批的是方向，不是每个参数
2. **指标是给机器跑的，判断是给人做的** — 防止古德哈特定律
3. **静态审计 > 跑流水线** — 测试集运行不花 LLM 钱
4. **快照先于修改** — 每次变更前保存完整快照，出错可一键回滚
5. **收敛自动停** — 不无休止循环，参数稳定即结束

---

## 十、附录：文件清单

### 新增文件 (12个)

| 文件 | 行数 | 说明 |
|------|------|------|
| `novel-os/core/outer_loop/__init__.py` | 50 | 模块入口 |
| `novel-os/core/outer_loop/models.py` | 271 | 7个核心数据结构 |
| `novel-os/core/outer_loop/assets_index.py` | 334 | 35项资产注册表 |
| `novel-os/core/outer_loop/rule_reader.py` | 189 | 统一规则读取 |
| `novel-os/core/outer_loop/rule_writer.py` | 308 | 变更应用+快照/回滚 |
| `novel-os/core/outer_loop/test_runner.py` | 255 | 测试集静态审计 |
| `novel-os/core/outer_loop/analyzer.py` | 339 | 代码+LLM双阶段分析 |
| `novel-os/core/outer_loop/proposer.py` | 368 | 发现→提案转化 |
| `novel-os/core/outer_loop/comparer.py` | 213 | before/after对比报告 |
| `novel-os/core/outer_loop/convergence.py` | 174 | 收敛检测 |
| `novel-os/core/outer_loop/approval.py` | 208 | 终端交互审批+JSON模式 |
| `novel-os/core/outer_loop/runner.py` | 338 | 7步骤主编排器+CLI |
| **总计** | **3047** | |

### 新增目录

| 目录 | 用途 |
|------|------|
| `novel-os/core/outer_loop/` | 外层回路模块 |
| `.rule_snapshots/` | 规则快照存储（运行时自动创建） |
| `.rule_proposals/` | 审批记录存储（运行时自动创建） |
| `reports/outer_loop/` | 对比报告和收敛报告输出 |
