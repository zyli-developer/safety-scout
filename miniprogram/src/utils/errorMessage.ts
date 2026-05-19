/**
 * Error code → UI 决策映射（架构 §4.2）。
 *
 * - display: toast / dialog / errorView 由前端按当前页选用
 * - allowRetry: 是否给"重试"按钮
 * - retryCountdownS: 强制等待秒数（429 RATE_LIMITED 时设 60）
 * - userMessage: 优先用 ApiError.userMessage（后端已经本地化），未知 code 走兜底
 *
 * 后端 errors.py 里的全部已知 code 都列在 ERROR_MAP 里，集中维护。
 * 新增后端错误码时同步更新本表 + 单测。
 */
import { ApiError } from '../api/client';

export type ErrorDisplay = 'toast' | 'dialog' | 'errorView';

export interface UiError {
  display: ErrorDisplay;
  userMessage: string;
  allowRetry: boolean;
  retryCountdownS?: number;
}

interface UiErrorRule {
  display: ErrorDisplay;
  allowRetry: boolean;
  retryCountdownS?: number;
}

const ERROR_MAP: Record<string, UiErrorRule> = {
  INVALID_IMAGE: { display: 'toast', allowRetry: true },
  IMAGE_TOO_LARGE: { display: 'dialog', allowRetry: true },
  RATE_LIMITED: { display: 'toast', allowRetry: true, retryCountdownS: 60 },
  LLM_TIMEOUT: { display: 'errorView', allowRetry: true },
  LLM_PARSE_FAILED: { display: 'errorView', allowRetry: true },
  LLM_CALL_FAILED: { display: 'errorView', allowRetry: true },
  NETWORK_ERROR: { display: 'toast', allowRetry: true },
  UPLOAD_FAILED: { display: 'toast', allowRetry: true },
  NOT_FOUND: { display: 'errorView', allowRetry: false },
  HTTP_ERROR: { display: 'toast', allowRetry: true },
  INTERNAL: { display: 'errorView', allowRetry: true },
};

const DEFAULT_RULE: UiErrorRule = {
  display: 'toast',
  allowRetry: true,
};

export function mapApiError(error: unknown): UiError {
  if (error instanceof ApiError) {
    const rule = ERROR_MAP[error.code] ?? DEFAULT_RULE;
    return { ...rule, userMessage: error.userMessage };
  }
  return {
    ...DEFAULT_RULE,
    userMessage: '未知错误，请重试',
  };
}
