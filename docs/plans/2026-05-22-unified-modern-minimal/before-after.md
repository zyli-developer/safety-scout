# Before / After — Unified Modern-Minimal 落地

把 `docs/plans/2026-05-22-unified-modern-minimal/` 原型里固化的 modern-minimal 系统
应用到 Taro miniprogram (`miniprogram/src/`) 代码后的真实截图对比。

捕获脚本：`miniprogram/tests/e2e/h5-responsive.mjs`（6 个视口 · 首页）。
报告/轮询页面需要后端有活跃任务才能截图，本轮先用单元测试覆盖（见文末）。

| 视口 | Before（旧实现） | After（unified-modern-minimal） |
| --- | --- | --- |
| Phone (390×844) | `before-after/before/h5-responsive-phone-home.png` | `before-after/after/h5-responsive-phone-home.png` |
| Tablet (768×1024) | `before-after/before/h5-responsive-tablet-home.png` | `before-after/after/h5-responsive-tablet-home.png` |
| Desktop-sm (1100×800) | `before-after/before/h5-responsive-desktop-sm-home.png` | `before-after/after/h5-responsive-desktop-sm-home.png` |
| Desktop-laptop (1280×800) | `before-after/before/h5-responsive-desktop-laptop-home.png` | `before-after/after/h5-responsive-desktop-laptop-home.png` |
| Desktop (1440×900) | `before-after/before/h5-responsive-desktop-home.png` | `before-after/after/h5-responsive-desktop-home.png` |
| **Wide (1920×1080)** | `before-after/before/h5-responsive-desktop-wide-home.png` | `before-after/after/h5-responsive-desktop-wide-home.png` |

## 可视化差异

### 1. 顶部导航砍到 2 项（巡检 / 报告）

- Before：四项（巡检 / 报告 / 班组 / 设置）
- After：两项（巡检 / 报告）。班组 / 设置功能未实装，且违反 `CLAUDE.md` 里
  "产品只做三步（拍照 → 等待 → 看报告）"主张，撤回导航席位。
- 同时把 `TopNav` 半透明背板从暖白 `rgba(250,250,248,.85)` 换成冷白
  `rgba(255,255,255,.92)` + `saturate(140%)`，与原型 sticky header 对齐。

### 2. Wide (1920) 容器宽度收紧到 1240

- Before：宽屏会把容器顶到 1440 / 1520，导致首页两侧 backdrop 被极薄白边占满，
  视觉上"页面跟着窗口张开"，没有定稿感。
- After：容器统一 `max-width: 1240`（home + report），两侧露出 `surface-2` backdrop。
  Wide 视口下 inspector 立刻能感受到这是一个被设计过的尺寸，而不是被强行拉宽。
- 验证：截图脚本输出的 `container w=1240` 在 1280/1440/1920 三档保持一致。

### 3. 三档窄屏布局保持原样

Phone / Tablet / Desktop-sm 的版式没有大改 — 它们本来就走 modern-minimal。
这次主要去掉了对 1600+/1920+ 的 max-width 上调（只放大 padding/gap，不再放大容器宽度）。

## 未进截图但已落地的改动

### 4. ProgressTracker 3 状态进度（取代 ProgressIndicator）

`miniprogram/src/components/ProgressTracker/{index.tsx, index.module.scss}`

- 新建。3 节点 tracker：「拍照已就绪 → AI 分析中 → 报告就绪」。
- Desktop 横向 grid（3 列 + 2 条 connector），Mobile <600px 纵向 timeline。
- Active 节点：橙色 dot + pulse 阴影 + 流动光带 connector。
- Done 节点：绿色 dot + 白色 ✓。
- Pending 节点：灰描边 + 文档 glyph。
- 底部：mono "已用时 0:12 / 预计 0:29" + 4px 进度条。
- Wired into：`miniprogram/src/pages/report/desktop.tsx` + `mobile.tsx`，
  替换原 `ProgressIndicator`（ring + step list）。
- 单测：`miniprogram/tests/components/ProgressTracker.test.tsx`（6 cases，全绿）。

> 想看 polling 状态的视觉对比，需要 backend 端起一条 inspection 任务并卡在 processing。
> 现有 e2e 脚本 `h5-photo-flow.mjs` 走过 polling 但等不到 processing 状态稳定停留，
> 后续如需归档可手动加 `--pause-on=processing` 的 dev hook。

## 不变的部分

报告页（succeeded 状态）已在 5/21 PC web UI plan 里改成 modern-minimal 白底数据卡（hero
photo + plain_warning + AlarmBox + 严重度 sidebar + HazardItem 列表 + 三联签字），
本轮没有重做。如发现仍残留 editorial 米黄痕迹，请定位具体组件再开一张任务。

## 验证

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 单元测试（含 ProgressTracker / TopNav 2-tab） | `pnpm jest` | 134 / 134 passed |
| H5 build | `pnpm build:h5` | 通过，1 warning（entrypoint size，与本次无关） |
| H5 responsive 截图（6 视口） | `node tests/e2e/h5-responsive.mjs` | ✅ PASSED |
