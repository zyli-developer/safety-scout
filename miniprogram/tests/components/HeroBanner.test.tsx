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

// NOTE: `SEVERITY_COLOR` import + `hexToRgb` helper 由 Task 4 加回 ——
// tsconfig 启用 noUnusedLocals，预先 stage 会让 ts-jest 编不过。

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
});
