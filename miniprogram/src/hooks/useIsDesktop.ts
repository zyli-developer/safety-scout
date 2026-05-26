/**
 * 视口检测 hook —— 返回当前是否处于桌面布局 (>=1024px)。
 *
 * 行为契约：
 * - process.env.TARO_ENV !== 'h5' → 始终返回 false（weapp 永不进桌面分支，
 *   且这样能让 dispatcher 里的桌面组件 import 在 weapp 包里成为 dead code，
 *   webpack 可 tree-shake 掉绝大部分）
 * - h5 端读 window.matchMedia('(min-width: 1024px)') 作为初值，并监听 change
 *   事件响应窗口缩放
 * - **打印期间冻结**：window.print() 触发 print preview 时浏览器把 viewport
 *   切到 A4 物理尺寸（< 1024px），matchMedia change 会把 isDesktop 改成 false，
 *   导致 dispatcher 切到 MobileReport，MobileReport 自己的 usePolling 从
 *   result=null 重启 → 渲染 ProgressTracker → 用户看到 "页面跳到分析中一下"。
 *   beforeprint / afterprint 间冻结 matchMedia 响应，print 结束后恢复。
 *
 * 不用 UA 检测：UA 字符串无法响应运行时窗口缩放（用户拖窗口大小），
 * 而 matchMedia 是浏览器原生的"视口已变化"信号。
 */
import { useEffect, useRef, useState } from 'react';

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

  // 打印期间冻结 matchMedia 响应。用 ref 拿 latest 值避免给 handler closure 注入依赖。
  const isPrintingRef = useRef(false);

  useEffect(() => {
    if (!isH5) return;
    if (typeof window === 'undefined') return;

    // 两路监听 print 状态，更可靠：
    // - beforeprint/afterprint：DOM event，Chrome/Firefox 都支持
    // - matchMedia('print')：CSS media query，触发更早（Chrome 在 viewport 变化
    //   时几乎同步 dispatch print MQ change），能抢在 (min-width:1024px) MQ
    //   change 之前 set 上 isPrinting
    const onBeforePrint = () => {
      isPrintingRef.current = true;
    };
    const onAfterPrint = () => {
      isPrintingRef.current = false;
    };
    const printMq = window.matchMedia('print');
    const printMqHandler = (e: MediaQueryListEvent) => {
      isPrintingRef.current = e.matches;
    };
    // 立刻读一次 print 状态当初值（防 hook mount 时已经在 print 态）
    isPrintingRef.current = printMq.matches;

    window.addEventListener('beforeprint', onBeforePrint);
    window.addEventListener('afterprint', onAfterPrint);
    printMq.addEventListener('change', printMqHandler);
    return () => {
      window.removeEventListener('beforeprint', onBeforePrint);
      window.removeEventListener('afterprint', onAfterPrint);
      printMq.removeEventListener('change', printMqHandler);
    };
  }, [isH5]);

  useEffect(() => {
    if (!isH5) return;
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia(DESKTOP_MQ);
    const handler = (e: MediaQueryListEvent) => {
      // 打印期间忽略 matchMedia change —— 否则 viewport 切到 A4 时会触发
      // dispatcher 重挂另一端组件，造成"分析中闪屏"
      if (isPrintingRef.current) return;
      setIsDesktop(e.matches);
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [isH5]);

  return isDesktop;
}
