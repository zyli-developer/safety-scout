/**
 * 单元测试：HazardCard.
 *
 * 验收要点：
 * - category_name / description / suggestion 都渲染
 * - regulation 默认折叠（不在 DOM）；点击展开按钮后显示
 * - regulation 为空字符串时，展开/收起按钮不出现
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { HazardCard } from '../../src/components/HazardCard';
import type { Hazard } from '../../src/types/report';

const baseHazard: Hazard = {
  category_code: 'H1',
  category_name: '高处作业',
  description: '工人未佩戴安全带',
  severity: 'high',
  regulation: 'JGJ59-2011 第 4.2.3 条',
  suggestion: '立即停工，配齐安全带后再施工',
};

describe('HazardCard', () => {
  it('renders category_name + description + suggestion', () => {
    render(<HazardCard hazard={baseHazard} />);
    expect(screen.getByText('高处作业')).toBeInTheDocument();
    expect(screen.getByText('工人未佩戴安全带')).toBeInTheDocument();
    expect(screen.getByText('立即停工，配齐安全带后再施工')).toBeInTheDocument();
  });

  it('regulation hidden by default, shown after click', () => {
    render(<HazardCard hazard={baseHazard} />);
    // 默认未展开
    expect(screen.queryByText('JGJ59-2011 第 4.2.3 条')).not.toBeInTheDocument();
    expect(screen.getByText('展开规范条款')).toBeInTheDocument();

    fireEvent.click(screen.getByText('展开规范条款'));
    expect(screen.getByText('JGJ59-2011 第 4.2.3 条')).toBeInTheDocument();
    expect(screen.getByText('收起规范条款')).toBeInTheDocument();
  });

  it('regulation toggle absent when regulation is empty string', () => {
    const hazard: Hazard = { ...baseHazard, regulation: '' };
    render(<HazardCard hazard={hazard} />);
    expect(screen.queryByText('展开规范条款')).not.toBeInTheDocument();
    expect(screen.queryByText('收起规范条款')).not.toBeInTheDocument();
  });
});
