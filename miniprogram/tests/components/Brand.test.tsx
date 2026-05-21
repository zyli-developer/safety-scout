import { render, screen } from '@testing-library/react';
import { Brand } from '../../src/components/Brand';

describe('Brand', () => {
  it('renders mark + wordmark', () => {
    render(<Brand />);
    expect(screen.getByText('Safety Scout')).toBeInTheDocument();
    expect(screen.getByText('S')).toBeInTheDocument();
  });

  it('size=lg adds lg modifier class', () => {
    const { container } = render(<Brand size="lg" />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toMatch(/lg/);
  });
});
