import { fireEvent, render, screen } from '@testing-library/react';

import { EmptyState } from '../../src/components/EmptyState';

describe('EmptyState', () => {
  it('renders empty variant with default eyebrow + title', () => {
    render(<EmptyState variant="empty" />);
    expect(screen.getByText('还没拍过照片')).toBeInTheDocument();
    expect(screen.getByText(/拍下第一张现场照片/)).toBeInTheDocument();
  });

  it('renders blurry variant with default title "这张照片有点糊"', () => {
    // 2026-05-22 critique P1 新增第 4 态
    render(<EmptyState variant="blurry" />);
    expect(screen.getByText('这张照片有点糊')).toBeInTheDocument();
  });

  it('renders rejected variant', () => {
    render(<EmptyState variant="rejected" />);
    expect(screen.getByText(/这张照片似乎不是工地现场/)).toBeInTheDocument();
  });

  it('renders network variant', () => {
    render(<EmptyState variant="network" />);
    expect(screen.getByText(/上传超时/)).toBeInTheDocument();
  });

  it('overrides title and sub when props provided', () => {
    render(<EmptyState variant="rejected" title="自定义标题" sub="自定义副本" />);
    expect(screen.getByText('自定义标题')).toBeInTheDocument();
    expect(screen.getByText('自定义副本')).toBeInTheDocument();
  });

  it('renders primary + ghost actions and fires callbacks', () => {
    const onPrimary = jest.fn();
    const onGhost = jest.fn();
    render(
      <EmptyState
        variant="blurry"
        primaryAction={{ label: '重拍', onTap: onPrimary }}
        ghostAction={{ label: '强制分析 · 结果将标记低置信度', onTap: onGhost }}
      />,
    );
    fireEvent.click(screen.getByText('重拍'));
    expect(onPrimary).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText('强制分析 · 结果将标记低置信度'));
    expect(onGhost).toHaveBeenCalledTimes(1);
  });

  it('renders details cells when provided', () => {
    render(
      <EmptyState
        variant="blurry"
        details={[
          { label: '清晰度评分', value: '0.31 · 偏低' },
          { label: '主要原因', value: '手部抖动 · 边缘失焦' },
        ]}
      />,
    );
    expect(screen.getByText('0.31 · 偏低')).toBeInTheDocument();
    expect(screen.getByText('手部抖动 · 边缘失焦')).toBeInTheDocument();
  });

  it('renders tips when provided', () => {
    render(
      <EmptyState
        variant="blurry"
        tips={{
          title: '下一张这样拍更清楚',
          items: ['双手持机', '停 1 秒再按快门'],
        }}
      />,
    );
    expect(screen.getByText('下一张这样拍更清楚')).toBeInTheDocument();
    expect(screen.getByText('双手持机')).toBeInTheDocument();
  });

  it('sets data-state attribute matching variant', () => {
    const { container } = render(<EmptyState variant="network" />);
    expect(container.querySelector('[data-state="network"]')).toBeTruthy();
  });
});
