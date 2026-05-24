# UI Parity Audit · 真实代码 vs 2026-05-22 unified-modern-minimal mockup

**审查时间**：2026-05-24
**审查分支**：`feat/clean-ui`
**审查范围**：`miniprogram/src/` 真实 H5/小程序代码 ↔ `docs/plans/2026-05-22-unified-modern-minimal/` 6 屏 HTML mockup
**审查方法**：静态代码比对（read-only），不跑 e2e（H5 build 命令在审查时段仍未产出，但 `tests/e2e/h5-responsive-*-home.png` 上一轮 May 22 17:10 截图仍可参考 —— 截图反映的 src 状态等于本审查的 src 状态）

---

## 一句话结论

**当前代码 UI 对齐度估计：35%**。tokens 命名层基本对齐（hex 已替代 oklch、命名表 --ink/--line/--high/--accent 与设计稿一致），但**视觉系统、信息架构、文案、组件行为四个维度都有显著偏离**：dev-chrome 严重（"Claude Vision 分析"、模型名直接铺在 sidepanel）、Brand mark 仍是 SaaS 字母 chip（不是工地 helmet）、TopNav 不 sticky 且没有固定 60/54px 高度、history 页完全缺失（且后端无 list 接口）、EmptyState 未抽离、第 4 态（模糊）完全缺、StepList 是简单进度组件而非 checkbox + confirm sheet + undo toast 的硬化版。

阶段 B 的 9 个切片**不应在一个 session 内完成** —— 详见末尾"阶段 B 工作量评估"。

---

## 逐屏对比

### 1. `home.html` ↔ `pages/index/{mobile,desktop}.tsx`

**桌面（desktop.tsx）**

| 维度 | mockup | 代码 | 判定 |
|---|---|---|---|
| Hero 文案 | "拍一张工地照片，AI 立刻找出隐患。" | "开始一次现场巡检" | ❌ 不一致 |
| Hero lede | "面向安全员的隐患识别工具。识别高处坠落、临边洞口、用电、消防、个人防护等十类常见隐患…平均 29 秒出报告。" | "上传一张施工现场照片，AI 会在 30 秒内识别隐患、引用规范条款、给出可执行的整改建议。" | ⚠️ 部分相近 |
| Hero 顶部 eyebrow | （无） | "AI 现场巡检" | ❌ 多了一个 eyebrow |
| Hero 右上 actions | （无，新建巡检按钮藏在 dropzone 里） | "历史报告 + 新建巡检" 两按钮 | ❌ 多余 |
| 上传卡 specs | "JPG / PNG · 单张 ≤ 10 MB · 不会上传到任何第三方" | "JPG · PNG · HEIC · 最大 15MB" | ⚠️ 部分（缺隐私说明、MB 数不同） |
| 三步流程卡 | 有（拍照 / 等待 / 看报告） | ❌ 完全缺 | ❌ 缺 |
| Engine strip | （无） | "Claude Sonnet 4.5 · 平均 29s · 服务可用 · v0.3.1" | ❌ **dev-chrome**（暴露模型名、版本号） |
| Aside 今日统计 | （在 home 上有 stats grid + 最近巡检列表） | ✅ 有 | ✅ 一致 |
| Aside 最近巡检 | 3 条 list item（含照片缩略） | ❌ 空态"暂无历史" | ❌ 不一致（这条要等 history list API） |

**移动端（mobile.tsx）**

| 维度 | mockup | 代码 | 判定 |
|---|---|---|---|
| 顶导 | 共享 TopNav（54px 高 / sticky） | 独立 `.brandBar`（不 sticky、与桌面不同结构） | ❌ 顶导不统一 |
| Hero 文案 | "拍一张工地照片，AI 立刻找出隐患" | "拍一张" + "AI 找隐患" 两行 | ❌ 不一致 |
| 主 CTA | 整块橙色 `.dropzone__tap`（"拍照"大字 + 副"对准隐患区域 AI 越靠近识别越准" + 下方小链接"或从相册选择已有照片 →"） | `<BigButton text="开始巡检" subtitle="拍照·上传·等待报告">` + 下方 `<Button variant="ghost" block>从相册选择` | ❌ 视觉权重 + 文案均不一致 |
| Tap target 行为 | `<a href="polling.html">`（mockup 已知设计问题，落代码时应是 `<input type=file capture=environment>`） | ✅ `captureImage()` hook 走真相机 intent | ✅ 落代码做得比 mockup 还对 |
| 今日统计区 | （无，移动 mockup 没有） | 有 `.today` 区 4 个 Stat | ❌ 多了 |
| 上次巡检 Photo 锚 | （无） | 有（仅 lastPhoto session 内） | ❌ 多了 |

---

### 2. `polling.html` ↔ `ProgressTracker/` + `pages/report/*` 轮询分支

| 维度 | mockup | 代码 | 判定 |
|---|---|---|---|
| 路由形态 | 独立 polling.html 屏 | 在 report.tsx 内根据 status==queued/processing 分支渲染 | ✅ 设计合理（前端路由结构）|
| Hero 主角 | 3-state tracker 当 hero（全屏居中、`stage` 容器） | `ProgressTracker` 包在 `.processing` / `.processingWrap` 中（不是 stage hero） | ⚠️ 视觉权重弱于 mockup |
| 3-state tracker 横向 | ✅ 横向 grid + 流动线 + done/active/pending 三态 | ✅ ProgressTracker 已实现（接近 mockup） | ✅ 大致一致 |
| 进度条 + 已用时 | ✅ 进度条 + "已用时 X / 预计 0:29" | ✅ ProgressTracker 已实现 | ✅ 一致 |
| Livelog（4 行实时分析，引 JGJ80-2016） | ✅ 有 livelog 容器 + done/active/pending 三态 dot | ❌ 完全缺 | ❌ 缺 |
| `.shot__badge` "已上传" 药丸 | ✅ 在照片上探出 | ❌ 无该组件 | ❌ 缺 |
| "不需要等在这页" 文案 | ✅ stage__cancel + 链接"取消并返回" | ✅ ProgressTracker.hint 文案存在（"完成后会自动跳转"） | ⚠️ 部分一致（缺"取消并返回"链接） |
| TopNav aria-current="step" | mockup 改为 "step"（critique P0 已修） | ❌ 代码侧仍是 `activeTab="reports"` → aria-current="page" | ❌ 未落地 |
| safe-area 表达式 | `bottom: calc(-10px - env(safe-area-inset-bottom, 0px))` | （代码侧无 .shot__badge）| n/a |

---

### 3. `report.html` ↔ `pages/report/{mobile,desktop}.tsx`

**桌面（desktop.tsx）**

| 维度 | mockup | 代码 | 判定 |
|---|---|---|---|
| Breadcrumb | "报告 / 5 月 22 日 · 14:08 外架巡检" | "← 报告 / NO.XXXX" | ❌ 不一致（缺日期 + 描述）|
| Header eyebrow | （无） | （无） | ✅ 一致 |
| Header h1 | "外架安全网松弛破损，高处坠落风险极高"（mock 取自 hazard） | "现场巡检报告" | ❌ 不一致（mockup 用 hazard 自然语言、代码用通用标题）|
| Header lede | （hero-card 内部 sum，描述 hazard） | "由 Claude Vision 分析 · N 项隐患" | ❌ **dev-chrome**（"Claude Vision" 暴露）|
| Hero CTA 主次 | "分享给班组" primary + "导出 PDF" ghost + "和现场不一致？" `<details>` 折叠"用同一张照片重新分析" | "导出 PDF" secondary + "分享" secondary + "转派班组" primary，无 `<details>` 折叠 | ❌ 主次倒装 + 缺 redo-disclosure |
| Hero card 一体化（左照片 / 右 severity-tag + h1 + sum + meta + actions） | ✅ 一体 | ❌ 拆成多块（breadcrumb / header / hero grid / alarmRow / listCard / signoff / footer） | ❌ IA 不一致 |
| 筛选 chip "全部 / 高 / 中 / 低" + count | ✅ 含 chip count + count=0 时 aria-disabled | ⚠️ 有 chip 但无 count、无 aria-disabled | ❌ 部分 |
| Hazards list | ✅ `.haz` 卡片含 num + code + name + pill + 现象 + 引用规范 + .suggestion-callout 橙色块 | ⚠️ HazardItem（待详查） | ⚠️ 部分（缺 .suggestion-callout 橙色块）|
| sidepanel `本次扫描概要` | ✅ 一张 card：bar(高3 中0 低0) + 涉及类别 pill + 拍摄与分析 + `<details class="tech-disclosure">` 藏 SHA/模型 | ❌ ReportSidebar 直接暴露 "模型: claude-sonnet-4-5" 在第二个 metaCell（**dev-chrome**） | ❌ 不一致 + dev-chrome |
| sidepanel 响应式断点 | `@media (min-width:1024px)`（critique 已修 1180→1024） | desktop.module.scss 待详查；hero grid 是 `1.4fr 1fr`，无 1024 sidepanel 切换 | ❌ 未落地 |
| 签字栏（安全员/班组长/项目经理） | （mockup 无） | ✅ 有 .signoff 3 联 | ❌ 多余（不属于 mockup IA） |
| Footer "Safety Scout · v0.3.1 / NO.XXXX · 报告完" | （mockup 用全局 `.metaftr` "服务可用 / 所有页面 →"） | ❌ "v0.3.1" 是版本号 dev-chrome | ❌ 不一致 |

**移动端（mobile.tsx）**

| 维度 | mockup | 代码 | 判定 |
|---|---|---|---|
| 顶导 | TopNav 共享 | AppBar（独立组件，不复用 TopNav） | ❌ 不一致 |
| 概要卡 | hero-card 全宽，含照片 + severity-tag + h1 + sum + meta + 2 CTA | summaryCard：eyebrow + 数字 + pill + summary + breakdown 三 pill | ❌ 结构完全不同 |
| 粘性底部 actbar | （mockup 无 sticky actbar，CTA 在 hero 里） | ✅ `.actbar` sticky 导出 PDF + 转派班组 | ❌ 多余 sticky |

---

### 4. `report-detail.html` ↔ desktop.tsx 右栏 / 单 hazard 视图

mockup 是独立 detail 屏（H1 高处坠落 一条详情 + 标注 photo + tabs(规范条款/整改建议·4 步/处置记录) + 确认表 + undo toast）；代码侧**没有单 hazard 详情页**，HazardItem 把所有信息内联在 report list item 里。

| 维度 | mockup | 代码 | 判定 |
|---|---|---|---|
| 单 hazard 视图 | 独立屏 | ❌ 无 | ❌ 全缺 |
| 标注 photo | ✅ annot box + tag "1 · H1 立网松弛" | ❌ 无 | ❌ 缺 |
| Tabs 规范/整改/记录 | ✅ 3 tab + tab panel | ❌ 无 | ❌ 缺 |
| step checkbox + confirm sheet + 5s undo toast | ✅ `.step__check` role=checkbox + 高 stakes 确认表 + toast | StepList 是 done/active/pending 简单进度（无交互） | ❌ 完全未实现 |
| .reg__quote 字体 | 非 display 字体（blockquote 编辑引用约定） | ❌ 无 | n/a |
| .step__act 用 display 字体 | ✅ | ❌ 无 | n/a |
| sticky 改 mobile-first | ✅ `@media (min-width:981px)` 才 sticky | ❌ 无 | n/a |
| prefers-reduced-motion guard | ✅ | ❌ 无 | n/a |

---

### 5. `history.html` ↔ （代码缺口）

代码侧**完全没有** `pages/history/`。

| 维度 | mockup | 代码 | 判定 |
|---|---|---|---|
| history 页 | ✅ 存在 | ❌ 全缺 | ❌ |
| 顶部 summary strip（24 / 8 / 18 / "H1 高处坠落 11 次"） | ✅ | ❌ | ❌ |
| Toolbar：search + "本周 ×" + "待整改 ×" + "+ 加筛选" 浮层 | ✅ | ❌ | ❌ |
| Filter sheet 4 组（时间 / 严重度 / 状态 / 类别） | ✅ Esc + 外部点击关闭 | ❌ | ❌ |
| Daygroup + dayhead sticky | ✅ top: 60px / mobile 54px | ❌ | ❌ |
| Row severity counts pill "H ×3 / M ×1 / L ×1 / ✓ 通过" | ✅ | ❌ | ❌ |
| **后端依赖** | mockup 不需后端 | **后端只有 `list_orphaned_queued`、没有 `GET /api/v1/inspections` 列表接口** | ⚠️ 阻塞 |

---

### 6. `empty-error.html` ↔ 各页内联 empty/error 分支

代码侧没有 `components/EmptyState/`。各页 empty/error 分支都内联：

| 态 | mockup | 代码 | 判定 |
|---|---|---|---|
| **空状态 / 冷启动** | ✅ `.state__art--empty` + "拍下第一张" primary + "看示例报告" ghost | ❌ home 直接渲染上传卡，没有"零巡检"主态切换 | ❌ |
| **照片模糊 / 低质量**（critique P1 新增第 4 态） | ✅ blurry 态完整：motion-blur SVG + "这张照片有点糊" + 重拍 primary + "强制分析 · 结果将标记低置信度" ghost + 3 tips | ❌ 完全缺 | ❌ |
| **AI 拒识 / 不是工地图** | ✅ `.state__art--reject` + tips | ❌ 代码侧 mapApiError 走 Taro.showToast 弹一行短信息 | ❌ |
| **网络 / 服务失败** | ✅ `.state__art--net` + "重试上传" + "仅保存本地" + tips | ⚠️ 代码侧 ErrorView 只显示 icon + userMessage + retryHint，无 tips/CTA 多选 | ❌ |

---

## 全局：tokens.scss 对齐

| 项 | mockup（oklch） | 代码（hex） | 判定 |
|---|---|---|---|
| `--bg` | `oklch(99% 0.002 240)` 冷白 | `#FAFAF8` 暖白 | ⚠️ **有意偏离**（用户明确说保留暖白），但 tokens.scss 顶部注释**未明确说明这是有意为之** —— 应补 |
| `--surface` | `oklch(100% 0 0)` | `#FFFFFF` | ✅ |
| `--surface-2` | `oklch(97% 0.004 250)` | `#F4F4F2` | ⚠️ 接近 |
| `--ink`（mockup `--fg`） | `oklch(18% 0.012 250)` | `#0E0E0C` | ⚠️ 接近（mockup 冷一点点）|
| `--accent` | `oklch(66% 0.17 50)` 安全橙 | `#E85D2C` | ⚠️ 接近（mockup 是约 #E45F2A）|
| `--high` | `oklch(58% 0.20 28)` | `#D7373F` | ⚠️ 接近（mockup 偏橙红、代码偏正红）|
| `--med` | `oklch(70% 0.15 70)` | `#C77A1F` | ⚠️ 接近 |
| `--low` | `oklch(60% 0.13 155)` | `#2F8454` | ⚠️ 接近 |
| `--r-sm` 圆角 | mockup 6px | 代码 10px | ❌ pill / 小卡圆角偏大 |
| `--r-md` 圆角 | mockup 10px | 代码 14px | ❌ 卡片圆角偏大 |
| `--r-lg` 圆角 | mockup 14px | 代码 20px | ❌ 大卡圆角偏大 |
| 字体 | mockup `--font-display` PingFang SC + `--font-mono` JetBrains Mono | `--f-sans` PingFang SC + `--f-mono` IBM Plex Mono | ⚠️ mono 字不同（IBM Plex Mono vs JetBrains Mono） |
| 阴影 | mockup 用 oklch alpha | 代码用 rgba | ✅ 等价 |

**判定**：tokens 命名层面对齐，色值近似，**圆角系统统一偏大 4-6px**（让整套视觉比 mockup 更"软"）。

---

## critique 6 个 priority issue 在代码侧落地状态

按 `.impeccable/critique/2026-05-24T13-57-35Z__docs-plans-2026-05-22-unified-modern-minimal.md`（最新一份，35/40）：

| # | Priority | mockup 状态 | 代码落地 | 判定 |
|---|---|---|---|---|
| 1 | H10 帮助/文档入口 | （仍未做，需 onboard） | 代码端同样无 ? icon、无引导 | ❌ 一致缺失 |
| 2 | home.html dropzone tap target 应是 `<input type=file>` | （仍是 `<a href>`） | ✅ mobile 已用 captureImage hook，desktop 用 UploadDropzone | ✅ **代码做得比 mockup 更对** |
| 3 | detail 页缺 "本次报告第 N/M 条" | （未触） | 没有 detail 页 | ❌ |
| 4 | `.brand__mark` SaaS chip → helmet logo | （未触，mockup 仍是 helmet SVG 装在橙圆角方块里） | 代码 Brand 是 "S" 字母 + 橙圆角方块（**还没升级到 helmet SVG**） | ❌ 落后于 mockup |
| 5 | quieter dev-chrome（SHA / 模型 / Prompt 版本 / STEP eyebrow） | ✅ 已做（livelog、details 折叠） | ❌ engineStrip "Claude Sonnet 4.5" / ReportSidebar 模型名直接暴露 / "由 Claude Vision 分析" lede / "v0.3.1" footer | ❌ **严重未落地** |
| 6 | safe-area no-op 修复 | ✅ 已修 | n/a（代码侧无 .shot__badge） | n/a |
| 6 | aria-current page → step | ✅ 已修 | ❌ 代码侧仍是 `activeTab="reports"` 在 polling 分支 | ❌ |
| 6 | "中 0 / 低 0" chip 噪声压制 | ✅ 已加 aria-disabled | ❌ 代码 filterChip 无 count 无 aria-disabled | ❌ |
| 6 | dayhead mobile 54px | ✅ 已加 | n/a（无 history 页） | n/a |
| 6 | 整改 step checkbox + confirm + undo | ✅ 已加 | ❌ StepList 是简单 done/active/pending，无 checkbox 交互 | ❌ |
| 6 | report ↔ detail .step accent tint 同源 | ✅ 已加 | n/a（无 detail 视图） | n/a |

---

## 缺口清单（mockup 有 / 代码没有）

1. **`pages/history/`** 整页 + 顶部 summary strip + toolbar + filter sheet + daygroup sticky
2. **`components/EmptyState/`** 抽离，覆盖 4 态（empty / blurry / rejected / network）
3. **第 4 态"模糊照片"**（critique P1 修复后新增）
4. **`pages/report/detail`** 单 hazard 详情（独立屏 + 标注 photo + tabs + step interactive）
5. **`components/SuggestionCallout`** 报告列表 hazard 卡里的橙色整改建议块（`.suggestion-callout`）
6. **`components/RedoDisclosure`** "和现场不一致？" 折叠 + "用同一张照片重新分析"按钮
7. **`components/TechDisclosure`** sidepanel 里 `<details>` 折叠技术信息（SHA / 模型 / Prompt 版本）
8. **TopNav sticky + 60/54px 固定高度**（当前 padding 20px 自适应）
9. **`.shot__badge` "已上传" pill** 在 polling 照片下方
10. **`livelog` 4 行实时分析** 在 polling tracker 下方
11. **stage__cancel "不想等？取消并返回"** 链接
12. **三步流程卡**（home 上的 .upload__steps "01 拍照 / 02 等待 / 03 看报告"）
13. **filterChip count 状态** + count=0 时 aria-disabled
14. **签字栏移除**（mockup 没有，代码多余）
15. **engineStrip 模型名移除**（dev-chrome）
16. **Footer "v0.3.1" 移除**（dev-chrome）

---

## 风险清单

1. **oklch 在 Taro / 微信小程序端不稳** —— 当前 tokens 已经全部用 hex，H5 端正常。但如果想保留 oklch 源标注，建议加注释指明色值来源（`#FAFAF8 /* ~oklch(99% 0.002 240) 暖偏移 */`），方便未来切换。
2. **`focus-visible` 在 Taro `<View>` 上不工作** —— Taro 把 `<View>` 编译到小程序 `<view>`（无 :focus 概念），H5 端 `<View>` 实际是 `<div>`，需要 `<div tabindex="0">` + 自定义 :focus-visible 才有效。当前代码大量用 `<View role="button">`，没有 tabindex、也没 :focus-visible 样式。**这是 a11y 大坑**，落地切片 9 时要明确：mobile/小程序端不可能有键盘 focus，桌面 H5 端要 tabindex=0 + 显式 :focus-visible 样式。
3. **`backdrop-filter` 在小程序端不支持** —— 当前 TopNav `backdrop-filter: blur` 只在 H5 端生效，小程序端会退化为半透明白底，可能与下方内容混淆。考虑在小程序端用 `background: rgba(255,255,255,0.98)` fallback。
4. **`env(safe-area-inset-bottom)` 在小程序端表现不稳** —— iOS 微信 webview 部分支持，Android 不支持。如果 `.shot__badge` 要全平台一致，需要 `padding-bottom: constant(safe-area-inset-bottom)` + env() 双写。
5. **CSS 自定义属性 `var(--ink)` 在小程序 `<text>` 上工作** —— 已在 Brand 组件里验证可用。但部分 SCSS module 类名嵌套深度过深时（Taro 编译时类名 mangling），CSS var 解析层级需要测试。
6. **history 页阻塞**：后端无 `list_inspections` 接口（`backend/app/storage/inspection_repo.py` 只有 `list_orphaned_queued`、`get`、`create`、`update_*`）。切片 8 的"对接 GET 接口"在落地前需要先加后端 list endpoint —— **这与"不要碰 backend/"约束冲突**，需要用户决策。
7. **`<details>` / `<summary>` 在 Taro 小程序端不可用** —— 小程序无原生 details，需要用 useState 自实现折叠组件。H5 端可用。redo-disclosure 和 tech-disclosure 都要看 Taro 编译策略。
8. **`<input type="file" capture="environment">`** 在小程序端不存在 —— 当前移动端用 `captureImage()` hook 调 `Taro.chooseImage`，OK。但桌面 H5 端 UploadDropzone 应该用真的 `<input type=file>`（让用户拖入 + 点击选择）。**需确认 UploadDropzone 当前是否真用 `<input>` 而非 `<a>` 跳页**。
9. **`window.print()` 是 H5 only** —— 当前 `handleExportPdf` 已经 guard `process.env.TARO_ENV === 'h5'`，小程序端弹 toast。OK。

---

## 阶段 B 工作量评估

切片 1-9 每片真实工作量预估（含代码 + 测试 + commit）：

| 切片 | 范围 | 改动文件预估 | 时间预估 | 风险 |
|---|---|---|---|---|
| 1. TopNav 统一 | TopNav.tsx + scss + Brand + tests | 4-5 个 | 30-45min | 低 |
| 2. tokens 校准 | tokens.scss + 注释 + 跑全套快照测试 | 1 个 + 测试可能更新多个快照 | 30min | 中（圆角变小会冲击大量布局） |
| 3. home 页对齐 | desktop.tsx/scss + mobile.tsx/scss + 三步流程组件 + UploadDropzone 调整 + 删 engineStrip | 6-8 个 | 1-1.5h | 中 |
| 4. polling 对齐 | ProgressTracker 扩 livelog + shot__badge + stage__cancel + aria-current step + 重排 layout | 3-4 个 | 1h | 中 |
| 5. report 对齐 | desktop.tsx/scss 大改（hero-card 一体化、删 signoff、删 engineStrip、SuggestionCallout 新组件、TechDisclosure 折叠、sidepanel 1024 断点）+ mobile.tsx/scss（删 actbar sticky、改 hero card 结构） | 8-10 个 | 2-3h | 高（动 IA 层）|
| 6. report-detail 视图 | 新增 pages/report/detail/ + 标注 photo + tabs + step interactive（checkbox + confirm sheet + undo toast）+ 单测 | 6-8 个新文件 | 2-3h | 高（StepList 重写 + 模态交互） |
| 7. EmptyState 抽离 + 模糊态 | 新增 components/EmptyState/（4 态）+ 替换各页内联 + 单测 | 5-7 个 | 1-1.5h | 中 |
| 8. history 页 | 新增 pages/history/{index,mobile,desktop} + scss + filter sheet + 后端 `list_inspections` endpoint + API 客户端 + e2e | 8-12 个 + 后端 3-4 个 | 3-4h | 高（**牵涉后端 + 用户约束冲突**）|
| 9. 全局 polish | :focus-visible 跨平台策略 + 删 dead CSS + 清 dev-chrome 散落文案 + "强制分析" 文案统一 + safe-area + sticky 媒体查询 | 10+ 个 | 1-1.5h | 中（focus-visible 在 Taro 上需要 tabindex 改造） |

**总计估算：15-20 小时工程工作**，加测试 / 截图回归 / commit 整理大约 18-22 小时。

**一个 session 内做完 9 切片不现实**（context window + 注意力 + 测试反馈循环）。

---

## 建议执行顺序（分批 session）

**第一批（基础对齐，~3-4h）**：切片 1 + 切片 2 + 切片 9 部分（dev-chrome 清扫 + dead CSS）—— 影响最广、风险最低、改动相对独立。完成后整套视觉系统就对齐了。

**第二批（主流程页，~3-4h）**：切片 3 + 切片 4 + 切片 5 mobile 部分 —— home / polling / report mobile 三条用户主流量入口对齐。

**第三批（桌面深度，~3-4h）**：切片 5 desktop + 切片 6 部分（基础 step interactive，先不做 confirm sheet/undo）。

**第四批（缺口补齐，~3-4h）**：切片 7（EmptyState）+ 切片 6 剩余（confirm sheet + undo toast）+ 切片 9 剩余（focus-visible / safe-area）。

**第五批（独立，~3-4h，需先后端决策）**：切片 8（history）—— 因后端 list 接口缺、与"不要碰 backend"约束冲突，**需用户先决策**：(a) 临时在 backend 加 list endpoint，(b) history 页用前端 localStorage 缓存（不要求服务端历史，只显示本设备拍过的），(c) 推迟到后端阶段。

---

## 落地完成（2026-05-24）

**本 session 完成 7/9 切片**（B6 / B8 跳过，新功能开发单独 session 做）。

### Commit 清单（branch: `feat/clean-ui`）

| Commit | 切片 | 改动文件数 | 行数 (+/-) | 关键改动摘要 |
|---|---|---:|---|---|
| `7942772` | B1 TopNav | 6 | +161 / -90 | sticky 60/54px、删 search、Brand mark → helmet SVG、ariaCurrent step 支持 |
| `f8759bd` | B2 tokens | 1 | +81 / -49 | 圆角 10/14/20 → 6/10/14，mono 字 IBM→JetBrains，注释暖白保留 |
| `805b007` | B3 home | 5 | +197 / -271 | 删 eyebrow/engineStrip/headerActions、新增三步流程卡、mobile 顶导改 TopNav + 大橙 dropzoneTap |
| `8f366d4` | B4 polling | 4 | +543 / -6 | ProgressTracker 加 livelog 4 行 + onCancel；轮询分支 ariaCurrent="step" |
| `cda26a8` | B5 report | 12 | +372 / -142 | HazardItem fix block→accent-soft callout；ReportSidebar 重写（bar+segments+TechDisclosure 折叠 model）；删 "Claude Vision"/"v0.3.1" dev-chrome；CTA 主次调整；filterChip 加 count+aria-disabled；mobile 删 sticky actbar |
| `15d02d8` | B7 EmptyState | 3 | +443 / -0 | 新组件 4 态（empty/blurry/rejected/network），含 9 个 unit tests |
| `a58f129` | B9 polish | 2 | +11 / -0 | Button :focus-visible、mobile dropzoneTap safe-area |

### 测试结果

- **150 jest tests 全通过**（B1 前 140 → B7 +9 EmptyState = 149 → +1 TopNav ariaCurrent = 150）
- **0 snapshot 破坏**（圆角变化未影响任何快照，测试均基于结构属性）
- **0 skipped** —— 符合 [[feedback_phase_unit_tests]] 红线

### 跳过的切片（留下次 session）

#### B6 · report-detail 视图（0-to-1 新页）

**未做原因**：mockup `report-detail.html` 是从 hazard 列表 "查看条款 →" 跳过去的独立屏，包含：
- 新 route `pages/report/detail/`
- annotated photo（accent-bordered annot box + #1 / #2 tag）
- Tabs（规范条款 / 整改建议 4 步 / 现场处置记录）
- Interactive step（`role="checkbox"` + aria-checked + 高 stakes 确认表 + 5s undo toast）
- prefers-reduced-motion guard

是 0-to-1 新功能开发，最小 2-3h 工作 + 测试，超出"对齐"范畴。

**建议**：单独 session，从 `superpowers:writing-plans` 入口建一份 detail 页 plan，然后 `superpowers:executing-plans` 落地。

#### B8 · history 页（0-to-1 新页 + 数据层）

**未做原因**：
- 新 route `pages/history/{index,mobile,desktop}/`
- summary strip + toolbar（search + chip + filter sheet 浮层）
- daygroup sticky + row severity counts pill
- **后端阻塞**：`backend/app/storage/inspection_repo.py` 没有 `list_inspections` endpoint
- localStorage 临时方案需新增 `historyStore.ts`（getList / clear / append）+ 接入各页

最小 2-3h 工作。**前置依赖**：决定 list 数据源（localStorage vs 临时后端 endpoint），需用户单独决策。

### 对齐度估计

| 维度 | 改前 | 改后 |
|---|---|---|
| 视觉系统（token / 圆角 / 字体 / accent） | 60% | 92% |
| 信息架构（顶导 / CTA 主次 / 整改 step / dev-chrome / footer） | 40% | 75% |
| Brand mark | 0%（字母 chip） | 100%（helmet SVG） |
| polling stage（livelog / cancel / aria-current） | 30% | 90% |
| report 页（hero / sidepanel / SuggestionCallout / model 折叠） | 25% | 80% |
| EmptyState 抽离 + 模糊态 | 0% | 70%（组件就位，各页未替换） |
| history 页 | 0% | 0%（未做） |
| detail 页 | 0% | 0%（未做） |
| **加权对齐度** | **35%** | **约 70%** |

剩余 30% 主要由 B6 / B8 + EmptyState 在各页的实际替换 + a11y 完整改造（focus-visible 跨平台 / tabindex 系统化）构成。

### 已知风险（继承自 audit 风险清单）

1. `oklch` 已统一为 hex（保留源色注释），跨端兼容稳；
2. `backdrop-filter` 在小程序端会退化（B1 TopNav 受影响），需 weapp 端 fallback 检验；
3. `:focus-visible` 在 Taro `<View>` 端要 tabindex 配合才完整工作（B9 加了 .btn 的样式，但全套 :focus-visible 系统化改造尚未做）；
4. ProgressTracker livelog 用 `aria-live="polite"`，screen reader 友好；但 `Text` 节点在 Taro 编译产物里行为需在真机验证。

