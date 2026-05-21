/**
 * Severity → 排序权重 / 颜色 / 中文标签 + hazards 排序工具。
 *
 * Clean & Minimal 色板：红/琥珀/绿 三档对应 high/medium/low，每档配 soft 软底。
 * UI 组件需要根据 severity 着色时一律走这里，不要硬编码 hex。
 */
import type { Severity, Hazard } from '../types/report';

export const SEVERITY_ORDER: Record<Severity, number> = {
  high: 3,
  medium: 2,
  low: 1,
};

/** Clean & Minimal 实色 — 用在 sev-solid / 数字着色等需要强对比的位置。 */
export const SEVERITY_COLOR: Record<Severity, string> = {
  high: '#D7373F',
  medium: '#C77A1F',
  low: '#2F8454',
};

/** Clean & Minimal 软底 — 严重度 pill 的 background。 */
export const SEVERITY_SOFT: Record<Severity, string> = {
  high: '#FCE7E9',
  medium: '#FBEED6',
  low: '#DEEFE3',
};

/** @deprecated Use {@link SEVERITY_SOFT} — kept only for legacy HazardCard during clean-UI migration. */
export const SEVERITY_BG_TINT = SEVERITY_SOFT;

/** @deprecated Use {@link SEVERITY_COLOR} — kept only for legacy HazardCard during clean-UI migration. */
export const SEVERITY_TEXT_ON_TINT = SEVERITY_COLOR;

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
