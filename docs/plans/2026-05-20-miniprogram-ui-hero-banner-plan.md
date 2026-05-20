# Miniprogram UI Hero Banner — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `HeroBanner` white-card pattern to both `pages/index` and `pages/report` to fix "太空 / 像没设计过" feedback on the post-`66d4d4e` iOS HIG redesign, without rolling back HIG style and without adding any new interaction.

**Architecture:** One new component (`HeroBanner`) with a discriminated-union prop (`intro` mode for index, `metric` mode for report). One new util (`relativeTime`). One new icon (`helmet`). Page diffs limited to header layout. All severity colors/labels reused from `src/utils/severity.ts`.

**Tech Stack:** Taro 4 + React 18 + TypeScript 5, Jest + jsdom + @testing-library/react, SCSS modules.

**Design doc:** `docs/plans/2026-05-20-miniprogram-ui-hero-banner-design.md`

---

## Corrections to the design doc

Verified against current source — apply these in the plan, not the design:

| Design doc says | Actual code | Action |
|---|---|---|
| "Add `SEVERITY_LABEL`" to severity.ts | Already exists at `src/utils/severity.ts:38-42` | **Do NOT add** — just import it |
| "Reuse `SEVERITY_TINT`" | Actual name is `SEVERITY_BG_TINT` (line 25) | Use `SEVERITY_BG_TINT` |
| "Dynamic import for color assertion" | Existing test (`PlainWarningCard.test.tsx`) uses top-import + value reference | Top import, mirror the pattern |
| Helmet "护目镜弧线" | New icon — must be drawn fresh in `PATHS` map | One SVG path string, stroke 1.5 |

## Pre-flight (no commit)

1. Pull latest on branch `feat/phase-3-miniprogram`. Verify clean working tree: `git status` → "nothing to commit".
2. Run baseline once so we know the bar: `cd miniprogram && pnpm test && pnpm lint && npx tsc --noEmit`.
   - Expected: tests **39/0/0**, lint **0**, tsc **0**.
   - If any baseline failure, stop and investigate; do not start the plan on broken main.

---

## Task 1: Add `helmet` icon to the Icon component

**Files:**
- Modify: `miniprogram/src/components/Icon/index.tsx` (add `'helmet'` to `IconName` union + path in `PATHS` map)
- Create: `miniprogram/tests/components/Icon.test.tsx`

**Step 1: Write the failing test**

```tsx
// miniprogram/tests/components/Icon.test.tsx
/**
 * 单元测试：Icon —— 集中验证图标集枚举 + helmet 新增。
 * 不渲染断言 path 字符串（dangerouslySetInnerHTML 走的是 innerHTML），
 * 只断言 IconName 联合类型可被使用 + 组件不抛错。
 */
import { render } from '@testing-library/react';
import { Icon } from '../../src/components/Icon';

describe('Icon', () => {
  it('renders helmet without crashing', () => {
    const { container } = render(<Icon name="helmet" size={56} color="#007AFF" />);
    // dangerouslySetInnerHTML injects an <svg> element under the View
    expect(container.querySelector('svg')).not.toBeNull();
  });

  it('respects size prop on the wrapper', () => {
    const { container } = render(<Icon name="helmet" size={56} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.width).toBe('56px');
    expect(wrapper.style.height).toBe('56px');
  });
});
```

**Step 2: Run test to verify it fails**

Command: `cd miniprogram && pnpm test -- Icon.test`
Expected: **FAIL** — TypeScript error `Type '"helmet"' is not assignable to type 'IconName'` OR runtime undefined path.

**Step 3: Add the `helmet` path**

Edit `miniprogram/src/components/Icon/index.tsx`:

1. Extend the union (line ~21):
   ```ts
   export type IconName =
     | 'camera'
     | 'chevron-right'
     | 'chevron-down'
     | 'chevron-up'
     | 'alert-triangle'
     | 'check-circle'
     | 'x-circle'
     | 'document'
     | 'lightbulb'
     | 'arrow-right'
     | 'helmet';
   ```
2. Add the path inside `PATHS` (single `d=` string — multiple `M` segments are fine):
   ```ts
   helmet:
     'M4 14a8 8 0 0 1 16 0 M3 14h18 M9 14v-3a3 3 0 0 1 6 0v3',
   ```
   What this draws (24×24 viewBox):
   - `M4 14a8 8 0 0 1 16 0` — top dome arc (helmet shell)
   - `M3 14h18` — horizontal brim line
   - `M9 14v-3a3 3 0 0 1 6 0v3` — small front visor arc

**Step 4: Run test to verify it passes**

Command: `cd miniprogram && pnpm test -- Icon.test`
Expected: **PASS** — both tests green.

**Step 5: Commit**

```bash
git add miniprogram/src/components/Icon/index.tsx miniprogram/tests/components/Icon.test.tsx
git commit -m "feat(miniprogram): add helmet icon for hero banner"
```

---

## Task 2: Add `relativeTime` util

**Files:**
- Create: `miniprogram/src/utils/relativeTime.ts`
- Create: `miniprogram/tests/utils/relativeTime.test.ts`

**Step 1: Write the failing test**

```ts
// miniprogram/tests/utils/relativeTime.test.ts
/**
 * relativeTime(iso, now?) —— 报告 banner 用的中文相对时间。
 *
 * 规则：
 * - < 60s   → "刚刚"
 * - < 60min → "N 分钟前"
 * - 同一日历日 → "今天 HH:mm"
 * - 前一日历日 → "昨天 HH:mm"
 * - 更早 → "YYYY-MM-DD HH:mm"
 *
 * 测试通过注入 now 保证确定性。
 */
import { relativeTime } from '../../src/utils/relativeTime';

const NOW = new Date('2026-05-20T14:32:00');

describe('relativeTime', () => {
  it('"刚刚" when within 60 seconds', () => {
    const iso = new Date(NOW.getTime() - 30_000).toISOString();
    expect(relativeTime(iso, NOW)).toBe('刚刚');
  });

  it('"N 分钟前" within the hour', () => {
    const iso = new Date(NOW.getTime() - 5 * 60_000).toISOString();
    expect(relativeTime(iso, NOW)).toBe('5 分钟前');
  });

  it('"今天 HH:mm" for same calendar day, hours earlier', () => {
    const iso = new Date(NOW.getTime() - 3 * 60 * 60_000).toISOString();
    expect(relativeTime(iso, NOW)).toBe('今天 11:32');
  });

  it('"昨天 HH:mm" for previous calendar day', () => {
    const iso = new Date('2026-05-19T22:10:00').toISOString();
    expect(relativeTime(iso, NOW)).toBe('昨天 22:10');
  });

  it('"YYYY-MM-DD HH:mm" for older dates', () => {
    const iso = new Date('2026-05-15T09:00:00').toISOString();
    expect(relativeTime(iso, NOW)).toBe('2026-05-15 09:00');
  });
});
```

**Step 2: Run test to verify it fails**

Command: `cd miniprogram && pnpm test -- relativeTime`
Expected: **FAIL** — `Cannot find module '../../src/utils/relativeTime'`.

**Step 3: Implement the util**

Create `miniprogram/src/utils/relativeTime.ts`:

```ts
/**
 * 中文相对时间格式化器。
 *
 * 用于报告页 HeroBanner 的 meta 行，例如 "中风险 · 2 分钟前"。
 *
 * 入参：
 *   iso —— 后端返回的 ISO 时间字符串（report.created_at 同一格式）
 *   now —— 注入用于测试；默认 new Date()
 *
 * 规则（5 档）：
 *   < 60s          → "刚刚"
 *   < 60min        → "N 分钟前"
 *   同一日历日      → "今天 HH:mm"
 *   前一日历日      → "昨天 HH:mm"
 *   更早            → "YYYY-MM-DD HH:mm"
 *
 * "同一日历日" 按本地时区比对（用户在工地是中国本地时间）。
 */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (isNaN(then.getTime())) return iso;

  const diffMs = now.getTime() - then.getTime();
  const diffMin = Math.floor(diffMs / 60_000);

  if (diffMs < 60_000) return '刚刚';
  if (diffMin < 60) return `${diffMin} 分钟前`;

  const sameDay =
    now.getFullYear() === then.getFullYear() &&
    now.getMonth() === then.getMonth() &&
    now.getDate() === then.getDate();
  const hh = String(then.getHours()).padStart(2, '0');
  const mm = String(then.getMinutes()).padStart(2, '0');

  if (sameDay) return `今天 ${hh}:${mm}`;

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday =
    yesterday.getFullYear() === then.getFullYear() &&
    yesterday.getMonth() === then.getMonth() &&
    yesterday.getDate() === then.getDate();
  if (isYesterday) return `昨天 ${hh}:${mm}`;

  const yyyy = then.getFullYear();
  const mo = String(then.getMonth() + 1).padStart(2, '0');
  const dd = String(then.getDate()).padStart(2, '0');
  return `${yyyy}-${mo}-${dd} ${hh}:${mm}`;
}
```

**Step 4: Run test to verify it passes**

Command: `cd miniprogram && pnpm test -- relativeTime`
Expected: **PASS** — 5/5.

**Step 5: Commit**

```bash
git add miniprogram/src/utils/relativeTime.ts miniprogram/tests/utils/relativeTime.test.ts
git commit -m "feat(miniprogram): add relativeTime util for report banner meta"
```

---

## Task 3: Create `HeroBanner` component — intro mode (TDD step 1)

**Files:**
- Create: `miniprogram/src/components/HeroBanner/index.tsx`
- Create: `miniprogram/src/components/HeroBanner/index.module.scss`
- Create: `miniprogram/tests/components/HeroBanner.test.tsx`

**Step 1: Write the failing test (intro mode only)**

```tsx
// miniprogram/tests/components/HeroBanner.test.tsx
/**
 * 单元测试：HeroBanner —— intro / metric 两种模式。
 *
 * 验收要点：
 * - intro: 渲染 title + subtitle + icon
 * - metric: 渲染 "{count} 项隐患" + meta；ring 元素有 severity 颜色
 *
 * styles.X 在 jest 里通过 styleMock 是 undefined，因此走 role / text / data-* 断言。
 */
import { render, screen } from '@testing-library/react';
import { HeroBanner } from '../../src/components/HeroBanner';
import { SEVERITY_COLOR } from '../../src/utils/severity';

function hexToRgb(hex: string): string {
  const m = hex.replace('#', '').match(/.{2}/g);
  if (!m) return hex;
  return `rgb(${parseInt(m[0], 16)}, ${parseInt(m[1], 16)}, ${parseInt(m[2], 16)})`;
}

describe('HeroBanner', () => {
  it('intro mode renders title, subtitle, and icon', () => {
    const { container } = render(
      <HeroBanner
        mode="intro"
        icon="helmet"
        title="工地隐患识别"
        subtitle="拍一张，AI 30 秒出报告"
      />,
    );
    expect(screen.getByText('工地隐患识别')).toBeInTheDocument();
    expect(screen.getByText('拍一张，AI 30 秒出报告')).toBeInTheDocument();
    // helmet icon injected as <svg> via Icon component
    expect(container.querySelector('svg')).not.toBeNull();
  });
});
```

**Step 2: Run test to verify it fails**

Command: `cd miniprogram && pnpm test -- HeroBanner`
Expected: **FAIL** — `Cannot find module '../../src/components/HeroBanner'`.

**Step 3: Implement intro-only HeroBanner**

Create `miniprogram/src/components/HeroBanner/index.tsx`:

```tsx
/**
 * HeroBanner —— 页面顶部白卡 hero，两种模式（discriminated union）：
 *  - intro: 左 icon + 右 title/subtitle，用于首页"产品名片"位
 *  - metric: 左 severity ring + 右 count/meta，用于报告页"风险概览"位
 *
 * 设计意图：信息密度 + 视觉锚点；不引入新色板、新交互。
 * 不接受 children —— 该组件是定型 pattern，不是通用 slot。
 */
import { View, Text } from '@tarojs/components';

import { Icon, type IconName } from '../Icon';
import {
  SEVERITY_COLOR,
  SEVERITY_BG_TINT,
  SEVERITY_TEXT_ON_TINT,
  SEVERITY_LABEL,
} from '../../utils/severity';
import type { Severity } from '../../types/report';

import styles from './index.module.scss';

export type HeroBannerProps =
  | {
      mode: 'intro';
      icon: IconName;
      title: string;
      subtitle: string;
    }
  | {
      mode: 'metric';
      severity: Severity;
      count: number;
      meta: string;
    };

export function HeroBanner(props: HeroBannerProps) {
  if (props.mode === 'intro') {
    return (
      <View className={styles.banner}>
        <View className={styles.iconSlot}>
          <Icon name={props.icon} size={56} color="#007AFF" />
        </View>
        <View className={styles.textCol}>
          <Text className={styles.title}>{props.title}</Text>
          <Text className={styles.subtitle}>{props.subtitle}</Text>
        </View>
      </View>
    );
  }
  // metric mode — implemented in Task 4
  return null;
}
```

Create `miniprogram/src/components/HeroBanner/index.module.scss`:

```scss
// iOS HIG hero banner — 白卡 + 圆角 16 + subtle shadow，沿用 summaryCard 阴影规格。
.banner {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16px;
  padding: 20px 22px;
  margin: 0 16px;
  background-color: #ffffff;
  border-radius: 16px;
  box-shadow: 0 0 0 0.5px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.04);
}

.iconSlot {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.textCol {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.title {
  font-size: 30px;
  font-weight: 600;
  color: #1c1c1e;
  letter-spacing: -0.2px;
  line-height: 1.25;
}

.subtitle {
  font-size: 22px;
  font-weight: 400;
  color: #8e8e93;
  line-height: 1.4;
  margin-top: 4px;
}

// metric mode 样式 —— Task 4 加
```

> Font sizes are in rpx-equivalent px values that match the existing pages (`largeTitle 50px`, `body 26px` etc., which derive from Taro's 750-design-width scaling). 30/22 here match `summaryLabel` weight and `summaryText` body.

**Step 4: Run test to verify it passes**

Command: `cd miniprogram && pnpm test -- HeroBanner`
Expected: **PASS** — 1/1.

**Step 5: Commit**

```bash
git add miniprogram/src/components/HeroBanner miniprogram/tests/components/HeroBanner.test.tsx
git commit -m "feat(miniprogram): HeroBanner component (intro mode)"
```

---

## Task 4: Extend `HeroBanner` with metric mode (TDD step 2)

**Files:**
- Modify: `miniprogram/src/components/HeroBanner/index.tsx`
- Modify: `miniprogram/src/components/HeroBanner/index.module.scss`
- Modify: `miniprogram/tests/components/HeroBanner.test.tsx`

**Step 1: Add failing metric-mode test**

Append to `HeroBanner.test.tsx`:

```tsx
  it('metric mode renders count and meta', () => {
    render(
      <HeroBanner mode="metric" severity="medium" count={3} meta="中风险 · 2 分钟前" />,
    );
    expect(screen.getByText('3 项隐患')).toBeInTheDocument();
    expect(screen.getByText('中风险 · 2 分钟前')).toBeInTheDocument();
  });

  it('metric mode applies severity color on ring element', () => {
    const { container } = render(
      <HeroBanner mode="metric" severity="high" count={5} meta="高风险 · 刚刚" />,
    );
    const ring = container.querySelector('[data-severity="high"]') as HTMLElement;
    expect(ring).not.toBeNull();
    const expectedHex = SEVERITY_COLOR.high.toLowerCase();
    const expectedRgb = hexToRgb(expectedHex);
    const actual = ring.style.borderColor.toLowerCase();
    expect([expectedHex, expectedRgb]).toContain(actual);
  });
```

**Step 2: Run tests to verify the 2 new ones fail**

Command: `cd miniprogram && pnpm test -- HeroBanner`
Expected: **FAIL** — `getByText('3 项隐患')` not found (metric branch returns null).

**Step 3: Implement metric branch**

Replace the `// metric mode — implemented in Task 4` placeholder + `return null` with:

```tsx
  const { severity, count, meta } = props;
  return (
    <View className={styles.banner}>
      <View
        className={styles.ring}
        data-severity={severity}
        style={{
          borderColor: SEVERITY_COLOR[severity],
          backgroundColor: SEVERITY_BG_TINT[severity],
        }}
      >
        <Text className={styles.ringLabel} style={{ color: SEVERITY_TEXT_ON_TINT[severity] }}>
          {SEVERITY_LABEL[severity].charAt(0)}
        </Text>
      </View>
      <View className={styles.textCol}>
        <Text className={styles.count}>{count} 项隐患</Text>
        <Text className={styles.subtitle}>{meta}</Text>
      </View>
    </View>
  );
```

> Why a Chinese single-char label (高/中/低) in the ring instead of an Icon component? The ring is 64×64 with a 6px border — a 24-viewBox icon needs to be ≥36px to read, but then it competes with the border. A single bold char is denser, accessibility-readable, and avoids importing yet another icon variant per severity.

Append the new SCSS classes to `index.module.scss`:

```scss
.ring {
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  border-radius: 32px;
  border-width: 6px;
  border-style: solid;
  // border-color + background-color come from inline style (severity-driven)
  display: flex;
  align-items: center;
  justify-content: center;
}

.ringLabel {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.count {
  font-size: 36px;
  font-weight: 700;
  color: #1c1c1e;
  letter-spacing: -0.4px;
  line-height: 1.15;
}
```

**Step 4: Run tests to verify all pass**

Command: `cd miniprogram && pnpm test -- HeroBanner`
Expected: **PASS** — 3/3 (intro + metric + ring color).

**Step 5: Commit**

```bash
git add miniprogram/src/components/HeroBanner miniprogram/tests/components/HeroBanner.test.tsx
git commit -m "feat(miniprogram): HeroBanner metric mode + severity ring"
```

---

## Task 5: Wire `HeroBanner` into the index page

**Files:**
- Modify: `miniprogram/src/pages/index/index.tsx`
- Modify: `miniprogram/src/pages/index/index.module.scss`

> No unit test exists for the index page (style-mock makes layout-only assertions weak). Visual verification is via Task 7 e2e screenshot.

**Step 1: Update `index.tsx`** — insert `HeroBanner` at the top of the page tree:

```tsx
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { BigButton } from '../../components/BigButton';
import { HeroBanner } from '../../components/HeroBanner';
import { captureImage } from '../../hooks/useImageCapture';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';

import styles from './index.module.scss';

export default function IndexPage() {
  const [uploading, setUploading] = useState(false);

  const handleTap = async () => {
    if (uploading) return;
    let image;
    try {
      image = await captureImage();
    } catch (_e) {
      return;
    }
    setUploading(true);
    try {
      const resp = await createInspection(image.tempFilePath);
      Taro.navigateTo({
        url:
          `/pages/report/index?id=${resp.inspection_id}` +
          `&pi=${resp.poll_interval_ms}&to=${resp.timeout_ms}`,
      });
    } catch (e) {
      const ui = mapApiError(e);
      Taro.showToast({ title: ui.userMessage, icon: 'none', duration: 3000 });
    } finally {
      setUploading(false);
    }
  };

  return (
    <View className={styles.indexPage}>
      <HeroBanner
        mode="intro"
        icon="helmet"
        title="工地隐患识别"
        subtitle="拍一张，AI 30 秒出报告"
      />

      <View className={styles.header}>
        <Text className={styles.eyebrow}>Safety Scout</Text>
        <Text className={styles.largeTitle}>工地隐患识别</Text>
      </View>

      <BigButton text="拍照检查" onTap={handleTap} loading={uploading} />

      <View className={styles.tipBlock}>
        <Text className={styles.tipText}>
          贴近隐患位置拍摄，保持光线充足；画面包含工人、护栏、电箱等关键元素，识别更准确。
        </Text>
      </View>
    </View>
  );
}
```

**Step 2: Update `index.module.scss`** — reduce top spacing + slightly smaller large title:

```scss
// iOS HIG 首页：systemGroupedBackground + HeroBanner + large title + 单 action + 脚注 tip。
.indexPage {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: 60px 0 40px;
  background-color: #f2f2f7;
}

.header {
  padding: 0 24px;
  margin-top: 32px;
  margin-bottom: 32px;
}

.eyebrow {
  display: block;
  font-size: 18px;
  font-weight: 500;
  color: #8e8e93;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.largeTitle {
  font-size: 50px;
  font-weight: 700;
  color: #000000;
  letter-spacing: -1px;
  line-height: 1.15;
}

.tipBlock {
  padding: 0 28px;
  margin-top: 16px;
}

.tipText {
  font-size: 22px;
  color: #8e8e93;
  line-height: 1.5;
  letter-spacing: 0.1px;
}
```

Diff summary:
- `.indexPage padding-top` 80 → 60
- `.header` add `margin-top: 32` (space below banner), keep `margin-bottom: 32` (was 48)
- `.eyebrow font-size` 22 → 18
- `.largeTitle font-size` 56 → 50

**Step 3: Run unit tests to verify nothing else broke**

Command: `cd miniprogram && pnpm test`
Expected: **PASS** — all tests (baseline 39 + Icon + relativeTime + HeroBanner) green, **0 skip / 0 fail**.

**Step 4: Commit**

```bash
git add miniprogram/src/pages/index
git commit -m "feat(miniprogram): wire HeroBanner into index page"
```

---

## Task 6: Wire `HeroBanner` into the report page

**Files:**
- Modify: `miniprogram/src/pages/report/index.tsx`
- Modify: `miniprogram/src/pages/report/index.module.scss`

**Step 1: Update `report/index.tsx`** — change `SucceededReport` to add the metric banner and drop the now-redundant `pageMeta` line:

Replace the `SucceededReport` function with:

```tsx
function SucceededReport({ report }: { report: ReportPayload }) {
  const sorted = sortBySeverity(report.hazards);
  const severity = report.overall_severity as Severity;
  const meta = `${SEVERITY_LABEL[severity]} · ${relativeTime(report.created_at)}`;
  return (
    <View className={styles.reportPage}>
      <HeroBanner mode="metric" severity={severity} count={sorted.length} meta={meta} />

      <View className={styles.pageHeader}>
        <Text className={styles.pageEyebrow}>{formatTimestamp(report.created_at)}</Text>
        <Text className={styles.pageTitle}>隐患报告</Text>
      </View>

      <PlainWarningCard
        text={report.plain_warning}
        severity={severity}
      />

      <View className={styles.summaryCard}>
        <Text className={styles.summaryLabel}>现场总览</Text>
        <Text className={styles.summaryText}>{report.summary}</Text>
      </View>

      <View className={styles.sectionHeader}>
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
  );
}
```

Add the new imports at the top:

```tsx
import { HeroBanner } from '../../components/HeroBanner';
import { SEVERITY_LABEL } from '../../utils/severity';
import { relativeTime } from '../../utils/relativeTime';
```

(`sortBySeverity` and `Severity` are already imported.)

Remove the unused `pageMeta` `<Text>` from the page header — already done in the replacement above. Verify by grep:

Command: `cd miniprogram && grep -n "共识别" src/pages/report/index.tsx`
Expected: no output.

**Step 2: Update `report/index.module.scss`** — adjust top padding and delete `.pageMeta`:

In `miniprogram/src/pages/report/index.module.scss`:
1. Change `.pageHeader { padding: 48px 24px 16px }` → `padding: 24px 24px 16px` (banner pushes everything down).
2. Add `.reportPage { padding-top: 24px }` (the metric banner needs breathing room from the screen top).
3. Delete the entire `.pageMeta { ... }` rule block (~5 lines, the one currently right after `.pageTitle`).

Final relevant portion:

```scss
.reportPage {
  padding: 24px 0 60px 0;
  background-color: #f2f2f7;
  min-height: 100vh;
}

.pageHeader {
  padding: 24px 24px 16px;
}

.pageEyebrow {
  display: block;
  font-size: 20px;
  color: #8e8e93;
  font-weight: 500;
  letter-spacing: 0.3px;
  margin-bottom: 6px;
}

.pageTitle {
  display: block;
  font-size: 50px;
  font-weight: 700;
  color: #000000;
  letter-spacing: -0.8px;
  line-height: 1.15;
  margin-bottom: 6px;
}

// .pageMeta removed — info migrated to HeroBanner
```

**Step 3: Run unit tests**

Command: `cd miniprogram && pnpm test`
Expected: **PASS** — full suite green, **0 skip / 0 fail**.

**Step 4: Commit**

```bash
git add miniprogram/src/pages/report
git commit -m "feat(miniprogram): wire HeroBanner metric into report page"
```

---

## Task 7: Quality gates + e2e visual verification

**Step 1: Lint + tsc**

Commands:
```bash
cd miniprogram
pnpm lint
npx tsc --noEmit
```
Expected: **0 errors** for both.

If lint complains about unused imports (e.g. removed `pageMeta` references), fix the imports in the offending file in-place; no separate commit needed — fold into Step 5 commit.

**Step 2: Full test run — confirm zero-skip mandate**

Command: `cd miniprogram && pnpm test`
Expected report ends with something like:
```
Tests:       45 passed, 45 total
```
(39 baseline + 2 Icon + 5 relativeTime + 3 HeroBanner = 49 if I counted right; the exact number depends on baseline. The hard requirement is **0 skipped, 0 failed** per `[[feedback_phase_unit_tests]]`.)

Verify zero skip explicitly:
```bash
cd miniprogram && pnpm test 2>&1 | grep -E "skipped|todo"
```
Expected: no output. If any test is `.skip` / `.todo`, stop and fix it before proceeding.

**Step 3: H5 build + e2e screenshot**

Two terminals needed:

Terminal A (backend, leave running):
```bash
cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Terminal B (one-shot build + e2e):
```bash
cd miniprogram
pnpm build:h5:dev
pnpm test:e2e:h5
```

Expected: e2e exits 0; check `miniprogram/tests/e2e/h5-smoke.png` and `h5-real-*.png` — eyeball that:
- Home screenshot now shows a white card at the top (helmet icon + title + subtitle), then the large title block, then the blue button.
- Report screenshot shows a white card at the top with a severity-colored ring + count + meta line, then the large title.
- Neither page has a "共识别 N 项" sub-line on the report (info is in the banner).
- No layout overflow, no broken icons.

**Step 4: If screenshots look wrong, iterate**

Common adjustments (do as small follow-up edits, not new commits unless meaningful):
- Banner padding feels off → tweak `padding` in `HeroBanner/index.module.scss`
- Title overflow → reduce `font-size` from 30 to 28
- Ring border-width feels heavy → 6 → 5

If you tweak, re-run `pnpm test:e2e:h5` and re-eyeball. Each meaningful design adjustment gets its own commit:
```bash
git add miniprogram/src/components/HeroBanner/index.module.scss
git commit -m "style(miniprogram): tighten HeroBanner padding after e2e review"
```

**Step 5: Final clean commit (only if you tweaked)**

Otherwise, the plan ends here. If everything passed cleanly, push the branch:
```bash
git log --oneline -10  # confirm 6 new commits land cleanly
git push  # if user is OK with pushing to origin/feat/phase-3-miniprogram
```
*(Per CLAUDE-instructions: only push if user explicitly asks.)*

---

## Acceptance checklist

Verify before declaring done:

- [ ] `pnpm test` — green, **0 skipped**, ≥ 39 baseline + 10 new tests passing.
- [ ] `pnpm lint` — **0 errors**.
- [ ] `npx tsc --noEmit` — **0 errors**.
- [ ] `pnpm test:e2e:h5` — exits 0.
- [ ] Home screenshot shows the white HeroBanner card with helmet + title + subtitle at the top.
- [ ] Report screenshot shows the white HeroBanner card with severity ring + count + meta at the top.
- [ ] "共识别 N 项" line no longer appears below the report title.
- [ ] iOS HIG palette intact — no emoji, no warm accents, single accent color is still `#007AFF`.
- [ ] No new color tokens introduced — verify by grep:
      `cd miniprogram && grep -E "#[0-9A-Fa-f]{6}" src/components/HeroBanner/`
      → all hex colors should also appear in `src/utils/severity.ts` or the existing palette (`#007AFF`, `#ffffff`, `#8e8e93`, `#1c1c1e`).
