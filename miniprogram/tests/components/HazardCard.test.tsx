/**
 * HazardCard (clean-minimal) —— 现在是 HazardItem 的薄壳，渲染列表 row 形态。
 * 旧 dossier 三栏（现象/依据/整改）+ stripe 已废弃，下面断言对齐新视觉。
 */
import { render, screen } from '@testing-library/react';
import { HazardCard } from '../../src/components/HazardCard';
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

describe('HazardCard (clean-minimal wrapper)', () => {
  it('renders zero-padded 2-digit index', () => {
    render(<HazardCard hazard={makeHazard()} index={1} total={3} />);
    expect(screen.getByText('01')).toBeInTheDocument();
  });

  it('defaults index to 01 when omitted', () => {
    render(<HazardCard hazard={makeHazard()} />);
    expect(screen.getByText('01')).toBeInTheDocument();
  });

  it('renders category_name, severity label, description, code and regulation', () => {
    render(<HazardCard hazard={makeHazard()} index={1} total={3} />);
    expect(screen.getByText('高处作业')).toBeInTheDocument();
    expect(screen.getByText('高风险')).toBeInTheDocument();
    expect(screen.getByText('高处作业未挂安全带')).toBeInTheDocument();
    expect(screen.getByText('H1')).toBeInTheDocument();
    expect(screen.getByText('GB 50656-2011 §3.2')).toBeInTheDocument();
  });

  it('renders the 整改建议 block with suggestion text', () => {
    render(<HazardCard hazard={makeHazard()} index={1} />);
    expect(screen.getByText('整改建议')).toBeInTheDocument();
    expect(screen.getByText('立即停工配发安全带')).toBeInTheDocument();
  });

  it('omits regulation when empty (no dot separator artifact)', () => {
    render(<HazardCard hazard={makeHazard({ regulation: '' })} index={1} />);
    expect(screen.queryByText(/§/)).not.toBeInTheDocument();
  });
});
