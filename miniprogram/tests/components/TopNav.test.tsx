import { fireEvent, render, screen } from '@testing-library/react';
import { TopNav } from '../../src/components/TopNav';

describe('TopNav', () => {
  it('renders only the inspect / reports tabs (no team / setting)', () => {
    render(<TopNav />);
    for (const label of ['巡检', '报告']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.queryByText('班组')).toBeNull();
    expect(screen.queryByText('设置')).toBeNull();
  });

  it('marks activeTab with aria-current=page by default', () => {
    const { container } = render(<TopNav activeTab="reports" />);
    const active = container.querySelector('[aria-current="page"]');
    expect(active?.getAttribute('data-tab')).toBe('reports');
  });

  it('marks activeTab with aria-current=step when in a step flow', () => {
    // critique P0 修复：polling 页等"流程中"场景，nav 链接指向其他 page，aria-current 应为 "step"
    const { container } = render(<TopNav activeTab="inspect" ariaCurrent="step" />);
    const step = container.querySelector('[aria-current="step"]');
    expect(step?.getAttribute('data-tab')).toBe('inspect');
    expect(container.querySelector('[aria-current="page"]')).toBeNull();
  });

  it('fires onTabChange with tab id', () => {
    const onTabChange = jest.fn();
    const { container } = render(<TopNav onTabChange={onTabChange} />);
    const reportsTab = container.querySelector('[data-tab="reports"]') as HTMLElement;
    fireEvent.click(reportsTab);
    expect(onTabChange).toHaveBeenCalledWith('reports');
  });

  it('renders Brand + avatar initial', () => {
    render(<TopNav user="王立" />);
    expect(screen.getByText('Safety Scout')).toBeInTheDocument();
    expect(screen.getByText('王')).toBeInTheDocument();
  });

  it('renders brand sub "/ 工地安全巡检" inside Brand', () => {
    render(<TopNav />);
    expect(screen.getByText('/ 工地安全巡检')).toBeInTheDocument();
  });

  it('no longer renders search icon button (removed in 2026-05-24 mockup alignment)', () => {
    render(<TopNav />);
    expect(screen.queryByRole('button', { name: '搜索' })).toBeNull();
  });
});
