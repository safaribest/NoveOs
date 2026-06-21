---
target: novel-os/frontend
total_score: 21
p0_count: 0
p1_count: 3
p2_count: 4
timestamp: 2026-06-18T18-11-58Z
slug: novel-os-frontend
---
#### Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | 流水线运行状态、保存 Toast、加载骨架屏都有；但命令面板等异步入口缺少更明确的反馈。 |
| 2 | Match System / Real World | 3 | 中文文案自然，图标与功能对应合理，网文术语使用正确。 |
| 3 | User Control and Freedom | 2 | 删除有二次确认、弹窗可取消；但缺少撤销、批量操作和更明显的返回路径。 |
| 4 | Consistency and Standards | 2 | 组件与配色统一，但所有页面都使用同一套“玻璃卡片+聚光灯+渐变标题”，导致层级扁平。 |
| 5 | Error Prevention | 2 | 表单有基础校验；但高风险操作（如启动/停止流水线）的二次确认不足。 |
| 6 | Recognition Rather Than Recall | 3 | 侧边栏常驻、命令面板可呼出，项目状态可见。 |
| 7 | Flexibility and Efficiency of Use | 2 | 有 ⌘K 搜索、Ctrl+S 保存；但命令面板无真实键盘上下选择，缺少批量编辑等高效操作。 |
| 8 | Aesthetic and Minimalist Design | 1 | 装饰性效果过多（玻璃拟态、极光背景、渐变文字、动效），干扰写作专注。 |
| 9 | Error Recovery | 2 | 错误提示使用中文，但部分仅展示消息，缺少“下一步怎么做”的引导。 |
| 10 | Help and Documentation | 1 | 缺少上下文帮助；空状态仅有简短文案，对新手作者引导不足。 |
| **Total** | | **21/40** | **Acceptable：视觉完成度高，但信息层级与视觉克制度需要优化。** |

#### Anti-Patterns Verdict

**LLM assessment**：界面有比较明显的“现代 SaaS 仪表盘”默认审美倾向。玻璃拟态卡片、极光背景、渐变文字、聚光灯动效等元素堆砌在一起，更像营销落地页而非作者每天长时间使用的写作工具。每一个页面标题都用 `GradientText` 包装，标题本身失去了层级意义，变成装饰。整体给人“AI 生成感”较强，缺乏面向严肃创作者的工具气质。

**Deterministic scan**：
- `gradient-text` 反模式：在 `src/styles/app.css:364` 的 `.gradient-text` 类被多处使用（首页“项目总览”、登录页大标题、项目列表、创建流程等）。
- `bounce-easing` 反模式：在 `src/styles/app.css:100` 定义了 `cubic-bezier(0.34, 1.56, 0.64, 1)` 的 spring 缓动，用于 `icon-bounce` 动画，显得廉价。

#### Overall Impression

视觉执行很完整，动效、主题切换、响应式都到位，能看出花了功夫。但核心问题是“**产品设计被视觉风格绑架**”：一个需要作者长时间专注的写作工具，目前看起来更像一个 AI 产品展示页。最大机会是**做减法**——把装饰性效果砍掉 30%–50%，让状态、进度、质量数据成为绝对主角。

#### What's Working

1. **信息架构清晰**：侧边栏分组（仪表盘 / 创作 / 系统）符合产品心智；写作工作台的三栏布局（目录 / 编辑器 / 信息面板）是合理且可扩展的。
2. **空状态与加载处理**：首页、项目列表、分类页都有空状态和骨架屏，比直接白屏好很多。
3. **深色模式与 reduced-motion**：主题切换和减少动画的媒体查询已经落地，具备基础可访问意识。

#### Priority Issues

**[P1] 页面标题过度使用渐变文字**
- **What**：首页、项目列表、项目看板、创建流程几乎每个一级标题都使用 `GradientText`。
- **Why it matters**：渐变文字本质是装饰，削弱了标题的层级功能；同时部分渐变与背景对比度不稳定，影响可读性。对需要长时间使用的工具来说，标题应该是“安静的锚点”，而不是“视觉焦点”。
- **Fix**：把页面标题统一改为纯色 `text-foreground` 或 `text-ink`，仅保留品牌登录页 hero 区可适度使用渐变。
- **Suggested command**：`$impeccable quieter`

**[P1] 玻璃拟态与极光背景喧宾夺主**
- **What**：`GlassCard`、`SpotlightCard`、`AuroraBackground`、`glow-border` 遍布首页、登录页、分类页、项目卡片。
- **Why it matters**：这些效果会抢夺用户对数据和操作的注意力；在需要长时间盯屏的写作场景中，背景动效（aurora-flow 12s 循环）容易造成视觉疲劳。
- **Fix**：将信息卡片降级为普通 `Card` + 浅背景；仅在高优先级 CTA 或空状态等关键转化点保留少量光晕，且默认关闭或遵循 reduced-motion。
- **Suggested command**：`$impeccable quieter`

**[P1] 写作工作台信息密度过高，缺少专注模式默认**
- **What**：写作页默认同时展示章节目录、编辑器、质量面板、流水线控制等多块信息。
- **Why it matters**：写作是核心沉浸任务，当前布局把“监控面板”和“创作面板”放在同等权重，容易打断心流。虽然提供了 focusMode，但不是默认。
- **Fix**：考虑默认收起右侧信息面板，或进入写作页时只保留目录+编辑器，质量指标通过悬浮/状态栏最小化展示。
- **Suggested command**：`$impeccable distill`

**[P2] 命令面板键盘体验未闭环**
- **What**：`command-palette.tsx` 底部提示“↑↓ 选择 · ↵ 确认”，但列表项是普通 `<button>`，没有实现上下键选择、高亮当前项、Enter 触发等键盘行为。
- **Why it matters**： power user 会本能地使用键盘，提示与行为不一致会破坏信任。
- **Fix**：引入 `cmdk` 或自己实现 `role="listbox"` + 上下键管理 + 当前项 `aria-selected` 样式。
- **Suggested command**：`$impeccable harden`

**[P2] 动画使用过度且存在 bounce 缓动**
- **What**：`app.css` 中定义了 `icon-bounce`、`aurora-flow`、`float`、`glow-pulse` 等装饰动画，并在分类卡片使用 stagger 入场。
- **Why it matters**：bounce 和持续循环动画会让界面显得“活泼”过头，不适合专业写作工具；也会给前庭功能障碍用户带来不适。
- **Fix**：删除 bounce 缓动；将循环背景动画改为静态或仅在首次加载时播放一次；列表入场动画统一为简单的 fade/slide。
- **Suggested command**：`$impeccable animate`

**[P2] 卡片嵌套与重复卡片模式**
- **What**：项目看板、人物、技能、道具等全部使用 `SpotlightCard` 包装，卡片内部再放 `CardHeader/CardContent`，形成视觉层级扁平的“卡片墙”。
- **Why it matters**：所有内容都被框起来，反而没有重点；用户需要更多时间扫描。
- **Fix**：对数据密集页（如大纲、人物列表）改用列表/表格+悬浮高亮，仅在需要强调单个对象时使用卡片。
- **Suggested command**：`$impeccable layout`

**[P3] 侧边栏副标题“AI 写作系统”使用全大写+宽字距**
- **What**：`sidebar.tsx:111` 的 `text-[10px] uppercase tracking-wider` 是 SaaS 模板常见的小眉标。
- **Why it matters**：这是 impeccable 绝对禁止的“tiny uppercase tracked eyebrow”AI 语法。
- **Fix**：直接删除或改为普通字号、正常大小写的描述文案。
- **Suggested command**：`$impeccable typeset`

#### Persona Red Flags

**Alex（高效型老用户）**
- 命令面板无法键盘上下选择，只能鼠标点击。
- 项目列表没有批量选择/批量删除，每本书只能一个个编辑。
- 写作页右侧信息面板常驻，需要手动进入 focus mode，不够默认高效。

**Jordan（新手作者）**
- 登录页品牌区文案“让 AI 成为你的写作搭档”+ 极光背景更像营销页，进入产品后风格骤变为仪表盘，造成预期错位。
- 首页“今日字数”显示为 “—”，没有解释什么时候会有数据。
- 创建项目流程有 4 步（category → topics → outline → confirm），但当前页面没有展示最终要收集哪些信息，容易让人担心流程太长。

**Sam（依赖键盘/屏幕阅读器用户）**
- 渐变文字在部分背景下对比度难以保证。
- 命令面板的列表没有 `listbox` 语义，屏幕阅读器无法感知当前选项。
- 虽然 reduced-motion 已处理，但持续的极光/发光脉冲动画默认开启，在关闭前已造成干扰。

#### Minor Observations

- 按钮组件同时存在 `rounded-xl`（默认）和 `rounded-md`（sm/lg size），圆角逻辑不统一。
- `app-shell.tsx` 中 `useEffect` 里调用 `setState` 被 eslint-disable 包裹，建议改用 `useQuery` 或 Suspense 模式。
- 项目看板的 Tab 导航使用 `sticky top-0`，但与页面 `p-4` 的负边距组合可能在某些滚动场景下出现抖动。
- 多处使用 `animate-pulse` 作为加载占位，虽然可用，但与整体精致的动效语言略不搭。

#### Questions to Consider

1. 这个界面想让人觉得“高科技 AI 工具”还是“可靠的专业写作环境”？当前视觉更偏向前者。
2. 如果每天要看这个界面 2–3 小时，极光背景和渐变标题是否还能保持舒适？
3. 写作工作台的右侧质量面板，有多少信息是作者在写作当下必须立即看到的？
