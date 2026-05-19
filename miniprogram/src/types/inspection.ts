/**
 * /api/v1/inspections API I/O 的 TypeScript 镜像。
 *
 * 后端对照：`backend/app/schemas/inspection.py`
 *
 * 状态机：
 * - POST 立返 202 + CreateInspectionResponse，status 恒为 "queued"
 * - GET 用 status 字段判断：
 *   - queued / processing → report 与 error 均 null
 *   - succeeded → report 非 null，error null
 *   - failed → error 非 null，report null
 */

import type { ReportPayload } from './report';

export type InspectionStatus = 'queued' | 'processing' | 'succeeded' | 'failed';

export interface CreateInspectionResponse {
  inspection_id: string;
  /** 例如 "/api/v1/inspections/{id}"。 */
  poll_url: string;
  poll_interval_ms: number;
  timeout_ms: number;
  status: 'queued';
}

export interface ErrorBody {
  /** 机器可读的错误码，如 "LLM_PARSE_FAILED"。 */
  code: string;
  /** dev-facing，英文，可含堆栈相关信息。 */
  message: string;
  /** zh，面向用户的友好提示，前端直接渲染。 */
  user_message: string;
}

export interface GetInspectionResponse {
  inspection_id: string;
  status: InspectionStatus;
  created_at: string;
  updated_at: string;
  report: ReportPayload | null;
  error: ErrorBody | null;
}
