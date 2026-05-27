/**
 * v2 → v1 适配器单测。
 *
 * 关键场景：
 * - 严重度 4 档映射 + is_major 触发
 * - findings → hazards 整段映射
 * - plain_warning 30 字截断
 * - summary 取 key_recommendations 首条；空时取 image_summary
 * - 空 findings 数组
 */
import {
  mapV2SeverityToV1,
  mapV2FindingToV1Hazard,
  mapV2ReportToV1,
} from '../../src/utils/v2Adapter';
import type { ReportV2Payload, FindingV2 } from '../../src/types/report-v2';

function makeFinding(overrides: Partial<FindingV2> = {}): FindingV2 {
  return {
    check_id: 'B01',
    category: '高坠风险',
    status: '存在隐患',
    title: '三层临边未设置防护栏杆',
    location: '图片中部，三层楼板边缘',
    description: '约 4m 高度，工人直接靠近边缘',
    severity: '较大',
    regulation: 'JGJ80-2016 第 4.1.1 条',
    action: '立即停工，搭设标准防护栏杆',
    confidence: '高',
    ...overrides,
  };
}

function makeReportV2(overrides: Partial<ReportV2Payload> = {}): ReportV2Payload {
  return {
    report_meta: {
      image_summary: '现场为多层在建结构，三层临边有工人作业',
      scene_detected: ['S05'],
      analysis_confidence: '高',
      overall_risk_level: '较大',
    },
    findings: [makeFinding()],
    no_findings: [],
    uncertain: [],
    summary: {
      total_checks: 35,
      findings_count: 1,
      fatal_count: 0,
      major_count: 1,
      minor_count: 0,
      no_issue_count: 30,
      uncertain_count: 4,
      key_recommendations: ['立即停工整改 1 项较大隐患'],
    },
    ...overrides,
  };
}

describe('mapV2SeverityToV1', () => {
  test('重大 → high', () => {
    expect(mapV2SeverityToV1('重大')).toBe('high');
  });
  test('较大 → high', () => {
    expect(mapV2SeverityToV1('较大')).toBe('high');
  });
  test('一般 → medium', () => {
    expect(mapV2SeverityToV1('一般')).toBe('medium');
  });
  test('低 → low', () => {
    expect(mapV2SeverityToV1('低')).toBe('low');
  });
});

describe('mapV2FindingToV1Hazard', () => {
  test('模型未提供 is_major → 默认 false + major_basis 为空（不合成假依据）', () => {
    // 这是回归保护：旧实现会把 severity=重大 等价代换为 is_major=true，
    // 并把 check_id 当作判定标准条款号拼进 major_basis（用户 2026-05 反馈的 bug）。
    const h = mapV2FindingToV1Hazard(
      makeFinding({ severity: '重大', check_id: 'S06-A01', category: '高坠风险' }),
    );
    expect(h.severity).toBe('high');
    expect(h.is_major).toBe(false);
    expect(h.major_basis).toBe('');
  });

  test('较大 finding 不触发重大隐患红标', () => {
    const h = mapV2FindingToV1Hazard(makeFinding({ severity: '较大' }));
    expect(h.severity).toBe('high');
    expect(h.is_major).toBe(false);
    expect(h.major_basis).toBe('');
  });

  test('模型提供 is_major=true + major_basis → adapter pass-through 原样保留', () => {
    const basis =
      '《房屋市政工程生产安全重大事故隐患判定标准（2024版）》建质规〔2024〕5号 第 6 条 高处作业 — 临边高度 ≥2m 无防护栏';
    const h = mapV2FindingToV1Hazard(
      makeFinding({ severity: '重大', is_major: true, major_basis: basis }),
    );
    expect(h.is_major).toBe(true);
    expect(h.major_basis).toBe(basis);
  });

  test('adapter 严格用 check_id 作字面值，不把它写进 major_basis', () => {
    // 模型不给 → adapter 不能把 check_id 'S06-A01' 拼进 major_basis 模板
    const h = mapV2FindingToV1Hazard(
      makeFinding({ severity: '重大', check_id: 'S06-A01' }),
    );
    expect(h.major_basis).not.toContain('S06-A01');
    expect(h.major_basis).not.toContain('建质规');
  });

  test('description 合并 title + location + description', () => {
    const h = mapV2FindingToV1Hazard(makeFinding());
    expect(h.description).toContain('三层临边未设置防护栏杆');
    expect(h.description).toContain('图片中部');
    expect(h.description).toContain('约 4m 高度');
  });

  test('location 为空时 description 不挂尾巴', () => {
    const h = mapV2FindingToV1Hazard(makeFinding({ location: '' }));
    expect(h.description).not.toContain(' · ');
  });

  test('check_id 写到 category_code，action 写到 suggestion，category 写到 category_name', () => {
    const h = mapV2FindingToV1Hazard(
      makeFinding({ check_id: 'B01', category: '高坠风险', action: '立即停工' }),
    );
    expect(h.category_code).toBe('B01');
    expect(h.category_name).toBe('高坠风险');
    expect(h.suggestion).toBe('立即停工');
  });
});

describe('mapV2ReportToV1', () => {
  const ID = 'aaaa-bbbb';
  const CREATED = '2026-05-26T01:00:00Z';

  test('happy path: findings → hazards 全量映射', () => {
    const v2 = makeReportV2();
    const v1 = mapV2ReportToV1(v2, ID, CREATED);
    expect(v1.inspection_id).toBe(ID);
    expect(v1.created_at).toBe(CREATED);
    expect(v1.hazards).toHaveLength(1);
    expect(v1.hazards[0].category_name).toBe('高坠风险');
  });

  test('overall_severity 跟 v2.report_meta.overall_risk_level 走', () => {
    const v2 = makeReportV2({
      report_meta: {
        image_summary: 'x',
        scene_detected: [],
        analysis_confidence: '高',
        overall_risk_level: '重大',
      },
    });
    const v1 = mapV2ReportToV1(v2, ID, CREATED);
    expect(v1.overall_severity).toBe('high');
  });

  test('plain_warning 短于 30 字时原样', () => {
    const v2 = makeReportV2({
      report_meta: {
        image_summary: '短摘要',
        scene_detected: [],
        analysis_confidence: '高',
        overall_risk_level: '低',
      },
    });
    const v1 = mapV2ReportToV1(v2, ID, CREATED);
    expect(v1.plain_warning).toBe('短摘要');
  });

  test('plain_warning 长于 30 字时截断 + 省略号', () => {
    const long = 'x'.repeat(50);
    const v2 = makeReportV2({
      report_meta: {
        image_summary: long,
        scene_detected: [],
        analysis_confidence: '高',
        overall_risk_level: '低',
      },
    });
    const v1 = mapV2ReportToV1(v2, ID, CREATED);
    expect(v1.plain_warning.length).toBeLessThanOrEqual(30);
    expect(v1.plain_warning.endsWith('...')).toBe(true);
  });

  test('summary 取 key_recommendations 首条', () => {
    const v2 = makeReportV2({
      summary: {
        ...makeReportV2().summary,
        key_recommendations: ['第一条建议', '第二条建议'],
      },
    });
    expect(mapV2ReportToV1(v2, ID, CREATED).summary).toBe('第一条建议');
  });

  test('summary 空 key_recommendations 时退到 image_summary', () => {
    const v2 = makeReportV2({
      report_meta: {
        image_summary: '默认摘要',
        scene_detected: [],
        analysis_confidence: '高',
        overall_risk_level: '低',
      },
      summary: {
        ...makeReportV2().summary,
        key_recommendations: [],
      },
    });
    expect(mapV2ReportToV1(v2, ID, CREATED).summary).toBe('默认摘要');
  });

  test('空 findings 数组 → 空 hazards', () => {
    const v2 = makeReportV2({ findings: [] });
    expect(mapV2ReportToV1(v2, ID, CREATED).hazards).toEqual([]);
  });
});
