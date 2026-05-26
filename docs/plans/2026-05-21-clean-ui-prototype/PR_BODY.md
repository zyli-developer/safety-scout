# docs: clean & minimal UI prototype (2026-05-21)

## Summary

新增 `docs/plans/2026-05-21-clean-ui-prototype/`，存档一个完整的高保真 UI 原型（HTML + JSX + CSS）以及完整设计规范。**不动 `miniprogram/` 现有代码**，只是放一个候选方向供评审。

前序两轮探索（dossier 工地许可证 / Tactical Scanner HUD 暗色）落地后被评审「乱、丑」否决。本版完全推翻方向 — 浅色暖白底、单一安全橙、真实工地照片占主导、移除一切装饰性元素（角标 / 十字 / 扫描线 / 刻度尺 / 点阵网格）。

详细设计逻辑、token 表、屏幕意图、与现有代码差异、落地切片，全部在 `design.md`。

## What's in this PR

```
docs/plans/2026-05-21-clean-ui-prototype/
├── README.md          ← 如何在本地打开原型
├── design.md          ← 完整设计文档（12k 字）
├── index.html         ← 原型入口（5 屏 + Tweaks）
├── styles/clean.css   ← Design tokens + 组件样式
├── app/*.jsx          ← React + JSX 实现
└── assets/fonts/      ← IBM Plex Mono woff2
```

5 屏覆盖：

| # | 屏 | 尺寸 |
|---|---|---|
| 01 | 移动 · 首页 | 390×900 |
| 02 | 移动 · 等待 | 390×900 |
| 03 | 移动 · 报告 | 390×2050 |
| 04 | 桌面 · 工作台 | 1280×920 |
| 05 | 桌面 · 报告 | 1280×2050 |

## How to review

```bash
git checkout <this-branch>
cd docs/plans/2026-05-21-clean-ui-prototype
python3 -m http.server 8080
open http://localhost:8080
```

操作：滚轮缩放、空格 + 拖动平移、点卡片右上 ⤢ 进入聚焦全屏、右上 Tweaks 切换报告风险等级。

## Decision asked

请评审：

1. **方向** —— Clean & Minimal 美学是否成为接下来 PC + 移动 UI 的统一基线？（是 → 进切片）
2. **范围** —— `design.md §6` 提了 6 个独立 PR 切片，是否同意按此节奏推进？
3. **照片** —— Demo 用 Unsplash CDN 是否可接受？或要换工地实拍 / 用纯灰色 placeholder？

## Non-goals

- ✋ 不替代 `miniprogram/src/components/*` —— 本 PR 不改动代码，只存档原型
- ✋ 不取消现有 dossier 设计文档 —— 标 `Status: Superseded` 是接下来 PR 的事
- ✋ 不引入 backend / API 改动

## Checklist

- [x] 原型可在静态服务器跑通
- [x] 全部 5 屏渲染正常，无 console error
- [x] 真实工地照片加载（Unsplash CDN）
- [x] design.md 包含 tokens / 屏幕意图 / 组件清单 / 落地切片 / YAGNI 边界 / 验收 / 风险
- [x] README.md 包含本地查看说明
- [ ] **评审签字** ← waiting

## Suggested labels

`design`, `prototype`, `docs`, `frontend`

## Suggested commit message

```
docs(design): clean & minimal UI prototype (2026-05-21)

Adds a high-fidelity HTML prototype + full design spec for the third
direction explored after the dossier and HUD aesthetics were rejected.

- 5 screens (3 mobile / 2 desktop) inside a pan/zoom design canvas
- New design tokens: warm-white surface, single safety-orange accent,
  calm severity tri-color, system sans + IBM Plex Mono for IDs only
- Real construction photos via Unsplash CDN
- design.md covers tokens, screen-by-screen intent, component list,
  diff against existing miniprogram code, 6-slice rollout plan,
  YAGNI boundaries, acceptance criteria, risks

This PR is doc-only — no changes to backend/ or miniprogram/.
```
