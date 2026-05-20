/**
 * 单元测试：Icon —— 集中验证图标集枚举 + helmet 新增。
 * 不渲染断言 path 字符串（dangerouslySetInnerHTML 走的是 innerHTML），
 * 只断言 IconName 联合类型可被使用 + 组件不抛错。
 */
import { render } from '@testing-library/react';
import { Icon } from '../../src/components/Icon';

describe('Icon', () => {
  it('renders helmet without crashing', () => {
    const { container } = render(<Icon name="helmet" size={56} color="#007AFF" />);
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('respects size prop on the wrapper', () => {
    const { container } = render(<Icon name="helmet" size={56} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.width).toBe('56px');
    expect(wrapper.style.height).toBe('56px');
  });

  // 守护：path 字符串被误删 → svg 仍渲染但 d="" 不可见。断言 d 以 M 开头即可。
  it('embeds a non-empty path for helmet', () => {
    const { container } = render(<Icon name="helmet" size={56} />);
    const path = container.querySelector('svg path');
    expect(path?.getAttribute('d')).toMatch(/^M/);
  });
});
