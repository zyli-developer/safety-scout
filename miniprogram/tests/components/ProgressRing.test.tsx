import { render, screen } from '@testing-library/react';
import { ProgressRing } from '../../src/components/ProgressRing';

describe('ProgressRing', () => {
  it('renders SVG with two circles', () => {
    const { container } = render(<ProgressRing pct={50} />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(container.querySelectorAll('svg circle').length).toBe(2);
  });

  it('renders label text', () => {
    render(<ProgressRing pct={63} label="63%" />);
    expect(screen.getByText('63%')).toBeInTheDocument();
  });

  it('clamps pct to [0,100] via data-pct', () => {
    const { container } = render(<ProgressRing pct={150} />);
    const root = container.firstChild as HTMLElement;
    expect(root.getAttribute('data-pct')).toBe('100');
  });
});
