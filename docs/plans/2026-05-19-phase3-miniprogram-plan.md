# Phase 3 · Miniprogram (Taro) Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 [`docs/plans/2026-05-18-架构-design.md`](./2026-05-18-架构-design.md) §3 设计的"Taro + React + TypeScript 小程序前端"实施落地 — 首页拍照按钮 → POST 上传 → 报告页轮询 → 渲染结构化报告。

**Upstream specs:**
- [`docs/plans/2026-05-18-架构-design.md`](./2026-05-18-架构-design.md) §3 (前端目录/组件分工), §4 (跨端契约)
- [`docs/specs/report-schema.md`](../specs/report-schema.md) — 报告 JSON 契约（前端手写双份）
- Phase 2 已交付后端 API：`POST /api/v1/inspections` + `GET /api/v1/inspections/{id}` + `GET /api/v1/healthz`

**Tech stack:**
- Taro 4.x latest + React 18 + TypeScript 5
- NutUI-React Taro 版 基础组件
- Jest + `@testing-library/react` 单测
- 目标编译：微信小程序（H5 / RN 不在范围）

---

## 重要前置说明

**本计划全部为"代码任务"+ 1 个手动验证收尾**：除最后一步 Phase 3 退出门验证需要用户打开微信开发者工具手动跑一遍，其它任务不需要用户参与凭证 / 数据。

**测试硬规则**（[[feedback-phase-unit-tests]]）：phase 退出时 `cd miniprogram && pnpm test` 必须 **0 failed / 0 skipped**；后端测试套件仍维持 87/0/0 不退步。

---

## Phase 3 brainstorm 决策（2026-05-19）

| 决策 | 选择 | 理由 |
| --- | --- | --- |
| 分支策略 | 一口气走完，单 PR | 个人项目；Phase 3 是完整前端 + 一个后端补丁 |
| Taro 版本 | 4.x latest | vite 构建快、React 18 / TS 5 原生支持 |
| 后端错误 shape | **修后端统一**到 `{error:{...}}` | 见 T0；HTTPException 现状返 `{detail:{error:{...}}}` 两种 shape，前端不该解两种 |
| 异常路径 UX | 全人手动重试 | 拍照失败 Toast 重拍；轮询超时错误页 + 重试按钮；429 带 60s 倒计时禁按钮 |
| Dev/Prod baseURL | `src/config.ts` + `process.env.NODE_ENV` 切 | 写死 dev=http://localhost:8000，prod=占位 |
| 测试 scope | api client + hooks + utils + components | 页面集成测试 Taro 环境 mock 较贵，不强制；交由微信开发者工具手动验证 |
| Phase 3 退出门 | 微信开发者工具跑通 + 单测绿 | 不要求上架 |

---

## 任务依赖图

```
T0 后端错误 shape 统一（轻 backend commit）
  │
  ▼
T1 Taro 工程骨架 ──> T2 types + config ──> T3 api client ──> T4 usePolling
                                                              ──> T5 useImageCapture
                                                              ──> T6 utils
                                                                    │
                                                                    ▼
                              T7 自撸 components (BigButton / PlainWarningCard /
                                                  HazardCard / ProgressIndicator)
                                                                    │
                                                                    ▼
                                                            T8 pages/index + pages/report
                                                                    │
                                                                    ▼
                                                          T9 Phase 3 退出门验证 + PR
```

---

## Task 0: 后端错误 shape 统一 [代码 · 后端]

**Files:**
- Modify: `backend/app/routes/inspections.py`（GET 404 抛 HTTPException 那处）
- Modify: `backend/app/main.py`（注册 HTTPException 全局 handler）
- Modify: `backend/tests/integration/test_routes.py`（404 测试断言改 body.error.code）

**架构参考：** §2.4 错误处理

**问题陈述：**

现状有两种错误 shape：
- `SafetyScoutError`（400 / 413 / 429 / 500 / 502 / 504） → `{"error":{code,message,user_message}}`
- `HTTPException` 404（GET 不存在 id） → `{"detail":{"error":{code,message,user_message}}}`

差一层 `detail` 包装。前端解两种 shape 不优雅。

**Approach:**

1. `main.py` 注册 FastAPI 默认 `HTTPException` handler，把 `detail`（约定为 `{"error":{...}}` 形状）扁平出去：

```python
from fastapi.exceptions import HTTPException as FastAPIHTTPException

@app.exception_handler(FastAPIHTTPException)
async def _http_exception_handler(request: Request, exc: FastAPIHTTPException) -> JSONResponse:
    # 我们的路由约定：detail = {"error": {...}}。直接把 detail 当 body。
    # 兼容偶尔 raise HTTPException(404)（detail 是 str），fallback 成最小 error 包。
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        body = exc.detail
    else:
        body = {
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
                "user_message": "请求出错，请稍后重试",
            }
        }
    return JSONResponse(status_code=exc.status_code, content=body)
```

2. `routes/inspections.py` 的 GET 404 不动（detail 形态已经是 `{"error":{...}}`），现在它会被新 handler 扁平化为 `{"error":{...}}`。

3. 改 `test_routes.py::test_get_inspection_404`：断言从 `body["detail"]["error"]["code"]` 改为 `body["error"]["code"]`。

**Tests:**
- 改一个已有测试（test_get_inspection_404），无新测试

**Validation:**
- `pytest backend/tests/integration/test_routes.py -v` → 6 passed
- 全套 `pytest backend/` → 87 passed
- ruff + mypy clean

**Commit:**
```
fix: 统一 HTTPException 错误响应 shape 与 SafetyScoutError 一致

Phase 3 前端启动前的小补丁：HTTPException 现状返 {"detail":{"error":{...}}}，
SafetyScoutError 返 {"error":{...}}，前端要解两种 shape 不必要复杂。

main.py 加一个 FastAPIHTTPException handler 把 detail 扁平化：
- detail 已是 {"error":{...}} → 直接当 body
- detail 是 str（极端 fallback） → 包成最小 error 包

测试 test_get_inspection_404 断言 body.error.code 而非 body.detail.error.code。
```

---

## Task 1: Miniprogram 工程骨架 [代码]

**Files:**
- Create: `miniprogram/package.json`
- Create: `miniprogram/tsconfig.json`
- Create: `miniprogram/jest.config.cjs`
- Create: `miniprogram/babel.config.cjs`
- Create: `miniprogram/.gitignore`
- Create: `miniprogram/project.config.json`（微信开发者工具识别）
- Create: `miniprogram/src/app.tsx`、`src/app.config.ts`、`src/app.scss`
- Create: `miniprogram/src/pages/index/{index.tsx, index.config.ts, index.module.scss}`（hello world 占位，T8 落地实现）
- Create: `miniprogram/src/pages/report/{index.tsx, index.config.ts, index.module.scss}`（占位）
- Create: `miniprogram/tests/setup.ts`（mock `@tarojs/taro`）

**Approach:**

1. **不用 `taro init` CLI**（避免交互式提示）—— 手写最小 package.json + Taro 4 项目结构

2. `package.json` 关键依赖：
```json
{
  "dependencies": {
    "@tarojs/components": "^4.0.0",
    "@tarojs/react": "^4.0.0",
    "@tarojs/runtime": "^4.0.0",
    "@tarojs/taro": "^4.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@nutui/nutui-react-taro": "^2.6.0"
  },
  "devDependencies": {
    "@tarojs/cli": "^4.0.0",
    "@tarojs/webpack5-runner": "^4.0.0",
    "@types/react": "^18",
    "@types/node": "^20",
    "@types/jest": "^29",
    "typescript": "^5",
    "jest": "^29",
    "ts-jest": "^29",
    "@testing-library/react": "^14",
    "@testing-library/jest-dom": "^6",
    "jest-environment-jsdom": "^29",
    "eslint": "^8",
    "@typescript-eslint/parser": "^6",
    "@typescript-eslint/eslint-plugin": "^6"
  },
  "scripts": {
    "build:weapp": "taro build --type weapp",
    "dev:weapp": "taro build --type weapp --watch",
    "test": "jest",
    "test:watch": "jest --watch",
    "lint": "eslint 'src/**/*.{ts,tsx}'"
  }
}
```

3. `tsconfig.json` — strict 模式 + paths 别名 `@/*` → `src/*`

4. `jest.config.cjs` — `preset: 'ts-jest'`, `testEnvironment: 'jsdom'`, `moduleNameMapper` 把 `@tarojs/taro` 等映射到 `tests/setup.ts` mock

5. `tests/setup.ts` — mock Taro API：`chooseMedia`, `uploadFile`, `request`, `navigateTo`, `useRouter`, `showToast` 等（每个测试自己用 `jest.mock` 覆盖也行；setup 提供 default no-op）

6. `project.config.json` — 微信开发者工具识别项目目录、AppID 占位 `touristappid`、`miniprogramRoot: "dist"`

7. `app.tsx` / `app.config.ts` — 注册 `pages/index/index` + `pages/report/index` 两页

**Tests:** 暂无（脚手架阶段；T3 开始有具体测试）

**Validation:**
- `cd miniprogram && pnpm install` 成功
- `pnpm test` 输出 "No tests found" 但不报错
- `pnpm lint` clean

**Commit:**
```
chore: 初始化 miniprogram 工程骨架（Taro 4 + React 18 + TS 5）
```

---

## Task 2: 跨端类型 + 配置 [代码]

**Files:**
- Create: `miniprogram/src/types/report.ts`（ReportPayload / Hazard / Severity / CategoryCode / ModelMeta，对齐 `docs/specs/report-schema.md`）
- Create: `miniprogram/src/types/inspection.ts`（CreateInspectionResponse / GetInspectionResponse / ErrorBody / ApiError）
- Create: `miniprogram/src/config.ts`（API_BASE_URL via NODE_ENV）
- Create: `miniprogram/tests/types/report.test.ts`（spec 一致性测试 —— 抓 `docs/specs/report-schema.md` 的 JSON 块，校验通过 TS 类型断言）

**Approach:**

1. `types/report.ts`：

```typescript
export type Severity = 'high' | 'medium' | 'low';
export type CategoryCode = 'H1'|'H2'|'H3'|'H4'|'H5'|'H6'|'H7'|'H8'|'H9'|'H10';

export interface Hazard {
  category_code: CategoryCode;
  category_name: string;
  description: string;
  severity: Severity;
  regulation: string;
  suggestion: string;
}

export interface ModelMeta {
  provider: 'claude_cli' | 'fake';
  model: string;
  latency_ms: number;
}

export interface ReportPayload {
  inspection_id: string;
  created_at: string;
  plain_warning: string;
  summary: string;
  overall_severity: Severity;
  hazards: Hazard[];
  model_meta: ModelMeta;
}
```

2. `types/inspection.ts`：

```typescript
import type { ReportPayload } from './report';

export type InspectionStatus = 'queued' | 'processing' | 'succeeded' | 'failed';

export interface CreateInspectionResponse {
  inspection_id: string;
  poll_url: string;
  poll_interval_ms: number;
  timeout_ms: number;
  status: 'queued';
}

export interface ErrorBody {
  code: string;
  message: string;
  user_message: string;
}

export interface GetInspectionResponse {
  inspection_id: string;
  status: InspectionStatus;
  created_at: string;
  updated_at: string;
  report: ReportPayload | null;
  error: ErrorBody | null;
}
```

3. `config.ts`：

```typescript
const isDev = process.env.NODE_ENV !== 'production';

export const API_BASE_URL = isDev
  ? 'http://localhost:8000'
  : 'https://api.example.com'; // TODO: Phase 4 上线前替换

export const DEFAULT_POLL_INTERVAL_MS = 2000;
export const DEFAULT_TIMEOUT_MS = 330_000;
```

4. spec 一致性测试：

```typescript
// tests/types/report.test.ts
import { readFileSync } from 'fs';
import { join } from 'path';
import type { ReportPayload } from '../../src/types/report';

const SPEC_PATH = join(__dirname, '../../../docs/specs/report-schema.md');

function extractFirstJsonBlock(md: string): unknown {
  const match = md.match(/```json\s*\n([\s\S]*?)\n```/);
  if (!match) throw new Error('找不到 ```json 块');
  return JSON.parse(match[1]);
}

test('report-schema.md 示例符合 ReportPayload 类型（结构性检查）', () => {
  const md = readFileSync(SPEC_PATH, 'utf-8');
  const example = extractFirstJsonBlock(md) as ReportPayload;
  expect(example.inspection_id).toBeDefined();
  expect(example.overall_severity).toMatch(/^(high|medium|low)$/);
  expect(Array.isArray(example.hazards)).toBe(true);
  expect(example.hazards.every(h => /^H([1-9]|10)$/.test(h.category_code))).toBe(true);
});
```

**Validation:** `pnpm test types/report` → 1 passed；`pnpm lint` clean

**Commit:**
```
feat: Task 2 — 跨端 TS 类型 + 配置 + spec 一致性测试
```

---

## Task 3: API client [代码]

**Files:**
- Create: `miniprogram/src/api/client.ts`（请求封装 + 错误归一）
- Create: `miniprogram/src/api/inspections.ts`（createInspection / getInspection）
- Create: `miniprogram/tests/api/client.test.ts`
- Create: `miniprogram/tests/api/inspections.test.ts`

**架构参考：** §3.4 API 客户端

**Approach:**

1. `client.ts`：

```typescript
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
  }
}

interface RequestOpts {
  url: string;
  method: 'GET' | 'POST';
  data?: unknown;
  timeoutMs?: number;
}

export async function request<T>(opts: RequestOpts): Promise<T> {
  const res = await Taro.request({
    url: API_BASE_URL + opts.url,
    method: opts.method,
    data: opts.data,
    header: { 'Content-Type': 'application/json' },
    timeout: opts.timeoutMs ?? 30_000,
  });

  if (res.statusCode >= 400) {
    const err = (res.data as { error?: ErrorBody })?.error;
    throw new ApiError(
      err?.code ?? 'UNKNOWN',
      err?.user_message ?? '网络异常，请重试',
      res.statusCode,
    );
  }
  return res.data as T;
}
```

2. `inspections.ts`：

```typescript
import Taro from '@tarojs/taro';
import { API_BASE_URL } from '../config';
import { ApiError, request } from './client';
import type {
  CreateInspectionResponse,
  GetInspectionResponse,
  ErrorBody,
} from '../types/inspection';

export function createInspection(
  imageTempFilePath: string,
): Promise<CreateInspectionResponse> {
  return new Promise((resolve, reject) => {
    Taro.uploadFile({
      url: API_BASE_URL + '/api/v1/inspections',
      filePath: imageTempFilePath,
      name: 'image',
      success: (res) => {
        const body: unknown = (() => {
          try { return JSON.parse(res.data); } catch { return null; }
        })();
        if (res.statusCode >= 400) {
          const err = (body as { error?: ErrorBody } | null)?.error;
          reject(new ApiError(
            err?.code ?? 'UPLOAD_FAILED',
            err?.user_message ?? '图片上传失败，请重试',
            res.statusCode,
          ));
          return;
        }
        resolve(body as CreateInspectionResponse);
      },
      fail: () => reject(new ApiError(
        'NETWORK_ERROR',
        '网络异常，请检查后重试',
        0,
      )),
    });
  });
}

export function getInspection(id: string): Promise<GetInspectionResponse> {
  return request<GetInspectionResponse>({
    url: `/api/v1/inspections/${id}`,
    method: 'GET',
  });
}
```

3. tests：mock `Taro.request` / `Taro.uploadFile`，验证：
   - 2xx 走 success path 返反序列化对象
   - 4xx body.error 抽出来转 ApiError
   - 4xx body 无 error 字段 → ApiError fallback user_message
   - 网络错（fail callback） → ApiError code=NETWORK_ERROR

约 6-8 个测试。

**Validation:** `pnpm test api` 全 pass

**Commit:**
```
feat: Task 3 — API client + inspections 调用 + ApiError 归一
```

---

## Task 4: `usePolling` hook [代码]

**Files:**
- Create: `miniprogram/src/hooks/usePolling.ts`
- Create: `miniprogram/tests/hooks/usePolling.test.ts`

**架构参考：** §3.3 `usePolling`

**Approach:**

```typescript
import { useEffect, useRef, useState } from 'react';

interface PollingOpts<T> {
  fetch: () => Promise<T>;
  intervalMs: number;
  timeoutMs: number;
  stopWhen: (result: T) => boolean;
}

interface PollingState<T> {
  result: T | null;
  error: Error | null;
  elapsedMs: number;
  isTimedOut: boolean;
}

export function usePolling<T>(opts: PollingOpts<T>): PollingState<T> {
  const [result, setResult] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [isTimedOut, setIsTimedOut] = useState(false);

  const stableOpts = useRef(opts);
  // 不响应 opts 变化（fetch / stopWhen 闭包稳定），避免无限重轮询
  
  useEffect(() => {
    let cancelled = false;
    const startedAt = Date.now();
    const intervalId = setInterval(async () => {
      if (cancelled) return;
      const elapsed = Date.now() - startedAt;
      setElapsedMs(elapsed);
      if (elapsed >= stableOpts.current.timeoutMs) {
        setIsTimedOut(true);
        clearInterval(intervalId);
        return;
      }
      try {
        const r = await stableOpts.current.fetch();
        if (cancelled) return;
        setResult(r);
        if (stableOpts.current.stopWhen(r)) {
          clearInterval(intervalId);
        }
      } catch (e) {
        if (cancelled) return;
        setError(e as Error);
        clearInterval(intervalId);
      }
    }, stableOpts.current.intervalMs);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

  return { result, error, elapsedMs, isTimedOut };
}
```

**Tests**（用 `jest.useFakeTimers()` 推时间）：
- `test_polls_at_interval_until_stopWhen` — mock fetch 第 3 次返"done"，验证 fetch 被调 3 次后停
- `test_returns_error_on_fetch_failure` — fetch reject，验证 error 被设置 + 不再 poll
- `test_times_out` — timeoutMs 推过去，isTimedOut=true，fetch 不再调
- `test_cleanup_on_unmount` — unmount 后 fetch 不再调

约 4 个测试。

**Validation:** `pnpm test usePolling` 4 passed

**Commit:**
```
feat: Task 4 — usePolling hook + fake-timers 状态机测试
```

---

## Task 5: `useImageCapture` hook [代码]

**Files:**
- Create: `miniprogram/src/hooks/useImageCapture.ts`
- Create: `miniprogram/tests/hooks/useImageCapture.test.ts`

**架构参考：** §3.2 首页中调用模式

**Approach:**

```typescript
import Taro from '@tarojs/taro';

export interface CapturedImage {
  tempFilePath: string;
  size: number;        // bytes
  fileType: string;    // 'image'
}

export async function captureImage(): Promise<CapturedImage> {
  const res = await Taro.chooseMedia({
    count: 1,
    mediaType: ['image'],
    sourceType: ['camera', 'album'],
    sizeType: ['original'],  // 必须原图（架构 §4.4）
  });
  const file = res.tempFiles[0];
  return {
    tempFilePath: file.tempFilePath,
    size: file.size,
    fileType: file.fileType,
  };
}
```

写成函数（而不是 hook）即可——首页直接 `await captureImage()`，无需 React state。文件名 `useImageCapture.ts` 保留语义，下层可以拆。

**Tests:**
- `test_returns_first_image_meta` — mock `chooseMedia` 返 1 张图，验证 path/size/fileType 透传
- `test_propagates_choose_media_error` — mock reject（用户取消），验证 error 原样抛

**Validation:** `pnpm test useImageCapture` 2 passed

**Commit:**
```
feat: Task 5 — captureImage 拍照/取相册（Taro.chooseMedia sizeType=original）
```

---

## Task 6: utils（severity + errorMessage）[代码]

**Files:**
- Create: `miniprogram/src/utils/severity.ts`
- Create: `miniprogram/src/utils/errorMessage.ts`
- Create: `miniprogram/tests/utils/severity.test.ts`
- Create: `miniprogram/tests/utils/errorMessage.test.ts`

**架构参考：** §4.2 错误码 → UI 映射

**Approach:**

1. `severity.ts`：

```typescript
import type { Severity, Hazard } from '../types/report';

export const SEVERITY_ORDER: Record<Severity, number> = {
  high: 3,
  medium: 2,
  low: 1,
};

export const SEVERITY_COLOR: Record<Severity, string> = {
  high: '#E63946',    // 红
  medium: '#F4A261',  // 橙
  low: '#2A9D8F',     // 绿
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
};

export function sortBySeverity(hazards: Hazard[]): Hazard[] {
  return [...hazards].sort(
    (a, b) => SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity],
  );
}
```

2. `errorMessage.ts`：

```typescript
import { ApiError } from '../api/client';

interface UiError {
  display: 'toast' | 'dialog' | 'errorView';
  userMessage: string;
  allowRetry: boolean;
  retryCountdownS?: number;
}

const ERROR_MAP: Record<string, Omit<UiError, 'userMessage'>> = {
  INVALID_IMAGE:     { display: 'toast',     allowRetry: true },
  IMAGE_TOO_LARGE:   { display: 'dialog',    allowRetry: true },
  RATE_LIMITED:      { display: 'toast',     allowRetry: true, retryCountdownS: 60 },
  LLM_TIMEOUT:       { display: 'errorView', allowRetry: true },
  LLM_PARSE_FAILED:  { display: 'errorView', allowRetry: true },
  LLM_CALL_FAILED:   { display: 'errorView', allowRetry: true },
  NETWORK_ERROR:     { display: 'toast',     allowRetry: true },
  NOT_FOUND:         { display: 'errorView', allowRetry: false },
  INTERNAL:          { display: 'errorView', allowRetry: true },
};

export function mapApiError(error: unknown): UiError {
  if (error instanceof ApiError) {
    const fallback = ERROR_MAP[error.code] ?? {
      display: 'toast',
      allowRetry: true,
    };
    return { ...fallback, userMessage: error.userMessage };
  }
  return {
    display: 'toast',
    userMessage: '未知错误，请重试',
    allowRetry: true,
  };
}
```

**Tests:**
- severity: sortBySeverity 高 → 中 → 低；颜色 / label 表完整
- errorMessage: 每个已知 code 映射正确；未知 code 走 fallback；非 ApiError 走 unknown

约 5-6 个测试。

**Commit:**
```
feat: Task 6 — utils/severity + utils/errorMessage
```

---

## Task 7: 自撸 components [代码]

**Files:**
- Create: `miniprogram/src/components/BigButton/index.tsx` + `index.module.scss`
- Create: `miniprogram/src/components/PlainWarningCard/index.tsx` + `index.module.scss`
- Create: `miniprogram/src/components/HazardCard/index.tsx` + `index.module.scss`
- Create: `miniprogram/src/components/ProgressIndicator/index.tsx` + `index.module.scss`
- Create: `miniprogram/tests/components/BigButton.test.tsx`
- Create: `miniprogram/tests/components/PlainWarningCard.test.tsx`
- Create: `miniprogram/tests/components/HazardCard.test.tsx`
- Create: `miniprogram/tests/components/ProgressIndicator.test.tsx`

**架构参考：** §3.5 NutUI 与自撸组件分工

**Approach（每个组件用途）：**

1. **BigButton**：首页"拍隐患"大按钮。`<View>` 包 `<Text>`，按下态 + loading 态；尺寸固定（占屏宽 80%）
2. **PlainWarningCard**：报告页顶部口语化警示卡。props: `text: string`, `severity: Severity`。背景按 severity 染色
3. **HazardCard**：单条隐患。props: `hazard: Hazard`。布局：category_name + severity 标签 → description → 折叠的 regulation（点击展开）→ suggestion 高亮
4. **ProgressIndicator**：三段进度（拍照成功 → AI 分析中 → 报告就绪）。props: `currentStep: 1 | 2 | 3`, `elapsedMs?: number`

**Tests**（用 @testing-library/react，每个组件 2-3 测试）：
- 文案 / props 渲染正确
- severity 颜色映射上去（断言 `style.background-color` 或 className）
- 交互（HazardCard 点击展开 regulation）

约 8-10 个测试。

**Validation:** `pnpm test components` 全 pass

**Commit:**
```
feat: Task 7 — 自撸 4 个核心组件（BigButton/PlainWarningCard/HazardCard/ProgressIndicator）
```

---

## Task 8: pages/index + pages/report [代码]

**Files:**
- Modify: `miniprogram/src/pages/index/index.tsx`（占位 → 完整首页）
- Modify: `miniprogram/src/pages/index/index.module.scss`
- Modify: `miniprogram/src/pages/report/index.tsx`（占位 → 完整报告页）
- Modify: `miniprogram/src/pages/report/index.module.scss`

**架构参考：** §3.2 页面 / 状态流

**Approach：**

1. **index 页**：

```tsx
import Taro from '@tarojs/taro';
import { View } from '@tarojs/components';
import { useState } from 'react';
import { BigButton } from '../../components/BigButton';
import { captureImage } from '../../hooks/useImageCapture';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';

export default function IndexPage() {
  const [uploading, setUploading] = useState(false);

  const handlePress = async () => {
    if (uploading) return;
    try {
      const image = await captureImage();
    } catch (e) {
      // 用户取消，不弹错（chooseMedia 取消是常态）
      return;
    }
    setUploading(true);
    try {
      const { inspection_id, poll_interval_ms, timeout_ms } =
        await createInspection(image.tempFilePath);
      Taro.navigateTo({
        url: `/pages/report/index?id=${inspection_id}&pi=${poll_interval_ms}&to=${timeout_ms}`,
      });
    } catch (e) {
      const ui = mapApiError(e);
      Taro.showToast({ title: ui.userMessage, icon: 'none' });
    } finally {
      setUploading(false);
    }
  };

  return (
    <View className="index-page">
      <BigButton onTap={handlePress} loading={uploading} text="拍隐患" />
    </View>
  );
}
```

注意：取相册取消（`chooseMedia` reject）不算错误，吞掉；上传错误才提示。

2. **report 页**：

```tsx
import Taro, { useRouter } from '@tarojs/taro';
import { View } from '@tarojs/components';
import { usePolling } from '../../hooks/usePolling';
import { getInspection } from '../../api/inspections';
import { PlainWarningCard } from '../../components/PlainWarningCard';
import { HazardCard } from '../../components/HazardCard';
import { ProgressIndicator } from '../../components/ProgressIndicator';
import { sortBySeverity } from '../../utils/severity';
import { mapApiError } from '../../utils/errorMessage';
import type { GetInspectionResponse } from '../../types/inspection';

export default function ReportPage() {
  const { params } = useRouter();
  const id = params.id ?? '';
  const intervalMs = Number(params.pi) || 2000;
  const timeoutMs = Number(params.to) || 330_000;

  const { result, error, isTimedOut } = usePolling<GetInspectionResponse>({
    fetch: () => getInspection(id),
    intervalMs,
    timeoutMs,
    stopWhen: (r) => r.status === 'succeeded' || r.status === 'failed',
  });

  if (error) {
    const ui = mapApiError(error);
    return <View className="error-view">{ui.userMessage}</View>;
  }
  if (isTimedOut) {
    return <View className="error-view">分析超时，请重试</View>;
  }
  if (!result || result.status === 'queued' || result.status === 'processing') {
    return <ProgressIndicator currentStep={result?.status === 'processing' ? 2 : 1} />;
  }
  if (result.status === 'failed') {
    const ui = mapApiError({ ...result.error, ...{ name: 'ApiError' } } as any);
    return <View className="error-view">{result.error?.user_message ?? '分析失败'}</View>;
  }

  // succeeded
  const report = result.report!;
  return (
    <View className="report-page">
      <PlainWarningCard text={report.plain_warning} severity={report.overall_severity} />
      <View className="summary">{report.summary}</View>
      {sortBySeverity(report.hazards).map((h, idx) => (
        <HazardCard hazard={h} key={`${h.category_code}-${idx}`} />
      ))}
    </View>
  );
}
```

**Tests:** 页面集成测试 Taro 环境 mock 复杂，**T8 不写测试**（按 brainstorm 决策 scope=api+hooks+utils+components）；交由 T9 微信开发者工具手动验证。

**Commit:**
```
feat: Task 8 — 首页（拍照 + 上传 + 跳转）+ 报告页（轮询 + 状态机渲染）
```

---

## Task 9: Phase 3 退出门验证 [混合]

**Files:** 无修改，只检查。

**Step 1: 单元测试全跑**

```bash
cd miniprogram && pnpm test
```

Expected: 全 passed、**0 failed**、**0 skipped**。

**Step 2: 静态检查**

```bash
cd miniprogram && pnpm lint
```

Expected: 0 错。

**Step 3: 后端测试仍维持**

```bash
cd backend && .venv/Scripts/python -m pytest
```

Expected: 87 passed（T0 错误 shape 修改后断言改了，但数字不变）。

**Step 4: 微信开发者工具手动验证**

1. `cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload` 起后端
2. `cd miniprogram && pnpm dev:weapp` 起编译 watch
3. 打开微信开发者工具，导入 `miniprogram/` 目录
4. 点首页"拍隐患"大按钮 → 选 `backend/tests/fixtures/images/case_001_*.jpg`
5. 等待 ~60-90s 看报告页是否正确渲染 H1 高处坠落 + 整改建议
6. 测一遍异常路径：故意上传 PDF → 应当 Toast"图片格式不支持..."

**Step 5: 总结追加到 prompt-poc-notes.md（？或专门 phase3 报告）**

可在 `docs/specs/prompt-poc-notes.md` 末尾追加 `§ Phase 3 退出门总结`：

```markdown
## § Phase 3 退出门总结（2026-05-DD）

- 单元 + 集成测试：miniprogram pnpm test → N/0/0；backend pytest → 87/0/0
- ruff + mypy + eslint 全 clean
- 微信开发者工具手动验证：1 张图端到端 ✅
- 异常路径手动验证：✅
- 累计 commit：N 个
- 带入 Phase 4 的问题：……
```

**Step 6: PR**

```bash
git push -u origin feat/phase-3-miniprogram
gh pr create --title "Phase 3 Miniprogram: Taro 工程 + 拍照页 + 报告轮询页" --body ...
```

---

## Phase 3 完成标准

- ✅ 10 个 task 全完成（T0 后端、T1-T8 前端、T9 手工验证）
- ✅ `cd miniprogram && pnpm test` → 0 failed / 0 skipped
- ✅ `cd miniprogram && pnpm lint` → 0 错
- ✅ `cd backend && pytest` → 仍 87/0/0
- ✅ 微信开发者工具跑通 1 张图端到端 + 1 个异常路径
- ✅ ApiError 归一、错误码 → UI 映射在 utils/errorMessage 集中

## Phase 3 不在本计划内的事

- 上架微信小程序审核（Phase 4）
- 多端编译（H5 / RN / 抖音小程序）
- 历史记录 / 导出功能
- 用户登录 / 工地维度（MVP 无）
- 业务监控 / 报表（Phase 4+）
- 设计师定稿视觉（自撸组件用最小可看版）
- E2E 自动化测试

## 风险与回退

| 风险 | 触发 | 回退 |
| --- | --- | --- |
| Taro 4.x 与 NutUI-React-Taro 兼容性 | T1 / T7 编译失败 | 退回 Taro 3.6.x + NutUI 2.x；架构层不变 |
| `Taro.chooseMedia` 在新版微信开发者工具行为变化 | T9 手动验证拍照失败 | 退回 `Taro.chooseImage`（deprecated 但稳）+ 加 toast 提示 |
| jest + ts-jest + Taro mock 互相打架 | T1 起测试跑不起来 | 把 setup.ts 里的 mock 改用 `__mocks__/@tarojs/taro.ts` 文件模拟 |
| 微信开发者工具 CORS / 域名白名单 | T9 调本机 8000 被拦 | 工具"详情 → 本地设置 → 不校验合法域名"勾上 |
| 前端 fetch 后端 60-260s 仍超时 | T9 真实工地照 → 超 timeout_ms | 临时调大 `DEFAULT_TIMEOUT_MS`；架构层 Settings.timeout_ms 已 = 330000 |
| H2 物体打击丢失（Phase 2 carryover） | T9 跑 case_002 时 | 不阻塞退出；记 Phase 4 prompt v3 时再补 |
