# PC Web UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use @superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 safety-scout 项目落地独立 PC web 端 UI（pages/index + pages/report 两页桌面变体），与移动 H5 / weapp 并存，零行为变化地切到 desktop 布局。

**Architecture:** Page-level dispatcher 模式 —— 每个 `pages/*/index.tsx` 退化为 dispatcher，通过 `useIsDesktop()` hook 选择渲染 `MobileXxx` 或 `DesktopXxx`。检测走 `window.matchMedia('(min-width: 1024px)')` + resize 监听，weapp 端永远返回 `false`（hook 内 `process.env.TARO_ENV` 守卫）。整页切换而不是 CSS 媒体查询 —— 桌面与移动的 DOM 结构差异过大。

**Tech Stack:** Taro 4 + React 18 + TypeScript + SCSS modules + Jest (jsdom) + Playwright (E2E)

**Design doc:** [`docs/plans/2026-05-21-pc-web-ui-design.md`](./2026-05-21-pc-web-ui-design.md)

**Feedback memory 约束：** 每个 phase 必须 ship 通过的单元测试，0 skipped 0 failed —— 否则不算完成。

**Sub-skills to reference while executing:**
- @superpowers:test-driven-development —— 每个 task 都是 TDD 一轮（红→绿→提交）
- @superpowers:verification-before-completion —— 标 task 完成前必须跑测试看输出
- @superpowers:systematic-debugging —— 卡住时用，不要瞎改

---

## 关键技术约束（先读再写）

1. **SCSS modules 在 jest 里是 `{}`** —— `tests/styleMock.cjs` 把所有 `*.module.scss` import 替换为空对象。所以 **测试断言不能用 `styles.foo` className**，只能用文案 / `role` / `aria-*` / `data-testid` 查询。
2. **`@tarojs/components` 在 jest 里被桥接为 div/span** —— 见 `tests/setup.ts`，`<View>` 渲染成 `<div>`、`<Text>` 渲染成 `<span>`，原 props 透传。
3. **`@tarojs/taro` 在 jest 里完全 mock** —— `Taro.uploadFile / request / chooseMedia / navigateTo / showToast / useRouter` 都是 `jest.fn()`，测试里 `mockImplementation` / `mockReset`。
4. **`process.env.TARO_ENV` 在 jest 里默认 undefined** —— 编译期 Taro webpack DefinePlugin 才会替换为 `'h5'` / `'weapp'`。`useIsDesktop` 测试需要在 `beforeEach` 里手动 `process.env.TARO_ENV = 'h5'`。
5. **jsdom 不提供 `window.matchMedia`** —— `useIsDesktop` 测试必须 mock `window.matchMedia`。

---

## Task 0: 准备工作

**Step 1: 确认起点干净**

Run from repo root:
```
cd D:/workspace/tiktok/safety-scout
git status
```

Expected: 当前分支 `feat/phase-3-miniprogram`。如有 Doubao provider 改动（来自上一个会话）未提交，先单独 commit 或 stash —— 它们与 PC web 工作正交。

**Step 2: 全量基线测试 ✅ 通过**

```
cd miniprogram
pnpm test
```

Expected: 全部测试通过（基线）。如有失败先修，否则后续无法判断"是新代码引入的回归还是原本就坏"。

**Step 3: 开新工作分支**

```
git checkout -b feat/pc-web-ui
```

---

## Task 1: `useIsDesktop` hook + 单测

**Files:**
- Create: `miniprogram/src/hooks/useIsDesktop.ts`
- Create: `miniprogram/tests/hooks/useIsDesktop.test.ts`
- Modify: `miniprogram/tests/setup.ts` —— 加 `process.env.TARO_ENV` 默认值与 `window.matchMedia` 全局 stub

**Step 1: 改 jest setup 注入 TARO_ENV 与 matchMedia 默认值**

Modify `miniprogram/tests/setup.ts`，在文件末尾追加：

```typescript
// 编译期 Taro DefinePlugin 会把 process.env.TARO_ENV 替换为字面量；
// 测试期手动注入 'h5'，让走 H5 分支的逻辑可测。
// 单测要测 weapp 分支时在自己 beforeEach 里覆盖。
process.env.TARO_ENV = process.env.TARO_ENV ?? 'h5';

// jsdom 不实现 matchMedia；给一个不匹配的默认 stub。
// useIsDesktop 测试在 beforeEach 里重写它来注入特定行为。
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
}
```

**Step 2: 写失败的单测**

Create `miniprogram/tests/hooks/useIsDesktop.test.ts`:

```typescript
/**
 * 单元测试：useIsDesktop hook.
 *
 * 验收要点：
 * - h5 环境下读 matchMedia.matches 作为初值
 * - h5 环境下 MQ change 事件触发 state 更新
 * - h5 环境下 unmount 时移除 listener
 * - 非 h5 环境（weapp）直接返回 false，不调用 matchMedia
 */
import { renderHook, act } from '@testing-library/react';

import { useIsDesktop } from '../../src/hooks/useIsDesktop';

interface MqStub {
  matches: boolean;
  addEventListener: jest.Mock;
  removeEventListener: jest.Mock;
  _handler?: (e: { matches: boolean }) => void;
}

function makeMqStub(matches: boolean): MqStub {
  const stub: MqStub = {
    matches,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  };
  stub.addEventListener.mockImplementation((evt: string, h: (e: { matches: boolean }) => void) => {
    if (evt === 'change') stub._handler = h;
  });
  return stub;
}

describe('useIsDesktop', () => {
  let originalTaroEnv: string | undefined;

  beforeEach(() => {
    originalTaroEnv = process.env.TARO_ENV;
    process.env.TARO_ENV = 'h5';
  });

  afterEach(() => {
    process.env.TARO_ENV = originalTaroEnv;
  });

  it('returns matchMedia.matches at mount in h5', () => {
    const mq = makeMqStub(true);
    window.matchMedia = jest.fn().mockReturnValue(mq) as unknown as typeof window.matchMedia;
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(true);
  });

  it('returns false at mount when matchMedia is false', () => {
    const mq = makeMqStub(false);
    window.matchMedia = jest.fn().mockReturnValue(mq) as unknown as typeof window.matchMedia;
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(false);
  });

  it('updates state when MediaQueryList emits change', () => {
    const mq = makeMqStub(false);
    window.matchMedia = jest.fn().mockReturnValue(mq) as unknown as typeof window.matchMedia;
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(false);

    act(() => {
      mq._handler?.({ matches: true });
    });
    expect(result.current).toBe(true);
  });

  it('removes the change listener on unmount', () => {
    const mq = makeMqStub(false);
    window.matchMedia = jest.fn().mockReturnValue(mq) as unknown as typeof window.matchMedia;
    const { unmount } = renderHook(() => useIsDesktop());
    unmount();
    expect(mq.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('returns false in weapp without calling matchMedia', () => {
    process.env.TARO_ENV = 'weapp';
    const spy = jest.fn();
    window.matchMedia = spy as unknown as typeof window.matchMedia;
    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(false);
    expect(spy).not.toHaveBeenCalled();
  });
});
```

**Step 3: 运行测试看它失败**

```
cd miniprogram
pnpm test -- --testPathPattern=useIsDesktop
```

Expected: FAIL —— `Cannot find module '../../src/hooks/useIsDesktop'` 或类似。

**Step 4: 实现 hook**

Create `miniprogram/src/hooks/useIsDesktop.ts`:

```typescript
/**
 * 视口检测 hook —— 返回当前是否处于桌面布局 (>=1024px)。
 *
 * 行为契约：
 * - process.env.TARO_ENV !== 'h5' → 始终返回 false（weapp 永不进桌面分支，
 *   且这样能让 dispatcher 里的桌面组件 import 在 weapp 包里成为 dead code，
 *   webpack 可 tree-shake 掉绝大部分）
 * - h5 端读 window.matchMedia('(min-width: 1024px)') 作为初值，并监听 change
 *   事件响应窗口缩放
 *
 * 不用 UA 检测：UA 字符串无法响应运行时窗口缩放（用户拖窗口大小），
 * 而 matchMedia 是浏览器原生的"视口已变化"信号。
 */
import { useEffect, useState } from 'react';

const DESKTOP_MQ = '(min-width: 1024px)';

export function useIsDesktop(): boolean {
  // process.env.TARO_ENV 在编译期被 Taro webpack DefinePlugin 替换为字面量字符串
  // ('h5' / 'weapp')。weapp 端这个表达式是 false 字面量，下面的 useState 初值函数与
  // useEffect 都按 isH5 = false 跑，matchMedia 永不被调用 —— 即便 weapp 没有
  // window.matchMedia API 也不会报错。
  const isH5 = process.env.TARO_ENV === 'h5';

  const [isDesktop, setIsDesktop] = useState<boolean>(() => {
    if (!isH5) return false;
    if (typeof window === 'undefined') return false;
    return window.matchMedia(DESKTOP_MQ).matches;
  });

  useEffect(() => {
    if (!isH5) return;
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia(DESKTOP_MQ);
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [isH5]);

  return isDesktop;
}
```

**Step 5: 运行测试看它通过**

```
pnpm test -- --testPathPattern=useIsDesktop
```

Expected: PASS（5 个用例全过）。

**Step 6: 全量回归**

```
pnpm test
```

Expected: 全部通过，0 skipped。

**Step 7: Commit**

```
git add miniprogram/src/hooks/useIsDesktop.ts \
        miniprogram/tests/hooks/useIsDesktop.test.ts \
        miniprogram/tests/setup.ts
git commit -m "feat(miniprogram): useIsDesktop hook + jest matchMedia stub

H5 端读 matchMedia('(min-width: 1024px)') 并监听 change；
weapp 端守卫住直接返回 false 让桌面分支成为 dead code。"
```

---

## Task 2: 拆 `pages/index` 为 dispatcher + mobile（零行为变化）

**目标：** 把 `pages/index/index.tsx` 现有内容原封不动搬到 `mobile.tsx`，新建 `index.tsx` 作 dispatcher（先让桌面分支也返回 mobile 内容，等 Task 5 再换成 DesktopIndex）。该 task 完成后跑 e2e 应当与之前完全一致。

**Files:**
- Modify: `miniprogram/src/pages/index/index.tsx` → 改成 dispatcher
- Create: `miniprogram/src/pages/index/mobile.tsx` → 现 index.tsx 内容
- Rename: `miniprogram/src/pages/index/index.module.scss` → `mobile.module.scss`
- 若有现成 `index.test.tsx` 需更新 import 路径

**Step 1: 备份现内容然后做文件重排**

读出 `miniprogram/src/pages/index/index.tsx` 全文。

`git mv` 重命名样式表：
```
git mv miniprogram/src/pages/index/index.module.scss miniprogram/src/pages/index/mobile.module.scss
```

把原 `index.tsx` 内容（默认导出函数原名 `IndexPage`）写入新文件 `miniprogram/src/pages/index/mobile.tsx`，并：
- 把组件名从 `IndexPage` 改为 `MobileIndex`
- import 路径 `./index.module.scss` 改为 `./mobile.module.scss`
- export `default function MobileIndex(...)`

**Step 2: 写新 dispatcher**

Overwrite `miniprogram/src/pages/index/index.tsx`:

```typescript
/**
 * pages/index dispatcher —— 根据视口宽度选择移动或桌面变体。
 *
 * weapp 端 useIsDesktop 始终返回 false，DesktopIndex import 在 weapp webpack
 * 构建中被 dead-code 处理（实测多 10-20KB，可接受；详见 design §3）。
 */
import { useIsDesktop } from '../../hooks/useIsDesktop';
import MobileIndex from './mobile';
import DesktopIndex from './desktop';

export default function IndexPage() {
  const isDesktop = useIsDesktop();
  return isDesktop ? <DesktopIndex /> : <MobileIndex />;
}
```

**Step 3: 创建 DesktopIndex 占位**

Create `miniprogram/src/pages/index/desktop.tsx` —— 临时返回与 mobile 完全等价的内容，让 dispatcher 能编译通过。先复用 MobileIndex 即可：

```typescript
/**
 * DesktopIndex 占位 —— 桌面布局将在 Task 5 实现，
 * 现阶段直接复用 MobileIndex 让 dispatcher 通编译并保持零行为变化。
 */
import MobileIndex from './mobile';

export default function DesktopIndex() {
  return <MobileIndex />;
}
```

**Step 4: 编译 + 单测 + e2e 验证零行为变化**

```
pnpm test
```

Expected: 全部通过（mobile.tsx 与原 index.tsx 内容相同，组件测试不需要改）。

```
pnpm build:h5:dev
```

Expected: build 成功，无 import 错误。

**Step 5: Commit**

```
git add miniprogram/src/pages/index/
git commit -m "refactor(miniprogram): split pages/index into dispatcher + mobile variant

Pure rearrangement — index.tsx 变 dispatcher，原内容搬到 mobile.tsx，
DesktopIndex 占位先复用 mobile。零行为变化，为 Task 5 桌面布局做准备。"
```

---

## Task 3: 拆 `pages/report` 为 dispatcher + mobile（同 Task 2 套路）

**Files:**
- Modify: `miniprogram/src/pages/report/index.tsx` → 改成 dispatcher
- Create: `miniprogram/src/pages/report/mobile.tsx`
- Rename: `miniprogram/src/pages/report/index.module.scss` → `mobile.module.scss`
- Create: `miniprogram/src/pages/report/desktop.tsx`（占位复用 mobile）

按 Task 2 完全相同的流程：先重命名 SCSS、原 tsx 内容搬到 mobile.tsx 改组件名为 `MobileReport`、新建 dispatcher / desktop 占位。

**Step 1-4: 重复 Task 2 步骤**（针对 report）

**Step 5: 跑测试**

```
pnpm test
pnpm build:h5:dev
```

Expected: 全部通过、build 成功。

**Step 6: Commit**

```
git add miniprogram/src/pages/report/
git commit -m "refactor(miniprogram): split pages/report into dispatcher + mobile variant"
```

---

## Task 4: `createInspection` 接受 `File`

**Files:**
- Modify: `miniprogram/src/api/inspections.ts`
- Modify: `miniprogram/tests/api/inspections.test.ts`

**Step 1: 写失败的新单测**

在 `miniprogram/tests/api/inspections.test.ts` 现有 describe block 后追加：

```typescript
describe('api/inspections.createInspection — File input (desktop H5)', () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('uses FormData + fetch when given a File, resolves on 2xx', async () => {
    const payload = {
      inspection_id: 'desk-1',
      poll_url: '/api/v1/inspections/desk-1',
      poll_interval_ms: 2000,
      timeout_ms: 330_000,
      status: 'queued',
    };
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const file = new File([new Uint8Array([0xff, 0xd8, 0xff])], 'photo.jpg', {
      type: 'image/jpeg',
    });
    const res = await createInspection(file);
    expect(res).toEqual(payload);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe(API_BASE_URL + '/api/v1/inspections');
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get('image')).toBeInstanceOf(File);
  });

  it('rejects ApiError with server error code on 4xx', async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({
        error: {
          code: 'INVALID_IMAGE',
          message: 'bad mime',
          user_message: '图片格式不支持',
        },
      }),
      text: async () => '{}',
    }) as unknown as typeof globalThis.fetch;

    const file = new File([new Uint8Array([0])], 'x.bin', { type: 'application/octet-stream' });
    await expect(createInspection(file)).rejects.toMatchObject({
      name: 'ApiError',
      code: 'INVALID_IMAGE',
      statusCode: 400,
    });
  });

  it('rejects NETWORK_ERROR on fetch reject', async () => {
    globalThis.fetch = jest.fn().mockRejectedValue(new Error('boom')) as unknown as typeof globalThis.fetch;
    const file = new File([new Uint8Array([0])], 'x.jpg', { type: 'image/jpeg' });
    await expect(createInspection(file)).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
      statusCode: 0,
    });
  });
});
```

**Step 2: 运行测试看它失败**

```
pnpm test -- --testPathPattern=inspections
```

Expected: 新 3 个用例 FAIL（`createInspection(file)` 签名不匹配 / 调 uploadFile 而不是 fetch）。原有 5 个用例仍 PASS（向后兼容）。

**Step 3: 改实现**

Modify `miniprogram/src/api/inspections.ts`:

```typescript
/**
 * Safety Scout API：POST 创建巡检任务 / GET 查询任务状态。
 *
 * createInspection 接受两种入参：
 * - string (Taro tempFilePath)：走 Taro.uploadFile —— 移动端 / weapp 路径
 * - File (浏览器原生)：走 FormData + fetch —— 桌面 H5 通过 <input type="file"> 拿到的对象
 *
 * 两条路径返回相同形状的 CreateInspectionResponse，错误统一归一为 ApiError。
 */
import Taro from '@tarojs/taro';
import { API_BASE_URL } from '../config';
import { ApiError, request } from './client';
import type {
  CreateInspectionResponse,
  GetInspectionResponse,
  ErrorBody,
} from '../types/inspection';

export function createInspection(
  input: string | File,
): Promise<CreateInspectionResponse> {
  if (typeof input === 'string') {
    return createFromTempFilePath(input);
  }
  return createFromFile(input);
}

function createFromTempFilePath(
  imageTempFilePath: string,
): Promise<CreateInspectionResponse> {
  return new Promise((resolve, reject) => {
    Taro.uploadFile({
      url: API_BASE_URL + '/api/v1/inspections',
      filePath: imageTempFilePath,
      name: 'image',
      success: (res) => {
        let body: unknown = null;
        try {
          body = JSON.parse(res.data);
        } catch {
          // body 不是 JSON，下面统一用 fallback 文案
        }
        if (res.statusCode >= 400) {
          const err = (body as { error?: ErrorBody } | null)?.error;
          reject(
            new ApiError(
              err?.code ?? 'UPLOAD_FAILED',
              err?.user_message ?? '图片上传失败，请重试',
              res.statusCode,
            ),
          );
          return;
        }
        resolve(body as CreateInspectionResponse);
      },
      fail: () =>
        reject(new ApiError('NETWORK_ERROR', '网络异常，请检查后重试', 0)),
    });
  });
}

async function createFromFile(file: File): Promise<CreateInspectionResponse> {
  const form = new FormData();
  form.append('image', file);

  let resp: Response;
  try {
    resp = await fetch(API_BASE_URL + '/api/v1/inspections', {
      method: 'POST',
      body: form,
    });
  } catch {
    throw new ApiError('NETWORK_ERROR', '网络异常，请检查后重试', 0);
  }

  if (!resp.ok) {
    let body: { error?: ErrorBody } | null = null;
    try {
      body = (await resp.json()) as { error?: ErrorBody };
    } catch {
      // 非 JSON body，用 fallback
    }
    throw new ApiError(
      body?.error?.code ?? 'UPLOAD_FAILED',
      body?.error?.user_message ?? '图片上传失败，请重试',
      resp.status,
    );
  }
  return (await resp.json()) as CreateInspectionResponse;
}

export function getInspection(id: string): Promise<GetInspectionResponse> {
  return request<GetInspectionResponse>({
    url: `/api/v1/inspections/${id}`,
    method: 'GET',
  });
}
```

**Step 4: 运行测试看新旧用例都通过**

```
pnpm test -- --testPathPattern=inspections
```

Expected: 8 个用例（5 原有 + 3 新增）全 PASS。

**Step 5: 全量回归**

```
pnpm test
```

Expected: 全部通过、0 skipped。

**Step 6: Commit**

```
git add miniprogram/src/api/inspections.ts \
        miniprogram/tests/api/inspections.test.ts
git commit -m "feat(miniprogram): createInspection accepts File for desktop H5

string (Taro tempFilePath) 路径不变；新增 File 入参走 fetch + FormData，
为桌面 UploadDropzone 准备。错误归一仍是 ApiError。"
```

---

## Task 5: `UploadDropzone` 组件 + 单测

**Files:**
- Create: `miniprogram/src/components/desktop/UploadDropzone/index.tsx`
- Create: `miniprogram/src/components/desktop/UploadDropzone/index.module.scss`
- Create: `miniprogram/tests/components/desktop/UploadDropzone.test.tsx`

**Step 1: 写失败的单测**

Create `miniprogram/tests/components/desktop/UploadDropzone.test.tsx`:

```typescript
/**
 * 单元测试：UploadDropzone.
 *
 * 验收要点：
 * - idle 默认渲染中文 + Latin 副标题 + 拖拽提示
 * - 点击触发隐藏 <input type="file"> 的 click()
 * - 选择文件触发 onSelect(file)
 * - 拖入文件触发 onSelect(file) + 阻止默认浏览器行为
 * - dragover 触发 hover 视觉状态（aria-busy/data-state 检查，因 SCSS modules 在测试里是 {}）
 * - uploading 时不响应 click / drop
 */
import { fireEvent, render, screen } from '@testing-library/react';

import { UploadDropzone } from '../../../src/components/desktop/UploadDropzone';

function makeJpegFile(name = 'photo.jpg'): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff])], name, { type: 'image/jpeg' });
}

describe('UploadDropzone', () => {
  it('renders default idle copy', () => {
    render(<UploadDropzone onSelect={() => undefined} />);
    expect(screen.getByText(/拖拽图片/)).toBeInTheDocument();
    expect(screen.getByText(/CAPTURE INSPECTION PHOTO/i)).toBeInTheDocument();
  });

  it('calls onSelect when file picked via input change', () => {
    const fn = jest.fn();
    const { container } = render(<UploadDropzone onSelect={fn} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).not.toBeNull();

    const file = makeJpegFile();
    fireEvent.change(input, { target: { files: [file] } });
    expect(fn).toHaveBeenCalledWith(file);
  });

  it('triggers hidden input click when dropzone is clicked', () => {
    const fn = jest.fn();
    const { container } = render(<UploadDropzone onSelect={fn} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = jest.spyOn(input, 'click').mockImplementation(() => undefined);
    fireEvent.click(screen.getByRole('button'));
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it('calls onSelect when file is dropped', () => {
    const fn = jest.fn();
    render(<UploadDropzone onSelect={fn} />);
    const zone = screen.getByRole('button');
    const file = makeJpegFile();

    fireEvent.drop(zone, {
      dataTransfer: { files: [file], items: [{ kind: 'file', type: file.type, getAsFile: () => file }] },
    });
    expect(fn).toHaveBeenCalledWith(file);
  });

  it('sets aria-busy when uploading and ignores interactions', () => {
    const fn = jest.fn();
    const { container } = render(<UploadDropzone onSelect={fn} uploading />);
    const zone = screen.getByRole('button');
    expect(zone).toHaveAttribute('aria-busy', 'true');

    fireEvent.click(zone);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = jest.spyOn(input, 'click').mockImplementation(() => undefined);
    expect(clickSpy).not.toHaveBeenCalled();

    fireEvent.drop(zone, { dataTransfer: { files: [makeJpegFile()] } });
    expect(fn).not.toHaveBeenCalled();
  });

  it('toggles data-hover on dragenter/dragleave', () => {
    render(<UploadDropzone onSelect={() => undefined} />);
    const zone = screen.getByRole('button');
    fireEvent.dragEnter(zone);
    expect(zone).toHaveAttribute('data-hover', 'true');
    fireEvent.dragLeave(zone);
    expect(zone).toHaveAttribute('data-hover', 'false');
  });
});
```

**Step 2: 运行测试看失败**

```
pnpm test -- --testPathPattern=UploadDropzone
```

Expected: FAIL（找不到模块）。

**Step 3: 实现组件**

Create `miniprogram/src/components/desktop/UploadDropzone/index.tsx`:

```typescript
/**
 * 桌面 H5 上传组件：拖拽 + 点击触发 <input type="file">。
 *
 * 不复用 hooks/useImageCapture —— 它包装 Taro.chooseMedia，weapp 用；桌面浏览器
 * 直接用原生 <input> + DataTransfer 体验更好且无 Taro 依赖。
 *
 * 状态：
 * - idle：默认提示文案
 * - hover：拖拽悬停（data-hover='true'）—— SCSS 用 [data-hover='true'] 选择器变色
 * - uploading：禁用交互 + aria-busy='true'
 */
import { useRef, useState } from 'react';
import { View, Text } from '@tarojs/components';

import { Icon } from '../../Icon';

import styles from './index.module.scss';

export interface UploadDropzoneProps {
  /** 用户选/拖完文件后回调；调用方负责调 createInspection 与 navigate。 */
  onSelect: (file: File) => void;
  /** 上传进行中：禁用点击与拖放，UI 灰态。 */
  uploading?: boolean;
}

export function UploadDropzone({ onSelect, uploading = false }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [hover, setHover] = useState(false);

  const trigger = () => {
    if (uploading) return;
    inputRef.current?.click();
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setHover(false);
    if (uploading) return;
    const f = e.dataTransfer?.files?.[0];
    if (f) onSelect(f);
  };

  return (
    <View
      className={styles.zone}
      role="button"
      aria-busy={uploading}
      data-hover={hover}
      onClick={trigger}
      onDragEnter={(e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setHover(true);
      }}
      onDragOver={(e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
      }}
      onDragLeave={(e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setHover(false);
      }}
      onDrop={handleDrop}
    >
      <View className={styles.icon}>
        <Icon name="plus-square" size={56} color="#1A1A1A" />
      </View>
      <Text className={styles.label}>
        {uploading ? '上传中...' : '拖拽图片到此 / 点击选择文件'}
      </Text>
      <Text className={styles.sublabel}>
        {uploading ? 'PROCESSING' : 'CAPTURE INSPECTION PHOTO'}
      </Text>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onSelect(f);
          // 清空 value 让选同一文件能再次触发 change
          e.target.value = '';
        }}
      />
    </View>
  );
}
```

Create `miniprogram/src/components/desktop/UploadDropzone/index.module.scss`:

```scss
// UploadDropzone —— dossier paper aesthetic 的桌面上传区。
// data-hover='true' 由 React 设置；hover 状态边框变 eng-red、背景轻微高亮。

.zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-5) var(--space-3);
  border: 2px dashed var(--color-charcoal);
  background-color: var(--color-paper);
  cursor: pointer;
  user-select: none;
  transition: border-color 120ms ease, background-color 120ms ease;
  min-height: 280px;
}

.zone[data-hover='true'] {
  border-color: var(--color-eng-red);
  background-color: rgba(200, 40, 28, 0.04);
}

.zone[aria-busy='true'] {
  cursor: progress;
  opacity: 0.6;
}

.icon {
  margin-bottom: var(--space-1);
}

.label {
  font-family: var(--font-body);
  font-size: 18px;
  color: var(--color-charcoal);
  letter-spacing: 1px;
}

.sublabel {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-caliper-grey);
  letter-spacing: 3px;
}
```

**Step 4: 运行测试看通过**

```
pnpm test -- --testPathPattern=UploadDropzone
```

Expected: 6 个用例 PASS。

**Step 5: 全量回归**

```
pnpm test
```

Expected: 全部通过、0 skipped。

**Step 6: Commit**

```
git add miniprogram/src/components/desktop/UploadDropzone/ \
        miniprogram/tests/components/desktop/UploadDropzone.test.tsx
git commit -m "feat(miniprogram): UploadDropzone component for desktop H5

拖拽 + 点击触发 <input type=file>；hover/uploading 状态；
不依赖 Taro.chooseMedia，纯 HTML5 实现，weapp 端不会用到。"
```

---

## Task 6: 实现 `DesktopIndex` + dispatcher 接入

**Files:**
- Rewrite: `miniprogram/src/pages/index/desktop.tsx`（Task 2 留的占位）
- Create: `miniprogram/src/pages/index/desktop.module.scss`
- Create: `miniprogram/tests/pages/DesktopIndex.test.tsx`

**Step 1: 写失败的页面测试**

Create `miniprogram/tests/pages/DesktopIndex.test.tsx`:

```typescript
/**
 * 单元测试：DesktopIndex 页面.
 *
 * 验收要点：
 * - 渲染上传区（UploadDropzone）+ 拍摄要点 + AI 引擎元信息
 * - 上传文件后调 createInspection 并 Taro.navigateTo 跳报告页
 * - 上传失败时 Taro.showToast 展示 user_message
 *
 * createInspection 用 jest.mock 替换，避免真的发请求。
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Taro from '@tarojs/taro';

import DesktopIndex from '../../src/pages/index/desktop';

jest.mock('../../src/api/inspections', () => ({
  createInspection: jest.fn(),
}));

import { createInspection } from '../../src/api/inspections';

const mockedCreate = createInspection as unknown as jest.Mock;
const mockedNavigate = Taro.navigateTo as unknown as jest.Mock;
const mockedToast = Taro.showToast as unknown as jest.Mock;

function makeFile(): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff])], 'photo.jpg', { type: 'image/jpeg' });
}

describe('DesktopIndex', () => {
  beforeEach(() => {
    mockedCreate.mockReset();
    mockedNavigate.mockReset();
    mockedToast.mockReset();
  });

  it('renders dropzone + 拍摄要点 list + AI 引擎 footer', () => {
    render(<DesktopIndex />);
    expect(screen.getByText('工地隐患识别')).toBeInTheDocument();
    expect(screen.getByText(/AI · SITE HAZARD INSPECTION/)).toBeInTheDocument();
    expect(screen.getByText(/拍摄要点/)).toBeInTheDocument();
    expect(screen.getByText(/贴近隐患位置/)).toBeInTheDocument();
    expect(screen.getByText(/AI ENGINE/)).toBeInTheDocument();
    expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'false');
  });

  it('navigates to report on successful upload', async () => {
    mockedCreate.mockResolvedValueOnce({
      inspection_id: 'desk-1',
      poll_url: '/api/v1/inspections/desk-1',
      poll_interval_ms: 2000,
      timeout_ms: 330_000,
      status: 'queued',
    });
    const { container } = render(<DesktopIndex />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile()] } });

    await waitFor(() => expect(mockedCreate).toHaveBeenCalledTimes(1));
    expect(mockedCreate).toHaveBeenCalledWith(expect.any(File));
    await waitFor(() => expect(mockedNavigate).toHaveBeenCalledTimes(1));
    const navArg = mockedNavigate.mock.calls[0][0];
    expect(navArg.url).toMatch(/^\/pages\/report\/index\?id=desk-1/);
  });

  it('shows toast on upload error', async () => {
    const err = Object.assign(new Error('boom'), {
      name: 'ApiError',
      code: 'INVALID_IMAGE',
      userMessage: '图片格式不支持',
      statusCode: 400,
    });
    mockedCreate.mockRejectedValueOnce(err);
    const { container } = render(<DesktopIndex />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile()] } });

    await waitFor(() => expect(mockedToast).toHaveBeenCalledTimes(1));
    const arg = mockedToast.mock.calls[0][0];
    expect(arg.title).toContain('图片格式不支持');
  });
});
```

**Step 2: 跑测试看失败**

```
pnpm test -- --testPathPattern=DesktopIndex
```

Expected: FAIL（desktop.tsx 还只是占位）。

**Step 3: 实现 DesktopIndex**

Overwrite `miniprogram/src/pages/index/desktop.tsx`:

```typescript
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { HeaderBand } from '../../components/HeaderBand';
import { UploadDropzone } from '../../components/desktop/UploadDropzone';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';

import styles from './desktop.module.scss';

const SHOT_TIPS = [
  '贴近隐患位置，保持光线充足',
  '画面含工人 / 护栏 / 电箱 等关键元素',
  '距离 1–3m 为佳',
];

export default function DesktopIndex() {
  const [uploading, setUploading] = useState(false);

  const handleFile = async (file: File) => {
    if (uploading) return;
    setUploading(true);
    try {
      const resp = await createInspection(file);
      Taro.navigateTo({
        url: `/pages/report/index?id=${resp.inspection_id}&pi=${resp.poll_interval_ms}&to=${resp.timeout_ms}`,
      });
    } catch (e) {
      const ui = mapApiError(e);
      Taro.showToast({ title: ui.userMessage, icon: 'none', duration: 3000 });
    } finally {
      setUploading(false);
    }
  };

  return (
    <View className={styles.page}>
      <HeaderBand subtitle="桌面端 · AI 30s 出报告" />

      <View className={styles.titleBlock}>
        <Text className={styles.h1}>工地隐患识别</Text>
        <Text className={styles.h1Latin}>AI · SITE HAZARD INSPECTION</Text>
      </View>

      <View className={styles.body}>
        <View className={styles.left}>
          <UploadDropzone onSelect={handleFile} uploading={uploading} />
        </View>

        <View className={styles.right}>
          <View className={styles.tipsCard}>
            <View className={styles.sectionRule}>
              <Text className={styles.sectionLabel}>拍摄要点</Text>
            </View>
            {SHOT_TIPS.map((tip, i) => (
              <View key={i} className={styles.tipRow}>
                <Text className={styles.tipIndex}>{String(i + 1).padStart(2, '0')}</Text>
                <Text className={styles.tipText}>{tip}</Text>
              </View>
            ))}
          </View>

          <View className={styles.engineCard}>
            <Text className={styles.engineLabel}>⌖ AI ENGINE v3</Text>
            <Text className={styles.engineText}>Claude / Doubao Vision · ~30s/帧</Text>
          </View>
        </View>
      </View>
    </View>
  );
}
```

Create `miniprogram/src/pages/index/desktop.module.scss`:

```scss
// DesktopIndex 桌面布局：左右分栏 60/40，整页 max-width 1200px 居中。
// 字号用 *-desktop 变量，不污染 tokens.scss。

:root {
  --fs-body-desktop: 16px;
  --fs-h1-desktop: 48px;
  --fs-eyebrow-desktop: 11px;
  --space-desktop-gutter: 48px;
}

.page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--space-desktop-gutter);
  background-color: var(--color-paper);
}

.titleBlock {
  padding: var(--space-5) 0 var(--space-3);
}

.h1 {
  display: block;
  font-family: var(--font-display);
  font-size: var(--fs-h1-desktop);
  font-weight: 700;
  letter-spacing: 6px;
  color: var(--color-charcoal);
  line-height: 1.1;
}

.h1Latin {
  display: block;
  margin-top: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow-desktop);
  font-weight: 400;
  letter-spacing: 4px;
  color: var(--color-caliper-grey);
}

.body {
  display: grid;
  grid-template-columns: 6fr 4fr;
  gap: var(--space-desktop-gutter);
  padding: var(--space-3) 0 var(--space-5);
}

.left {
  display: flex;
  align-items: stretch;
}

.right {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.tipsCard,
.engineCard {
  padding: var(--space-3);
  border: var(--border-charcoal);
  background-color: var(--color-paper);
}

.sectionRule {
  border-top: var(--border-charcoal);
  padding-top: var(--space-1);
  margin-bottom: var(--space-2);
}

.sectionLabel {
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow-desktop);
  letter-spacing: 3px;
  color: var(--color-charcoal);
}

.tipRow {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-1) 0;
}

.tipIndex {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--color-eng-red);
}

.tipText {
  font-size: var(--fs-body-desktop);
  color: var(--color-charcoal);
  line-height: 1.5;
}

.engineLabel {
  display: block;
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow-desktop);
  letter-spacing: 3px;
  color: var(--color-caliper-grey);
  margin-bottom: var(--space-1);
}

.engineText {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-charcoal);
  letter-spacing: 2px;
}
```

**Step 4: 跑测试看通过**

```
pnpm test -- --testPathPattern=DesktopIndex
```

Expected: 3 个用例 PASS。

**Step 5: 全量回归 + build 验证**

```
pnpm test
pnpm build:h5:dev
```

Expected: 全部通过 + build 成功。

**Step 6: 浏览器肉眼验证（@superpowers:verification-before-completion）**

```
pnpm serve:h5
```

打开 http://localhost:8080（端口看 serve-h5.mjs 输出），把窗口拉到 1440×900 看 DesktopIndex 是否：
- 左右分栏（左 60% dropzone / 右 40% 卡片）
- 标题字号明显比移动端小（fs-h1-desktop=48px）
- 拖一张图进 dropzone 边框变红
- 缩窗口到 <1024px 应当无缝切回 mobile 布局

**Step 7: Commit**

```
git add miniprogram/src/pages/index/desktop.tsx \
        miniprogram/src/pages/index/desktop.module.scss \
        miniprogram/tests/pages/DesktopIndex.test.tsx
git commit -m "feat(miniprogram): DesktopIndex page with dropzone + tips sidebar

左右分栏 60/40，max-width 1200px；上传走 createInspection(File) +
fetch + FormData，错误归一 toast 提示。"
```

---

## Task 7: `ReportSidebar` 组件 + 单测

**Files:**
- Create: `miniprogram/src/components/desktop/ReportSidebar/index.tsx`
- Create: `miniprogram/src/components/desktop/ReportSidebar/index.module.scss`
- Create: `miniprogram/tests/components/desktop/ReportSidebar.test.tsx`

**Step 1: 写失败的单测**

Create `miniprogram/tests/components/desktop/ReportSidebar.test.tsx`:

```typescript
/**
 * 单元测试：ReportSidebar.
 *
 * 验收要点：
 * - 渲染 'INSPECTION REPORT' eyebrow + 中文标题
 * - 渲染隐患数 + 风险等级
 * - 渲染 summary + plain_warning（plain_warning 可选）
 */
import { render, screen } from '@testing-library/react';

import { ReportSidebar } from '../../../src/components/desktop/ReportSidebar';
import type { ReportPayload } from '../../../src/types/report';

const SAMPLE: ReportPayload = {
  inspection_id: 'rep-1',
  created_at: '2026-05-21T10:00:00Z',
  plain_warning: '注意临边坠落',
  summary: '外架与楼梯间防护多处缺失',
  overall_severity: 'high',
  hazards: [],
  model_meta: { provider: 'claude_cli', model: 'sonnet', latency_ms: 30000 },
};

describe('ReportSidebar', () => {
  it('renders inspection report eyebrow + title', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={7} />);
    expect(screen.getByText(/INSPECTION REPORT/i)).toBeInTheDocument();
    expect(screen.getByText('现场巡检报告')).toBeInTheDocument();
  });

  it('renders hazard count + severity label', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={7} />);
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText(/项隐患待整改/)).toBeInTheDocument();
    expect(screen.getByText(/高风险/)).toBeInTheDocument();
  });

  it('renders summary + plain_warning when both present', () => {
    render(<ReportSidebar report={SAMPLE} hazardCount={7} />);
    expect(screen.getByText('外架与楼梯间防护多处缺失')).toBeInTheDocument();
    expect(screen.getByText('注意临边坠落')).toBeInTheDocument();
  });

  it('omits plain_warning element when empty', () => {
    const r = { ...SAMPLE, plain_warning: '' };
    render(<ReportSidebar report={r} hazardCount={3} />);
    expect(screen.queryByText('注意临边坠落')).not.toBeInTheDocument();
  });
});
```

**Step 2: 跑测试看失败**

```
pnpm test -- --testPathPattern=ReportSidebar
```

Expected: FAIL（模块找不到）。

**Step 3: 实现组件**

Create `miniprogram/src/components/desktop/ReportSidebar/index.tsx`:

```typescript
/**
 * 报告页桌面端左 sticky 侧栏：标题块 + 隐患数 + 风险等级 + 现场总览 + plain_warning.
 *
 * sticky 定位由父容器（DesktopReport）的 grid 配合 position:sticky 实现；本组件不
 * 自己 sticky，只负责内容编排。
 */
import { View, Text } from '@tarojs/components';

import { SEVERITY_LABEL, SEVERITY_COLOR } from '../../../utils/severity';
import type { ReportPayload } from '../../../types/report';

import styles from './index.module.scss';

export interface ReportSidebarProps {
  report: ReportPayload;
  hazardCount: number;
}

export function ReportSidebar({ report, hazardCount }: ReportSidebarProps) {
  const severity = report.overall_severity;
  return (
    <View className={styles.sidebar}>
      <View className={styles.titleBlock}>
        <Text className={styles.eyebrow}>INSPECTION REPORT</Text>
        <Text className={styles.title}>现场巡检报告</Text>
      </View>

      <View className={styles.hero}>
        <View className={styles.heroRow}>
          <Text
            className={styles.heroCount}
            style={{ color: SEVERITY_COLOR[severity] }}
          >
            {hazardCount}
          </Text>
          <Text className={styles.heroCountLabel}>项隐患待整改</Text>
        </View>
        <View className={styles.heroRow}>
          <Text
            className={styles.heroSeverity}
            style={{ color: SEVERITY_COLOR[severity] }}
          >
            {SEVERITY_LABEL[severity]}
          </Text>
          <Text className={styles.heroSeverityLabel}>风险等级判定</Text>
        </View>
      </View>

      <View className={styles.summarySection}>
        <View className={styles.summaryLabel}>
          <Text className={styles.summaryLabelBar}>▎</Text>
          <Text className={styles.summaryLabelText}>现场总览</Text>
        </View>
        <Text className={styles.summaryText}>{report.summary}</Text>
        {report.plain_warning && (
          <Text className={styles.warning}>{report.plain_warning}</Text>
        )}
      </View>
    </View>
  );
}
```

Create `miniprogram/src/components/desktop/ReportSidebar/index.module.scss`:

```scss
.sidebar {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  border: var(--border-charcoal);
  background-color: var(--color-paper);
}

.titleBlock {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 4px;
  color: var(--color-caliper-grey);
}

.title {
  font-family: var(--font-display);
  font-size: 32px;
  letter-spacing: 4px;
  color: var(--color-charcoal);
  line-height: 1.1;
}

.hero {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-top: var(--border-hairline);
  border-bottom: var(--border-hairline);
}

.heroRow {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.heroCount {
  font-family: var(--font-mono);
  font-size: 56px;
  font-weight: 700;
  line-height: 1;
}

.heroCountLabel,
.heroSeverityLabel {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 3px;
  color: var(--color-caliper-grey);
}

.heroSeverity {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 600;
}

.summarySection {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.summaryLabel {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
}

.summaryLabelBar {
  color: var(--color-eng-red);
  font-weight: 700;
}

.summaryLabelText {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 3px;
  color: var(--color-charcoal);
}

.summaryText {
  font-size: 15px;
  line-height: 1.6;
  color: var(--color-charcoal);
}

.warning {
  margin-top: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background-color: rgba(224, 123, 31, 0.08);
  border-left: 3px solid var(--color-warning-amber);
  color: var(--color-charcoal);
  font-size: 14px;
}
```

**Step 4: 跑测试看通过**

```
pnpm test -- --testPathPattern=ReportSidebar
```

Expected: 4 个用例 PASS。

**Step 5: 全量回归**

```
pnpm test
```

Expected: 全部通过。

**Step 6: Commit**

```
git add miniprogram/src/components/desktop/ReportSidebar/ \
        miniprogram/tests/components/desktop/ReportSidebar.test.tsx
git commit -m "feat(miniprogram): ReportSidebar component for desktop report page"
```

---

## Task 8: 实现 `DesktopReport` + dispatcher 接入

**Files:**
- Rewrite: `miniprogram/src/pages/report/desktop.tsx`（Task 3 留的占位）
- Create: `miniprogram/src/pages/report/desktop.module.scss`
- Create: `miniprogram/tests/pages/DesktopReport.test.tsx`

**Step 1: 写失败的单测**

Create `miniprogram/tests/pages/DesktopReport.test.tsx`:

```typescript
/**
 * 单元测试：DesktopReport 页面.
 *
 * 验收要点：
 * - 加载中 → 渲染 ProgressIndicator
 * - 失败 → ErrorView 等价文案
 * - 成功 → 渲染 ReportSidebar + HazardCard 列表
 */
import { render, screen, waitFor } from '@testing-library/react';
import Taro from '@tarojs/taro';

import DesktopReport from '../../src/pages/report/desktop';
import type { GetInspectionResponse } from '../../src/types/inspection';
import type { ReportPayload } from '../../src/types/report';

jest.mock('../../src/api/inspections', () => ({
  getInspection: jest.fn(),
}));
import { getInspection } from '../../src/api/inspections';

const mockedGet = getInspection as unknown as jest.Mock;
const mockedRouter = Taro.useRouter as unknown as jest.Mock;

const SAMPLE_REPORT: ReportPayload = {
  inspection_id: 'r-1',
  created_at: '2026-05-21T10:00:00Z',
  plain_warning: '注意临边',
  summary: '现场存在多处临边作业风险',
  overall_severity: 'high',
  hazards: [
    {
      category_code: 'H1',
      category_name: '高处坠落',
      description: '人字梯使用高度超过 2m',
      severity: 'high',
      regulation: '《建筑施工高处作业安全技术规范》JGJ80-2016 第 5.1.2 条',
      suggestion: '改用合规直梯或脚手架',
    },
    {
      category_code: 'H2',
      category_name: '物体打击',
      description: '外架与结构间无防护',
      severity: 'medium',
      regulation: 'JGJ130-2011 第 6.2.1 条',
      suggestion: '加挂密目网',
    },
  ],
  model_meta: { provider: 'claude_cli', model: 'sonnet', latency_ms: 30000 },
};

describe('DesktopReport', () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedRouter.mockReturnValue({ params: { id: 'r-1', pi: '2000', to: '60000' } });
  });

  it('renders ProgressIndicator while processing', async () => {
    const resp: GetInspectionResponse = {
      inspection_id: 'r-1',
      status: 'processing',
      created_at: '2026-05-21T10:00:00Z',
      updated_at: '2026-05-21T10:00:01Z',
      report: null,
      error: null,
    };
    mockedGet.mockResolvedValue(resp);
    render(<DesktopReport />);
    await waitFor(() => {
      // ProgressIndicator 在等待态的标志文案（来自现移动版报告页同款组件）
      expect(screen.getByText(/AI 分析中|正在为你生成报告|拍照成功/)).toBeInTheDocument();
    });
  });

  it('renders sidebar + hazard list when succeeded', async () => {
    const resp: GetInspectionResponse = {
      inspection_id: 'r-1',
      status: 'succeeded',
      created_at: '2026-05-21T10:00:00Z',
      updated_at: '2026-05-21T10:00:30Z',
      report: SAMPLE_REPORT,
      error: null,
    };
    mockedGet.mockResolvedValue(resp);
    render(<DesktopReport />);

    await waitFor(() => {
      expect(screen.getByText('现场巡检报告')).toBeInTheDocument();
    });
    expect(screen.getByText('2')).toBeInTheDocument(); // hazardCount
    expect(screen.getByText('高处坠落')).toBeInTheDocument();
    expect(screen.getByText('物体打击')).toBeInTheDocument();
  });

  it('renders ErrorView on failed status', async () => {
    const resp: GetInspectionResponse = {
      inspection_id: 'r-1',
      status: 'failed',
      created_at: '2026-05-21T10:00:00Z',
      updated_at: '2026-05-21T10:00:30Z',
      report: null,
      error: {
        code: 'LLM_TIMEOUT',
        message: 'timed out',
        user_message: 'AI 分析超时，请稍后重试',
      },
    };
    mockedGet.mockResolvedValue(resp);
    render(<DesktopReport />);
    await waitFor(() => {
      expect(screen.getByText(/AI 分析超时|请稍后重试/)).toBeInTheDocument();
    });
  });
});
```

**Step 2: 跑测试看失败**

```
pnpm test -- --testPathPattern=DesktopReport
```

Expected: FAIL（desktop.tsx 还只是占位）。

**Step 3: 实现 DesktopReport**

Overwrite `miniprogram/src/pages/report/desktop.tsx`:

```typescript
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';

import { usePolling } from '../../hooks/usePolling';
import { getInspection } from '../../api/inspections';
import { HazardCard } from '../../components/HazardCard';
import { HeaderBand } from '../../components/HeaderBand';
import { Icon } from '../../components/Icon';
import { ProgressIndicator } from '../../components/ProgressIndicator';
import { ReportSidebar } from '../../components/desktop/ReportSidebar';
import { sortBySeverity } from '../../utils/severity';
import { mapApiError } from '../../utils/errorMessage';
import { ApiError } from '../../api/client';
import { DEFAULT_POLL_INTERVAL_MS, DEFAULT_TIMEOUT_MS } from '../../config';
import type { GetInspectionResponse } from '../../types/inspection';
import type { ReportPayload } from '../../types/report';

import styles from './desktop.module.scss';

export default function DesktopReport() {
  const router = Taro.useRouter();
  const id = router.params.id ?? '';
  const intervalMs = Number(router.params.pi) || DEFAULT_POLL_INTERVAL_MS;
  const timeoutMs = Number(router.params.to) || DEFAULT_TIMEOUT_MS;

  const { result, error, elapsedMs, isTimedOut } = usePolling<GetInspectionResponse>({
    fetch: () => getInspection(id),
    intervalMs,
    timeoutMs,
    stopWhen: (r) => r.status === 'succeeded' || r.status === 'failed',
  });

  if (error) {
    const ui = mapApiError(error);
    return <DesktopErrorView userMessage={ui.userMessage} allowRetry={ui.allowRetry} />;
  }

  if (isTimedOut) {
    return <DesktopErrorView userMessage="AI 分析超时，请重试" allowRetry />;
  }

  if (!result || result.status === 'queued' || result.status === 'processing') {
    const step = result?.status === 'processing' ? 2 : 1;
    return (
      <View className={styles.centered}>
        <ProgressIndicator currentStep={step} elapsedMs={elapsedMs} />
      </View>
    );
  }

  if (result.status === 'failed') {
    const err = result.error;
    const fakeApiError = new ApiError(
      err?.code ?? 'INTERNAL',
      err?.user_message ?? '分析失败，请重试',
      500,
    );
    const ui = mapApiError(fakeApiError);
    return <DesktopErrorView userMessage={ui.userMessage} allowRetry={ui.allowRetry} />;
  }

  return <DesktopSucceededReport report={result.report!} />;
}

function DesktopErrorView({
  userMessage,
  allowRetry,
}: {
  userMessage: string;
  allowRetry: boolean;
}) {
  return (
    <View className={styles.centered}>
      <View className={styles.errorBox}>
        <Icon name="x-circle" size={56} color="#C8281C" />
        <Text className={styles.errorText}>{userMessage}</Text>
        {allowRetry && <Text className={styles.retryHint}>请返回首页重新上传</Text>}
      </View>
    </View>
  );
}

function DesktopSucceededReport({ report }: { report: ReportPayload }) {
  const sorted = sortBySeverity(report.hazards);
  return (
    <View className={styles.page}>
      <HeaderBand
        identifier={`NO.${formatIdentifier(report.created_at)}`}
        subtitle={report.summary}
      />

      <View className={styles.body}>
        <View className={styles.aside}>
          <ReportSidebar report={report} hazardCount={sorted.length} />
        </View>

        <View className={styles.main}>
          <View className={styles.sectionRule}>
            <Text className={styles.sectionLabel}>隐患明细</Text>
          </View>
          {sorted.map((h, idx) => (
            <HazardCard
              hazard={h}
              key={`${h.category_code}-${idx}`}
              index={idx + 1}
              total={sorted.length}
            />
          ))}
        </View>
      </View>
    </View>
  );
}

function formatIdentifier(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const seq = Math.abs(hash(iso)) % 10000;
    return `${yyyy}-${mm}-${dd}-${String(seq).padStart(4, '0')}`;
  } catch {
    return iso;
  }
}
function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h << 5) - h + s.charCodeAt(i);
  return h;
}
```

Create `miniprogram/src/pages/report/desktop.module.scss`:

```scss
:root {
  --fs-body-desktop: 15px;
  --space-desktop-gutter: 48px;
}

.page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 var(--space-desktop-gutter);
  background-color: var(--color-paper);
}

.body {
  display: grid;
  grid-template-columns: 4fr 6fr;
  gap: var(--space-desktop-gutter);
  padding: var(--space-3) 0 var(--space-5);
  align-items: start;
}

.aside {
  position: sticky;
  top: var(--space-3);
  align-self: start;
}

.main {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sectionRule {
  border-top: var(--border-charcoal);
  padding-top: var(--space-1);
  margin-bottom: var(--space-2);
}

.sectionLabel {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 3px;
  color: var(--color-charcoal);
}

.centered {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: var(--space-3);
}

.errorBox {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4);
  border: var(--border-charcoal);
  background-color: var(--color-paper);
  max-width: 480px;
}

.errorText {
  font-size: 18px;
  color: var(--color-charcoal);
  text-align: center;
}

.retryHint {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 2px;
  color: var(--color-caliper-grey);
}
```

**Step 4: 跑测试看通过**

```
pnpm test -- --testPathPattern=DesktopReport
```

Expected: 3 个用例 PASS。

**Step 5: 全量回归 + build**

```
pnpm test
pnpm build:h5:dev
```

Expected: 全部通过 + build 成功。

**Step 6: 浏览器肉眼验证**

`pnpm serve:h5` 后用 `tests/fixtures/images/case_001_stepladder_over_2_meters.jpg` 走一次完整流程：
- 首页 1440×900 看 DesktopIndex 左右分栏
- 上传后跳报告页，看到 ProgressIndicator 居中
- 等 Claude 返回，看到 DesktopReport 左 sticky + 右滚动
- 缩窗口到 <1024px 应当无缝切回 mobile

**Step 7: Commit**

```
git add miniprogram/src/pages/report/desktop.tsx \
        miniprogram/src/pages/report/desktop.module.scss \
        miniprogram/tests/pages/DesktopReport.test.tsx
git commit -m "feat(miniprogram): DesktopReport page with sticky sidebar + hazard grid

左 sticky ReportSidebar (4 fr) + 右 scrollable hazard list (6 fr)；
max-width 1400px；错误页桌面化居中。"
```

---

## Task 9: 桌面 E2E（Playwright，1440×900 视口）

**Files:**
- Create: `miniprogram/tests/e2e/h5-desktop.mjs`
- Modify: `miniprogram/package.json` —— 加 `test:e2e:h5:desktop:real` 脚本

**Step 1: 把 h5-real.mjs 复制成 h5-desktop.mjs 改 viewport + 上传方式**

Create `miniprogram/tests/e2e/h5-desktop.mjs`:

```javascript
/**
 * 桌面 H5 端到端 e2e —— 与 h5-real.mjs 完全相同的后端 / Claude 真调，
 * 但 viewport=1440×900，触发 useIsDesktop=true 进 Desktop 分支。
 *
 * 上传方式：在 page 上找到隐藏 <input type=file>，调 setInputFiles 喂图。
 * （Mobile 版是先点击 BigButton 等 fileChooser；桌面 dropzone 直接点击也行
 * 但 setInputFiles 更稳，避免 fileChooser event 时序竞争）
 *
 * 用法：cd miniprogram && pnpm test:e2e:h5:desktop:real
 *
 * 退出码：0 通过 / 1 任一断言失败 / 2 启动失败
 */

import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

import { HEALTH_URL, spawnBackend } from '../../scripts/start-backend.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..', '..', '..');
const DIST_DIR = resolve(__dirname, '..', '..', 'dist');
const BACKEND_DIR = resolve(REPO_ROOT, 'backend');
const SAMPLE_IMG = resolve(
  BACKEND_DIR,
  'tests',
  'fixtures',
  'images',
  'case_001_stepladder_over_2_meters.jpg',
);
const SCREENSHOT_DIR = __dirname;

const CHROME_PATH =
  process.env.CHROME_PATH ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
};

async function startBackend() {
  const proc = spawnBackend({ stdio: 'pipe' });
  proc.stdout.on('data', (b) => process.stdout.write(`[backend] ${b}`));
  proc.stderr.on('data', (b) => process.stderr.write(`[backend] ${b}`));
  const deadline = Date.now() + 45_000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(HEALTH_URL);
      if (r.ok && (await r.json()).status === 'ok') return proc;
    } catch {
      /* not ready */
    }
    await sleep(500);
  }
  throw new Error('backend /healthz 未在 45s 内就绪');
}

function stopBackend(proc) {
  if (!proc) return;
  try { proc.kill('SIGTERM'); } catch {}
  if (process.platform === 'win32' && proc.pid) {
    spawn('taskkill', ['/F', '/T', '/PID', String(proc.pid)], { stdio: 'ignore' });
  }
}

function startStaticServer(rootDir) {
  return new Promise((resolveStart, rejectStart) => {
    const server = createServer(async (req, res) => {
      try {
        let urlPath = decodeURIComponent(req.url.split('?')[0]);
        if (urlPath === '/favicon.ico') { res.writeHead(204); res.end(); return; }
        if (urlPath === '/' || urlPath === '') urlPath = '/index.html';
        const filePath = join(rootDir, urlPath);
        if (!filePath.startsWith(rootDir)) { res.writeHead(403); res.end(); return; }
        const content = await readFile(filePath);
        const ct = MIME[extname(filePath).toLowerCase()] || 'application/octet-stream';
        res.writeHead(200, { 'Content-Type': ct });
        res.end(content);
      } catch { res.writeHead(404); res.end(); }
    });
    server.listen(0, '127.0.0.1', () => {
      resolveStart({ server, port: server.address().port });
    });
    server.on('error', rejectStart);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function ensureDistExists() {
  try { await readFile(join(DIST_DIR, 'index.html')); }
  catch { console.error('dist/index.html 不存在；先跑 pnpm build:h5:dev'); process.exit(2); }
}

async function main() {
  console.log(`========== H5 DESKTOP REAL E2E ==========`);
  console.log(`  viewport: 1440x900 (desktop branch)`);

  await ensureDistExists();

  let backendProc = null;
  let staticSrv = null;
  let browser = null;
  const failures = [];
  const consoleErrors = [];

  try {
    backendProc = await startBackend();
    const { server, port } = await startStaticServer(DIST_DIR);
    staticSrv = server;
    const h5Url = `http://127.0.0.1:${port}/`;

    browser = await chromium.launch({ executablePath: CHROME_PATH, headless: true });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
    page.on('pageerror', (err) => consoleErrors.push(err.message));

    console.log(`[step 1/4] 打开 H5 首页 (desktop)...`);
    await page.goto(h5Url, { waitUntil: 'networkidle', timeout: 30_000 });

    // 桌面分支：找到 dropzone 副标题 "CAPTURE INSPECTION PHOTO"
    await page.waitForSelector('text=/CAPTURE INSPECTION PHOTO/i', { timeout: 10_000 });
    await page.screenshot({ path: join(SCREENSHOT_DIR, 'h5-desktop-01-home.png'), fullPage: true });

    // 验证桌面分栏存在：查询拍摄要点卡片（仅桌面 DesktopIndex 渲染）
    const tipsVisible = await page.locator('text=拍摄要点').first().isVisible();
    if (!tipsVisible) failures.push('桌面首页未渲染 "拍摄要点" 侧栏');

    console.log(`[step 2/4] 把图片塞进隐藏 <input>...`);
    await page.locator('input[type="file"]').setInputFiles(SAMPLE_IMG);

    console.log(`[step 3/4] 等跳转报告页...`);
    await page.waitForURL(/\/pages\/report\/index/i, { timeout: 30_000 });
    await page.waitForSelector('text=/AI 分析中|正在为你生成报告|拍照成功/', { timeout: 5_000 })
      .catch(() => console.log('未匹配到 polling 文案'));
    await page.screenshot({ path: join(SCREENSHOT_DIR, 'h5-desktop-02-polling.png'), fullPage: true });

    console.log(`[step 4/4] 等真实 Claude CLI 返回...`);
    const deadline = Date.now() + 200_000;
    let ok = false;
    while (Date.now() < deadline) {
      const sidebarVisible = await page.locator('text=现场巡检报告').first().isVisible().catch(() => false);
      const hazardVisible = await page.locator('text=高处坠落').first().isVisible().catch(() => false);
      if (sidebarVisible && hazardVisible) { ok = true; break; }
      const errVisible = await page.locator('text=/AI 分析超时|AI 分析失败|网络异常/').first().isVisible().catch(() => false);
      if (errVisible) {
        failures.push('报告页显示错误页');
        break;
      }
      await sleep(2_000);
    }
    await page.screenshot({ path: join(SCREENSHOT_DIR, 'h5-desktop-03-final.png'), fullPage: true });
    if (!ok && failures.length === 0) failures.push('200s 内未看到桌面侧栏 + "高处坠落"');

    if (consoleErrors.length > 0) failures.push(`浏览器 error: ${consoleErrors.slice(0, 5).join(' | ')}`);
  } catch (e) {
    failures.push(`异常: ${e.message}\n${e.stack}`);
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (staticSrv) staticSrv.close();
    if (backendProc) stopBackend(backendProc);
  }

  if (failures.length === 0) {
    console.log(`✅ H5 DESKTOP E2E PASSED`);
    process.exit(0);
  } else {
    console.log(`❌ H5 DESKTOP E2E FAILED:`);
    for (const f of failures) console.log(`   - ${f}`);
    process.exit(1);
  }
}

main().catch((e) => { console.error(`[FATAL] ${e.stack}`); process.exit(2); });
```

**Step 2: 在 package.json 加 script**

Modify `miniprogram/package.json` 的 scripts 块，在 `"test:e2e:h5:real": "..."` 后追加：

```
"test:e2e:h5:desktop:real": "node tests/e2e/h5-desktop.mjs"
```

**Step 3: build + 跑桌面 e2e**

```
cd miniprogram
pnpm build:h5:dev
pnpm test:e2e:h5:desktop:real
```

Expected: PASSED，3 张截图落到 `tests/e2e/h5-desktop-*.png`，可肉眼复查桌面布局。

成本约 $0.10-0.20、90-180s 一次（真打 Claude CLI），同 h5-real.mjs。

**Step 4: 同时跑移动 e2e 回归**

```
pnpm test:e2e:h5:real
```

Expected: PASSED，移动布局未受影响。

**Step 5: Commit**

```
git add miniprogram/tests/e2e/h5-desktop.mjs miniprogram/package.json
git commit -m "test(miniprogram): h5-desktop.mjs e2e — 1440×900 viewport with real Claude

验证 DesktopIndex 渲染拍摄要点侧栏、setInputFiles 触发上传、跳报告页后
DesktopReport 渲染 ReportSidebar + HazardCard 列表。"
```

---

## Task 10: 收尾 / Phase 完成验证

**Step 1: 全量测试 0 skipped 0 failed**

```
cd miniprogram
pnpm test --verbose
```

Expected: 全部通过；**skipped = 0**（feedback memory 要求）。

**Step 2: lint**

```
pnpm lint
```

Expected: 0 errors。如有警告评估是否本 PR 引入。

**Step 3: build 两端都过**

```
pnpm build:weapp
pnpm build:h5
```

Expected: 两端 build 都成功。

**Step 4: 检查 weapp 包大小是否未超 50KB 增长**

对比 `dist/` 大小（weapp build）。设计 §3 给的容忍上限：~10-20KB 多出桌面 dead code 可接受，>50KB 需要切 dynamic import。

```
# 跑两次 build:weapp，分别在 main 与本分支，对比 dist/ 大小
# 或者用 du / Get-ChildItem | Measure-Object -Sum Length
```

Expected: 增量 < 50KB（实测应该 ~10-20KB）。

**Step 5: 跑双端真 e2e**

```
pnpm test:e2e:h5:real
pnpm test:e2e:h5:desktop:real
```

两端都过 → 该 phase 算完成。

**Step 6: 写 progress note 到 docs/plans/（可选）**

如有 surprise / 修正 / 与设计稿不一致的地方，更新 design 文档相关章节，commit。

**Step 7: Final commit / 准备开 PR**

```
git log --oneline feat/phase-3-miniprogram..feat/pc-web-ui
```

应当看到 9 个 commit（Task 1-9 各一），加可能的 Task 10 更新。准备 `gh pr create`。

---

## 故障预案

每个 task 跑 `pnpm test` 失败时，按 @superpowers:systematic-debugging 走：

1. **读 jest 全部输出**，不要只看顶部一行 "X tests failed"
2. **定位是哪个 assertion 失败** —— testing-library 的 `screen.debug()` 在测试里加一行可以打印当前 DOM
3. **不要瞎改测试断言** —— 测试是契约。先怀疑实现，再怀疑测试
4. 卡 >15min 没进展，把症状 + 已经尝试的 hypothesis 列出来再继续

特别警告：
- **`process.env.TARO_ENV` 在测试里是 string，不是字面量替换** —— 用 `process.env.TARO_ENV = 'h5'` 不会触发 webpack DefinePlugin 的 dead code elimination，但在 jest 里跑时表现一致
- **`scss` 在测试里是 `{}`** —— `styles.foo` 是 `undefined`。永远用文案/aria/role/data-* 查询
- **`@testing-library/react` 的 `act` 必须包住状态变化** —— 不包会有 React 警告但不影响断言通过；MQ change handler 调用必须 `act(() => mq._handler?.(...))`
