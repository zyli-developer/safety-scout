/**
 * FeedbackModal 单元测试。
 *
 * 覆盖：
 * - 不渲染：isOpen=false
 * - 有 checkId：两档 kind chip 可见 + 默认 false_positive
 * - 无 checkId：kind chip 不渲染（锁死 missed）
 * - description 空时 submit 按钮禁用
 * - 提交流程：调 submitFeedback、参数对、成功后回调 + 关闭
 * - 提交失败：错误文案显示，modal 不关
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { FeedbackModal } from '../../src/components/FeedbackModal';
import * as api from '../../src/api/inspections';

describe('FeedbackModal', () => {
  let submitSpy: jest.SpyInstance;

  beforeEach(() => {
    submitSpy = jest.spyOn(api, 'submitFeedback').mockResolvedValue({
      feedback_id: 'fb-1',
      inspection_id: 'i-1',
      created_at: '2026-05-26T00:00:00Z',
    });
  });

  afterEach(() => {
    submitSpy.mockRestore();
  });

  it('does not render when isOpen=false', () => {
    const { container } = render(
      <FeedbackModal isOpen={false} onClose={() => {}} inspectionId="i-1" />,
    );
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it('with checkId: renders both kind chips, default 误报', () => {
    render(
      <FeedbackModal isOpen={true} onClose={() => {}} inspectionId="i-1" checkId="B01" />,
    );
    expect(screen.getByText('误报')).toBeInTheDocument();
    expect(screen.getByText('建议不可执行')).toBeInTheDocument();
    // title 包含 check_id
    expect(screen.getByText('反馈 · B01')).toBeInTheDocument();
    // 默认 false_positive 高亮（aria-checked）
    const radios = screen.getAllByRole('radio');
    expect(radios.find((r) => r.getAttribute('aria-checked') === 'true')?.textContent).toBe('误报');
  });

  it('without checkId: kind 行不渲染，锁死 missed', () => {
    const { container } = render(
      <FeedbackModal isOpen={true} onClose={() => {}} inspectionId="i-1" />,
    );
    expect(screen.queryByText('误报')).toBeNull();
    expect(screen.queryByText('建议不可执行')).toBeNull();
    // 找不到 radiogroup
    expect(container.querySelector('[role="radiogroup"]')).toBeNull();
    expect(screen.getByText('反馈：我们漏了什么')).toBeInTheDocument();
  });

  it('submit 按钮空 description 时 aria-disabled=true', () => {
    render(
      <FeedbackModal isOpen={true} onClose={() => {}} inspectionId="i-1" checkId="B01" />,
    );
    const submitBtn = screen.getByText('提交反馈').closest('[role="button"]');
    expect(submitBtn?.getAttribute('aria-disabled')).toBe('true');
  });

  it('happy path：填 description → 提交 → 调 submitFeedback 带正确参数 + 关闭', async () => {
    const onClose = jest.fn();
    const onSuccess = jest.fn();
    render(
      <FeedbackModal
        isOpen={true}
        onClose={onClose}
        onSuccess={onSuccess}
        inspectionId="i-1"
        checkId="B01"
      />,
    );

    const textarea = screen.getByLabelText('反馈描述') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '工人其实戴了安全带，模型没看到' } });

    fireEvent.click(screen.getByText('提交反馈'));

    await waitFor(() => {
      expect(submitSpy).toHaveBeenCalledWith('i-1', {
        kind: 'false_positive',
        check_id: 'B01',
        description: '工人其实戴了安全带，模型没看到',
      });
    });
    expect(onSuccess).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('missed mode：提交时 body 不含 check_id', async () => {
    render(
      <FeedbackModal
        isOpen={true}
        onClose={() => {}}
        inspectionId="i-1"
      />,
    );
    fireEvent.change(screen.getByLabelText('反馈描述'), {
      target: { value: '右下角钢筋未捆扎' },
    });
    fireEvent.click(screen.getByText('提交反馈'));
    await waitFor(() => expect(submitSpy).toHaveBeenCalledTimes(1));
    const [, body] = submitSpy.mock.calls[0];
    expect(body).toEqual({
      kind: 'missed',
      description: '右下角钢筋未捆扎',
    });
    expect('check_id' in body).toBe(false);
  });

  it('切 kind 到 bad_action：body 用新 kind', async () => {
    render(
      <FeedbackModal isOpen={true} onClose={() => {}} inspectionId="i-1" checkId="B01" />,
    );
    fireEvent.click(screen.getByText('建议不可执行'));
    fireEvent.change(screen.getByLabelText('反馈描述'), {
      target: { value: '现场条件不允许执行' },
    });
    fireEvent.click(screen.getByText('提交反馈'));
    await waitFor(() => expect(submitSpy).toHaveBeenCalledTimes(1));
    expect(submitSpy.mock.calls[0][1].kind).toBe('bad_action');
  });

  it('提交失败：错误文案出现，modal 不关', async () => {
    submitSpy.mockRejectedValueOnce(
      Object.assign(new Error('boom'), {
        name: 'ApiError',
        code: 'NETWORK_ERROR',
        userMessage: '网络异常，请检查后重试',
        statusCode: 0,
      }),
    );
    const onClose = jest.fn();
    render(
      <FeedbackModal isOpen={true} onClose={onClose} inspectionId="i-1" checkId="B01" />,
    );
    fireEvent.change(screen.getByLabelText('反馈描述'), { target: { value: '测试' } });
    fireEvent.click(screen.getByText('提交反馈'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('字数 counter 实时显示', () => {
    render(<FeedbackModal isOpen={true} onClose={() => {}} inspectionId="i-1" />);
    expect(screen.getByText('0 / 500')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('反馈描述'), {
      target: { value: 'abc' },
    });
    expect(screen.getByText('3 / 500')).toBeInTheDocument();
  });
});
