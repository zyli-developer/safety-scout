/**
 * /api/v2/analyze + /api/v2/inspections/{id} 的 TypeScript 镜像。
 *
 * 后端对照：`backend/app/schemas/inspection_v2.py`。
 *
 * ErrorBody 与 v1 (`types/inspection.ts`) 完全相同，直接复用。
 */
import type { ErrorBody, InspectionStatus } from './inspection';
import type { ReportV2Payload } from './report-v2';

export interface CreateInspectionV2Response {
  inspection_id: string;
  /** 例如 "/api/v2/inspections/{id}"。 */
  poll_url: string;
  poll_interval_ms: number;
  timeout_ms: number;
  status: 'queued';
}

export interface GetInspectionV2Response {
  inspection_id: string;
  status: InspectionStatus;
  created_at: string;
  updated_at: string;
  report: ReportV2Payload | null;
  error: ErrorBody | null;
}

/** API 版本判别器，跟 URL 上的 `v` 参数同步。 */
export type SchemaVersion = 'v1' | 'v2';
