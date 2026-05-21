import { render, screen } from '@testing-library/react';
import { SeverityPill } from '../../src/components/SeverityPill';

describe('SeverityPill', () => {
  it('renders high label by default (soft)', () => {
    const { container } = render(<SeverityPill level="high" />);
    expect(screen.getByText('高风险')).toBeInTheDocument();
    expect(container.querySelector('[data-sev="high"][data-variant="soft"]')).not.toBeNull();
  });

  it('solid variant strips the dot and uses solid attribute', () => {
    const { container } = render(<SeverityPill level="medium" variant="solid" />);
    expect(container.querySelector('[data-variant="solid"]')).not.toBeNull();
  });

  it('appends count when provided', () => {
    render(<SeverityPill level="low" count={3} />);
    expect(screen.getByText('低风险 · 3')).toBeInTheDocument();
  });
});
