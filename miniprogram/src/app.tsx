import Taro from '@tarojs/taro';
import { PropsWithChildren, useEffect } from 'react';
import './app.scss';

export default function App({ children }: PropsWithChildren<unknown>) {
  // weapp 上无法直接走 @font-face，要在 onLaunch 时通过 loadFontFace 拉远端字体。
  // H5 上 process.env.TARO_ENV === 'h5'，此 effect 短路跳过。
  // 字体加载失败也无所谓 —— tokens.scss 里 var(--font-mono) 有系统等宽 fallback。
  useEffect(() => {
    if (process.env.TARO_ENV !== 'weapp') return;
    // jsdelivr URL 钉到 v6.4.0 —— 跟 src/assets/fonts/ 自托管的 woff2 同源同版本。
    Taro.loadFontFace?.({
      family: 'IBM Plex Mono',
      source: 'url("https://cdn.jsdelivr.net/gh/IBM/plex@v6.4.0/IBM-Plex-Mono/fonts/complete/woff2/IBMPlexMono-Regular.woff2")',
      desc: { style: 'normal', weight: 'normal' },
      global: true,
      success: () => undefined,
      fail: () => undefined,
      complete: () => undefined,
    });
  }, []);

  return children;
}
