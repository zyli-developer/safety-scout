/**
 * 单元测试：ReportSidebar (2026-05-22 unified-modern-minimal · 2026-05-24 B5 改造)。
 *
 * 验收要点：
 * - 标题 "本次扫描概要"
 * - bar 显示 hazardCount + "项隐患"
 * - severity breakdown 仍可通过 SeverityPill 找到（保留为 .legacyBreakdown 隐藏渲染）
 * - 渲染 summary
 * - 默认不暴露 model 名（dev-chrome 藏进 TechDisclosure 折叠）
 * - 点击"技术信息"展开后能看到 model + latency
 */
import { fireEvent, render, screen } from '@testing-library/react';

import { ReportSidebar } from '../../../src/components/desktop/ReportSidebar';
import type { Hazard, ReportPayload } from '../../../src/types/report';

function makeHazard(severity: Hazard['severity']): Hazard {
  return {
    category_code: 'H1',
    category_name: '高处作业',
    description: '描述',
    severity,
    regulation: '',
    suggestion: '建议',
  };
}

const SAMPLE: ReportPayload = {
  inspection_id: 'rep-1',
  created_at: '2026-05-21T10:00:00Z',
  plain_warning: '注意临边坠落',
  summary: '外架与楼梯间防护多处缺失',
  overall_severity: 'high',
  hazards: [makeHazard('high'), makeHazard('high'), makeHazard('medium'), makeHazard('low')],
  model_meta: { provider: 'claude_cli', model: 'sonnet', latency_ms: 30000 },
};

describe('ReportSidebar (2026-05-22)', () => {
  it('renders "本次扫描概要" title', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    expect(screen.getByText('本次扫描概要')).toBeInTheDocument();
  });

  it('renders hazard total in bar', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    // bar 渲染 "共 4 项隐患"；4 出现在 barNum 节点
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('renders severity breakdown via legacy SeverityPill (hidden but query-able)', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    expect(screen.getByText('高风险 · 2')).toBeInTheDocument();
    expect(screen.getByText('中风险 · 1')).toBeInTheDocument();
    expect(screen.getByText('低风险 · 1')).toBeInTheDocument();
  });

  it('renders summary text', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    expect(screen.getByText('外架与楼梯间防护多处缺失')).toBeInTheDocument();
  });

  it('shows analysis latency in summary section', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    expect(screen.getByText('30.0 秒')).toBeInTheDocument();
  });

  it('hides model name by default; reveals after expanding TechDisclosure', () => {
    // 2026-05-24 B5: model 名是 dev-chrome 必须藏进 details。默认 collapsed。
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    expect(screen.queryByText('sonnet')).toBeNull();

    const techToggle = screen.getByText('技术信息');
    fireEvent.click(techToggle);
    expect(screen.getByText('sonnet')).toBeInTheDocument();
  });

  it('falls back to — when latency is missing', () => {
    const r = { ...SAMPLE, model_meta: { ...SAMPLE.model_meta, latency_ms: 0 } };
    render(<ReportSidebar report={r} hazardCount={4} />);
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
});
