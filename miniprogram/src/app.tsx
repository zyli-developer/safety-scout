import Taro from '@tarojs/taro';
import { PropsWithChildren, useEffect } from 'react';
import './app.scss';

export default function App({ children }: PropsWithChildren<unknown>) {
  // weapp 上无法直接走 @font-face，要在 onLaunch 时通过 loadFontFace 拉远端字体。
  // H5 上 process.env.TARO_ENV === 'h5'，此 effect 短路跳过。
  // 字体加载失败也无所谓 —— tokens.scss 里 var(--font-mono) 有系统等宽 fallback。
  useEffect(() => {
    if (process.env.TARO_ENV !== 'weapp') return;
    Taro.loadFontFace?.({
      family: 'IBM Plex Mono',
      source: 'url("https://cdn.jsdelivr.net/gh/IBM/plex@master/IBM-Plex-Mono/fonts/complete/woff2/IBMPlexMono-Regular.woff2")',
      desc: { style: 'normal', weight: 'normal' },
      global: true,
      success: () => undefined,
      fail: () => undefined,
      complete: () => undefined,
      // Taro 的 loadFontFace 类型签名不含 global，但实际 wx API 支持。
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
  }, []);

  return children;
}
