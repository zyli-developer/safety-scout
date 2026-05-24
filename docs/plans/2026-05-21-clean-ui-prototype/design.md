# Clean UI Prototype — Design

**Date**: 2026-05-21
**Status**: Prototype landed, awaiting review · 候选方向
**Author**: zyli + Claude
**Supersedes**: 不替代任何已落地的 design，并行候选方向。前序两轮探索（`2026-05-20-miniprogram-ui-dossier-design.md` 工地许可证、Tactical Scanner HUD 暗色版）经评审「乱、丑」否决；本次完全推翻方向。

## 0. 为什么换方向

| 此前方向 | 落地后被否决的原因 |
|---|---|
| **Site Inspection Dossier**（纸质文档调） | 信息密度过高、ruled lines 过多、像盖章公文，普通安全员日常用起来累 |
| **Tactical Scanner HUD**（暗色科技调） | 视觉装饰过载——角标 + 十字 + 扫描线 + 点阵网格 + telemetry + 警报条纹，每屏都在嘶吼，认知负担重 |

两轮共同问题：**用视觉语汇硬塞"专业感"，反而牺牲了基础可用性**。安全员的工作流是单手拍照 → 等结果 → 转发，需要的是「快、准、轻」。

本版 Clean & Minimal 的指导原则：

1. **一屏一件事** —— home 屏就是「拍照」一个动作，scan 屏就是「等」，report 屏就是「看 + 转派」
2. **真实工地照片占视觉主导** —— 比任何 SVG placeholder / 数据可视化都更能传达"这是工地巡检工具"
3. **配色克制** —— 暖白底 + 单一安全橙强调 + 三色严重度 pill，不再发光、不再加纹理
4. **字号有节奏** —— h1 56px / h2 28-40 / body 14-15 / mono 仅用于编号；建立明确的视觉层级，让眼睛知道往哪儿看

## 1. Design tokens

完整定义见 `styles/clean.css` 顶部 `:root`。摘要：

### 色板

| 角色 | Hex | 说明 |
|---|---|---|
| `--bg` | `#FAFAF8` | 暖白底（轻微 warm bias，不是冷白 #FFF） |
| `--surface` | `#FFFFFF` | 卡片底 |
| `--surface-2` | `#F4F4F2` | 输入框 / 按钮悬停 / 软底 |
| `--line` | `#ECECE8` | 几乎不可见的边框 |
| `--line-2` | `#DCDCD6` | 显式边框（按钮、虚线） |
| `--ink` | `#0E0E0C` | 接近黑的文字主色（非纯黑） |
| `--ink-2` | `#4D4E4B` | 次级文字 |
| `--ink-3` | `#8A8B86` | 辅助 / caption / label |
| `--ink-4` | `#B6B6B0` | 占位 / 禁用 |
| `--accent` | `#E85D2C` | **唯一强调色 · 安全橙**。只用于主 CTA 与数据高亮 |
| `--accent-2` | `#C44A1F` | accent hover |
| `--accent-soft` | `#FFF1EA` | accent 软底（标签 / chip） |
| `--high` | `#D7373F` | 高风险（克制红、不发光） |
| `--high-soft` | `#FCE7E9` | high pill bg |
| `--med` | `#C77A1F` | 中风险（克制琥珀） |
| `--med-soft` | `#FBEED6` | medium pill bg |
| `--low` | `#2F8454` | 低风险（克制绿） |
| `--low-soft` | `#DEEFE3` | low pill bg |

**严格规则**：`--accent` 一屏最多出现 1–2 处；severity 色仅用于 pill 与统计数字，**不**作为大面积底色 / 边框（避免警报疲劳）。

### 字体

```
--f-sans: -apple-system, BlinkMacSystemFont, 'Helvetica Neue',
          'PingFang SC', 'Noto Sans SC', 'Hiragino Sans GB',
          ui-sans-serif, sans-serif;
--f-mono: 'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, monospace;
```

**Why**：

- 苹方 + 系统 sans —— 中文阅读最舒适，全平台已装、零下载成本。前两版用 Plex Sans 跑中文 fallback 视觉一致性差
- IBM Plex Mono **只**用在编号 / 时间戳 / 数字 stat —— 是「这是技术工具」的克制信号，不染到正文
- 不引入 Manrope / Geist / Inter 等 web font —— 微信小程序里加载 webfont 成本高，**优先用系统字体**

### 字号 scale

| token | px | 用法 |
|---|---|---|
| title-xl | 56 | mobile home / report 大数字 |
| title-lg | 40 | desktop 页面标题 |
| title-md | 28 | mobile 报告大数字 / sub-titles |
| title-sm | 20 | 卡片 section 标题 |
| body | 15 | 正文 |
| body-sm | 13.5 | 二级正文 / 描述 |
| caption | 12 | 标注 / meta |

### 间距 & 几何

8px 基准。卡片圆角 `--r-md: 14px`、按钮 pill 圆角 `--r-pill: 999px`、小卡 / 输入 `--r-sm: 10px`。**前版 0 圆角 dossier 调被废**，原因是太硬，不适合移动端日常使用。

## 2. 屏幕清单 & 设计意图

### 01 · 移动 · 首页（390×900）

```
┌──────────────────┐
│ ⓢ Safety Scout  王│  ← 极简品牌栏 + 头像
├──────────────────┤
│ AI 现场巡检        │  ← eyebrow
│                   │
│ 拍一张            │  ← 大字 hero (44px)
│ AI 找隐患         │
│                   │
│ 上传现场照片...    │  ← body 副文
│                   │
│ [现场照片 4:3]    │  ← 真实工地图（圆角卡）
│                   │
│ ┌──────────────┐ │
│ │ 开始巡检      │ │  ← 大橙色 CTA
│ │ 拍照·上传·... │ │
│ └──────────────┘ │
│   📷 从相册选择   │  ← ghost button
│                   │
│ 今日巡检          │  ← section header
│ ┌──────────────┐ │
│ │ 12  03  05   │ │  ← 三宫格 stat
│ └──────────────┘ │
└──────────────────┘
```

**核心决策**：

- 首页**没有**操作指南（拍摄要点）、模型可用性、上次巡检详情。这些都是认知负担，安全员每天用这屏 10+ 次，要的是直击 CTA
- 工地照片放在 CTA **上方**——肉眼一扫就知道「这工具是看现场的」，比任何文字标题都强

### 02 · 移动 · 等待（390×900）

```
┌──────────────────┐
│ ←  正在分析     ✕ │  ← AppBar，可取消
├──────────────────┤
│ [刚上传的照片]    │  ← 让用户看到自己刚拍的什么
│                   │
│ ┌──────────────┐ │
│ │ ◯ 62%         │ │  ← Progress ring + 标题
│ │   AI 正在分析  │ │
│ │   预计 30s    │ │
│ │   已用 23s    │ │
│ └──────────────┘ │
│                   │
│ 分析进度          │
│ ✓ 图像上传完成    │
│ ● AI 视觉解析中   │
│ ○ 生成结构化报告  │
│                   │
│ ┌ 提示 ─────────┐│
│ │ 可保持页面...   ││
│ └──────────────┘ │
└──────────────────┘
```

**核心决策**：

- 进度环用 `--accent`，不用 severity 色——避免在 idle 状态就让用户产生「危险」联想
- 已上传照片占顶部 1/3，**用户能看到 AI 在看什么**，是信任建立的关键
- 步骤列表 3 条而非 5 条 ——「上传 → 分析 → 报告」三步，对应产品契约 `CLAUDE.md` 中的 "拍照 → 等待 → 看报告"

### 03 · 移动 · 报告（390×2050，可滚）

```
┌──────────────────┐
│ ←  巡检报告  ⇪ ⋯ │
│ [现场照片大图]    │  ← 报告即报告，照片永远是核心证据
│                   │
│ ┌ 概要卡 ────────┐│
│ │ 检出隐患        ││
│ │ 5 项     [高风险]││  ← 大数字 + 风险 pill (solid)
│ │                ││
│ │ 现场存在 2 项高..││  ← summary
│ │                ││
│ │ 高·2  中·2  低·1││  ← 严重度 breakdown
│ └──────────────┘ │
│                   │
│ ⚠ 立即处置·楼板...│  ← AlarmBox（红软底，不发光）
│                   │
│ 隐患明细          │
│ ─────────────────│
│ 01 高处坠落 [高]   │
│    画面中楼板...   │
│    依据 JGJ 80... │
│    [整改建议软块]  │
│ ─────────────────│
│ 02 ...            │
│                   │
│ [底部粘性 actbar] │  ← 导出 PDF | 转派班组
└──────────────────┘
```

**核心决策**：

- 把「立即处置」（plain_warning）放在概要卡之**外**单列 AlarmBox——这是最需要警觉的信息，不能埋在卡里
- HazardItem 是**列表 row**，不是带边框的卡。卡片堆卡片视觉碎，列表式扫读快
- 整改建议（suggestion）放在每条 hazard 的**软底块**里，视觉上做"二级强调"——是真正可执行的动作，不能被忽略
- 底部粘性 actionbar `导出 PDF / 转派班组` 始终可见——用户看完报告下一步几乎一定是这两件事

### 04 · 桌面 · 工作台（1280×920）

```
┌────────────────────────────────────────────┐
│  ⓢ Safety Scout   巡检 报告 班组 设置  🔍 王 │  ← topnav
├────────────────────────────────────────────┤
│ SH-PD-JQ-001 · 上海·浦东金桥项目              │
│                                              │
│ 开始一次现场巡检                              │
│ 上传一张施工现场照片，AI 会在...               │
│                                              │
│ ┌────────────────────────────┐ ┌──────────┐│
│ │ 上传现场照片                │ │ 今日巡检 ││
│ │ ─────────────────────────  │ │ 12 03... ││
│ │                            │ ├──────────┤│
│ │      ⤓                     │ │ 最近巡检  ││
│ │   拖拽图片到此处            │ │ ──────── ││
│ │                            │ │ 🖼 北区5F  ││
│ │   [选择文件] [手机扫码]     │ │ 🖼 南区配电││
│ │                            │ │ 🖼 东侧脚手││
│ │ ─────────────────────────  │ │ 🖼 材料堆场││
│ │ ● Claude Sonnet 4.5 · ...  │ └──────────┘│
│ └────────────────────────────┘              │
└────────────────────────────────────────────┘
```

**核心决策**：

- 顶部水平 nav（巡检 / 报告 / 班组 / 设置）——给桌面端一个产品骨架，但**不**真的实现这些页面，避免承诺超出 MVP 范围
- dropzone **不模拟相机取景框 / 不画十字** —— 一个朴实的 dashed 区域 + 上传图标即可。前版 HUD 取景框是无效装饰
- 模型可用性条放 dropzone 卡底部，绿色脉冲点 + 文案"Claude Sonnet 4.5 · 平均 29s · 今日 99.4% 可用"——单行、低对比、不抢主体
- 右侧 sidebar 把今日数据 + 最近 4 条巡检塞一栏——给重度用户的快速跳转入口

### 05 · 桌面 · 报告（1280×2050）

```
┌──────── topnav ────────┐
│ 报告 > NO.2026-05-21-3742│   ← breadcrumb
│                          │
│ [高风险] NO.2026-05-...   │   ← solid pill + 编号
│ 北区 5F 楼板巡检报告      │   ← 大标题
│ ...项目 · 王立 · ...      │   ← meta line
│        [导出 PDF][分享][转派班组]│ ← 主操作
│                          │
│ ┌──大照片──┐ ┌──概要卡──┐│
│ │           │ │ 5 项隐患  ││  ← 1.4fr / 1fr
│ │           │ │ 高·中·低  ││
│ │           │ │ summary  ││
│ │           │ │ 耗时·命中 ││
│ └──────────┘ └──────────┘│
│                          │
│ ⚠ 立即处置 ...           │   ← 全宽 alarm
│                          │
│ ┌── 隐患明细卡 ──────────┐│
│ │ 隐患明细  共5项 [全 高 中 低]│
│ │ ─────────────────────  ││
│ │ 01 高处坠落 [高]        ││
│ │    描述... 整改软块     ││
│ │ ─────────────────────  ││
│ │ 02 ...                ││
│ └──────────────────────┘│
│                          │
│ [安全员卡][班组长卡][项目经理卡]│ ← 三联签字栏
│                          │
│ Safety Scout · v0.3.1    │
└──────────────────────────┘
```

**核心决策**：

- 报告头部三按钮 `导出 PDF / 分享 / 转派班组`——盖住安全员看完报告 80% 的下一步动作
- 大照片左 + 概要卡右 —— 1.4 / 1 比例，照片**永远比数据视觉权重大**，因为照片就是事实证据
- 三联签字栏取代前版「公文式签字格」，每个签字是一张卡（角色 + 姓名 + 状态 pill + 时间戳 + 提醒按钮）——给「签字流程」一个真实落地入口，而不是装饰性的下划线
- **不**画类别热力图（H1–H10 命中图）—— 前版 HUD 加过，评审反馈"信息无用"。报告页只显示实际命中的隐患，不显示"没命中什么"

## 3. 组件清单

| 组件 | 用途 | 替代关系 |
|---|---|---|
| `<Brand>` | 顶部品牌（小方块 mark + 文字） | 新增；接近 现有 `HeaderBand` 但去掉了编号 / 副标 |
| `<TopNav>` | 桌面 4 tab 导航 | 新增 |
| `<AppBar>` | 移动顶部栏（返回 + 标题 + 右操作组） | 新增；前版 dossier 无此组件 |
| `<Photo>` | 真实工地图卡（圆角 + 角标 meta + 渐变 overlay） | 新增；替代 `PhotoSlot` 条纹占位 |
| `<SeverityPill>` | 严重度 pill（软底 / solid 两种） | 替代 dossier `hcard-tag` |
| `<HazardItem>` | 隐患列表 row（编号 + 类目 + 描述 + 整改软块） | **重写** `HazardCard` —— 列表式而非卡片堆叠 |
| `<Stat>` | 大数字 + 标注 | 替代 dossier `HeroMetric` |
| `<AlarmBox>` | 红软底警示条 | 替代 dossier `warning-box` |
| `<ProgressRing>` | SVG 进度环 | 替代 dossier 的 `READING ···· %` 文本读出 |
| `<StepList>` | 三步分析进度 | 替代 dossier `ProgressIndicator` 步骤部分 |
| `<Icon>` | 内联 stroke icon set（heroicons-mini 风格） | 复用现有 `Icon` 组件、新增若干路径 |
| 按钮 | `btn-primary / btn-secondary / btn-ghost / btn-hero` | 替代 dossier `BigButton`；hero 变体专为 mobile home CTA |

## 4. 真实工地照片来源

原型使用 Unsplash CDN 占位图，路径见 `app/clean-components.jsx` 顶部 `PHOTO_URLS`。

```js
const PHOTO_URLS = {
  hero:    'https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=1200&q=70&auto=format&fit=crop',
  worker:  'https://images.unsplash.com/photo-1581094288338-2314dddb7ece?w=1200&q=70&auto=format&fit=crop',
  site1:   'https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=1200&q=70&auto=format&fit=crop',
  site2:   'https://images.unsplash.com/photo-1590502593747-42a996133562?w=1200&q=70&auto=format&fit=crop',
  scaff:   'https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=1200&q=70&auto=format&fit=crop',
  panel:   'https://images.unsplash.com/photo-1597166914903-d56f0b71f53e?w=1200&q=70&auto=format&fit=crop',
};
```

**落地时**：

- 移动端用户实拍照片直接放进 `<Photo>` 即可（base64 / `tempFilePath` / OSS URL 都行）
- 桌面端 demo / placeholder 可保留 Unsplash CDN，也可以下载后放进 `assets/images/`（**注意 Unsplash 协议允许商用 + 免署名**）

## 5. 与现有 miniprogram 代码的差异

### 必改

| 文件 | 改动 |
|---|---|
| `src/styles/tokens.scss` | 顶层 `:root` 全套替换为 `clean.css` 同名变量 |
| `src/styles/fonts.scss` | 移除 IBM Plex Serif / Sans Condensed / Source Han Serif 引入，保留 Plex Mono |
| `src/components/HazardCard/*` | API 保留，render 完全重写为列表 row 形态 |
| `src/components/BigButton/*` | 改为 `btn-hero` 形态（圆角 pill、橙底、阴影、内含 icon 圆框） |
| `src/components/HeaderBand/*` | 拆为 `<Brand>` + `<AppBar>` 两个，移动 / 桌面分别使用 |
| `src/pages/index/mobile.tsx` | 删除 SHOT_TIPS 列表渲染、删除 CAD 刻度尺、按 §2.01 重排 |
| `src/pages/index/desktop.tsx` | 按 §2.04 重排，加 `<TopNav>` |
| `src/pages/report/mobile.tsx` | 按 §2.03 重排；加底部粘性 actionbar |
| `src/pages/report/desktop.tsx` | 按 §2.05 重排；加三联签字栏 + 三按钮操作 |

### 不动

- `src/api/*` —— API contract 不变
- `src/hooks/*` —— 数据流逻辑不变
- `src/types/*` —— 数据契约不变
- `src/utils/severity.ts` —— 严重度排序逻辑不变，只改色值映射
- `app/specs/report-schema.md` —— 报告 JSON schema 不变

### Backend

零改动。本设计纯前端。

## 6. 落地切片

按 dossier 设计的分阶段习惯，建议 6 个独立 PR：

1. **Tokens commit** —— 替换 `tokens.scss` + `fonts.scss`；本 commit 后旧组件会变难看但不应崩溃；跑 `pnpm test` 通过即可
2. **基础组件重写** —— `Brand` / `AppBar` / `TopNav` / `Photo` / `SeverityPill` / `Stat` / `AlarmBox`；带 jest 快照
3. **HazardCard 重写 + BigButton 重写**
4. **移动端两屏** —— `index/mobile.tsx` + `report/mobile.tsx`；带 e2e
5. **桌面端两屏** —— `index/desktop.tsx` + `report/desktop.tsx`；新增 `<TopNav>`、删 dossier 刻度尺；带 e2e
6. **清理** —— 删除已废弃的 dossier 组件（`PlainWarningCard` 早已删 / `ProgressIndicator` 改名 / `HazardCard` 旧版本 .module.scss）；删除前两版设计文档的 status: approved 标识、标 superseded

每片完成跑 `pnpm test && pnpm test:e2e:h5 && pnpm lint && npx tsc --noEmit` 全绿再进下一片。

## 7. YAGNI / 明确不做

- ✋ **不引入 webfont 库** —— Inter / Manrope / Geist 等都不要；系统字体足够
- ✋ **不实现 nav 里的「班组」「设置」页** —— topnav 4 个 tab 只点亮 `巡检` / `报告`，其他显示但不可点（hover 灰）
- ✋ **不做暗色模式** —— 浅色是品牌；后续如真需要再说
- ✋ **不做隐患类别热力图 / 类别覆盖网格** —— 前版加过，被否决
- ✋ **不画 CAD 刻度尺 / 取景框 / 扫描线 / 点阵网格** —— 装饰性元素全部砍掉
- ✋ **不增加 emoji** —— 严守 `CLAUDE.md` 规约
- ✋ **不加渐变背景** —— 仅 photo overlay 有底→透明渐变，其余实色

## 8. 验收

当本设计落地：

- 桌面浏览器 1440×900 打开 `pages/index`：看到 topnav + 大字标题 + 左 dropzone 右 sidebar 双列
- 桌面打开 `pages/report?id=...succeeded`：照片左 + 概要右、警示条、隐患列表、签字栏，整体留白 ≥ 旧版 50%
- iPhone 390×844 打开 `pages/index`：极简单页，CTA 一眼可见
- 报告页所有 `--accent` 出现次数手数 ≤ 3（标题 / pill / CTA）
- 单页元素数（DOM nodes 在视口内）较 dossier 版本下降 ≥ 30%
- 跑测试全绿，桌面 / 移动 e2e 截图通过

## 9. 风险

- **Unsplash CDN 在生产可能因网络问题加载慢** —— 落地时换成同源资源 (`assets/images/`) 或工地实拍
- **iOS 小程序 Taro 不支持 `aspect-ratio` CSS** —— 需 fallback 用 padding-bottom hack 维持 4:3 / 16:9
- **粘性底部 actionbar 在低端 Android 上可能卡顿** —— 可降级为非粘性（滚到底才出现）

## 10. 下一步

1. 评审本设计（本 PR） —— 若通过，先合并设计文档
2. 按 §6 切片 1（tokens）开新 PR
3. 后续切片依次推进

---

**Prior art / 致谢**: Linear、Vercel、Apple Pro Display 的极简产品 UI；前序两版 dossier / HUD 探索是这一版的对照组，没有它们这版的克制感找不到方向。
