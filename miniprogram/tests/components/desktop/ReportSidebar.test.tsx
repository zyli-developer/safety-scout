/**
 * 单元测试：ReportSidebar.
 *
 * 验收要点：
 * - 渲染 'INSPECTION REPORT' eyebrow + 中文标题
 * - 渲染隐患数 + 风险等级
 * - 渲染 summary + plain_warning（plain_warning 可选）
 */
import { render, screen } from '@testing-library/react';

import { ReportSidebar } from '../../../src/components/desktop/ReportSidebar';
import type { ReportPayload } from '../../../src/types/report';

const SAMPLE: ReportPayload = {
  inspection_id: 'rep-1',
  created_at: '2026-05-21T10:00:00Z',
  plain_warning: '注意临边坠落',
  summary: '外架与楼梯间防护多处缺失',
  overall_severity: 'high',
  hazards: [],
  model_meta: { provider: 'claude_cli', model: 'sonnet', latency_ms: 30000 },
};

describe('ReportSidebar', () => {
  it('renders inspection report eyebrow + title', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={7} />);
    expect(screen.getByText(/INSPECTION REPORT/i)).toBeInTheDocument();
    expect(screen.getByText('现场巡检报告')).toBeInTheDocument();
  });

  it('renders hazard count + severity label', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={7} />);
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText(/项隐患待整改/)).toBeInTheDocument();
    expect(screen.getByText(/高风险/)).toBeInTheDocument();
  });

  it('renders summary + plain_warning when both present', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={7} />);
    expect(screen.getByText('外架与楼梯间防护多处缺失')).toBeInTheDocument();
    expect(screen.getByText('注意临边坠落')).toBeInTheDocument();
  });

  it('omits plain_warning element when empty', () => {
    const r = { ...SAMPLE, plain_warning: '' };
    render(<ReportSidebar report={r} hazardCount={3} />);
    expect(screen.queryByText('注意临边坠落')).not.toBeInTheDocument();
  });
});
