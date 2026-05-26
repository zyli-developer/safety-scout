/**
 * ProgressTracker — unified-modern-minimal 3-state 进度组件。
 *
 * 把 ProgressIndicator（小 ring + 列表）升级为屏幕主角的横向 / 纵向 3-节点 tracker，
 * 兑现 architecture 里"拍照成功 → AI 分析中 → 报告就绪"承诺。
 */
import { render, screen } from '@testing-library/react';
import { ProgressTracker } from '../../src/components/ProgressTracker';

describe('ProgressTracker', () => {
  it('renders all three node labels', () => {
    render(<ProgressTracker currentStep={2} elapsedMs={12000} />);
    expect(screen.getByText('拍照已就绪')).toBeInTheDocument();
    expect(screen.getByText('AI 分析中')).toBeInTheDocument();
    expect(screen.getByText('报告就绪')).toBeInTheDocument();
  });

  it('shows elapsed mm:ss / ~estimate on the active node during processing', () => {
    render(<ProgressTracker currentStep={2} elapsedMs={12000} estimatedSeconds={29} />);
    // node B hint = "0:12 / ~0:29"
    expect(screen.getByText('0:12 / ~0:29')).toBeInTheDocument();
  });

  it('uses "上传完成 · 等待分析" hint when still queued (step 1)', () => {
    render(<ProgressTracker currentStep={1} elapsedMs={3000} />);
    expect(screen.getByText('上传完成 · 等待分析')).toBeInTheDocument();
  });

  it('renders elapsed bar percent based on elapsed/estimate', () => {
    const { container } = render(
      <ProgressTracker currentStep={2} elapsedMs={15000} estimatedSeconds={30} />,
    );
    // elapsed-fill width = 50%
    const fill = container.querySelector('[style*="width: 50%"]');
    expect(fill).not.toBeNull();
  });

  it('clamps elapsed percent at 100 when over estimate', () => {
    const { container } = render(
      <ProgressTracker currentStep={2} elapsedMs={60000} estimatedSeconds={30} />,
    );
    const fill = container.querySelector('[style*="width: 100%"]');
    expect(fill).not.toBeNull();
  });

  it('shows the average-time hint footer in seconds when estimatedSeconds < 60', () => {
    render(<ProgressTracker currentStep={2} estimatedSeconds={29} />);
    expect(
      screen.getByText('不需要等在这页 — 完成后会自动跳转。平均 29 秒出结果。'),
    ).toBeInTheDocument();
  });

  it('shows minutes formatting when estimatedSeconds >= 60 (180s → 3 分钟)', () => {
    render(<ProgressTracker currentStep={2} estimatedSeconds={180} />);
    expect(
      screen.getByText('不需要等在这页 — 完成后会自动跳转。平均 3 分钟出结果。'),
    ).toBeInTheDocument();
  });

  it('defaults estimatedSeconds to 180 (~3 分钟) when prop omitted', () => {
    render(<ProgressTracker currentStep={2} />);
    // default hint 走 minutes 分支
    expect(screen.getByText(/平均 3 分钟出结果/)).toBeInTheDocument();
  });
});
