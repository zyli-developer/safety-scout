/**
 * 运行期配置常量。
 *
 * 注意 dev / prod 切换的机制：
 * Taro 在编译时会把 `process.env.NODE_ENV` 替换为字面字符串（"development" /
 * "production"），所以下面的三元分支会在打包阶段被 tree-shake 掉一支，
 * 运行期分支只剩一个 —— 不要把这个判断暴露成可被代码改写的运行期 const，
 * 否则失去编译期裁剪的意义。
 *
 * 生产域名 TODO：见 API_BASE_URL 注释。
 */

const isDev = process.env.NODE_ENV !== 'production';

export const API_BASE_URL = isDev
  ? 'http://localhost:8000'
  : 'https://api.example.com'; // TODO: Phase 4 上线前替换为生产域名

export const DEFAULT_POLL_INTERVAL_MS = 2000;
export const DEFAULT_TIMEOUT_MS = 330_000;
