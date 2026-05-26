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

  // 2026-05-25 重大事故隐患（建质规〔2024〕5号）路径
  describe('重大隐患 badge + 判定依据', () => {
    const MAJOR_BASIS = '《房屋市政工程生产安全重大事故隐患判定标准（2024版）》建质规〔2024〕5号 第十一条';

    it('hides badge by default when is_major is undefined (backward compat)', () => {
      render(<HazardItem hazard={makeHazard()} index={1} />);
      expect(screen.queryByText('重大隐患')).toBeNull();
      expect(screen.queryByText('判定依据 · ')).toBeNull();
    });

    it('hides badge when is_major=false even with non-empty basis (defensive)', () => {
      render(
        <HazardItem
          hazard={makeHazard({ is_major: false, major_basis: MAJOR_BASIS })}
          index={1}
        />,
      );
      expect(screen.queryByText('重大隐患')).toBeNull();
    });

    it('renders red 重大隐患 badge when is_major=true', () => {
      render(
        <HazardItem
          hazard={makeHazard({ is_major: true, major_basis: MAJOR_BASIS })}
          index={1}
        />,
      );
      const badge = screen.getByLabelText('重大事故隐患');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent('重大隐患');
    });

    it('renders 判定依据 row with full major_basis text', () => {
      render(
        <HazardItem
          hazard={makeHazard({ is_major: true, major_basis: MAJOR_BASIS })}
          index={1}
        />,
      );
      expect(screen.getByText(/判定依据/)).toBeInTheDocument();
      expect(screen.getByText(MAJOR_BASIS)).toBeInTheDocument();
    });

    it('omits 判定依据 block when major_basis is empty even if is_major=true', () => {
      // 防御性渲染：模型返回 is_major=true 但漏填 major_basis 时不渲染空白 block
      render(
        <HazardItem
          hazard={makeHazard({ is_major: true, major_basis: '' })}
          index={1}
        />,
      );
      // badge 仍出（is_major 为权威信号），但 basis block 不出
      expect(screen.getByText('重大隐患')).toBeInTheDocument();
      expect(screen.queryByText(/判定依据/)).toBeNull();
    });

    it('sets data-major attribute on row for downstream styling', () => {
      const { container } = render(
        <HazardItem
          hazard={makeHazard({ is_major: true, major_basis: MAJOR_BASIS })}
          index={1}
        />,
      );
      const row = container.querySelector('[data-major="true"]');
      expect(row).not.toBeNull();
    });
  });
});
