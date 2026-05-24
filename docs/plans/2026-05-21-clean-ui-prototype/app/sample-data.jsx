// Sample data, faithful to /docs/specs/hazards.md + /docs/specs/report-schema.md

const SAMPLE_HAZARDS = [
  {
    category_code: 'H1', category_name: '高处坠落',
    severity: 'high',
    description: '二层楼板边缘缺失防护栏杆，距地面约 4m，作业人员频繁穿行',
    regulation: 'JGJ 80-2016 第 4.2.1 条',
    suggestion: '24 小时内设置高度不低于 1.2m 的临边防护栏杆，挂设警示标志',
  },
  {
    category_code: 'H9', category_name: '个人防护缺失',
    severity: 'high',
    description: '画面中 2 名工人未佩戴安全帽进入施工区，1 人未系下颌带',
    regulation: 'JGJ 80-2016 第 3.0.3 条',
    suggestion: '立即责令补齐安全帽并系紧下颌带；班组每日班前会增加 PPE 检查项',
  },
  {
    category_code: 'H3', category_name: '触电',
    severity: 'medium',
    description: '临时配电箱箱门未关闭，箱内空气开关与接线端子裸露在外',
    regulation: 'JGJ 46-2005 第 8.1.10 条',
    suggestion: '24 小时内增设箱门锁具与"非工作人员禁止靠近"警示标志',
  },
  {
    category_code: 'H10', category_name: '其他 / 文明施工',
    severity: 'medium',
    description: '主通道堆放钢筋占据宽度约 1.2m，影响人员通行与应急疏散',
    regulation: '',
    suggestion: '立即清理通道，钢筋集中堆放至指定料场，保持通道净宽 ≥ 1.5m',
  },
  {
    category_code: 'H6', category_name: '火灾',
    severity: 'low',
    description: '作业面附近灭火器配置不足，最近一具距动火点约 18m',
    regulation: 'GB 50720-2011 第 5.1.2 条',
    suggestion: '增配 4kg ABC 干粉灭火器 2 具至作业面 ≤ 15m 半径内',
  },
];

const SAMPLE_REPORT = {
  inspection_id: '550e8400-e29b-41d4-a716-446655440000',
  created_at: '2026-05-21T07:18:32Z',
  plain_warning: '楼板临边无防护，工人未戴帽，立刻撤离整改',
  summary: '现场存在 2 项高风险隐患，整体风险等级：高。建议立即停工整改临边防护与个人防护问题。',
  overall_severity: 'high',
  hazards: SAMPLE_HAZARDS,
};

const SHOT_TIPS = [
  '贴近隐患位置，保持光线充足',
  '画面含工人 / 护栏 / 电箱 等关键元素',
  '距离 1–3m 为佳，避免逆光',
];

Object.assign(window, { SAMPLE_HAZARDS, SAMPLE_REPORT, SHOT_TIPS });
