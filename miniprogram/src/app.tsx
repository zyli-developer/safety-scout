import Taro from '@tarojs/taro';
import { PropsWithChildren, useEffect } from 'react';
import './app.scss';

/**
 * 浏览器扩展（沉浸式翻译 / Grammarly 等）在 reload 时会向页面 window 抛
 * "Extension context invalidated" / "The message port closed before a response
 * was received." 之类的错误。这不是我们的代码，但会污染控制台、容易让用户
 * 误以为是 app 异常。这里在最早期挂一对 listener 把它们就地静默。
 * 仅 H5 端启用；过滤精确匹配字符串，不影响真正的应用错误。
 */
function isBrowserExtensionNoise(msg: unknown): boolean {
  if (typeof msg !== 'string') return false;
  return (
    msg.includes('Extension context invalidated') ||
    msg.includes('message port closed before a response') ||
    msg.includes('chrome-extension://') ||
    msg.includes('moz-extension://')
  );
}

function installExtensionErrorFilter(): void {
  if (typeof window === 'undefined') return;
  window.addEventListener(
    'error',
    (e) => {
      if (
        isBrowserExtensionNoise(e.message) ||
        isBrowserExtensionNoise(e.filename) ||
        (e.error && isBrowserExtensionNoise(String(e.error?.message)))
      ) {
        e.stopImmediatePropagation();
        e.preventDefault();
      }
    },
    true,
  );
  window.addEventListener(
    'unhandledrejection',
    (e) => {
      const reason = e.reason;
      const msg = typeof reason === 'string' ? reason : String(reason?.message ?? '');
      if (isBrowserExtensionNoise(msg)) {
        e.preventDefault();
      }
    },
    true,
  );
}

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

  useEffect(() => {
    if (process.env.TARO_ENV !== 'h5') return;
    installExtensionErrorFilter();
  }, []);

  return children;
}
