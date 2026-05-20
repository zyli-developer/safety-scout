/**
 * 单元测试：PlainWarningCard.
 *
 * 验收要点：
 * - 渲染传入文案 + 对应 severity 的中文标签
 * - 卡片上能找到带 severity 颜色的 inline background（accent bar / 主体卡 / 任何 data-severity 元素）
 *
 * 不写死 hex —— SEVERITY_COLOR 改动（如 iOS 风调色）时测试自动跟随。
 */
import { render, screen } from '@testing-library/react';
import { PlainWarningCard } from '../../src/components/PlainWarningCard';
import { SEVERITY_COLOR } from '../../src/utils/severity';

function hexToRgb(hex: string): string {
  const m = hex.replace('#', '').match(/.{2}/g);
  if (!m) return hex;
  return `rgb(${parseInt(m[0], 16)}, ${parseInt(m[1], 16)}, ${parseInt(m[2], 16)})`;
}

describe('PlainWarningCard', () => {
  it('renders text + severity label', () => {
    render(<PlainWarningCard text="工地很危险" severity="high" />);
    expect(screen.getByText('工地很危险')).toBeInTheDocument();
    expect(screen.getByText('高风险')).toBeInTheDocument();
  });

  it('applies severity color as inline background on data-severity element', () => {
    const { container } = render(
      <PlainWarningCard text="工地很危险" severity="high" />,
    );
    const el = container.querySelector('[data-severity="high"]') as HTMLElement;
    expect(el).not.toBeNull();
    const bg = el.style.backgroundColor.toLowerCase();
    const expectedHex = SEVERITY_COLOR.high.toLowerCase();
    const expectedRgb = hexToRgb(expectedHex);
    // jsdom 会把 hex 规范化为 rgb()，两种形式都接
    expect([expectedHex, expectedRgb]).toContain(bg);
  });
});
