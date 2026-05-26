/**
 * ProgressIndicator (clean-minimal) —— ProgressRing + StepList 组合。
 *
 * 形态：
 *   ⏺ <ring 50%>   READING
 *                  预计 60–180s · Claude Vision 推理中
 *   ✓  拍照已就绪
 *   02 AI 识别中  ← active row
 *   03 报告生成中
 *
 * 进度环：currentStep 1→5% / 2→50% / 3→100%；step 2 时环中央显示 'Xs' 而非百分比。
 */
import { render, screen } from '@testing-library/react';
import { ProgressIndicator } from '../../src/components/ProgressIndicator';

describe('ProgressIndicator (clean-minimal)', () => {
  it('renders all three step labels', () => {
    render(<ProgressIndicator currentStep={2} elapsedMs={5000} />);
    expect(screen.getByText('拍照已就绪')).toBeInTheDocument();
    expect(screen.getByText('AI 识别中')).toBeInTheDocument();
    expect(screen.getByText('报告生成中')).toBeInTheDocument();
  });

  it('shows ✓ for done step + zero-padded number for active/pending', () => {
    const { container } = render(<ProgressIndicator currentStep={2} elapsedMs={0} />);
    // step 1 (done) shows ✓
    const done = container.querySelector('[data-state="done"]');
    expect(done?.textContent).toContain('✓');
    // step 2/3 show 02 / 03
    expect(screen.getByText('02')).toBeInTheDocument();
    expect(screen.getByText('03')).toBeInTheDocument();
  });

  it('shows elapsed seconds in the ring during step 2', () => {
    render(<ProgressIndicator currentStep={2} elapsedMs={5000} />);
    expect(screen.getByText('5s')).toBeInTheDocument();
  });

  it('marks the active step with data-state="active"', () => {
    const { container } = render(<ProgressIndicator currentStep={2} elapsedMs={0} />);
    const active = container.querySelectorAll('[data-state="active"]');
    expect(active.length).toBe(1);
  });

  it('all steps numbered when currentStep=1 (no done yet)', () => {
    render(<ProgressIndicator currentStep={1} />);
    expect(screen.getByText('01')).toBeInTheDocument();
    expect(screen.getByText('02')).toBeInTheDocument();
    expect(screen.getByText('03')).toBeInTheDocument();
  });
});
