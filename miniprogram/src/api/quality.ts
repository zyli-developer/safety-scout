/**
 * 质量趋势 API client —— 对应 backend GET /api/v1/quality/trend
 * (docs/specs/quality-tracking.md §5.1)
 *
 * 设计：保持极简 —— 单个 fetchQualityTrend 函数即可，避免造无用抽象。
 */
import { request } from './client';

export type QualityMetric =
  | 'judge_win_rate'
  | 'p50_latency'
  | 'output_tokens'
  | 'finding_count'
  | 'reg_coverage';

export type QualityGroupBy = 'prompt_version' | 'model' | 'day';

export interface QualityTrendPoint {
  /** 桶 key，等于 prompt_version / model 字符串或 YYYY-MM-DD */
  group: string;
  /** x 轴值，与 group 当前实现一致（每个桶单个点）；保留独立字段便于未来扩展二维 */
  x: string;
  value: number;
  /** 该桶内样本数 */
  n: number;
}

export interface QualityTrendResponse {
  metric: QualityMetric;
  group_by: QualityGroupBy;
  since: string;
  series: QualityTrendPoint[];
}

/** 拉一个 metric × group_by 的趋势序列。 */
export async function fetchQualityTrend(
  metric: QualityMetric,
  groupBy: QualityGroupBy,
  since?: string,
): Promise<QualityTrendResponse> {
  const params = new URLSearchParams({ metric, group_by: groupBy });
  if (since) params.set('since', since);
  return request<QualityTrendResponse>({
    url: `/api/v1/quality/trend?${params.toString()}`,
    method: 'GET',
  });
}
