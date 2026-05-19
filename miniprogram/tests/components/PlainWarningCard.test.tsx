/**
 * 单元测试：PlainWarningCard.
 *
 * 验收要点：
 * - 渲染传入文案 + 对应 severity 的中文标签
 * - inline style 应用 severity 颜色（high → #E63946）
 *
 * 颜色断言走 inline style，因为 SCSS module className 在测试里是 undefined。
 */
import { render, screen } from '@testing-library/react';
import { PlainWarningCard } from '../../src/components/PlainWarningCard';

describe('PlainWarningCard', () => {
  it('renders text + severity label', () => {
    render(<PlainWarningCard text="工地很危险" severity="high" />);
    expect(screen.getByText('工地很危险')).toBeInTheDocument();
    expect(screen.getByText('高风险')).toBeInTheDocument();
  });

  it('applies severity color as inline background', () => {
    const { container } = render(
      <PlainWarningCard text="工地很危险" severity="high" />,
    );
    const card = container.querySelector('[data-severity="high"]') as HTMLElement;
    expect(card).not.toBeNull();
    // jsdom 会把 #E63946 规范化为 rgb()，所以只断言其中之一
    const bg = card.style.backgroundColor.toLowerCase();
    expect(bg === '#e63946' || bg === 'rgb(230, 57, 70)').toBe(true);
  });
});
