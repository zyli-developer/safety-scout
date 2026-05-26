---
target: docs/plans/2026-05-22-unified-modern-minimal/
total_score: 30
p0_count: 1
p1_count: 2
timestamp: 2026-05-24T13-37-16Z
slug: docs-plans-2026-05-22-unified-modern-minimal
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 3 | Polling tracker + livelog + 整改 1/4 + undo toast are real wins. -1 因为 livelog 第一行就漏 `SHA256 校验完成`（polling.html:264）、`aria-current="page"` 在 polling 错挂到"巡检"上（polling.html:200）。 |
| 2 | Match System / Real World | 4 | JGJ80-2016 4.3.1 原文 + 现场实测解读 + "疏散临边作业人员"等动作动词，整套已是安全员语域。这一项已经做到位。 |
| 3 | User Control & Freedom | 3 | high-stakes 确认表 + 5 秒撤销 toast 完整落地（report-detail.html:542-561, 629-655）。-1: detail 页 `← 上一条/下一条` 之外没有 "回到本次报告" 的明确路径，依赖面包屑。 |
| 4 | Consistency & Standards | 3 | token / topnav / footer 真共享。-1: 同一条 "整改建议" 在 report.html 是橙色 `.suggestion-callout`，在 report-detail.html 是中性白卡 `.step` 列表——下钻应展开同一视觉语言，现在是两套。 |
| 5 | Error Prevention | 3 | high-stakes 步骤含 "错误标记可能误导班组停工" 的后果说明，"仍要分析" 按钮标签也带后果。-1: home dropzone 用 `<a>` 当 tap target（home.html:254）直接跳页，没有真正的 file-picker 中间态。 |
| 6 | Recognition Rather than Recall | 3 | severity 三冗 + H1-H10 编号 + history chip 计数。-1: report 顶部筛选 chip `中 0 / 低 0` 在 high-only 报告里成噪声（report.html:362）。 |
| 7 | Flexibility & Efficiency | 2 | sidepanel 漂亮但 `min-width:1180px`（report.html:237）——典型 1366 笔记本边缘命中，1280×800 OK，1024 iPad landscape 直接没有。无键盘快捷键、history 无批量动作、detail 不显示 "本次报告第 1/3 条" 位置。 |
| 8 | Aesthetic & Minimal Design | 4 | 白底 + 冷灰二级面 + 单橙 accent + 系统字+ JetBrains Mono + 无渐变（除照片占位）+ 无阴影（除 hover）。7 屏视觉节奏整齐。这是这套设计执行最强的一维。 |
| 9 | Help with Errors | 3 | 空态 / 拒识 / 网络三态完整。但**spec 要 4 态，模糊态完全缺**（empty-error.html:167-172 只有 3 个 swbtn）——50 岁单手拍照工地光照下最常见的失败类型没覆盖。 |
| 10 | Help & Documentation | 2 | 无 `?` icon、无首次使用引导、无 "如何拍出好照片" 文档入口。Tips 只在拒识态内联——王师傅碰运气。 |
| **Total** | | **30 / 40** | **+2 vs 28/40 baseline · Good 上端**。6 步修复落地但未跨越；新增 2 处 fix-introduced 问题（safe-area 数学失效、SHA256 leak）。 |

---

## Anti-Patterns Verdict

**LLM 评估**：一个 Linear/Stripe-fluent 的用户大致会信任这套——OKLCH 调色板、tabular-mono 数字、ghost+primary CTA 纪律、focus-visible 全覆盖、`<details class="redo-disclosure">` 折叠重新分析、`<details class="tech-disclosure">` 藏 SHA/模型名——都是有人认真过了一遍的真信号。

但有两处 product-slop 残留：

1. **`polling.html:264` livelog 头一行就是 `图像入库 · SHA256 校验完成`**。这是 fix 3 应该清掉的那种 dev-chrome——王师傅在脚手架旁焦虑等结果，首先看到的是一个加密散列校验术语。是 quieter 没扫到的死角。
2. **`.brand__mark` 还是 SaaS chip 形态**（home.html:224 等）——安全帽 SVG 被装在橙色圆角方块里。从"SS 字母 chip"升级到"helmet chip"是改善，但底盘还是 Linear 系的 app-tile。一个 product designer 二刷会看出来。

**Deterministic scan**（`detect.mjs --json`）—— 2 条命中：

| 文件 | 行 | 规则 | 判定 |
|---|---:|---|---|
| `polling.html` | 153 | `layout-transition` —— `.elapsed__fill { transition: width }` | **真实命中**。单元素 1.4s 宽度过渡在 mockup 阶段无伤，但落到 Taro 代码前应换 `transform: scaleX()` + transform-origin。继承自上轮，未修。 |
| `report-detail.html` | 170 | `side-tab` —— `.reg__quote { border-left:3px solid var(--accent) }` | **false positive**（与上轮判定一致）。该元素是真 `<blockquote>`，3px 左边线是 NYT/FT/Monocle 的编辑引用约定，不是 AI-slop 卡片侧条。检测器无法区分语义。 |

**Visual overlays**：未启动浏览器叠加（静态文件审查）。Detector 输出本身已构成确定性信号。

---

## Overall Impression

这套从 28/40 走到 30/40，**修了 6 件事，引入了 2 件新事**——`safe-area-inset-bottom` 数学失效 + `SHA256` livelog 漏字。6 个 priority 项里 5 个 P1 都对了语域（report CTA 倒转、step 确认表、dev-chrome 剥离、history toolbar、home dropzone 适配），但 `quieter` 没扫到 livelog、`harden` 在 safe-area 上写错了表达式——这恰是"快速做了 6 片但没在浏览器/真机上跑一次"的痕迹。

**最大单点机会**：现在的瓶颈不是"哪屏不好看"——美学一维已经 4/4。瓶颈是 **completeness**：模糊态缺、help 入口缺、empty-error 没接 history 空数据。再修一轮可以稳进 33-34/40；要破 35 得回到 IA 层（auto-open 单隐患、整改单与报告分离）。

---

## What's Working

1. **`polling.html:221-269` 三状态 tracker + 自脉冲流动线 + livelog + 显式 "不需要等在这页"。** §4 架构不变量被渲染成视觉主角——这套里最有产品 confidence 的一屏。除了 SHA256 那一条 livelog，其余信任建立做得到位。
2. **`report-detail.html:425-455 + 542-561 + 629-655` step-checkbox 完整硬化。** `role="checkbox"` + `aria-checked` + 确认表（含后果文案）+ 5 秒撤销 toast + `prefers-reduced-motion` 守卫。这是 `/impeccable harden` 应当长这样的样板。
3. **`report.html:396 整改建议文本**（"重新张紧立网，绳扣间距 ≤45cm…张挂安全平网；临边补设 ≥1.2m 双横杆防护栏；整改前禁止临边作业"）。**真·安全员语域**：动词 + 数字 + 顺序、不绕弯。是这套对得起 CLAUDE.md "产出读起来像安全员写的"的直接证据。

---

## Priority Issues

**[P0] Polling livelog 第一行漏 SHA256 给用户**
- File: `polling.html:264`
- 为什么重要：fix 3 明文要把 SHA/模型/Prompt 版本从用户面前的页面清掉。这条是 livelog 的**第一行**，王师傅打开等待页看到的第一个字符串就是加密散列校验术语。整套 quieter 工程的最显眼漏网之鱼。
- Fix: 改成用户语言——`[0:04] 照片已收到 · 准备分析`；或直接删掉（[0:06] 现场场景识别已经做了"已收到"的隐含确认）。
- Suggested command: `/impeccable quieter`

**[P1] empty-error.html 缺第 4 态（模糊/低质量）**
- File: `empty-error.html:167-172`（label-strip 仅 3 个 swbtn）、`175-288`（仅 3 个 `.state` panel）
- 为什么重要：模糊态是 50 岁单手在工地灰尘/逆光下最常见的失败模式。没有它，系统对"照片不行"只有两条路——非工地拒识 or 接受低置信度。这一漏是"看似覆盖全"的隐形缺口，reviewer 容易直接划掉。
- Fix: 增第 4 个 `<section class="state" data-state="blurry">`：art 用 motion-blur SVG，title "这张照片有点糊"，CTA `重拍`（primary）+ `仍要分析（结果会标记低置信度）`（ghost，与 reject 态 line 230 复用）。label-strip 加第 4 个 `.swbtn`。
- Suggested command: `/impeccable clarify`

**[P1] `shot__badge` safe-area 数学是 no-op**
- File: `polling.html:67`（badge 自身）+ `:68`（@supports 块）
- 为什么重要：`bottom: max(-10px, calc(-10px + env(safe-area-inset-bottom, 0px) * -1 + env(safe-area-inset-bottom, 0px)))` 在代数上等于 `-10px`——两个 env() 项符号相反互相抵消。`@supports` 块给 `.shot` 加 margin 不是给 `.shot__badge`。**fix 6 没真落地**。iPhone 14 Pro 真机上 "已上传" 药丸还是会被 home indicator 切。
- Fix: `bottom: calc(-10px - env(safe-area-inset-bottom, 0px))`（让 badge 被 safe-area 顶上去），或者去掉 calc、用 `bottom: -10px; margin-bottom: env(safe-area-inset-bottom, 0px)` 加在外层 `.shot` 上。DevTools 切 iPhone 14 Pro viewport 验证。
- Suggested command: `/impeccable harden`

**[P2] 整改建议在 report 和 detail 是两套视觉**
- File: `report.html:394-397`（橙色 `.suggestion-callout`）vs `report-detail.html:423-456`（中性白 `.step` 卡 ×4）
- 为什么重要：同一条 hazard 的整改内容，列表页是橙色单块 callout，详情页是 4 行白色 checklist。用户点进去预期 "橙色块展开成 4 步同色调"，实际看到 "白色卡片列表"——下钻关系视觉断裂。
- Fix: 详情页 `.step` 卡加极浅 `accent-soft`（≤4% alpha）背景 tint，或者把 callout 在列表页缩成 mini-checklist 预览（前 2/4 步）。两侧建立同源视觉。
- Suggested command: `/impeccable typeset`

**[P2] sidepanel 在 1180px 才出现，1366 笔记本边缘命中**
- File: `report.html:237-242`
- 为什么重要：1180px 阈值高。`本次扫描概要` 是 项目经理 桌面审阅的 key affordance（CLAUDE.md persona）。1366×768 还在；1280×800 在；1024 (iPad landscape) 没有；外接显示器 + iPad fallback 两屏会看到两份不同的报告。
- Fix: 降到 `min-width:1024px`，侧栏宽度从 280 缩到 240 给主列让空间，跑一遍 hazard list 不挤压。
- Suggested command: `/impeccable adapt`

---

## Persona Red Flags

**王师傅（50 岁，工地单手，触屏，App 不熟）**：
- `home.html:254` 拍照按钮是 `<a href="polling.html">` 直接跳页，没有真正的 file-picker 中间态。mockup 阶段无伤，但落代码时必须接 `<input type="file" capture="environment">`；今天的标记教错了 tap target。
- `polling.html:175-176` "不想等？取消并返回" 是 13px underline-only。50 岁老花 + 工地强光下基本看不见。提到 15px + `text-decoration-thickness:1.5px` 或干脆做成 ghost button。
- `polling.html` livelog 第一行 SHA256 校验——他读不懂还会担心是不是出错了。

**项目经理（桌面审阅，PDF 导出）**：
- `导出 PDF` 现在是 ghost button（report.html:340-343），与"分享给班组优先"对齐。但项目经理 persona 恰恰是 PDF 主使用者——他要越过橙色 primary 找灰色 secondary。两 persona 在同一个 hero 上拉锯。
- sidepanel 1180px 阈值漏掉 1024（见 P2）。
- `report-detail.html:499` "导出整改单 PDF" 只导这一条 hazard——没有 "导出整本报告 PDF" 的入口；从 detail 流出只能靠面包屑回 report，再点 ghost。

**首次使用（无任何巡检记录）**：
- `empty-error.html` 空态做得好（CTA："拍下第一张照片"primary + "看示例报告"ghost），但**只在原型 label-strip 切换时可见**——`history.html` 现在永远渲染 populated rows，真后端返回空列表时没有 `.rlist:empty` fallback。需要补 history 的空态渲染逻辑。

---

## Minor Observations

1. `home.html:116-120` 定义了 `.hero__eyebrow` CSS 但 markup 不用——fix 3 剥离 dev-chrome 时遗留的 dead code；`polling.html:60` 的 `.stage__eyebrow` 同理。删 CSS 或回填非 dev-chrome 内容（如 "拍照入口"、"等待中"）。
2. `report.html:362-363` `M 0` 和 `L 0` 在 high-only 报告里是噪声 chip。count 为 0 时改 `aria-disabled="true"` + `.3` opacity，或直接隐藏。
3. `history.html:167` `.dayhead { top:60px }` 等于桌面 topnav 高；mobile 下 topnav 缩到 54px（line 208），sticky dayhead 会有 6px 空隙或重叠。
4. `report-detail.html:357 / :360` 标注 `#1 H1` 和 `#3 H9` 跳过 `#2 H2 物体打击`——H2 没标注却保留编号，导致 #2 缺失看着像 bug。要么也标 H2，要么重编号 1/2。
5. `polling.html:200` `aria-current="page"` 挂在"巡检"上——但"巡检"链接到 `home.html`，当前页是 `polling.html`。要么去掉（流程中无 page active），要么改为 `aria-current="step"`/`aria-current="true"` 表达 "巡检流程中的某步"。
6. `empty-error.html:230` 按钮标签 "仍要分析（结果会标记「低置信度」)"——括号 + 角标引号叠加偏重。试 "强制分析 · 结果将标记低置信度"——同等信息、更轻。
7. `index.html:212` launcher 顶部 `.t-eyebrow` 还有 "Modern-Minimal · 安全橙 accent · 已统一首页/轮询/报告"——launcher 内部 OK，但若有人把 launcher 当产品入口看会读成产品 surface chrome。
8. `polling.html:153` 的 `transition: width` （detector 命中）在 1.4s 单元素上 mockup 无害，但落 Taro 代码前换 `transform: scaleX()` + transform-origin: left。

---

## Questions to Consider

1. **拍照在 mockup 里是 navigation，在真产品里是 camera intent——这套设计教对了 tap target 吗？** `home.html:254` 的 `<a>` 越过了 file-picker 这一步。落代码时这里必须是 `<input type="file" capture="environment">` 或原生相机调用，UI 反馈也会不同（picker 弹层 → 选定 → 上传 → 跳页）。今天的 mockup 在教错的交互。
2. **报告页 list-first vs detail-first 应该看 hazard count 切换吗？** 1 条隐患时 list 视图是浪费；3 条全 high 时用户只想转发；8 条 mixed 时才需要 triage。auto-open 单条隐患或可成为有条件默认。
3. **"用同一张照片重新分析" 在 deterministic prompt 下是 theater，在非 deterministic 下是让用户赌——这个按钮的存在到底想解决什么？** 如果是 A/B prompt 切换的 dev 工具，标签应该反映；如果是给"AI 也许错了"留出口，藏到 `<details>` 里是对的但措辞还可以更克制（"标记结果存疑" 之类）。
4. **整改 checklist 把 "AI 说什么" 和 "我做了什么" 装进同一表面——这是 UI 决定还是 IA 决定？** 用户勾选 "重新张紧立网" 时，他在更新物理现实而不是编辑 AI 报告。这个数据应该挂在 report 上还是单独 entity（整改单 ↔ report 关联）？mockup 阶段不必改，但下一次 IA 评审值得拉出来。
