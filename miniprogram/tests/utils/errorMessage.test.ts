/** errorMessage 的单测：已知 code、限频倒计时、未知 code 兜底、非 ApiError 兜底、retry 禁用。 */
import { ApiError } from '../../src/api/client';
import { mapApiError } from '../../src/utils/errorMessage';

describe('utils/errorMessage.mapApiError', () => {
  it('maps known code to specified rule + userMessage', () => {
    const e = new ApiError('INVALID_IMAGE', '图片格式不支持', 400);

    const ui = mapApiError(e);

    expect(ui.display).toBe('toast');
    expect(ui.allowRetry).toBe(true);
    expect(ui.userMessage).toBe('图片格式不支持');
  });

  it('rate-limited carries retryCountdownS=60', () => {
    const e = new ApiError('RATE_LIMITED', '请求过于频繁', 429);

    const ui = mapApiError(e);

    expect(ui.retryCountdownS).toBe(60);
    expect(ui.allowRetry).toBe(true);
    expect(ui.display).toBe('toast');
  });

  it('unknown code falls back to DEFAULT_RULE preserving userMessage', () => {
    const e = new ApiError('NEW_CODE_PHASE_4', '新错误', 599);

    const ui = mapApiError(e);

    expect(ui.display).toBe('toast');
    expect(ui.allowRetry).toBe(true);
    expect(ui.userMessage).toBe('新错误');
    expect(ui.retryCountdownS).toBeUndefined();
  });

  it('non-ApiError input falls back to default + generic message', () => {
    const ui = mapApiError(new Error('oops'));

    expect(ui.display).toBe('toast');
    expect(ui.allowRetry).toBe(true);
    expect(ui.userMessage).toBe('未知错误，请重试');
  });

  it('NOT_FOUND has allowRetry=false', () => {
    const e = new ApiError('NOT_FOUND', '记录不存在', 404);

    const ui = mapApiError(e);

    expect(ui.allowRetry).toBe(false);
    expect(ui.display).toBe('errorView');
    expect(ui.userMessage).toBe('记录不存在');
  });
});
