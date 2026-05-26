import { render, screen } from '@testing-library/react';
import { Brand } from '../../src/components/Brand';

describe('Brand', () => {
  it('renders wordmark and helmet mark', () => {
    const { container } = render(<Brand />);
    expect(screen.getByText('Safety Scout')).toBeInTheDocument();
    // 2026-05-24：mark 从字母 "S" 升级为 helmet SVG；验 SVG 节点存在
    const svg = container.querySelector('svg');
    expect(svg).toBeTruthy();
  });

  it('renders default sub "/ 工地安全巡检"', () => {
    render(<Brand />);
    expect(screen.getByText('/ 工地安全巡检')).toBeInTheDocument();
  });

  it('hides sub when sub={false}', () => {
    render(<Brand sub={false} />);
    expect(screen.queryByText('/ 工地安全巡检')).toBeNull();
  });

  it('accepts custom sub text', () => {
    render(<Brand sub="/ 自定义" />);
    expect(screen.getByText('/ 自定义')).toBeInTheDocument();
  });

  it('size=lg adds lg modifier class', () => {
    const { container } = render(<Brand size="lg" />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toMatch(/lg/);
  });
});
