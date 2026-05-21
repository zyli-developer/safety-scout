/**
 * 单元测试：ReportSidebar (clean-minimal 概要卡)。
 *
 * 验收要点：
 * - eyebrow "巡检概要"
 * - 渲染 hazardCount + "项隐患" 单位
 * - 渲染 high/medium/low 三档 SeverityPill（含 count）
 * - 渲染 summary 文案
 * - 渲染 model_meta 的 latency / model 名字
 */
import { render, screen } from '@testing-library/react';

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

describe('ReportSidebar (clean-minimal)', () => {
  it('renders 巡检概要 eyebrow', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    expect(screen.getByText('巡检概要')).toBeInTheDocument();
  });

  it('renders hazard count + 项隐患 unit', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('项隐患')).toBeInTheDocument();
  });

  it('renders severity breakdown pills with per-level counts', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    expect(screen.getByText('高风险 · 2')).toBeInTheDocument();
    expect(screen.getByText('中风险 · 1')).toBeInTheDocument();
    expect(screen.getByText('低风险 · 1')).toBeInTheDocument();
  });

  it('renders summary text', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    expect(screen.getByText('外架与楼梯间防护多处缺失')).toBeInTheDocument();
  });

  it('renders model meta — latency in seconds + model name', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={4} />);
    expect(screen.getByText('30.0 秒')).toBeInTheDocument();
    expect(screen.getByText('sonnet')).toBeInTheDocument();
  });

  it('falls back to — when latency is missing', () => {
    const r = { ...SAMPLE, model_meta: { ...SAMPLE.model_meta, latency_ms: 0 } };
    render(<ReportSidebar report={r} hazardCount={4} />);
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
});
