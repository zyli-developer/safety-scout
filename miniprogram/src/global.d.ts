/**
 * 环境声明：让 TS 接受 SCSS module 的 default import。
 *
 * 运行时表现：
 * - Taro 打包：把 *.module.scss 解析为生成的 hash class 名映射对象。
 * - Jest：jest.config.cjs 的 moduleNameMapper 把它映射到 styleMock.cjs，
 *   返回 `{}`，因此组件里 `styles.button` 在测试中是 undefined（属性而非
 *   编译错误），组件测试不要断言 className。
 */
declare module '*.module.scss' {
  const classes: { readonly [key: string]: string };
  export default classes;
}

declare module '*.module.css' {
  const classes: { readonly [key: string]: string };
  export default classes;
}
