/**
 * 单元测试：ProgressIndicator.
 *
 * 验收要点：
 * - 三段标签都渲染
 * - currentStep=2 时显示 "已耗时 {Xs}s"
 * - step=1 / step=3 不显示耗时
 */
import { render, screen } from '@testing-library/react';
import { ProgressIndicator } from '../../src/components/ProgressIndicator';

describe('ProgressIndicator', () => {
  it('renders 3 step labels', () => {
    render(<ProgressIndicator currentStep={2} />);
    expect(screen.getByText('拍照成功')).toBeInTheDocument();
    expect(screen.getByText('AI 分析中')).toBeInTheDocument();
    expect(screen.getByText('报告就绪')).toBeInTheDocument();
  });

  it('shows elapsedMs in seconds when step=2', () => {
    render(<ProgressIndicator currentStep={2} elapsedMs={75_000} />);
    // toFixed(0) → "75"；含 "已耗时 75s" 即可
    expect(screen.getByText(/已耗时 75s/)).toBeInTheDocument();
  });

  it('does not show elapsed when step=1 or step=3', () => {
    const { rerender } = render(
      <ProgressIndicator currentStep={1} elapsedMs={75_000} />,
    );
    expect(screen.queryByText(/已耗时/)).not.toBeInTheDocument();

    rerender(<ProgressIndicator currentStep={3} elapsedMs={75_000} />);
    expect(screen.queryByText(/已耗时/)).not.toBeInTheDocument();
  });
});
