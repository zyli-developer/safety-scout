/**
 * 视口检测 hook —— 返回当前是否处于桌面布局 (>=1024px)。
 *
 * 行为契约：
 * - process.env.TARO_ENV !== 'h5' → 始终返回 false（weapp 永不进桌面分支，
 *   且这样能让 dispatcher 里的桌面组件 import 在 weapp 包里成为 dead code，
 *   webpack 可 tree-shake 掉绝大部分）
 * - h5 端读 window.matchMedia('(min-width: 1024px)') 作为初值，并监听 change
 *   事件响应窗口缩放
 *
 * 不用 UA 检测：UA 字符串无法响应运行时窗口缩放（用户拖窗口大小），
 * 而 matchMedia 是浏览器原生的"视口已变化"信号。
 */
import { useEffect, useState } from 'react';

const DESKTOP_MQ = '(min-width: 1024px)';

export function useIsDesktop(): boolean {
  // process.env.TARO_ENV 在编译期被 Taro webpack DefinePlugin 替换为字面量字符串
  // ('h5' / 'weapp')。weapp 端这个表达式是 false 字面量，下面的 useState 初值函数与
  // useEffect 都按 isH5 = false 跑，matchMedia 永不被调用 —— 即便 weapp 没有
  // window.matchMedia API 也不会报错。
  const isH5 = process.env.TARO_ENV === 'h5';

  const [isDesktop, setIsDesktop] = useState<boolean>(() => {
    if (!isH5) return false;
    if (typeof window === 'undefined') return false;
    return window.matchMedia(DESKTOP_MQ).matches;
  });

  useEffect(() => {
    if (!isH5) return;
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia(DESKTOP_MQ);
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [isH5]);

  return isDesktop;
}
