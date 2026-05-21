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

/** White + iOS-blue palette —— severity 走蓝色家族 (deep / mid / light)。
 *  代替早期 dossier 红/橙/绿三档；语义保留：值越高视觉越重。
 *  注意：这是有意识的设计权衡，违背了「红色=最危险」的工业惯例 ——
 *  详见 PR 描述。saber officer 需要重新建立"深蓝=高风险"的视觉记忆。 */
export const SEVERITY_COLOR: Record<Severity, string> = {
  high: '#0040C8',    // deep blue (alarm, critical)
  medium: '#007AFF',  // iOS system blue (mid)
  low: '#38BDF8',     // sky blue (info, calmer)
};

/** White-base pill 背景：与 #FFFFFF body 形成淡蓝层次。 */
export const SEVERITY_BG_TINT: Record<Severity, string> = {
  high: '#DCE7FA',    // deep-blue 12% on white
  medium: '#D6E8FF',  // system-blue tint
  low: '#E0F4FE',     // sky-blue tint
};

/** AA-contrast 深蓝文字色，分别落在对应 tint 上保证可读。 */
export const SEVERITY_TEXT_ON_TINT: Record<Severity, string> = {
  high: '#001E66',    // deep navy
  medium: '#003E80',  // royal navy
  low: '#075985',     // sky-800
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
