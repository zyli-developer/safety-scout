// Jest setup: globally mock @tarojs/taro since jsdom can't actually run wx.*
import '@testing-library/jest-dom';
import React from 'react';

jest.mock('@tarojs/taro', () => ({
  __esModule: true,
  default: {
    request: jest.fn(),
    uploadFile: jest.fn(),
    chooseMedia: jest.fn(),
    navigateTo: jest.fn(),
    showToast: jest.fn(),
    useRouter: jest.fn(() => ({ params: {} })),
  },
}));

/**
 * @tarojs/components 在发布包里是原生 ESM（`export * from ...`），ts-jest 默认不转换
 * node_modules，导致 jsdom 测试运行时报 `Unexpected token 'export'`。
 *
 * 组件测试只关心 DOM 结构（文案 / role / data-*），把 Taro 的 View/Text 桥接为
 * 普通 div / span 即可。Taro 自带的 props（onClick / className / style / role /
 * aria-* / data-*）都是合法 HTML 属性，原样透传即可被 testing-library 查询到。
 */
jest.mock('@tarojs/components', () => {
  const passthrough =
    (tag: 'div' | 'span') =>
    ({ children, ...props }: { children?: React.ReactNode } & Record<string, unknown>) =>
      React.createElement(tag, props, children);
  return {
    __esModule: true,
    View: passthrough('div'),
    Text: passthrough('span'),
  };
});
