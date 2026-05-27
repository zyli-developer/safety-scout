/**
 * v2 → v1 报告形状适配器。
 *
 * 动机：v2 (`ReportV2Payload`) 与 v1 (`ReportPayload`) 顶层 shape 不同，
 * 但前端 v1 渲染组件（HazardItem / SeverityPill / ReportSidebar 等）已经成熟。
 * 这一层把 v2 的 `findings[]` 映射为 v1 的 `hazards[]`，让 v1 组件可以直接渲染
 * v2 报告 —— PR #6 阶段的最小集成。
 *
 * 损失（PR #6 阶段不渲染，留作后续 PR 增量）：
 * - `report_meta.image_summary` / `scene_detected` / `analysis_confidence` —— 整图描述层信息
 * - `no_findings[]` —— 已核查无隐患项明细（仅保留计数 summary.no_issue_count）
 * - `uncertain[]` 明细 —— 仅保留计数
 * - 每条 finding 的 `location` / `confidence` / `category` / `status`
 *
 * 严重度映射（v2 中文四档 → v1 三档）：
 *   重大 / 较大 → high
 *   一般       → medium
 *   低         → low
 *
 * **is_major / major_basis 是模型字段，adapter 不参与判定**：
 *   旧实现曾用「severity=重大 → 拼模板」等价代换，会把 check_id 当作判定标准条款号写进
 *   `major_basis`，造成"判定依据"虚构（用户 2026-05 反馈的 S06-A01 案例就是这个 bug）。
 *   现在 adapter 严格 pass-through `f.is_major` / `f.major_basis` —— 模型不给就显示不出，
 *   宁可少一个红标，也不要伪造一句"建质规〔2024〕5号"。
 */
import type { Hazard, ReportPayload, Severity, CategoryCode } from '../types/report';
import type { ReportV2Payload, V2Severity, FindingV2 } from '../types/report-v2';

export function mapV2SeverityToV1(v2: V2Severity): Severity {
  switch (v2) {
    case '重大':
    case '较大':
      return 'high';
    case '一般':
      return 'medium';
    case '低':
      return 'low';
  }
}

/**
 * v2 Finding → v1 Hazard。
 *
 * category_code 写 v2 的 check_id（如 "B01" / "S03-A01"）—— 不是 v1 的 H1..H10 literal，
 * 但 HazardItem 渲染时只把它当文本显示，运行时无差。类型上做 `as` 断言通过编译。
 */
export function mapV2FindingToV1Hazard(f: FindingV2): Hazard {
  return {
    category_code: f.check_id as CategoryCode,
    category_name: f.category,
    description: f.title + (f.location ? ` · ${f.location}` : '') + (f.description ? `\n${f.description}` : ''),
    severity: mapV2SeverityToV1(f.severity),
    regulation: f.regulation,
    suggestion: f.action,
    // 严格 pass-through：模型未提供则视为 false / 空串，不再合成假依据。
    is_major: f.is_major === true,
    major_basis: typeof f.major_basis === 'string' ? f.major_basis : '',
  };
}

/**
 * 完整 v2 报告 → v1 报告。
 *
 * 输入是 v2 GET response body 的 `report` 字段 + 外部已知的 inspection_id + created_at。
 * inspection_id 与 created_at 不在 ReportV2Payload 里（v2 单独通过 GetInspectionV2Response
 * 顶层暴露），caller 必须传进来。
 */
export function mapV2ReportToV1(
  v2: ReportV2Payload,
  inspectionId: string,
  createdAt: string,
): ReportPayload {
  const hazards = v2.findings.map(mapV2FindingToV1Hazard);
  const overall = mapV2SeverityToV1(v2.report_meta.overall_risk_level);

  // plain_warning 给 1-30 字醒目卡片用 —— v2 没有直接对应，取 image_summary 截断。
  const plainWarning = v2.report_meta.image_summary.length <= 30
    ? v2.report_meta.image_summary
    : v2.report_meta.image_summary.slice(0, 27) + '...';

  // summary 给 ≤100 字专业总结 —— 取 key_recommendations 首条，没有则用 image_summary。
  const summary = v2.summary.key_recommendations.length > 0
    ? v2.summary.key_recommendations[0]
    : v2.report_meta.image_summary;

  return {
    inspection_id: inspectionId,
    created_at: createdAt,
    plain_warning: plainWarning,
    summary,
    overall_severity: overall,
    hazards,
    // v2 没有原生 model_meta；造一个 placeholder 让下游不崩。
    model_meta: {
      provider: 'claude_cli',
      model: 'agent-sdk',
      latency_ms: 0,
    },
  };
}
