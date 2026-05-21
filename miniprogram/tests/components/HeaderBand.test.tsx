/**
 * HeaderBand —— 顶部铭牌，每页都有。
 * 不再有 intro / metric 两种 mode；只有一个统一形态：
 *   SAFETY SCOUT            NO.xxx (optional)
 *   工地安全巡检系统          subtitle (optional, e.g. timestamp)
 *   ─────────────────────  (1px charcoal rule)
 */
import { render, screen } from '@testing-library/react';
import { HeaderBand } from '../../src/components/HeaderBand';

describe('HeaderBand', () => {
  it('renders the brand mark every time', () => {
    render(<HeaderBand />);
    expect(screen.getByText('SAFETY SCOUT')).toBeInTheDocument();
    expect(screen.getByText('工地安全巡检系统')).toBeInTheDocument();
  });

  it('renders optional identifier (e.g. NO.2026-05-20-0001) when provided', () => {
    render(<HeaderBand identifier="NO.2026-05-20-0001" />);
    expect(screen.getByText('NO.2026-05-20-0001')).toBeInTheDocument();
  });

  it('renders optional subtitle (e.g. timestamp) when provided', () => {
    render(<HeaderBand subtitle="2026·05·20  14:32" />);
    // RTL normalizes whitespace in textContent (collapses runs to single space)
    // before comparing to the query; match with a regex tolerant of that.
    expect(screen.getByText(/2026·05·20\s+14:32/)).toBeInTheDocument();
  });

  it('omits identifier line when not provided', () => {
    render(<HeaderBand />);
    expect(screen.queryByText(/^NO\./)).not.toBeInTheDocument();
  });
});
