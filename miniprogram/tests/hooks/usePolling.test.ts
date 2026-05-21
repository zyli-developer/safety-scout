/**
 * 单元测试：usePolling.
 *
 * 关键技巧：tick 是 async（await fetch()），所以 advanceTimersByTime 之后必须
 * 在同一个 act 块里 flush 微任务队列。下面 advance() 帮助函数把这两步合一。
 */
import { act, renderHook } from '@testing-library/react';
import { usePolling } from '../../src/hooks/usePolling';

async function advance(ms: number) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
    // 多刷几次 microtask，覆盖 tick 内部多层 await + setState 触发的更新。
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe('usePolling', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it('polls at interval until stopWhen returns true', async () => {
    let counter = 0;
    const fetchFn = jest.fn().mockImplementation(() => {
      counter += 1;
      return Promise.resolve(counter);
    });

    renderHook(() =>
      usePolling<number>({
        fetch: fetchFn,
        intervalMs: 100,
        timeoutMs: 10_000,
        stopWhen: (r) => r >= 3,
      }),
    );

    expect(fetchFn).toHaveBeenCalledTimes(0); // setInterval 不会立即执行
    await advance(100);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    await advance(100);
    expect(fetchFn).toHaveBeenCalledTimes(2);
    await advance(100);
    expect(fetchFn).toHaveBeenCalledTimes(3);
    // 第 3 次 stopWhen 返 true，interval 已清；再 advance 不应再调
    await advance(500);
    expect(fetchFn).toHaveBeenCalledTimes(3);
  });

  it('sets error and stops polling on fetch rejection', async () => {
    const fetchFn = jest
      .fn()
      .mockRejectedValue(new Error('boom'));

    const { result } = renderHook(() =>
      usePolling<number>({
        fetch: fetchFn,
        intervalMs: 100,
        timeoutMs: 10_000,
        stopWhen: () => false,
      }),
    );

    await advance(100);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe('boom');

    await advance(500);
    expect(fetchFn).toHaveBeenCalledTimes(1); // 不再调
  });

  it('times out and sets isTimedOut after timeoutMs', async () => {
    const fetchFn = jest.fn().mockResolvedValue('still-queued');

    const { result } = renderHook(() =>
      usePolling<string>({
        fetch: fetchFn,
        intervalMs: 100,
        timeoutMs: 250,
        stopWhen: () => false,
      }),
    );

    // 100ms → tick #1, elapsed=100 < 250，正常 fetch
    await advance(100);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    // 200ms → tick #2, elapsed=200 < 250
    await advance(100);
    expect(fetchFn).toHaveBeenCalledTimes(2);
    // 300ms → tick #3, elapsed=300 ≥ 250 → 不再 fetch，置 isTimedOut
    await advance(100);
    expect(result.current.isTimedOut).toBe(true);
    expect(fetchFn).toHaveBeenCalledTimes(2);

    // 之后不应再调
    await advance(1_000);
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it('cleanup on unmount stops further fetch calls', async () => {
    const fetchFn = jest.fn().mockResolvedValue('x');

    const { unmount } = renderHook(() =>
      usePolling<string>({
        fetch: fetchFn,
        intervalMs: 100,
        timeoutMs: 10_000,
        stopWhen: () => false,
      }),
    );

    await advance(100);
    expect(fetchFn).toHaveBeenCalledTimes(1);

    unmount();
    await advance(1_000);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });
});
