/**
 * 单元测试：useIsDesktop hook.
 *
 * 验收要点：
 * - h5 环境下读 matchMedia.matches 作为初值
 * - h5 环境下 MQ change 事件触发 state 更新
 * - h5 环境下 unmount 时移除 listener
 * - 非 h5 环境（weapp）直接返回 false，不调用 matchMedia
 * - 打印期间（beforeprint/afterprint 或 matchMedia('print').matches）冻结切换
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

/**
 * 安装一个 query-aware matchMedia mock：
 * - '(min-width: 1024px)' → desktopMq
 * - 'print' → printMq
 * - 其它 → 一个临时空 stub
 */
function installQueryAwareMatchMedia(desktopMq: MqStub, printMq: MqStub): jest.Mock {
  const fn = jest.fn().mockImplementation((q: string) => {
    if (q === '(min-width: 1024px)') return desktopMq;
    if (q === 'print') return printMq;
    return makeMqStub(false);
  });
  window.matchMedia = fn as unknown as typeof window.matchMedia;
  return fn;
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
    installQueryAwareMatchMedia(makeMqStub(true), makeMqStub(false));
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(true);
  });

  it('returns false at mount when matchMedia is false', () => {
    installQueryAwareMatchMedia(makeMqStub(false), makeMqStub(false));
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(false);
  });

  it('updates state when MediaQueryList emits change', () => {
    const desktopMq = makeMqStub(false);
    installQueryAwareMatchMedia(desktopMq, makeMqStub(false));
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(false);

    act(() => {
      desktopMq._handler?.({ matches: true });
    });
    expect(result.current).toBe(true);
  });

  it('removes the change listener on unmount', () => {
    const desktopMq = makeMqStub(false);
    installQueryAwareMatchMedia(desktopMq, makeMqStub(false));
    const { unmount } = renderHook(() => useIsDesktop());
    unmount();
    expect(desktopMq.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('returns false in weapp without calling matchMedia', () => {
    process.env.TARO_ENV = 'weapp';
    const spy = jest.fn();
    window.matchMedia = spy as unknown as typeof window.matchMedia;
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(false);
    expect(spy).not.toHaveBeenCalled();
  });

  it('freezes matchMedia response during window.print() via beforeprint/afterprint', () => {
    // 2026-05-25 修复：window.print() 进入 print preview 时浏览器 viewport 切到
    // A4 size，matchMedia 触发 false，会导致 dispatcher 重挂另一端组件造成
    // "分析中闪屏"。beforeprint / afterprint 间应冻结 matchMedia 响应。
    const desktopMq = makeMqStub(true);
    installQueryAwareMatchMedia(desktopMq, makeMqStub(false));
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(true);

    act(() => {
      window.dispatchEvent(new Event('beforeprint'));
    });

    act(() => {
      desktopMq._handler?.({ matches: false });
    });
    expect(result.current).toBe(true); // 仍 true，被冻结

    act(() => {
      window.dispatchEvent(new Event('afterprint'));
    });

    act(() => {
      desktopMq._handler?.({ matches: false });
    });
    expect(result.current).toBe(false); // 解冻后正常响应
  });

  it('also freezes via matchMedia("print") change event (more reliable than DOM events)', () => {
    // 双路监听：print MQ change 比 beforeprint event 触发更早，能抢在
    // desktop MQ change 之前 set isPrinting
    const desktopMq = makeMqStub(true);
    const printMq = makeMqStub(false);
    installQueryAwareMatchMedia(desktopMq, printMq);
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(true);

    // print MQ 报告进入打印态
    act(() => {
      printMq._handler?.({ matches: true });
    });

    // print 期间 desktop MQ change → 应被冻结
    act(() => {
      desktopMq._handler?.({ matches: false });
    });
    expect(result.current).toBe(true); // 仍 true
  });
});
