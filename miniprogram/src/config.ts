/**
 * 运行期配置常量。
 *
 * `API_BASE_URL` 的取值机制（Taro 4 H5 / 微信小程序通用）：
 * - 由 config/index.ts 的 `defineConstants['process.env.API_BASE_URL']` 在
 *   编译期通过 webpack DefinePlugin 注入字面字符串
 * - 注入值来自 build 时的 shell env var `TARO_API_BASE_URL`
 *   - dev：`pnpm build:h5:dev` 设 `TARO_API_BASE_URL=http://localhost:8000`
 *   - prod：默认（不设） → 走 `https://api.example.com`（占位，Phase 4 上线前换）
 *
 * 为什么不用 `process.env.NODE_ENV` 切：Taro CLI 内部对 `taro build` 强制
 * NODE_ENV='production'、`taro build --watch` 强制 NODE_ENV='development'，
 * 用户从外部 `cross-env NODE_ENV=development taro build` 也会被 Taro 覆盖。
 * 所以引入独立 env var `TARO_API_BASE_URL` 完全绕开 NODE_ENV 的覆盖逻辑。
 */

// `process.env.API_BASE_URL` 由 webpack DefinePlugin 编译期替换；
// fallback 仅在测试 / 失配场景兜底，正常路径都被裁剪掉。
export const API_BASE_URL =
  process.env.API_BASE_URL || 'http://localhost:8000';

export const DEFAULT_POLL_INTERVAL_MS = 2000;
export const DEFAULT_TIMEOUT_MS = 330_000;

/**
 * v2 灰度比例（0.0 ~ 1.0）：决定多少比例的 createInspection 走 /api/v2/analyze。
 *
 * 当前 = 0：默认全走 v1，v2 代码就位但不投放真实流量。
 * 灰度节奏见 `docs/specs/v2-rollout.md` §一：
 *   0 → 1.0（内部账号试用 1 周）→ 0.1（灰度 1-2 天）→ 0.5 → 1.0（全量）
 *
 * MVP 阶段直接改这个常量重新打包；后续可换成远程配置中心动态下发。
 * v2 timeout 比 v1 大（agent 多轮慢约 2.5×）；createInspection 会按后端
 * 返回的 timeout_ms 自动覆盖前端默认值，不需要在这里调。
 */
export const V2_TRAFFIC_SHARE = 0;
