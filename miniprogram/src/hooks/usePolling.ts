/**
 * 通用轮询 hook。
 *
 * 行为：
 * - 每 `intervalMs` 调一次 `fetch`；
 * - `stopWhen(result)` 返 true 时停（succeeded / failed 都走这里）；
 * - 累计 `elapsedMs >= timeoutMs` 时自动停 + 置 `isTimedOut=true`；
 * - `fetch` 抛异常时立刻停 + 置 `error`（不重试 —— 重试策略归调用方）；
 * - unmount 时清 interval。
 *
 * 实现细节：fetch / stopWhen 用 ref 钉住，避免父组件每次渲染传入新闭包
 * 触发 useEffect 重跑（否则会反复重启 interval、漏掉已收到的 result）。
 */
import { useEffect, useRef, useState } from 'react';

interface PollingOpts<T> {
  fetch: () => Promise<T>;
  intervalMs: number;
  timeoutMs: number;
  stopWhen: (result: T) => boolean;
}

interface PollingState<T> {
  result: T | null;
  error: Error | null;
  elapsedMs: number;
  isTimedOut: boolean;
}

export function usePolling<T>(opts: PollingOpts<T>): PollingState<T> {
  const [result, setResult] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [isTimedOut, setIsTimedOut] = useState(false);

  // 把 opts 钉在 ref 上，避免 fetch / stopWhen 引用变化触发重轮询
  const optsRef = useRef(opts);
  optsRef.current = opts;

  useEffect(() => {
    let cancelled = false;
    const startedAt = Date.now();

    const tick = async () => {
      if (cancelled) return;
      const elapsed = Date.now() - startedAt;
      setElapsedMs(elapsed);

      if (elapsed >= optsRef.current.timeoutMs) {
        setIsTimedOut(true);
        clearInterval(intervalId);
        return;
      }

      try {
        const r = await optsRef.current.fetch();
        if (cancelled) return;
        setResult(r);
        if (optsRef.current.stopWhen(r)) {
          clearInterval(intervalId);
        }
      } catch (e) {
        if (cancelled) return;
        setError(e as Error);
        clearInterval(intervalId);
      }
    };

    const intervalId = setInterval(tick, optsRef.current.intervalMs);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
    // 只在 mount 时启动一次；opts 变化通过 ref 透传，故意空依赖。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { result, error, elapsedMs, isTimedOut };
}
