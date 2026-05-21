import { fireEvent, render, screen } from '@testing-library/react';
import { TopNav } from '../../src/components/TopNav';

describe('TopNav', () => {
  it('renders all 4 tabs', () => {
    render(<TopNav />);
    for (const label of ['巡检', '报告', '班组', '设置']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('marks activeTab with aria-current=page', () => {
    const { container } = render(<TopNav activeTab="reports" />);
    const active = container.querySelector('[aria-current="page"]');
    expect(active?.getAttribute('data-tab')).toBe('reports');
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
});
