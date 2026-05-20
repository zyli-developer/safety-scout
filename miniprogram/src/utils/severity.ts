/**
 * Severity → 排序权重 / 颜色 / 中文标签 + hazards 排序工具。
 *
 * 色板：红橙绿三档对应 high/medium/low，对应架构 §3 组件分工里 hazard 卡片的
 * 暗示性配色。任何 UI 组件需要根据 severity 着色都走这里，不要硬编码 hex。
 */
import type { Severity, Hazard } from '../types/report';

export const SEVERITY_ORDER: Record<Severity, number> = {
  high: 3,
  medium: 2,
  low: 1,
};

/** Dossier engineering palette — sharper than iOS HIG, matches paper-document context.
 *  See docs/plans/2026-05-20-miniprogram-ui-dossier-design.md. */
export const SEVERITY_COLOR: Record<Severity, string> = {
  high: '#C8281C',    // engineering red (stamps, critical)
  medium: '#E07B1F',  // warning amber
  low: '#3D7C3D',     // pass green
};

/** Paper-tinted pill background — sits on the #F4EFE5 body. */
export const SEVERITY_BG_TINT: Record<Severity, string> = {
  high: '#F5DDD9',
  medium: '#F6E2CB',
  low: '#DDE8DD',
};

/** AA-contrast text on the tint background. */
export const SEVERITY_TEXT_ON_TINT: Record<Severity, string> = {
  high: '#7A1812',
  medium: '#7C4214',
  low: '#1F4A1F',
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
};

/**
 * 按 severity 降序排列（high → medium → low）。
 * 稳定排序：相同 severity 的 hazards 保留输入顺序。
 * 入参标 readonly 表示不会原地改 —— 调用方可以直接传 store 里的数组。
 */
export function sortBySeverity(hazards: readonly Hazard[]): Hazard[] {
  return [...hazards].sort(
    (a, b) => SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity],
  );
}
