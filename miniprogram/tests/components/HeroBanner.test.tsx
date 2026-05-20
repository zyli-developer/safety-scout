/**
 * 单元测试：HeroBanner —— intro / metric 两种模式。
 *
 * 验收要点：
 * - intro: 渲染 title + subtitle + icon
 * - metric: 渲染 "{count} 项隐患" + meta；ring 元素有 severity 颜色
 *
 * styles.X 在 jest 里通过 styleMock 是 undefined，因此走 role / text / data-* 断言。
 */
import { render, screen } from '@testing-library/react';
import { HeroBanner } from '../../src/components/HeroBanner';
import { SEVERITY_COLOR } from '../../src/utils/severity';

function hexToRgb(hex: string): string {
  const m = hex.replace('#', '').match(/.{2}/g);
  if (!m) return hex;
  return `rgb(${parseInt(m[0], 16)}, ${parseInt(m[1], 16)}, ${parseInt(m[2], 16)})`;
}

describe('HeroBanner', () => {
  it('intro mode renders title, subtitle, and icon', () => {
    const { container } = render(
      <HeroBanner
        mode="intro"
        icon="helmet"
        title="工地隐患识别"
        subtitle="拍一张，AI 30 秒出报告"
      />,
    );
    expect(screen.getByText('工地隐患识别')).toBeInTheDocument();
    expect(screen.getByText('拍一张，AI 30 秒出报告')).toBeInTheDocument();
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('metric mode renders count and meta', () => {
    render(
      <HeroBanner mode="metric" severity="medium" count={3} meta="中风险 · 2 分钟前" />,
    );
    expect(screen.getByText('3 项隐患')).toBeInTheDocument();
    expect(screen.getByText('中风险 · 2 分钟前')).toBeInTheDocument();
  });

  it('metric mode applies severity color on ring element', () => {
    const { container } = render(
      <HeroBanner mode="metric" severity="high" count={5} meta="高风险 · 刚刚" />,
    );
    const ring = container.querySelector('[data-severity="high"]') as HTMLElement;
    expect(ring).not.toBeNull();
    const expectedHex = SEVERITY_COLOR.high.toLowerCase();
    const expectedRgb = hexToRgb(expectedHex);
    const actual = ring.style.borderColor.toLowerCase();
    expect([expectedHex, expectedRgb]).toContain(actual);
  });
});
