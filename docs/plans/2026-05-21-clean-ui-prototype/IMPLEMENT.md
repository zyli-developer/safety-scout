# Safety Scout · UI 重构任务书

> **TO**: 任何接到这份任务的 AI Agent（Claude Code / Cursor / 等）
> **FROM**: 设计评审已通过的新 UI 方向 · 2026-05-21
> **GOAL**: 把 `miniprogram/` 现有的 Taro UI 改造成新的 Clean & Minimal 方向

读完这份文档你应该清楚：(1) 要做什么 / 不做什么 (2) 改哪些文件 (3) 按什么顺序切片提交 (4) 每片的验收标准。

---

## 0. 上下文

仓库：`safety-scout`
工程：`miniprogram/` 是 Taro + React + TypeScript 工程，编译到微信小程序 + H5 双端
当前 UI 状态：已落地 dossier「工地许可证」美学（见 `docs/plans/2026-05-20-miniprogram-ui-dossier-design.md`），被评审「乱、丑」否决
本任务：换成 Clean & Minimal 美学
原型参考：`docs/plans/2026-05-21-clean-ui-prototype/`（HTML + JSX + CSS 已落到这个目录，用浏览器打开 `index.html` 看效果）

**关键约束**：

- ✅ 后端 `backend/` 零改动
- ✅ API 契约 (`docs/specs/report-schema.md` / `docs/specs/hazards.md`) 零改动
- ✅ `src/api/*` / `src/hooks/*` / `src/types/*` / `src/utils/severity.ts` 业务逻辑零改动
- ❌ 不引入 webfont 库（Inter / Manrope / Geist 等都不要）
- ❌ 不引入 UI 组件库（antd / chakra 都不要，继续手写）
- ❌ 不引入 CSS-in-JS（继续用 SCSS module）
- ❌ 不增加 emoji
- ❌ 不画装饰元素：刻度尺 / 取景框 / 扫描线 / 点阵网格 / 角标 / 印章 — 全部不要

---

## 1. 设计 Token（必须严格落地）

新建 `miniprogram/src/styles/tokens.scss`，**整体替换**现有内容：

```scss
:root {
  // Neutrals — 暖白底
  --bg:        #FAFAF8;
  --surface:   #FFFFFF;
  --surface-2: #F4F4F2;
  --line:      #ECECE8;
  --line-2:    #DCDCD6;

  --ink:       #0E0E0C;
  --ink-2:     #4D4E4B;
  --ink-3:     #8A8B86;
  --ink-4:     #B6B6B0;

  // 唯一强调色：安全橙
  --accent:    #E85D2C;
  --accent-2:  #C44A1F;
  --accent-soft: #FFF1EA;
  --on-accent: #FFFFFF;

  // 严重度（克制，不发光）
  --high:      #D7373F;
  --high-soft: #FCE7E9;
  --med:       #C77A1F;
  --med-soft:  #FBEED6;
  --low:       #2F8454;
  --low-soft:  #DEEFE3;

  // 字体
  --f-sans: -apple-system, BlinkMacSystemFont, 'Helvetica Neue',
            'PingFang SC', 'Noto Sans SC', 'Hiragino Sans GB',
            ui-sans-serif, sans-serif;
  --f-mono: 'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, monospace;

  // 间距 (8px 基准)
  --s-1: 4px; --s0: 8px; --s1: 12px; --s2: 16px; --s3: 24px; --s4: 32px;
  --s5: 48px; --s6: 64px; --s7: 96px;

  // 圆角
  --r-sm: 10px;
  --r-md: 14px;
  --r-lg: 20px;
  --r-pill: 999px;

  // 阴影
  --shadow-sm: 0 1px 2px rgba(20,20,16,0.04);
  --shadow:    0 6px 24px rgba(20,20,16,0.06);
  --shadow-lg: 0 16px 48px rgba(20,20,16,0.10);
}
```

**字号 scale**（在各 module SCSS 里按需引用，不进 token）：

| 用途 | px | weight | line-height |
|---|---|---|---|
| title-xl | 56 | 600 | 1.05 |
| title-lg | 40 | 600 | 1.1 |
| title-md | 28 | 600 | 1.15 |
| title-sm | 20 | 600 | 1.2 |
| body | 15 | 400 | 1.55 |
| body-sm | 13.5 | 400 | 1.5 |
| caption | 12 | 400 | 1.4 |

**严重度色映射**改 `src/utils/severity.ts`：

```typescript
export const SEVERITY_COLOR: Record<Severity, string> = {
  high:   '#D7373F',
  medium: '#C77A1F',
  low:    '#2F8454',
};
export const SEVERITY_SOFT: Record<Severity, string> = {
  high:   '#FCE7E9',
  medium: '#FBEED6',
  low:    '#DEEFE3',
};
```

---

## 2. 字体改造

修改 `miniprogram/src/styles/fonts.scss`：

- **删除** IBM Plex Serif 引入
- **删除** IBM Plex Sans Condensed 引入
- **删除** Source Han Serif 思源宋体 woff2（如果有）
- **保留** IBM Plex Mono Regular + Medium 两个权重
- 同步删除 `src/assets/fonts/` 下不再用的 .woff2

`app.tsx` 的 `wx.loadFontFace` 调用：只保留 Plex Mono Regular，其他全部移除。

---

## 3. 组件改造

### 3.1 新增组件

| 路径 | 用途 |
|---|---|
| `src/components/Brand/` | 小品牌 mark（橙色方块 + "Safety Scout" 文字） |
| `src/components/TopNav/` | 桌面 4-tab 水平导航（巡检 / 报告 / 班组 / 设置） |
| `src/components/AppBar/` | 移动顶部栏（返回 + 标题 + 右操作组） |
| `src/components/Photo/` | 圆角工地图卡（接 src + meta 角标） |
| `src/components/SeverityPill/` | 严重度 pill（soft / solid 两 variant） |
| `src/components/Stat/` | 大数字 + 标注（接 num / label / tone） |
| `src/components/AlarmBox/` | 红软底警示条 |
| `src/components/ProgressRing/` | SVG 圆环进度（接 pct / label） |
| `src/components/StepList/` | 步骤列表（done / active / pending 三态） |
| `src/components/HazardItem/` | **新版**隐患列表 row（替代 HazardCard 卡片） |
| `src/components/Button/` | 统一按钮组件（primary / secondary / ghost / hero 四 variant） |

每个新组件的 props API 与渲染细节，**直接读** `docs/plans/2026-05-21-clean-ui-prototype/app/clean-components.jsx`。那是参考实现，把它从 JSX 翻译到 Taro `<View>` / `<Text>` 即可。

**重要**：原型里用了 `<button>` / `<input>` / `<svg>` 等 HTML 原生标签 —— Taro 编译到 weapp 时要换成 `<View>` / `<Text>` + `dangerouslySetInnerHTML`（参考现有 `src/components/Icon/index.tsx` 的处理方式）。

### 3.2 重写现有组件

| 现有组件 | 改动 |
|---|---|
| `src/components/HazardCard/` | **整体重写** 渲染为列表 row 形态（参见 §3.1 HazardItem），可保留 props API |
| `src/components/BigButton/` | **整体重写** 为 hero CTA（橙底圆角 pill、左侧 icon 圆框、右侧主副文案两行） |
| `src/components/HeaderBand/` | **删除** —— 拆为 `Brand` + `AppBar` 两组件代替；调用方相应迁移 |
| `src/components/ProgressIndicator/` | **整体重写** 用 ProgressRing + StepList 组合 |
| `src/components/desktop/UploadDropzone/` | **整体重写** —— 朴素 dashed 区 + 上传图标 + 选择文件按钮；删掉 CAD 刻度尺 / 取景框 / 扫描线 |
| `src/components/desktop/ReportSidebar/` | **整体重写** 为右侧概要卡（大数字 + summary + 严重度 breakdown） |

### 3.3 删除组件

如有以下文件，全部删除：

- `src/components/CADRuler/`（如果存在）
- 任何 `*-stamp.tsx` / `*-corner.tsx` / `*-scanner.tsx` 装饰组件
- `src/components/PlainWarningCard/`（已删的话忽略）

---

## 4. 屏幕重排

参考实现：`docs/plans/2026-05-21-clean-ui-prototype/app/clean-mobile-*.jsx` / `clean-desktop-*.jsx`。
把每个文件的 JSX 结构翻译到对应 Taro page。

### 4.1 `src/pages/index/mobile.tsx`

布局（从上到下）：

```
[品牌栏] Brand + 头像
[Hero] eyebrow "AI 现场巡检" + 大字 "拍一张 / AI 找隐患" + 副文
[现场照片卡] Photo (4:3) · meta="上次巡检 · ..."
[主 CTA] Button.hero "开始巡检" + 副文 "拍照·上传·等待报告"
[次 CTA] Button.ghost "从相册选择"
[今日数据卡] 三宫格 Stat (次数 / 高风险 / 中风险)
```

**关键删除**：

- 删除 `SHOT_TIPS` 数组及所有 tip-row 渲染
- 删除 `rulerLeft` / `rulerRight` JSX 节点（包括 `isH5 ?` 判断）
- 删除底部 footer 「⌖ AI ENGINE v3 · Claude Vision · ~30s/帧」整段

### 4.2 `src/pages/index/desktop.tsx`

```
[TopNav] 巡检（active）/ 报告 / 班组 / 设置 / 搜索 / 头像
[Page header] eyebrow + h1 "开始一次现场巡检" + 副文 + 右上「历史报告 / 新建巡检」二按钮
[主体 grid 1.5fr / 1fr]
  左：[Dropzone 卡] 顶栏 "上传现场照片 · JPG/PNG/HEIC · 15MB"
                  中部 上传图标 + 文案 + 「选择文件 / 手机扫码」二按钮
                  底栏 模型可用性条（绿点 + "Claude Sonnet 4.5 · 平均 29s · 99.4%"）
  右：[今日卡] 四宫格 Stat
      [最近巡检卡] 4 条 row（图标 + 站点 + pill + meta + chevron）
```

**关键删除**：

- 删除 CAD 刻度尺 / 边距 ruler
- 删除「拍摄要点」「AI ENGINE」「TODAY · STATS」三块旧 aside card
- 桌面容器 max-width 改 1280px，左右 32px gutter

### 4.3 `src/pages/report/mobile.tsx`

```
[AppBar] 返回 + "巡检报告" + 右「分享 / dots」
[现场照片大图] Photo (4:3) · meta="NO.xxx · 区域"
[概要卡] eyebrow + 大数字 + SeverityPill.solid + summary + 严重度 breakdown
[AlarmBox] 立即处置 · plain_warning
[隐患明细 section] title + caption + HazardItem 列表
[粘性底部 actbar] 导出 PDF / 转派班组
```

### 4.4 `src/pages/report/desktop.tsx`

```
[TopNav]
[Breadcrumb] 报告 > NO.xxx
[Page header] severity pill + 编号 + h1 + 副文 + 右三按钮「导出 PDF / 分享 / 转派班组」
[Hero grid 1.4fr/1fr]
  左：Photo
  右：概要卡（大数字 + breakdown + summary + meta「分析耗时 / 类别命中」）
[全宽 AlarmBox]
[隐患明细卡] 顶部 title + 段过滤「全/高/中/低」+ HazardItem 列表
[三联签字栏] 安全员 / 班组长 / 项目经理（每张含角色 / 姓名 / 状态 pill / 时间戳 / 提醒按钮）
[Footer] Safety Scout · v0.3.1 · NO.xxx · 报告完
```

---

## 5. 执行节奏 — 6 个独立 PR

每片完成必须跑 `pnpm test && pnpm test:e2e:h5 && pnpm lint && npx tsc --noEmit` 全绿才进下一片。

### Slice 1: Tokens

- 替换 `src/styles/tokens.scss` 为 §1 内容
- 修改 `src/utils/severity.ts` 色值
- 修改 `src/styles/fonts.scss`（删 Serif / Condensed，保 Mono）
- 删除不再用的 `src/assets/fonts/*.woff2`
- 修改 `src/app.scss` body bg → `var(--bg)`

**验收**：build 不崩；旧组件渲染可能变难看（预期），但不应崩溃；测试全绿。

### Slice 2: 基础组件（新增）

按 §3.1 创建 11 个新组件，每个带：
- `index.tsx` + `index.module.scss`
- jest 快照测试 `__tests__/index.test.tsx`

参考实现：`docs/plans/2026-05-21-clean-ui-prototype/app/clean-components.jsx`。

**验收**：所有新组件单独 import 渲染 OK；快照通过；TypeScript 无 error。

### Slice 3: 重写 HazardCard + BigButton

按 §3.2 重写两个最常用组件。旧 SCSS 全部删除重写。

**验收**：现有页面调用方不报错（API 保留）；视觉变为新规范。

### Slice 4: 重写 ProgressIndicator + 删除 HeaderBand

按 §3.2 重写 ProgressIndicator。
HeaderBand 删除前先找出所有 import 它的文件，逐个迁移到 `<AppBar>`（移动）或 `<TopNav>`（桌面）。

**验收**：grep `HeaderBand` 在 src/ 下无结果；所有页面渲染正常。

### Slice 5: 移动端两屏

按 §4.1 + §4.3 重排：
- `pages/index/mobile.tsx` + `mobile.module.scss`
- `pages/report/mobile.tsx` + `mobile.module.scss`

**验收**：iPhone 390×844 viewport 下截图与原型基本一致；e2e 流通过。

### Slice 6: 桌面端两屏 + 收尾

按 §4.2 + §4.4 重排：
- `pages/index/desktop.tsx` + `desktop.module.scss`
- `pages/report/desktop.tsx` + `desktop.module.scss`
- 重写 `desktop/UploadDropzone` 与 `desktop/ReportSidebar`（§3.2）

收尾：
- 在 `docs/plans/2026-05-20-miniprogram-ui-dossier-design.md` 顶部加 `**Status**: Superseded by 2026-05-21-clean-ui-prototype`
- 更新 `CLAUDE.md` 里的 UI 描述段（如果有）
- 跑全套测试

**验收**：1440×900 截图与原型基本一致；所有测试 + lint + tsc 全绿。

---

## 6. 验收标准（整体）

落地完成后，以下条件**全部**满足：

- [ ] 桌面 1440×900 打开 `pages/index`：顶部 nav + 大字标题 + 双列（左 dropzone 右 sidebar）
- [ ] 桌面打开 `pages/report?id=...succeeded`：照片左 + 概要右、警示条、隐患列表、三联签字栏
- [ ] iPhone 390×844 打开 `pages/index`：极简单页，CTA 一眼可见
- [ ] 报告页 `--accent` 出现次数手数 ≤ 3
- [ ] 全部 6 个 slice 测试全绿
- [ ] 无任何 emoji 漏网
- [ ] grep 仓库：`刻度尺` / `viewfinder` / `scanner` / `stamp` 等装饰术语已删
- [ ] `docs/plans/2026-05-20-miniprogram-ui-dossier-design.md` 已标 Superseded

---

## 7. 关键参考路径速查

| 你需要找 | 去这里读 |
|---|---|
| 新 UI 视觉效果（HTML 原型） | `docs/plans/2026-05-21-clean-ui-prototype/index.html` |
| 新组件参考实现（JSX） | `docs/plans/2026-05-21-clean-ui-prototype/app/clean-*.jsx` |
| 新 CSS token / 组件样式 | `docs/plans/2026-05-21-clean-ui-prototype/styles/clean.css` |
| 新设计完整规范 | `docs/plans/2026-05-21-clean-ui-prototype/design.md` |
| 旧（要废弃的）dossier 规范 | `docs/plans/2026-05-20-miniprogram-ui-dossier-design.md` |
| 业务数据契约（不动） | `docs/specs/report-schema.md` + `docs/specs/hazards.md` |
| Product 契约（不动） | `CLAUDE.md` |

---

## 8. 你可以问的问题

如果遇到以下情况，**停下来问用户**而不是自己决策：

1. 现有测试覆盖了被删除组件的行为 → 是删测试还是迁移到新组件？
2. 微信小程序某 CSS 特性不支持（如 `aspect-ratio` / `position: sticky` / `backdrop-filter`） → 用哪种 fallback？
3. Unsplash 在生产网络访问不稳定 → 换工地实拍 / OSS / 纯灰底？
4. 新组件命名与现有 ESLint 规则冲突
5. 任何方向性问题（"这里要不要再加一个 xx"）

---

## 9. 你不需要问的事情

直接动手：

- 任何样式微调（间距 ±4px、字号 ±2px、色值 ±5%）
- 把 `<button>` 翻译成 `<View role="button">`、`<svg>` 翻译成 dangerouslySetInnerHTML 等 Taro 兼容性处理
- 写 jest 快照测试
- 删除已废弃的 .scss 文件
- 重命名 module（如 `HeaderBand.module.scss` → `AppBar.module.scss`）

---

## 10. 自适应 / 断点策略

仓库目前用 dispatcher 模式分发：`pages/*/index.tsx` 调用 `useIsDesktop()` hook，在 `≥ 1024px` 时渲染 `desktop.tsx`，否则渲染 `mobile.tsx`。weapp 永远走 mobile 分支。**保留这个机制，不要改它。**

### 10.1 全局断点

| 断点 | 范围 | 渲染 | 说明 |
|---|---|---|---|
| **phone** | `< 600px` | `mobile.tsx` | 默认 mobile 布局，container 占满 |
| **tablet** | `600 – 1023px` | `mobile.tsx` | 同一个 JSX，但 container `max-width: 640px` 居中，左右露 backdrop |
| **desktop-sm** | `1024 – 1279px` | `desktop.tsx` | grid 缩窄、按钮组可换行 |
| **desktop** | `≥ 1280px` | `desktop.tsx` | 完整桌面布局，`max-width: 1280px` 居中 |

weapp：永远当作 phone 渲染，所有 `@media` query 在 weapp 编译时不生效，安全无副作用。

**原型采用 `@container` queries 而不是 `@media`** — 让同一个 HTML 画布中不同尺寸的 artboard 独立响应。
产品落地时两者都可以：
- `@container` 需 page-root 设 `container-type: inline-size`，Chrome 105+ / Safari 16+ / WeChat 微信 X5 内核支持不定
- `@media` 是传统 safe choice
- **产品推荐 `@media`**（兼容性优先）；原型采用 `@container` 仅为了画布演示

### 10.2 Mobile (`mobile.module.scss`) 自适应

**phone 默认** (< 600px)：
- 页面 `padding: 0 20px`
- 大字 hero `font-size: 44px`
- Photo 卡片 `aspect-ratio: 4/3`，宽度 = 100%
- 主 CTA 占满宽

**tablet (≥ 600px)** — 在 mobile.module.scss 加 `@media`：

```scss
@media (min-width: 600px) {
  .page {
    max-width: 640px;
    margin: 0 auto;
    border-left: 1px solid var(--line);
    border-right: 1px solid var(--line);
    background: var(--surface);
  }
}
```

平板上不重新设计 layout——保持单列，只是更窄居中，避免出现「600 字宽的恐怖文本墙」。

### 10.3 Desktop (`desktop.module.scss`) 自适应

**desktop 默认** (≥ 1024px)：
- 容器 `max-width: 1280px; margin: 0 auto; padding: 0 32px`
- 工作台双列 grid: `grid-template-columns: 1.5fr 1fr; gap: 24px`
- 报告页 hero grid: `grid-template-columns: 1.4fr 1fr; gap: 24px`
- 报告页三联签字: `grid-template-columns: 1fr 1fr 1fr`

**desktop-sm (1024 – 1279px)** — 收紧：

```scss
@media (max-width: 1279px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  // 按钮组换行到标题下方
}

@media (max-width: 1100px) {
  .home-body, .report-hero {
    grid-template-columns: 1fr;  // 单列
  }
  // sidebar 移到下方
}
```

低于 1024 时 dispatcher 自动切回 mobile，桌面 JSX 不用再模拟移动布局。

### 10.4 字号 / 间距随屏自适应

**桌面端大字段**用 `clamp()` 流体字号（H5 支持，weapp 不识别会 fallback 到首值）：

```scss
.h1-title {
  font-size: clamp(28px, 4vw, 40px);    // mobile 28 → desktop 40
}
.h1-hero {
  font-size: clamp(36px, 9vw, 56px);    // 小屏 36 → 大屏 56
}
```

weapp 视口固定在 375 左右，min 值即正确显示。

### 10.5 触控 vs 鼠标

- **hit target**：移动端所有 button / icon-button `min-height: 44px; min-width: 44px`（iOS HIG）
- **hover**：所有 `:hover` 必须有 `:focus-visible` 等价；weapp 端 `:hover` 不触发，仅靠 `:active` 反馈
- **粘性底部 actionbar**（mobile 报告页）weapp 用 `cover-view` 兼容；H5 用 `position: sticky; bottom: 0`

### 10.6 图片自适应

**问题**：weapp 的 `<image>` 不支持 `aspect-ratio` CSS。所有 Photo / 媒体容器统一用 padding-bottom hack：

```scss
.photo {
  position: relative;
  width: 100%;
  padding-bottom: 75%;     // 4:3
}
.photo .image, .photo img {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  object-fit: cover;
}
```

H5 + weapp 双端一致。

### 10.7 E2E 测试新增 viewport

```js
// tests/e2e/h5-responsive.mjs
const VIEWPORTS = [
  { name: 'phone',      width: 390,  height: 844 },
  { name: 'tablet',     width: 768,  height: 1024 },
  { name: 'desktop-sm', width: 1100, height: 800 },
  { name: 'desktop',    width: 1440, height: 900 },
];
```

每个 viewport 跑首页 + 报告页截图。Slice 5 / 6 提交时验证四个截图都合理。

### 10.8 验收（追加）

Slice 5 完成 → mobile 验收：
- [ ] 320px 视口（iPhone SE）页面不横向滚动
- [ ] 768px 视口下 container 居中，左右有空白
- [ ] 字号 / 行高在两个尺寸下都舒服阅读

Slice 6 完成 → desktop 验收：
- [ ] 1024px 视口（断点临界）布局不破
- [ ] 1100px 视口下 sidebar 已经移到下方或 grid 单列
- [ ] 1440px 视口下 max-width 1280 居中，左右露 backdrop
- [ ] 2560px 4K 视口下不被拉伸（max-width 生效）

---

## 11. Done definition

当你完成全部 6 个 slice、所有验收项打勾、PR 全部合并后：

- 在仓库根 `README.md` 的「项目进度」追加：`✅ Phase 4: Clean & Minimal UI 重构（PR #N – #N+5）`
- 在 GitHub 上 close 本 issue / merge 本 task PR
- 通知评审验收

完成。
