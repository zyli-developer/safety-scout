# PC Web UI — 独立桌面端布局

**Date**: 2026-05-21
**Status**: Approved, ready for implementation plan
**Author**: zyli + Claude (brainstorming)
**上游**: [`2026-05-20-miniprogram-ui-dossier-design.md`](./2026-05-20-miniprogram-ui-dossier-design.md)（dossier design tokens 与移动端布局已落地；本设计在此之上补桌面变体）

## 0. 用途

为 safety-scout 项目新增**独立 PC web 端 UI**，与现有移动端 H5 / 微信小程序并存。

桌面用户（safety officer 在办公室 PC 浏览器看报告）当前看到的是「宽屏上居中显示的手机页面」—— 内容被 `max-width: 720px` 钉死在中间。目标：换成真正的桌面级排版（左右分栏、信息密度合理、不再像"放大的手机"），但**不增加新功能、不引入历史 / 导出 / 登录**，仍然遵守 `CLAUDE.md` 的「拍照 → 等待 → 看报告」三步产品契约（桌面端拍照变上传，其余不变）。

## 1. 决策汇总

| 维度 | 结论 | 备注 |
| --- | --- | --- |
| 范围 | 重做 `pages/index` + `pages/report` 两个页面的桌面布局 | 不加历史、不加导出、不加登录 |
| 桌面断点 | `min-width: 1024px` | 与现有 `index.module.scss` 桌面媒体查询断点一致 |
| 检测方式 | `window.matchMedia('(min-width: 1024px)')` + resize 监听 | UA 检测被否决（无法响应窗口缩放）|
| 切换粒度 | **整页切换** —— `pages/*/index.tsx` 退化为 dispatcher | CSS 媒体查询不够 —— 桌面 vs 移动的 DOM 结构差异过大 |
| weapp 影响 | 静态 import 桌面组件，weapp 包多 ~10-20KB 死代码 | 可接受；>50KB 再做 dynamic import 优化 |
| 移动端 H5 影响 | 零变化 | viewport <1024px 时 dispatcher 走 mobile 分支 |
| 字号 | 桌面页面引用新 token `--fs-*-desktop`，不污染移动 tokens | 仅在桌面 SCSS 中定义 |
| 文件上传 | 桌面用原生 `<input type="file">` + drag/drop，不复用 `Taro.chooseImage` | API 层 `createInspection` 扩展接受 `string \| File` |
| 共用组件 | `HeaderBand` / `HazardCard` / `Icon` / `ProgressIndicator` 原样复用 | 不改组件本身，只在桌面布局里换位置 |

## 2. 布局

### 首页（桌面端）—— 左右分栏

上传区是核心动作，给最大视觉权重；要点列表退到右侧辅助位。

```
┌─ HeaderBand · NO.20260521 ──────────────────────────────────────┐
│                                                                  │
│  工地隐患识别                          ┌──────────────────────┐  │
│  AI · SITE HAZARD INSPECTION          │  拍摄要点            │  │
│                                        │  ── 01 贴近隐患位置  │  │
│  ┌──────────────────────────────┐    │  ── 02 含工人/护栏   │  │
│  │                              │    │  ── 03 距离 1-3m     │  │
│  │     ⊕  拖拽图片到此          │    └──────────────────────┘  │
│  │     或点击选择文件            │                              │
│  │                              │    ┌──────────────────────┐  │
│  │     CAPTURE INSPECTION PHOTO │    │  AI ENGINE v3        │  │
│  └──────────────────────────────┘    │  Claude / Doubao     │  │
│                                        │  ~30s / 帧            │  │
│                                        └──────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

栅格比例：左 60% / 右 40%；整页 `max-width: 1200px` 居中。

### 报告页（桌面端）—— 左 sticky + 右滚动

safety officer 在桌面侧的工作流是「左边盯 summary + risk level，右边逐条看 hazard」。sticky 左侧让上下文不消失。

```
┌─ HeaderBand · NO.2026-05-21-3742 · 高风险 · 3分钟前 ──────────────┐
│  ┌────────────────────────┐  ┌─ 隐患明细 ───────────────────┐    │
│  │ INSPECTION REPORT      │  │                               │    │
│  │ 现场巡检报告           │  │  [01/05] 高处坠落 · 高        │    │
│  │                        │  │  人字梯使用高度超过 2m...     │    │
│  │  ╔══╗                  │  │  → JGJ80 第 5.1.2 条          │    │
│  │  ║07║ 项隐患待整改     │  │  ────────────────────────     │    │
│  │  ╚══╝                  │  │                               │    │
│  │                        │  │  [02/05] 物体打击 · 高        │    │
│  │  高风险                │  │  外架与结构间无防护...        │    │
│  │  风险等级判定          │  │  → JGJ130 第 6.2.1 条         │    │
│  │                        │  │  ────────────────────────     │    │
│  │  ▎现场总览             │  │                               │    │
│  │  外架与楼梯间防护...   │  │  [...]                        │    │
│  │  ⚠ 注意临边坠落        │  │                               │    │
│  └────────────────────────┘  └───────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────┘
   ↑ position: sticky          ↑ overflow-y: auto
```

栅格比例：左 40% / 右 60%；整页 `max-width: 1400px` 居中。

## 3. 架构 / 文件组织

### 文件改动

```
miniprogram/src/
├── hooks/
│   └── useIsDesktop.ts                ← 新
├── pages/
│   ├── index/
│   │   ├── index.tsx                  ← 改：dispatcher（选 Mobile/Desktop）
│   │   ├── mobile.tsx                 ← 现 index.tsx 全部内容搬这里
│   │   ├── mobile.module.scss         ← 现 index.module.scss 改名
│   │   ├── desktop.tsx                ← 新
│   │   └── desktop.module.scss        ← 新
│   └── report/
│       ├── index.tsx                  ← 改：dispatcher
│       ├── mobile.tsx                 ← 现 index.tsx 全部内容搬这里
│       ├── mobile.module.scss
│       ├── desktop.tsx                ← 新
│       └── desktop.module.scss        ← 新
└── components/
    └── desktop/
        ├── UploadDropzone/
        │   ├── index.tsx              ← 新
        │   └── index.module.scss      ← 新
        └── ReportSidebar/
            ├── index.tsx              ← 新
            └── index.module.scss      ← 新
```

### 检测 hook

```typescript
// hooks/useIsDesktop.ts
export function useIsDesktop(): boolean {
  // weapp 永远 false，桌面分支 dead code
  if (process.env.TARO_ENV !== 'h5') return false;

  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window !== 'undefined' &&
    window.matchMedia('(min-width: 1024px)').matches
  );

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(min-width: 1024px)');
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return isDesktop;
}
```

### Dispatcher 模板

```typescript
// pages/index/index.tsx
import { useIsDesktop } from '../../hooks/useIsDesktop';
import MobileIndex from './mobile';
import DesktopIndex from './desktop';

export default function IndexPage() {
  const isDesktop = useIsDesktop();
  return isDesktop ? <DesktopIndex /> : <MobileIndex />;
}
```

## 4. 组件清单

### 新组件 1：`UploadDropzone`（首页桌面端用）

替代移动端的 `BigButton + captureImage`。

- **交互**：HTML5 drag & drop + 点击触发 `<input type="file" accept="image/*">`；选中 / 拖入后立即调 `createInspection(file)`，跳转 `/pages/report?id=...`
- **状态**：`idle` / `hover`（拖拽悬停高亮边框）/ `uploading`（loading spinner + 禁用交互）
- **不复用 `useImageCapture`** —— 桌面 `<input>` + drop event 比 Taro chooseImage 直接

### 新组件 2：`ReportSidebar`（报告页桌面端用）

左 sticky 侧栏，包含：
- `INSPECTION REPORT / 现场巡检报告` 标题块
- 隐患计数 + 风险等级双栏
- `▎现场总览` 段（summary + plain_warning）

行为：`position: sticky; top: 0`；右侧 hazards 列表正常滚动。

### 复用现有组件

| 组件 | 桌面端用法 | 是否改动 |
|---|---|---|
| `HeaderBand` | 桌面页顶部横幅，width 100% | 不改 |
| `HazardCard` | 桌面 main 区列表，卡片宽度由父决定 | 不改 |
| `Icon` | 完全复用 | 不改 |
| `ProgressIndicator` | 桌面端等待状态，外面包 flex 容器居中 | 不改 |
| `BigButton` | 桌面不用 | 不改 |

### 桌面字号 tokens

不改 `tokens.scss`，在 `desktop.module.scss` 局部覆盖：

```scss
:root {
  --fs-body-desktop: 16px;
  --fs-h1-desktop: 48px;
  --fs-eyebrow-desktop: 11px;
  --space-desktop-gutter: 48px;
}
```

## 5. 数据流 / 错误处理 / 测试

### 数据流

```
桌面入口：
  UploadDropzone (file/drop) → createInspection(File)
                             → 拿到 inspection_id
                             → Taro.navigateTo('/pages/report?id=...')

桌面报告页：
  dispatcher 渲染 DesktopReport → usePolling(getInspection, ...)
                               → status=succeeded → 渲染 sidebar + cards
                               → status=failed/timeout → ErrorView (复用)
```

唯一改动：`api/inspections.ts` 里 `createInspection` 当前接 `tempFilePath: string`，改成 `string | File`：
- `typeof input === 'string'`：原 `Taro.uploadFile` 路径（mobile）
- `instanceof File`：`FormData + fetch` 路径（桌面 H5）

`usePolling` / `getInspection` / 全部类型不动。

### 错误处理

`mapApiError` / `ApiError` / `errorMessage.ts` / `ErrorView` 全部复用 —— 这是 API code → 中文 user message 的业务映射，与布局无关。

桌面 `ErrorView` 不新写，外面套 flex 容器居中即可（错误页本来就极简）。

`captureImage` 用户取消 silent return 的语义，桌面 `UploadDropzone` 等价处理：
- 用户取消 input → 不调 createInspection（silent）
- 上传失败 → 走 `mapApiError` → `Taro.showToast`

### 测试

| 类型 | 工具 | 覆盖 |
|---|---|---|
| Jest 单元 | jest-jsdom（现有） | `useIsDesktop`（matchMedia mock + resize event）；`UploadDropzone`（drop / click / 状态）；dispatcher 选分支 |
| Jest 快照 | `@testing-library/react`（现有） | `DesktopIndex` / `DesktopReport` 结构稳定性 |
| Playwright E2E | 现有 `tests/e2e/h5-real.mjs` 加 `h5-desktop.mjs` | 1440×900 视口跑「上传 → 等待 → 报告」全流程；验证桌面选择器（sidebar / dropzone）存在 |

不做：视觉回归（截图 diff），dossier 仍在演进期 YAGNI。

## 6. 实施切片

5 个独立 PR / commit，每片自带测试，可中途暂停：

1. **`useIsDesktop` hook + dispatcher 骨架** —— 各页面拆 `index.tsx`(dispatcher) + `mobile.tsx`(原内容)，桌面分支先返回 mobile 同款内容。**零行为变化的纯重排**，让后续切片建立在干净 dispatcher 上。
2. **`createInspection` 接受 File** —— api 层小扩展，独立提交独立测。
3. **`UploadDropzone` 组件 + 单测** —— 独立组件先到位，不接 dispatcher。
4. **`DesktopIndex` + e2e** —— 装上 UploadDropzone；切到桌面首页能跑。
5. **`ReportSidebar` + `DesktopReport` + e2e** —— 桌面报告页收尾。

每切片完成跑 `pnpm test` + `pnpm test:e2e:h5` 再进下一片。

**预估**：4-5 工作日。

## 7. YAGNI / 不做的事

- ✋ 不做历史列表 / 历史报告页面 —— 后端没有 `GET /inspections` 列表 API；本设计不动后端
- ✋ 不做 PDF 导出 / 打印优化 —— 用户后续需要再加 `@media print`
- ✋ 不做登录 / 多用户 —— 与 `CLAUDE.md` 「无登录墙」契约一致
- ✋ 不做 UA 检测 —— matchMedia 已覆盖 resize
- ✋ 不做 SSR —— Taro H5 CSR 足够
- ✋ 不做用户手动切「PC 版 / 移动版」按钮 —— 增加复杂度无产品价值
- ✋ 不做视觉回归测试 —— dossier 演进期，截图 diff 噪声大
- ✋ 不引入 `react-router` / 状态管理库 —— Taro 路由 + URL 参数够用
- ✋ 不重做 `HazardCard` / `HeaderBand` / `Icon` —— 组件层稳定，仅在桌面页面里换位置

## 8. 与上游契约的关系

- **CLAUDE.md 三步产品契约**：保持。桌面拍照变上传（drag/drop），仍是「上传 → 等待 → 看报告」三步，不增加表单 / 强制选择项。
- **`docs/specs/report-schema.md` 报告契约**：不动。桌面只换 render，schema 一字不改。
- **`2026-05-20-miniprogram-ui-dossier-design.md` dossier tokens**：保留。桌面字号开新 `*-desktop` 变量，dossier 色板 / 字族 / 间距规则不变。
