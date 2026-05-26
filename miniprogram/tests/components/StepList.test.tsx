import { render, screen } from '@testing-library/react';
import { StepList } from '../../src/components/StepList';

describe('StepList', () => {
  const steps = ['上传照片', 'AI 分析', '报告就绪'];

  it('marks earlier steps as done, current as active, later as pending', () => {
    const { container } = render(<StepList steps={steps} currentStep={2} />);
    const items = container.querySelectorAll('[data-state]');
    expect(items[0].getAttribute('data-state')).toBe('done');
    expect(items[1].getAttribute('data-state')).toBe('active');
    expect(items[2].getAttribute('data-state')).toBe('pending');
  });

  it('done step renders ✓ instead of number', () => {
    const { container } = render(<StepList steps={steps} currentStep={3} />);
    const items = container.querySelectorAll('[data-state="done"]');
    expect(items.length).toBe(2);
    // first done step shows ✓
    expect(items[0].textContent).toContain('✓');
  });

  it('renders all step labels', () => {
    render(<StepList steps={steps} currentStep={1} />);
    for (const s of steps) {
      expect(screen.getByText(s)).toBeInTheDocument();
    }
  });
});
