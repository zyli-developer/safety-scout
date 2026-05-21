/**
 * 单元测试：BigButton.
 *
 * 验收要点：
 * - text 渲染
 * - 点击触发 onTap（仅当 isInteractive=true）
 * - loading 状态下文案改为 "上传中..." 且不响应点击
 * - disabled 状态下不响应点击
 *
 * 不断言 className —— jest 的 styleMock 把 SCSS modules 映射为 `{}`，
 * `styles.button` 在测试运行时是 undefined，因此用文案 + role + aria 断言。
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { BigButton } from '../../src/components/BigButton';

describe('BigButton', () => {
  it('renders provided text', () => {
    render(<BigButton text="拍隐患" onTap={() => undefined} />);
    expect(screen.getByText('拍隐患')).toBeInTheDocument();
  });

  it('calls onTap when clicked', () => {
    const fn = jest.fn();
    render(<BigButton text="拍隐患" onTap={fn} />);
    fireEvent.click(screen.getByRole('button'));
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('does not call onTap when loading or disabled', () => {
    const fn = jest.fn();
    const { rerender } = render(<BigButton text="拍隐患" onTap={fn} loading />);
    fireEvent.click(screen.getByRole('button'));
    expect(fn).not.toHaveBeenCalled();

    rerender(<BigButton text="拍隐患" onTap={fn} disabled />);
    fireEvent.click(screen.getByRole('button'));
    expect(fn).not.toHaveBeenCalled();
  });

  it('shows "处理中" when loading', () => {
    render(<BigButton text="拍隐患" onTap={() => undefined} loading />);
    expect(screen.getByText('处理中')).toBeInTheDocument();
    expect(screen.queryByText('拍隐患')).not.toBeInTheDocument();
  });

  it('renders both Chinese label and Latin subtitle', () => {
    render(<BigButton text="拍摄现场照片" subtitle="CAPTURE INSPECTION PHOTO" onTap={() => undefined} />);
    expect(screen.getByText('拍摄现场照片')).toBeInTheDocument();
    expect(screen.getByText('CAPTURE INSPECTION PHOTO')).toBeInTheDocument();
  });

  it('renders prefix glyph if provided', () => {
    const { container } = render(
      <BigButton text="拍摄现场照片" subtitle="CAPTURE" prefixGlyph="plus-square" onTap={() => undefined} />,
    );
    expect(container.querySelector('svg')).not.toBeNull();
  });
});
