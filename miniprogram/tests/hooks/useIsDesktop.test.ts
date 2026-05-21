/**
 * 单元测试：useIsDesktop hook.
 *
 * 验收要点：
 * - h5 环境下读 matchMedia.matches 作为初值
 * - h5 环境下 MQ change 事件触发 state 更新
 * - h5 环境下 unmount 时移除 listener
 * - 非 h5 环境（weapp）直接返回 false，不调用 matchMedia
 */
import { renderHook, act } from '@testing-library/react';

import { useIsDesktop } from '../../src/hooks/useIsDesktop';

interface MqStub {
  matches: boolean;
  addEventListener: jest.Mock;
  removeEventListener: jest.Mock;
  _handler?: (e: { matches: boolean }) => void;
}

function makeMqStub(matches: boolean): MqStub {
  const stub: MqStub = {
    matches,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  };
  stub.addEventListener.mockImplementation((evt: string, h: (e: { matches: boolean }) => void) => {
    if (evt === 'change') stub._handler = h;
  });
  return stub;
}

describe('useIsDesktop', () => {
  let originalTaroEnv: string | undefined;

  beforeEach(() => {
    originalTaroEnv = process.env.TARO_ENV;
    process.env.TARO_ENV = 'h5';
  });

  afterEach(() => {
    process.env.TARO_ENV = originalTaroEnv;
  });

  it('returns matchMedia.matches at mount in h5', () => {
    const mq = makeMqStub(true);
    window.matchMedia = jest.fn().mockReturnValue(mq) as unknown as typeof window.matchMedia;
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(true);
  });

  it('returns false at mount when matchMedia is false', () => {
    const mq = makeMqStub(false);
    window.matchMedia = jest.fn().mockReturnValue(mq) as unknown as typeof window.matchMedia;
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(false);
  });

  it('updates state when MediaQueryList emits change', () => {
    const mq = makeMqStub(false);
    window.matchMedia = jest.fn().mockReturnValue(mq) as unknown as typeof window.matchMedia;
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(false);

    act(() => {
      mq._handler?.({ matches: true });
    });
    expect(result.current).toBe(true);
  });

  it('removes the change listener on unmount', () => {
    const mq = makeMqStub(false);
    window.matchMedia = jest.fn().mockReturnValue(mq) as unknown as typeof window.matchMedia;
    const { unmount } = renderHook(() => useIsDesktop());
    unmount();
    expect(mq.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('returns false in weapp without calling matchMedia', () => {
    process.env.TARO_ENV = 'weapp';
    const spy = jest.fn();
    window.matchMedia = spy as unknown as typeof window.matchMedia;
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(false);
    expect(spy).not.toHaveBeenCalled();
  });
});
