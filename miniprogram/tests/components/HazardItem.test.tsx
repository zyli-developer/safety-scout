import { fireEvent, render, screen } from '@testing-library/react';
import { HazardItem } from '../../src/components/HazardItem';
import type { Hazard } from '../../src/types/report';

function makeHazard(overrides: Partial<Hazard> = {}): Hazard {
  return {
    category_code: 'H1',
    category_name: '高处作业',
    description: '高处作业未挂安全带',
    severity: 'high',
    regulation: 'GB 50656-2011 §3.2',
    suggestion: '立即停工配发安全带',
    ...overrides,
  };
}

describe('HazardItem', () => {
  it('renders index as zero-padded 2-digit', () => {
    render(<HazardItem hazard={makeHazard()} index={3} />);
    expect(screen.getByText('03')).toBeInTheDocument();
  });

  it('shows category, severity label, description and code/regulation', () => {
    render(<HazardItem hazard={makeHazard()} index={1} />);
    expect(screen.getByText('高处作业')).toBeInTheDocument();
    expect(screen.getByText('高风险')).toBeInTheDocument();
    expect(screen.getByText('高处作业未挂安全带')).toBeInTheDocument();
    expect(screen.getByText('H1')).toBeInTheDocument();
    expect(screen.getByText('GB 50656-2011 §3.2')).toBeInTheDocument();
  });

  it('omits regulation when empty', () => {
    render(<HazardItem hazard={makeHazard({ regulation: '' })} index={1} />);
    expect(screen.queryByText(/§/)).not.toBeInTheDocument();
  });

  it('renders 整改建议 by default and hides on showFix=false', () => {
    // 2026-05-24 B5: 文案从 "整改建议" → "整改建议 · " 前缀（与 mockup .suggestion-callout 一致）
    const { rerender } = render(<HazardItem hazard={makeHazard()} index={1} />);
    expect(screen.getByText(/整改建议/)).toBeInTheDocument();
    rerender(<HazardItem hazard={makeHazard()} index={1} showFix={false} />);
    expect(screen.queryByText(/整改建议/)).not.toBeInTheDocument();
  });

  it('fires onAction when right-side chevron clicked', () => {
    const onAction = jest.fn();
    const { container } = render(
      <HazardItem hazard={makeHazard()} index={1} onAction={onAction} />,
    );
    const action = container.querySelector('[role="button"]') as HTMLElement;
    expect(action).not.toBeNull();
    fireEvent.click(action);
    expect(onAction).toHaveBeenCalledTimes(1);
  });
});
