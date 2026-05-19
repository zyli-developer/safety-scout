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

export const SEVERITY_COLOR: Record<Severity, string> = {
  high: '#E63946', // 红 —— 主色，PlainWarningCard 全背景 / HazardCard 圆点指示
  medium: '#F4A261', // 橙
  low: '#2A9D8F', // 绿
};

/** 浅底色 tint，用于 HazardCard 严重度 pill 背景（搭配 SEVERITY_TEXT_ON_TINT 文字）。 */
export const SEVERITY_BG_TINT: Record<Severity, string> = {
  high: '#FEE2E2',
  medium: '#FEF3C7',
  low: '#D1FAE5',
};

/** SEVERITY_BG_TINT 之上的深色文字色，保证对比度 ≥ AA。 */
export const SEVERITY_TEXT_ON_TINT: Record<Severity, string> = {
  high: '#991B1B',
  medium: '#92400E',
  low: '#065F46',
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
