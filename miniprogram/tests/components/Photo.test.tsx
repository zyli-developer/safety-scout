import { render, screen } from '@testing-library/react';
import { Photo } from '../../src/components/Photo';

describe('Photo', () => {
  it('renders <img> with src', () => {
    const { container } = render(<Photo src="https://example.com/x.jpg" alt="site" />);
    const img = container.querySelector('img');
    expect(img).not.toBeNull();
    expect(img?.getAttribute('src')).toBe('https://example.com/x.jpg');
  });

  it('renders meta badge when provided', () => {
    render(<Photo src="x.jpg" meta="上次巡检 · 12 分钟前" />);
    expect(screen.getByText('上次巡检 · 12 分钟前')).toBeInTheDocument();
  });

  it('uses height in style when provided', () => {
    const { container } = render(<Photo src="x.jpg" height={300} />);
    const root = container.firstChild as HTMLElement;
    expect(root.style.height).toBe('300px');
  });

  it('uses aspect-ratio when only ratio provided', () => {
    const { container } = render(<Photo src="x.jpg" ratio="4/3" />);
    const root = container.firstChild as HTMLElement;
    expect(root.style.aspectRatio).toBe('4 / 3');
  });

  it('empty src renders no <img> (avoids broken-image icon)', () => {
    const { container } = render(<Photo src="" ratio="4/3" meta="占位" />);
    expect(container.querySelector('img')).toBeNull();
    // meta still rendered — Photo can serve as labeled placeholder
    expect(container.textContent).toContain('占位');
  });
});
