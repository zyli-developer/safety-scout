/**
 * ProgressIndicator (dossier) —— monospace readout, no spinner.
 *
 * 形态：
 *   READING ················ 12s
 *   01  拍照已就绪
 *   02  AI 识别中  ◀ active row
 *   03  报告生成中
 */
import { render, screen } from '@testing-library/react';
import { ProgressIndicator } from '../../src/components/ProgressIndicator';

describe('ProgressIndicator (dossier)', () => {
  it('renders all three numbered step labels', () => {
    render(<ProgressIndicator currentStep={2} elapsedMs={5000} />);
    expect(screen.getByText('01')).toBeInTheDocument();
    expect(screen.getByText('02')).toBeInTheDocument();
    expect(screen.getByText('03')).toBeInTheDocument();
    expect(screen.getByText('拍照已就绪')).toBeInTheDocument();
    expect(screen.getByText('AI 识别中')).toBeInTheDocument();
    expect(screen.getByText('报告生成中')).toBeInTheDocument();
  });

  it('shows elapsed seconds during step 2', () => {
    render(<ProgressIndicator currentStep={2} elapsedMs={5000} />);
    expect(screen.getByText(/5s/)).toBeInTheDocument();
  });

  it('marks the active step with data-state="active"', () => {
    const { container } = render(<ProgressIndicator currentStep={2} elapsedMs={0} />);
    const activeRows = container.querySelectorAll('[data-state="active"]');
    expect(activeRows.length).toBeGreaterThan(0);
  });
});
