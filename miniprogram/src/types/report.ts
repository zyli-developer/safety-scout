/**
 * 报告 JSON Schema 的 TypeScript 镜像。
 *
 * 单一来源：`docs/specs/report-schema.md`
 * 后端对照：`backend/app/schemas/report.py`
 *
 * 任何字段增删 / 类型变更必须同 PR 改 spec + 后端 Pydantic 模型 + 本文件。
 * `tests/types/report.test.ts` 会读取 spec 的第一个 ```json 块做结构断言，
 * schema 漂移时该测试会挂。
 */

export type Severity = 'high' | 'medium' | 'low';

export type CategoryCode =
  | 'H1'
  | 'H2'
  | 'H3'
  | 'H4'
  | 'H5'
  | 'H6'
  | 'H7'
  | 'H8'
  | 'H9'
  | 'H10';

export interface Hazard {
  category_code: CategoryCode;
  category_name: string;
  description: string;
  severity: Severity;
  /** 可为空字符串；不允许编造规范条款。 */
  regulation: string;
  suggestion: string;
}

export interface ModelMeta {
  provider: 'claude_cli' | 'fake';
  model: string;
  latency_ms: number;
}

export interface ReportPayload {
  inspection_id: string;
  /** ISO 8601 UTC，例如 "2026-05-18T08:23:11Z"。 */
  created_at: string;
  /** 1-30 字口语化中文警示，顶部醒目卡片用。 */
  plain_warning: string;
  /** ≤ 100 字，专业总结，面向安全员。 */
  summary: string;
  /** 取 hazards[] 中最高 severity；空列表时为 "low"。 */
  overall_severity: Severity;
  hazards: Hazard[];
  model_meta: ModelMeta;
}
