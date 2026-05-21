/**
 * CSS module mock — Proxy returns the property name as a class string.
 * 让组件测试可以断言 `className` 包含某个 module class（如 "lg" / "block" / "high"），
 * 而不必在每个组件里加 data-* attr 给测试用。
 *
 * ts-jest 内联 tsconfig 不含 esModuleInterop —— 必须把 default 自指 + __esModule
 * 标记一并返回，才能让 `import styles from './x.scss'` 解析到同一个 Proxy。
 */
const proxy = new Proxy(
  {},
  {
    get(_target, prop) {
      if (prop === '__esModule') return true;
      if (prop === 'default') return proxy;
      if (typeof prop === 'symbol') return undefined;
      return prop;
    },
  },
);

module.exports = proxy;
