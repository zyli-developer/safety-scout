# Clean UI Prototype · 2026-05-21

工地安全巡检小程序 + PC Web 端的高保真 UI 原型。**纯静态 HTML 原型**，不动 `miniprogram/` 现有 Taro 代码。

## 目录

```
2026-05-21-clean-ui-prototype/
├── README.md              ← 本文件
├── design.md              ← 完整设计规范（token / 屏幕 / 组件 / 与现有代码对比）
├── index.html             ← 原型入口
├── styles/clean.css       ← 设计 token + 组件样式（CSS 变量）
├── app/                   ← React + JSX 屏幕实现
│   ├── sample-data.jsx
│   ├── clean-components.jsx
│   ├── clean-mobile-home.jsx
│   ├── clean-mobile-scan.jsx
│   ├── clean-mobile-report.jsx
│   ├── clean-desktop-home.jsx
│   ├── clean-desktop-report.jsx
│   └── clean-main.jsx
├── design-canvas.jsx      ← 演示画布（pan / zoom / focus）
├── ios-frame.jsx          ← iPhone 设备外壳
├── tweaks-panel.jsx       ← 风险等级切换
└── assets/fonts/          ← IBM Plex Mono woff2 子集
```

## 本地查看

```bash
# 任意静态服务器即可，例：
cd docs/plans/2026-05-21-clean-ui-prototype
python3 -m http.server 8080
# 浏览器打开 http://localhost:8080
```

> 直接双击 `index.html` 也能看，但 `file://` 协议下浏览器会拒绝加载 `.woff2`，编号会回退到系统等宽字体。开个本地服务器最稳。

## 演示画布操作

- **滚轮 / 双指**：缩放
- **空格 + 拖拽** / 中键拖拽：平移
- **点卡片右上角 ⤢**：进入聚焦全屏，`←/→` 切换、`Esc` 退出
- **右上 "Tweaks"**：切换报告页风险等级（高 / 中 / 低）

## 屏幕清单

| # | 屏幕 | 尺寸 | 备注 |
|---|---|---|---|
| 01 | 移动 · 首页 | 390×900 | iPhone frame · 拍照入口 |
| 02 | 移动 · 等待 | 390×900 | iPhone frame · AI 分析中 |
| 03 | 移动 · 报告 | 390×2050 | iPhone frame · 滚动 |
| 04 | 桌面 · 工作台 | 1280×920 | 上传 dropzone + 最近巡检 |
| 05 | 桌面 · 报告 | 1280×2050 | 双列 · 滚动 |

## 设计文档

完整设计逻辑（为什么浅色 / 为什么不再 dossier / 与现有代码差异 / 落地切片）见 [design.md](./design.md)。

## 与现有 miniprogram 代码的关系

本原型 **不替代** `miniprogram/src/components/*`，只是另一个候选方向。若决定采纳：

1. 弃用 `miniprogram/src/styles/tokens.scss` 里的 dossier 调色板，换成本原型 `styles/clean.css` 顶部的 `:root` 变量
2. 重写 `HazardCard` / `BigButton` / `HeaderBand` 三个组件的渲染（API 可保留）
3. 拍照流改用真实照片而非纯灰底，建议接入微信 `chooseMedia` 后将 `tempFilePath` 渲染到 `<image>` 上而不是只显示文件名
4. PC 桌面端布局（`pages/*/desktop.tsx`）按原型 04 / 05 重排，去掉 CAD 刻度尺、加大留白

完整迁移计划见 design.md §6「落地切片」。
