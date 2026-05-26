---
target: docs/plans/2026-05-22-unified-modern-minimal/
total_score: 35
p0_count: 0
p1_count: 1
timestamp: 2026-05-24T13-57-35Z
slug: docs-plans-2026-05-22-unified-modern-minimal
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 4 | livelog 第一行 SHA256 已改为 "照片已收到 · 准备分析"（polling.html:264），aria-current 改为 "step" 表达流程位（polling.html:200）。tracker + 自脉冲流动线 + livelog + "不需要等在这页" 这套已经无明显短板。 |
| 2 | Match System / Real World | 4 | JGJ80-2016 4.3.1 原文 + 现场实测解读 + 安全员动作动词（"疏散临边作业人员"）保持不变。语域已到位。 |
| 3 | User Control & Freedom | 3 | 高 stakes 确认表 + 5 秒撤销 toast 都在。-1: detail 页 `← 上一条/下一条` 之外仍无 "回到本次报告" 的明确路径（除面包屑），本轮未触。 |
| 4 | Consistency & Standards | 4 | 同一条整改建议在 report.html 是橙色 `.suggestion-callout`，在 report-detail.html `.step` 卡现已注入 3.5% accent alpha tint（report-detail.html:179-188）；下钻展开同色调。同时 `.step--done` 回中性，未完成态用 accent tint 形成"待做才热"的进度节奏，是细节加分。 |
| 5 | Error Prevention | 3 | high-stakes 步骤含 "错误标记可能误导班组停工" 后果说明。-1: home dropzone 仍用 `<a href="polling.html">` 当 tap target（home.html:254），落代码时必须接 `<input type="file" capture="environment">`。这条本轮未触。 |
| 6 | Recognition Rather than Recall | 4 | severity 三冗 + H1-H10 + history chip 计数都在。"中 0 / 低 0" chip 现已加 `aria-disabled` + 30% opacity（report.html:184/362-363），噪声压成背景但筛选维度仍可见。 |
| 7 | Flexibility & Efficiency | 3 | sidepanel `min-width` 已从 1180 降到 1024 + 侧栏 240（report.html:237-242）—— iPad landscape 现在能看到"本次扫描概要"。键盘快捷键、history 批量动作、detail "本次报告第 1/3 条" 位置仍缺，故停在 3 而非 4。 |
| 8 | Aesthetic & Minimal Design | 4 | 白底 + 冷灰二级面 + 单橙 accent + 系统字 + JetBrains Mono + 无渐变 + 无阴影（除 hover）保持。本轮多了 `.step--done` 回中性、annot 编号去 `#` 前缀两个克制的细节判断，整体视觉节奏不破。 |
| 9 | Help with Errors | 4 | 第 4 态（模糊 / 低质量）已补齐（empty-error.html:202-238）：motion-blur SVG + "这张照片有点糊" + 重拍 primary + 强制分析 ghost + 3 条 tips。50 岁单手拍 + 工地灰尘 / 逆光这个最常见失败模式有了专门出口。 |
| 10 | Help & Documentation | 2 | 无 `?` icon、无首次使用引导、无 "如何拍出好照片" 文档入口。本轮未触；Tips 仍内联在拒识 / 模糊态内。 |
| **Total** | | **35 / 40** | **+5 vs 30/40 baseline · 跨过 33/34 进入 Very Good 区**。6 priority + 6 minor 全部按建议落地，未引入新 fix-introduced regression。 |

---

## Anti-Patterns Verdict

**LLM 评估**：本轮把上轮两个 fix-introduced regression（SHA256 livelog + safe-area no-op）都修干净了。整改建议在 report 列表（橙色 callout）和 detail（accent-tinted step 卡）之间建立了同源视觉，下钻不再断裂。第 4 态（模糊）的加入填补了"看似覆盖全"的隐形缺口 —— 这是 reviewer 一眼就能挑出的 completeness 漏，现在补上了。

唯一仍刺眼的"AI 像"信号是 `.brand__mark` 的 SaaS chip 形态（橙色圆角方块裹安全帽 SVG），底盘还是 Linear 系 app-tile，二刷会被看出。但这是 IA / brand 层决策，不在本轮 6 步范围。

**Deterministic scan**（`detect.mjs --json`）—— 2 条命中，与上轮完全一致：

| 文件 | 行 | 规则 | 判定 |
|---|---:|---|---|
| `polling.html` | 156 | `layout-transition` —— `.elapsed__fill { transition:width }` | **真实命中（carry-over）**。单元素 0.8s 宽度过渡在静态 mockup 阶段无伤，但落 Taro 代码前应换 `transform: scaleX()` + `transform-origin: left`。两轮一致，未修，纳入"代码化前债务清单"。 |
| `report-detail.html` | 170 | `side-tab` —— `.reg__quote { border-left:3px solid var(--accent) }` | **false positive（carry-over）**。该元素是真 `<blockquote>`，3px 左边线是 NYT/FT/Monocle 编辑引用约定，不是 AI 卡片侧条；上轮已判定，本轮维持。 |

**Visual overlays**：本轮未启动浏览器叠加（静态文件审查 + Windows 终端 sandbox 限制）。两条命中均为代码层面，Detector 输出已足够。

---

## Overall Impression

从 30/40 到 35/40 是这轮的真实进展：**6 priority + 6 minor 全部按设计指令落地，0 新 regression**。最大的两件事：(1) 整改建议视觉同源（H4 +1）、(2) 模糊态补齐（H9 +1）—— 加上 (3) sidepanel 1024 适配（H7 +1）、(4) "中 0 / 低 0" 噪声压制（H6 +1）、(5) SHA256 livelog + aria-current 双修（H1 +1），五个 heuristic 各 +1。

**剩余瓶颈**：H10（Help & Documentation, 2/4）—— 无 `?` icon、无首次使用引导、无 "如何拍出好照片" 文档入口。下一轮想破 36/37 应该从这条切入，且 IA 层（auto-open 单隐患、整改单与报告分离）的考虑也开始值得做了。

---

## What's Working

1. **`polling.html:67` safe-area 数学修复**。从两个 env() 互相抵消的 no-op `bottom: max(-10px, calc(-10px + env() * -1 + env()))` 改成 `bottom: calc(-10px - env(safe-area-inset-bottom, 0px))`，iPhone 14 Pro home indicator 不再切药丸。是 `/impeccable harden` 的最小可逆样板。
2. **`empty-error.html:202-238` 第 4 态完整起来**：motion-blur SVG 隐喻 + "这张照片有点糊" + 重拍 primary + "强制分析 · 结果将标记低置信度" ghost + 3 条拍摄建议。文案与 reject 态的"强制分析"按钮也做了同步对齐（empty-error.html:230），术语一致。
3. **`report-detail.html:179-188` 整改建议 step 卡的 3.5% accent tint + step--done 回中性**。极浅渗透不抢眼，且建立了"未完成才热、已完成回灰"的进度节奏 —— 既解决 report ↔ detail 视觉断裂，又顺手加了一个 progress affordance。这是 `/impeccable typeset` 应当长这样的小手术。

---

## Priority Issues

**[P1] H10 帮助 / 文档入口仍未建立**
- File: 全套（无 `?` icon、无引导）
- 为什么重要：王师傅 persona 第一次打开 Safety Scout 仍是"碰运气"。Tips 只内联在错误态里，正常路径上没有任何 "拍出好照片" 文档入口。这是当前 35/40 的最大单点空缺，要破 36/37 必经此路。
- Fix: home.html topnav 右侧加 `?` icon → 弹简短引导面板（首次自动展开、之后手动）；或 home.html 上传卡下加一行 "拍出好照片的 4 个要点" 折叠 `<details>`。
- Suggested command: `/impeccable onboard`

**[P2] home.html dropzone tap target 仍是 `<a href>` 而非 file-picker**
- File: `home.html:254`
- 为什么重要：mockup 阶段无伤，落 Taro 代码就是错的 tap target —— 用户预期 "点了打开相机"，实际是 "点了跳到 polling 页"。CLAUDE.md §1 "三步无摩擦"被这一行轻微破坏。Phase 3 接 `<input type="file" capture="environment">` 时需要 mockup 也呈现该交互（picker → 选定 → 上传中 → 跳页）。
- Fix: 把 `<a class="dropzone__tap">` 改为 `<label class="dropzone__tap" for="hiddenFilePicker">` + 隐藏 `<input type="file" accept="image/*" capture="environment">`；视觉不变但语义对了。
- Suggested command: `/impeccable harden`

**[P2] detail 页缺 "本次报告第 N/M 条" 位置感**
- File: `report-detail.html:344-347` pager 区
- 为什么重要：H7 -1 的主因之一。`← 上一条/下一条` 不告诉用户"我在哪"；3 条隐患的报告里第 2 条和第 3 条只能靠 disabled 状态推断。
- Fix: pager 中间加一个 `<span class="pager__pos">2 / 3</span>`，与按钮同行；mono 字 + muted 色。
- Suggested command: `/impeccable clarify`

**[P3] `.brand__mark` 仍是 SaaS chip 形态（橙色圆角方块 + 安全帽 SVG）**
- File: 全套 topnav
- 为什么重要：这是产品的 "底盘信号"。从字母 chip 到 helmet chip 升级过了，但容器还是 Linear 风 app-tile，二刷会被一眼识破。
- Fix: brand mark 改为更"工地工程"的视觉锚 —— 比如纯 SVG 单色 logomark（无圆角方块裹层），或把 chip 高度收到 24px、移除 box-shadow / hover lift，让它更像印章而非 app icon。
- Suggested command: `/impeccable shape`（这是 IA / brand 层决策，不是 polish 范围）

---

## Persona Red Flags

**王师傅（50 岁，工地单手，触屏）**：
- 模糊态终于有了专门出口（`empty-error.html:202-238`），抖动 / 失焦不再被推到"拒识"或"低置信度强行分析"两个错路径。
- `polling.html:175-176` "不想等？取消并返回" 仍是 13px underline-only。50 岁老花 + 工地强光下基本看不见；上轮 minor 漏了，本轮也未修。下一轮可考虑提到 15px + `text-decoration-thickness:1.5px`。
- `home.html:254` 仍 `<a>` 当 tap target（见 P2）。
- topnav 仍无 `?` icon，首次使用没有引导（见 P1）。

**项目经理（桌面审阅，PDF 导出）**：
- sidepanel 1024 适配后，iPad landscape 审阅终于看得到"本次扫描概要"。
- `导出 PDF` 仍是 ghost button（`report.html:340-343`）—— 与"分享给班组优先"对齐，但 PDF 主使用者要越过橙色 primary 找灰色 secondary。两 persona 在同一 hero 上拉锯仍未解决，下一轮可考虑 hero CTA 按 viewport 切换（mobile = 分享 primary、desktop = PDF primary）。
- `report-detail.html:499` "导出整改单 PDF" 只导这一条；从 detail 流出仍只能靠面包屑回 report 找"导出本次报告 PDF"。

---

## Minor Observations

1. polling.html `.elapsed__fill { transition:width .8s ease }` (`polling.html:156`) 是 detector 唯一真实命中。0.8s 单元素无伤，但落 Taro 代码前换 `transform:scaleX()` + transform-origin。纳入"Phase 3 代码化前债务清单"。
2. `empty-error.html` reject 态 tips 第 3 条仍提"强制分析"按钮 —— 与本轮统一后的按钮文案"强制分析 · 结果将标记低置信度"一致，不冲突，但措辞可考虑改"低置信度强制分析"使括号词序更顺。
3. `report-detail.html` 中 `.step--done` 标记后 `.step__check::after` 的红色待办点会从"还没办"状态消失，但视觉上没有"刚完成"动效。可考虑给 `.step--done` 加 50ms scale-fade 让"刚刚标记"有反馈（critique 此次不强求）。
4. `history.html .dayhead { top:54px }` mobile 适配已加（`history.html:170-173`），但桌面上若用户 zoom > 110%，topnav 高度被 chrome 改造，sticky 仍会差几像素 —— 可考虑用 `var(--topnav-h)` CSS 变量根 absolute 化。下一轮 polish。
5. `report-detail.html` annot tag 改去 `#` 前缀后，无障碍 reader 读出来是 "1 H1 立网松弛" / "2 H9 未系安全带"，读法略生硬。可在 `.annot__tag` 外层加 `aria-label="第 1 处标注 H1 立网松弛"` 提升朗读体验。
6. `empty-error.html` blurry 态新加的 SVG 用 `filter:blur(0.8px)` 模糊隐喻 —— 视觉表达直接，但 prefers-reduced-motion 不影响 filter；如果项目后续要对低视力用户做无障碍照顾，filter 应允许被 forced-colors 取消。

---

## Questions to Consider

1. **H10 是这套设计现在最大的单点空缺 —— `?` icon 弹引导 vs home 上传卡折叠 tips，哪种更不破"三步无摩擦"？** 弹层会打断流，折叠 tips 容易被忽略。也许首次使用 1-shot tooltip（用过即消）是第三条路。
2. **report.html 的 hero CTA 应该 viewport 自适应吗？** mobile 上"分享给班组"是 primary，桌面上项目经理要的是"导出 PDF"。两 persona 在同一表面上的 CTA 拉锯，要么按 viewport 切换 primary/ghost，要么干脆把两个 CTA 都做成同等权重 dual-primary（违反"一屏一个 primary"惯例，但符合这个特殊场景）。
3. **`.brand__mark` 是 product mark 还是 helmet logo？现在两个都没做透。** 真正的工程 / 工地品牌（如 PingCAP、JFrog、Datadog）的 mark 都是单色 logomark，没有橙色圆角方块裹层。下次到 brand 层时这个值得正面解决。
