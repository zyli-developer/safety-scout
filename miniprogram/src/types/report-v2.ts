/**
 * v2 报告 JSON Schema 的 TypeScript 镜像。
 *
 * 单一来源：`backend/app/schemas/report_v2.py` + `safety_skills/_shared/output_schema.md`。
 * 与 v1 (`types/report.ts`) 完全独立 —— 顶层 shape 不同（findings vs hazards）、
 * severity 用中文档位、新增 check_id / location / confidence / no_findings / uncertain。
 *
 * 前端鉴别 v1 vs v2 的运行时方法：检测 `report.findings` 是否存在
 * （v1 报告无此字段；v2 报告无 `hazards` 字段）。
 */

export type V2Severity = '重大' | '较大' | '一般' | '低';
export type V2Confidence = '高' | '中' | '低';
export type V2FindingStatus = '存在隐患' | '不存在' | '无法判断';

export interface ReportMetaV2 {
  /** 对图片整体场景的一句话描述。 */
  image_summary: string;
  /** 命中的场景 ID 列表，如 ['S03', 'S05']。 */
  scene_detected: string[];
  analysis_confidence: V2Confidence;
  overall_risk_level: V2Severity;
}

export interface FindingV2 {
  /** L1/L2 清单条目编号，如 B01 或 S03-A01。 */
  check_id: string;
  /** 风险类别（中文），如"高坠风险" / "触电"。 */
  category: string;
  status: V2FindingStatus;
  title: string;
  /** 图片相对位置，便于人工复核（如"图片中部，三层楼板边缘"）。 */
  location: string;
  description: string;
  severity: V2Severity;
  /** 引用的规范条款编号；可为空字符串。 */
  regulation: string;
  /** 给安全员的整改建议，动作可执行。 */
  action: string;
  confidence: V2Confidence;
}

export interface NoFindingV2 {
  check_id: string;
  note: string;
}

export interface UncertainV2 {
  check_id: string;
  reason: string;
  suggested_action: string;
}

export interface ReportSummaryV2 {
  total_checks: number;
  findings_count: number;
  fatal_count: number;
  major_count: number;
  minor_count: number;
  no_issue_count: number;
  uncertain_count: number;
  key_recommendations: string[];
}

export interface ReportV2Payload {
  report_meta: ReportMetaV2;
  findings: FindingV2[];
  no_findings: NoFindingV2[];
  uncertain: UncertainV2[];
  summary: ReportSummaryV2;
}
