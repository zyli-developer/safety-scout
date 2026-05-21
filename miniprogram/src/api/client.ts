/**
 * 通用 HTTP 请求封装：把 Taro.request 包装成 Promise + 错误归一为 ApiError。
 *
 * 错误形状契约（Phase 3 T0 后端补丁后）：
 * 所有 4xx / 5xx 响应统一是 `{"error": {code, message, user_message}}`，
 * 包括 404、422、500。前端只需处理这一种错误形状 —— 见
 * `backend/app/main.py` 的全局 exception handler。
 *
 * 网络异常（DNS / 超时 / fail callback）统一归一为 `ApiError("NETWORK_ERROR", ..., 0)`。
 */
import Taro from '@tarojs/taro';
import { API_BASE_URL } from '../config';
import type { ErrorBody } from '../types/inspection';

export class ApiError extends Error {
  constructor(
    public code: string,
    public userMessage: string,
    public statusCode: number,
  ) {
    super(userMessage);
    this.name = 'ApiError';
    // 在编译目标 ES5/ES2015 下，自定义 Error 子类的原型链会丢；显式修一下，
    // 这样 `instanceof ApiError` 在所有 lib target 下都成立。
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

interface RequestOpts {
  /** 相对路径，会拼到 API_BASE_URL 后面。 */
  url: string;
  method: 'GET' | 'POST';
  data?: unknown;
  /** 默认 30s；轮询接口由调用方传更短的值。 */
  timeoutMs?: number;
}

export async function request<T>(opts: RequestOpts): Promise<T> {
  let res: Taro.request.SuccessCallbackResult;
  try {
    res = await Taro.request({
      url: API_BASE_URL + opts.url,
      method: opts.method,
      data: opts.data,
      header: { 'Content-Type': 'application/json' },
      timeout: opts.timeoutMs ?? 30_000,
    });
  } catch {
    // Taro.request fail callback / network error / DNS / 超时
    throw new ApiError('NETWORK_ERROR', '网络异常，请检查后重试', 0);
  }

  if (res.statusCode >= 400) {
    const err = (res.data as { error?: ErrorBody } | null)?.error;
    throw new ApiError(
      err?.code ?? 'UNKNOWN',
      err?.user_message ?? '网络异常，请重试',
      res.statusCode,
    );
  }
  return res.data as T;
}
