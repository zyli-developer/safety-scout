import { render, screen } from '@testing-library/react';
import { Stat } from '../../src/components/Stat';

describe('Stat', () => {
  it('renders num + label', () => {
    render(<Stat num={12} label="今日巡检" />);
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('今日巡检')).toBeInTheDocument();
  });

  it('applies tone class', () => {
    const { container } = render(<Stat num={3} label="高风险" tone="high" />);
    const numEl = container.querySelector('span');
    expect(numEl?.className).toMatch(/high/);
  });
});
