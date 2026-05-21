import { fireEvent, render, screen } from '@testing-library/react';
import { Button } from '../../src/components/Button';

describe('Button', () => {
  it('renders children inside non-hero variants', () => {
    render(<Button variant="primary">开始巡检</Button>);
    expect(screen.getByText('开始巡检')).toBeInTheDocument();
  });

  it('fires onTap when interactive', () => {
    const onTap = jest.fn();
    render(<Button variant="primary" onTap={onTap}>X</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onTap).toHaveBeenCalledTimes(1);
  });

  it('does not fire onTap when disabled', () => {
    const onTap = jest.fn();
    render(<Button variant="primary" disabled onTap={onTap}>X</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onTap).not.toHaveBeenCalled();
  });

  it('does not fire onTap when loading', () => {
    const onTap = jest.fn();
    render(<Button variant="primary" loading onTap={onTap}>X</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onTap).not.toHaveBeenCalled();
  });

  it('hero variant renders title + subtitle + icon + arrow', () => {
    const { container } = render(
      <Button
        variant="hero"
        icon="camera"
        title="开始巡检"
        subtitle="拍照·上传·等待报告"
        onTap={() => undefined}
      />,
    );
    expect(screen.getByText('开始巡检')).toBeInTheDocument();
    expect(screen.getByText('拍照·上传·等待报告')).toBeInTheDocument();
    // 1 icon + 1 arrow inside the hero
    expect(container.querySelectorAll('svg').length).toBeGreaterThanOrEqual(2);
  });

  it('block adds full-width modifier', () => {
    const { container } = render(<Button variant="secondary" block>X</Button>);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toMatch(/block/);
  });
});
