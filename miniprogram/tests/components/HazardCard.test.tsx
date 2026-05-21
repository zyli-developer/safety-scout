/**
 * HazardCard (dossier) —— 编号 + severity 条带 + 三栏 (现象/依据/整改)。
 */
import { render, screen } from '@testing-library/react';
import { HazardCard } from '../../src/components/HazardCard';
import { SEVERITY_COLOR, SEVERITY_TEXT_ON_TINT } from '../../src/utils/severity';
import type { Hazard } from '../../src/types/report';

function makeHazard(overrides: Partial<Hazard> = {}): Hazard {
  return {
    category_code: 'H1',
    category_name: '高处作业',
    description: '高处作业未挂安全带',
    severity: 'high',
    regulation: 'GB 50656-2011 §3.2',
    suggestion: '立即停工配发安全带',
    ...overrides,
  };
}

describe('HazardCard (dossier)', () => {
  it('renders numbered identifier "01" with severity tag "HIGH"', () => {
    render(<HazardCard hazard={makeHazard()} index={1} total={3} />);
    expect(screen.getByText('01')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
  });

  it('renders 现象 / 依据 / 整改 three labeled rows', () => {
    render(<HazardCard hazard={makeHazard()} index={1} total={3} />);
    expect(screen.getByText('现象')).toBeInTheDocument();
    expect(screen.getByText('依据')).toBeInTheDocument();
    expect(screen.getByText('整改')).toBeInTheDocument();
    expect(screen.getByText('高处作业未挂安全带')).toBeInTheDocument();
    expect(screen.getByText('GB 50656-2011 §3.2')).toBeInTheDocument();
    expect(screen.getByText('立即停工配发安全带')).toBeInTheDocument();
  });

  it('omits 依据 row when regulation is empty', () => {
    render(<HazardCard hazard={makeHazard({ regulation: '' })} index={1} total={3} />);
    expect(screen.queryByText('依据')).not.toBeInTheDocument();
  });

  it('severity stripe element carries severity color in background', () => {
    const { container } = render(<HazardCard hazard={makeHazard()} index={1} total={3} />);
    const stripe = container.querySelector('[data-severity-stripe="high"]') as HTMLElement;
    expect(stripe).not.toBeNull();
    // jsdom may normalize hex → rgb; tolerant assertion: look for either form
    const expectedHex = SEVERITY_COLOR.high.toLowerCase();
    const expectedRgb = `rgb(${parseInt(expectedHex.slice(1, 3), 16)}, ${parseInt(expectedHex.slice(3, 5), 16)}, ${parseInt(expectedHex.slice(5, 7), 16)})`;
    const bg = stripe.style.backgroundColor.toLowerCase();
    expect([expectedHex, expectedRgb]).toContain(bg);
  });

  it('severity tag text uses SEVERITY_TEXT_ON_TINT (AA-contrast on paper)', () => {
    const { container } = render(<HazardCard hazard={makeHazard({ severity: 'medium' })} index={1} total={3} />);
    const tag = container.querySelector('[data-severity-tag="medium"]') as HTMLElement;
    expect(tag).not.toBeNull();
    const expectedHex = SEVERITY_TEXT_ON_TINT.medium.toLowerCase();
    const expectedRgb = `rgb(${parseInt(expectedHex.slice(1, 3), 16)}, ${parseInt(expectedHex.slice(3, 5), 16)}, ${parseInt(expectedHex.slice(5, 7), 16)})`;
    const color = tag.style.color.toLowerCase();
    expect([expectedHex, expectedRgb]).toContain(color);
  });
});
