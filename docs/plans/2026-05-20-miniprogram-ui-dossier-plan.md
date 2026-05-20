# Dossier UI Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the miniprogram UI from iOS HIG to a "Site Inspection Dossier" aesthetic — paper-tone palette, IBM Plex + Source Han Serif typography, numbered list patterns, ruled separators, stamp-style identifiers — so the product reads as an official construction-inspection document rather than a generic consumer app.

**Architecture:** Token-first phased rewrite. Phase 1-2 ship the design system (CSS variables + webfonts). Phase 3-7 rewrite each component in dependency order. Phase 8 stitches pages + desktop chrome. Phase 9 verifies. Same components serve weapp + H5; platform divergence is gated by `process.env.TARO_ENV` only for font loading.

**Tech Stack:** Taro 4 + React 18 + TypeScript 5, SCSS modules + raw SCSS for global tokens/fonts, IBM Plex woff2 (self-hosted, ~100KB total) + Source Han Serif fallback cascade.

**Design doc:** `docs/plans/2026-05-20-miniprogram-ui-dossier-design.md`

---

## Pre-flight (no commit)

1. Confirm clean working tree: `git -C /d/workspace/tiktok/safety-scout status` → "nothing to commit"
2. Baseline gates: `cd D:\workspace\tiktok\safety-scout\miniprogram && pnpm test && pnpm lint && npx tsc --noEmit`
   - Expected: tests **51/0/0**, lint clean, tsc clean (after the dossier design doc commit `6b1231e`)
   - If anything fails, stop and investigate — do not start the rewrite on broken main

## Windows / shell notes (apply to every task)

- `cd` does not persist between Bash tool calls reliably. Use one of:
  - Chain commands in a single Bash call: `cd D:\path && cmd1 && cmd2`
  - Use `git -C /d/workspace/tiktok/safety-scout <cmd>` (forward-slashes work in `-C`)
- Forward-slashes in paths work in heredoc git commit messages; backslashes in heredocs get mangled.
- All `pnpm` commands run from `D:\workspace\tiktok\safety-scout\miniprogram`.

---

## Task 1: Design tokens

**Files:**
- Create: `miniprogram/src/styles/tokens.scss`
- Modify: `miniprogram/src/utils/severity.ts` (color values)
- Modify: `miniprogram/src/app.scss` (import tokens, set body backdrop)

**Step 1: Write the failing test (severity color contract)**

The existing test at `miniprogram/tests/utils/severity.test.ts:44-55` asserts each `SEVERITY_COLOR[k]` matches `/^#[0-9A-Fa-f]{6}$/`. That still passes with new colors — no test change needed.

Add one assertion to the existing test that pins the **new dossier palette** explicitly (so the values don't silently drift back):

Append inside the `describe('utils/severity')` block in `miniprogram/tests/utils/severity.test.ts`:

```ts
  it('uses dossier engineering palette (not iOS systemRed/Orange/Green)', () => {
    expect(SEVERITY_COLOR.high).toBe('#C8281C');
    expect(SEVERITY_COLOR.medium).toBe('#E07B1F');
    expect(SEVERITY_COLOR.low).toBe('#3D7C3D');
  });
```

**Step 2: Run test to verify it fails**

Command: `pnpm test -- severity`
Expected: **FAIL** — current values are `#FF3B30 / #FF9500 / #34C759` (iOS HIG).

**Step 3: Update severity.ts color values**

Edit `miniprogram/src/utils/severity.ts`. Replace the existing `SEVERITY_COLOR`, `SEVERITY_BG_TINT`, `SEVERITY_TEXT_ON_TINT` constants (lines ~18-36) with the dossier palette:

```ts
/** Dossier engineering palette — sharper than iOS HIG, matches paper-document context.
 *  See docs/plans/2026-05-20-miniprogram-ui-dossier-design.md. */
export const SEVERITY_COLOR: Record<Severity, string> = {
  high: '#C8281C',    // engineering red (stamps, critical)
  medium: '#E07B1F',  // warning amber
  low: '#3D7C3D',     // pass green
};

/** Paper-tinted pill background — sits on the #F4EFE5 body. */
export const SEVERITY_BG_TINT: Record<Severity, string> = {
  high: '#F5DDD9',
  medium: '#F6E2CB',
  low: '#DDE8DD',
};

/** AA-contrast text on the tint background. */
export const SEVERITY_TEXT_ON_TINT: Record<Severity, string> = {
  high: '#7A1812',
  medium: '#7C4214',
  low: '#1F4A1F',
};
```

Leave `SEVERITY_ORDER`, `SEVERITY_LABEL`, `sortBySeverity` unchanged.

**Step 4: Run test to verify it passes**

Command: `pnpm test -- severity`
Expected: **PASS** — 4 cases (3 original + 1 new dossier pin).

**Step 5: Create `src/styles/tokens.scss`**

Create the directory and file:

```scss
// Dossier design tokens — paper-document aesthetic.
// Used globally via app.scss import; module SCSS files reference via var(--token).
// Both H5 (regular CSS) and weapp (WXSS) support CSS custom properties.

:root {
  // Palette
  --color-paper: #F4EFE5;
  --color-paper-backdrop: #E8E2D4;
  --color-charcoal: #1A1A1A;
  --color-eng-red: #C8281C;
  --color-survey-blue: #1A4B8C;
  --color-caliper-grey: #A8A096;
  --color-warning-amber: #E07B1F;
  --color-pass-green: #3D7C3D;

  // Spacing (8px base)
  --space-1: 8px;
  --space-2: 16px;
  --space-3: 24px;
  --space-4: 32px;
  --space-5: 48px;
  --space-6: 64px;

  // Type scale — px values; Taro pxtransform handles weapp scaling
  --fs-eyebrow: 12px;       // Plex Mono labels
  --fs-meta: 14px;          // Plex Mono identifiers
  --fs-body: 26px;          // 中文 body text
  --fs-section: 30px;       // section labels
  --fs-h2: 40px;            // sub-titles
  --fs-h1: 56px;            // page large title (H5 desktop)
  --fs-display: 96px;       // hazard count number

  // Font families — Latin first, Chinese fallback chain.
  // Source Han Serif is OPTIONAL — if the woff2 isn't loaded, system serif takes over.
  --font-display: 'IBM Plex Serif', 'Source Han Serif SC', 'STSongti-SC', 'Songti SC', 'SimSun', serif;
  --font-body: 'IBM Plex Sans', 'Source Han Sans SC', 'PingFang SC', 'Helvetica Neue', sans-serif;
  --font-mono: 'IBM Plex Mono', 'Sarasa Mono SC', 'Menlo', 'Consolas', monospace;
  --font-condensed: 'IBM Plex Sans Condensed', 'IBM Plex Sans', 'Helvetica Neue Condensed', sans-serif;

  // Geometry
  --radius-button: 4px;
  --radius-card: 0;
  --border-charcoal: 1px solid var(--color-charcoal);
  --border-hairline: 1px solid var(--color-caliper-grey);
}
```

**Step 6: Update `src/app.scss`**

Replace the entire file with:

```scss
// 全局样式：dossier 调子，paper 背景 + 默认 charcoal 文字 + 桌面 backdrop。
@import './styles/tokens.scss';

page {
  font-family: var(--font-body);
  background-color: var(--color-paper);
  color: var(--color-charcoal);
}

// 平板 / 桌面 H5：手机宽度以外露出 paper-darker backdrop。
// weapp 永远是单一手机视口，media query 不会触发，noop 安全。
@media (min-width: 768px) {
  body {
    background-color: var(--color-paper-backdrop);
    margin: 0;
  }
}
```

> Note: this removes the prior `#f5f5f5` background on `page`. Verify by visual eyeball after Task 8 lands.

**Step 7: Run quality gates**

Commands:
```bash
cd D:\workspace\tiktok\safety-scout\miniprogram && pnpm test && pnpm lint && npx tsc --noEmit
```
Expected: all green. Test count: **52** (51 baseline + 1 new dossier-palette pin).

> Note: `PlainWarningCard.test.tsx` and `HeroBanner.test.tsx` use dynamic `SEVERITY_COLOR[...]` references — they automatically follow the new palette. No edit needed.

**Step 8: Commit**

```bash
git -C /d/workspace/tiktok/safety-scout add miniprogram/src/utils/severity.ts miniprogram/src/styles/tokens.scss miniprogram/src/app.scss miniprogram/tests/utils/severity.test.ts
git -C /d/workspace/tiktok/safety-scout commit -m "feat(miniprogram): dossier design tokens"
```

---

## Task 2: Webfonts (IBM Plex)

**Files:**
- Create: `miniprogram/src/assets/fonts/IBMPlexSerif-Bold.woff2` (manual download)
- Create: `miniprogram/src/assets/fonts/IBMPlexMono-Regular.woff2` (manual download)
- Create: `miniprogram/src/assets/fonts/IBMPlexMono-Medium.woff2` (manual download)
- Create: `miniprogram/src/assets/fonts/IBMPlexSansCondensed-Bold.woff2` (manual download)
- Create: `miniprogram/src/styles/fonts.scss`
- Modify: `miniprogram/src/app.scss` (import fonts.scss)
- Modify: `miniprogram/src/app.tsx` (wx.loadFontFace for weapp on Plex Mono)
- Modify: `miniprogram/config/index.ts` (h5 copy patterns for fonts)

**Step 1: Download font files (manual)**

IBM Plex is Open Font License. Sources (no install required, just download woff2):

- https://github.com/IBM/plex/raw/master/IBM-Plex-Serif/fonts/complete/woff2/IBMPlexSerif-Bold.woff2
- https://github.com/IBM/plex/raw/master/IBM-Plex-Mono/fonts/complete/woff2/IBMPlexMono-Regular.woff2
- https://github.com/IBM/plex/raw/master/IBM-Plex-Mono/fonts/complete/woff2/IBMPlexMono-Medium.woff2
- https://github.com/IBM/plex/raw/master/IBM-Plex-Sans-Condensed/fonts/complete/woff2/IBMPlexSansCondensed-Bold.woff2

Drop them into `miniprogram/src/assets/fonts/` exactly with those filenames.

If you cannot download (sandbox restriction): create the directory + a `README.md` in `src/assets/fonts/` listing the URLs above + filenames, then **continue with Task 2 anyway** — the fonts.scss `@font-face` rules will reference non-existent files; the browser will fall back through the cascade defined in `tokens.scss`. The user will drop the files in later. Surface this clearly in your task report.

**Step 2: Create `src/styles/fonts.scss`**

```scss
// Self-hosted IBM Plex subset for H5. weapp uses wx.loadFontFace (see app.tsx).
// font-display: swap → no FOIT; fallback renders immediately, swaps to Plex when ready.

@font-face {
  font-family: 'IBM Plex Serif';
  src: url('../assets/fonts/IBMPlexSerif-Bold.woff2') format('woff2');
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: 'IBM Plex Mono';
  src: url('../assets/fonts/IBMPlexMono-Regular.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: 'IBM Plex Mono';
  src: url('../assets/fonts/IBMPlexMono-Medium.woff2') format('woff2');
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: 'IBM Plex Sans Condensed';
  src: url('../assets/fonts/IBMPlexSansCondensed-Bold.woff2') format('woff2');
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}
```

**Step 3: Update `src/app.scss`**

Add the fonts import above the tokens import:

```scss
@import './styles/fonts.scss';
@import './styles/tokens.scss';

page { ... }
@media (min-width: 768px) { ... }
```

**Step 4: Update `src/app.tsx` — weapp font loading**

Replace the existing `src/app.tsx` body with:

```tsx
import Taro from '@tarojs/taro';
import { PropsWithChildren, useEffect } from 'react';
import './app.scss';

export default function App({ children }: PropsWithChildren<unknown>) {
  // weapp 上无法直接走 @font-face，要在 onLaunch 时通过 loadFontFace 拉远端字体。
  // H5 上 process.env.TARO_ENV === 'h5'，此 effect 短路跳过。
  // 字体加载失败也无所谓 —— tokens.scss 里 var(--font-mono) 有系统等宽 fallback。
  useEffect(() => {
    if (process.env.TARO_ENV !== 'weapp') return;
    Taro.loadFontFace?.({
      family: 'IBM Plex Mono',
      source: 'url("https://cdn.jsdelivr.net/gh/IBM/plex@master/IBM-Plex-Mono/fonts/complete/woff2/IBMPlexMono-Regular.woff2")',
      desc: { style: 'normal', weight: 'normal' },
      global: true,
      success: () => undefined,
      fail: () => undefined,
      complete: () => undefined,
    } as any);
  }, []);

  return children;
}
```

> Why `as any`: Taro's `loadFontFace` type may not include `global: true`; the actual API supports it. Cast and move on. If this surfaces a real type error, drop `global: true` (the font will then need to be loaded per-page, but the API call still succeeds).

**Step 5: Update `config/index.ts` — copy fonts on H5 build**

Find the `copy.patterns` block (line ~30-33). Change from:
```ts
copy: {
  patterns: [],
  options: {},
},
```
to:
```ts
copy: {
  patterns: [
    // H5: 把 src/assets/fonts 拷到 dist/assets/fonts 让 @font-face 找得到。
    // weapp 上拷过去也无害，weapp build 自己会忽略未被引用的资源。
    { from: 'src/assets/fonts/', to: 'dist/assets/fonts/', ignore: ['*.md'] },
  ],
  options: {},
},
```

**Step 6: Run quality gates + build**

```bash
cd D:\workspace\tiktok\safety-scout\miniprogram && pnpm test && pnpm lint && npx tsc --noEmit && pnpm build:h5:dev
```
Expected: all green. Build succeeds. If fonts directory is empty (you skipped download in Step 1), webpack copy plugin emits a warning but does not fail.

**Step 7: Commit**

```bash
git -C /d/workspace/tiktok/safety-scout add miniprogram/src/styles/fonts.scss miniprogram/src/app.scss miniprogram/src/app.tsx miniprogram/config/index.ts miniprogram/src/assets/fonts/
git -C /d/workspace/tiktok/safety-scout commit -m "feat(miniprogram): self-host IBM Plex fonts + weapp loadFontFace"
```

> Note: if `src/assets/fonts/` is empty (no real woff2 files), git add will skip empty dirs. In that case `git add` the README.md you created in Step 1 instead, so the directory is tracked.

---

## Task 3: Icon set — add dossier glyphs, remove helmet

**Files:**
- Modify: `miniprogram/src/components/Icon/index.tsx`
- Modify: `miniprogram/tests/components/Icon.test.tsx`

**Step 1: Write failing tests**

Append to `miniprogram/tests/components/Icon.test.tsx`:

```tsx
  // Dossier glyphs (Task 3)
  it.each(['stamp', 'plus-square', 'crosshair', 'slash-circle', 'tick'] as const)(
    'renders %s glyph without crashing',
    (name) => {
      const { container } = render(<Icon name={name} size={24} />);
      const path = container.querySelector('svg path');
      expect(path?.getAttribute('d')).toMatch(/^M/);
    },
  );

  it('helmet glyph is removed', () => {
    // @ts-expect-error — 'helmet' should no longer be in IconName union
    render(<Icon name="helmet" size={24} />);
  });
```

**Step 2: Run tests to verify they fail**

Command: `pnpm test -- Icon.test`
Expected: **FAIL** — TS error on the 5 new names (not in `IconName` union); the `@ts-expect-error` line passes IFF the previous error is real (TS6133 if `'helmet'` is still in the union).

**Step 3: Update `Icon/index.tsx`**

1. In the `IconName` union (around line 11), remove `'helmet'` and append the 5 new names:

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
  | 'stamp'
  | 'plus-square'
  | 'crosshair'
  | 'slash-circle'
  | 'tick';
```

2. In the `PATHS` map, remove the `helmet` entry and add 5 new entries:

```ts
  stamp:
    'M6 4h12v8H6z M4 16h16v2H4z M9 12v4 M15 12v4',  // 印章 + 底座 + 两条挂绳
  'plus-square':
    'M4 4h16v16H4z M12 8v8 M8 12h8',  // ⊕ measure plus inside square
  crosshair:
    'M12 2v20 M2 12h20 M12 6a6 6 0 1 0 0 12 6 6 0 0 0 0-12z',  // ⌖ engineering target
  'slash-circle':
    'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M5 5l14 14',  // ⊘ forbid / strike
  tick:
    'M5 12l4 4 10-10',  // ✓ checkmark
```

**Step 4: Run tests to verify they pass**

Command: `pnpm test -- Icon.test`
Expected: **PASS** — 5 new glyph tests pass; the `@ts-expect-error` line stops complaining because `'helmet'` is now actually invalid.

**Step 5: Verify no caller still references `helmet`**

```bash
cd D:\workspace\tiktok\safety-scout\miniprogram && grep -rn "name=\"helmet\"\|name: 'helmet'\|name: \"helmet\"" src/
```
Expected: no output. (Task 7 in the prior plan landed `35c8713` which removed the only helmet reference, and replaced it with `Safety Scout` brand text, but the icon's `helmet` value was still being PASSED through HeroBanner intro mode — verify by reading `src/pages/index/index.tsx` for any leftover `icon="helmet"`. If found, remove that prop; Task 5 will rewrite HeroBanner soon anyway.)

If a caller is found, update to `icon="crosshair"` as a placeholder; Task 5 will rip out the prop entirely.

**Step 6: Run full gates**

```bash
pnpm test && pnpm lint && npx tsc --noEmit
```
Expected: all green. Test count 52 + 6 new (5 glyph + 1 type-removal) = **58**.

**Step 7: Commit**

```bash
git -C /d/workspace/tiktok/safety-scout add miniprogram/src/components/Icon/index.tsx miniprogram/tests/components/Icon.test.tsx miniprogram/src/pages/index/index.tsx
git -C /d/workspace/tiktok/safety-scout commit -m "feat(miniprogram): dossier icon glyphs (stamp/plus-square/crosshair/slash-circle/tick), drop helmet"
```

---

## Task 4: BigButton — square, charcoal, two-line label

**Files:**
- Modify: `miniprogram/src/components/BigButton/index.tsx`
- Modify: `miniprogram/src/components/BigButton/index.module.scss`
- Modify: `miniprogram/tests/components/BigButton.test.tsx`

**Step 1: Write failing tests**

Update `miniprogram/tests/components/BigButton.test.tsx` to add subtitle assertions:

```tsx
  it('renders both Chinese label and Latin subtitle', () => {
    render(<BigButton text="拍摄现场照片" subtitle="CAPTURE INSPECTION PHOTO" onTap={() => undefined} />);
    expect(screen.getByText('拍摄现场照片')).toBeInTheDocument();
    expect(screen.getByText('CAPTURE INSPECTION PHOTO')).toBeInTheDocument();
  });

  it('renders prefix glyph if provided', () => {
    const { container } = render(
      <BigButton text="拍摄现场照片" subtitle="CAPTURE" prefixGlyph="plus-square" onTap={() => undefined} />,
    );
    expect(container.querySelector('svg')).not.toBeNull();
  });
```

(The existing 4 tests still apply but the loading-state assertion `expect(screen.getByText('上传中...')).toBeInTheDocument()` continues to pass if we keep the loading-text behavior.)

**Step 2: Run tests to verify the 2 new ones fail**

Command: `pnpm test -- BigButton.test`
Expected: **FAIL** — `subtitle` prop doesn't exist; `prefixGlyph` prop doesn't exist.

**Step 3: Rewrite `BigButton/index.tsx`**

```tsx
import { View, Text } from '@tarojs/components';

import { Icon, type IconName } from '../Icon';

import styles from './index.module.scss';

export interface BigButtonProps {
  text: string;                  // 中文 label (e.g. "拍摄现场照片")
  subtitle?: string;             // Latin uppercase subtitle (e.g. "CAPTURE INSPECTION PHOTO")
  prefixGlyph?: IconName;        // Optional engineering glyph (e.g. 'plus-square')
  onTap: () => void;
  loading?: boolean;
  disabled?: boolean;
}

export function BigButton({
  text,
  subtitle,
  prefixGlyph,
  onTap,
  loading = false,
  disabled = false,
}: BigButtonProps) {
  const isInteractive = !loading && !disabled;
  const className = [
    styles.button,
    loading ? styles.loading : '',
    disabled ? styles.disabled : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <View
      className={className}
      onClick={isInteractive ? onTap : undefined}
      role="button"
      aria-disabled={!isInteractive}
    >
      {prefixGlyph && (
        <View className={styles.glyphSlot}>
          <Icon name={prefixGlyph} size={28} color="#F4EFE5" />
        </View>
      )}
      <View className={styles.labels}>
        <Text className={styles.labelZh}>{loading ? '处理中' : text}</Text>
        {subtitle && <Text className={styles.labelEn}>{loading ? 'PROCESSING' : subtitle}</Text>}
      </View>
    </View>
  );
}
```

**Step 4: Rewrite `BigButton/index.module.scss`**

```scss
// Dossier 直角按钮：炭灰底、纸色字、中英文两行、可选 prefix glyph。
.button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  width: 88%;
  padding: 24px 28px;
  margin: 32px auto;
  border-radius: 4px;
  background-color: var(--color-charcoal);
  border: 1px solid var(--color-charcoal);
  transition: background-color 0.12s linear;
  user-select: none;

  &:active {
    background-color: #000000;  // even darker; no scale, no shadow — static document feel
  }

  &.loading,
  &.disabled {
    background-color: var(--color-caliper-grey);
    border-color: var(--color-caliper-grey);
    &:active { background-color: var(--color-caliper-grey); }
  }
}

.glyphSlot {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.labels {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.labelZh {
  color: var(--color-paper);
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 2px;
}

.labelEn {
  color: var(--color-paper);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 400;
  letter-spacing: 2px;
  opacity: 0.8;
  text-transform: uppercase;
}
```

**Step 5: Run tests to verify all pass**

Command: `pnpm test -- BigButton.test`
Expected: **PASS** — 6/6 (4 existing + 2 new).

> Note: the existing test `'shows "上传中..." when loading'` checks for the literal "上传中...". The new loading text is "处理中" (without ellipsis). Update that test:
>
> ```tsx
>   it('shows "处理中" when loading', () => {
>     render(<BigButton text="拍隐患" onTap={() => undefined} loading />);
>     expect(screen.getByText('处理中')).toBeInTheDocument();
>     expect(screen.queryByText('拍隐患')).not.toBeInTheDocument();
>   });
> ```

**Step 6: Run full gates**

```bash
pnpm test && pnpm lint && npx tsc --noEmit
```
Expected: all green. Test count **60** (58 + 2 net new, with 1 existing test text updated).

**Step 7: Commit**

```bash
git -C /d/workspace/tiktok/safety-scout add miniprogram/src/components/BigButton miniprogram/tests/components/BigButton.test.tsx
git -C /d/workspace/tiktok/safety-scout commit -m "feat(miniprogram): BigButton dossier rewrite (charcoal/paper, two-line label)"
```

---

## Task 5: HeaderBand (rename of HeroBanner)

**Files:**
- Rename: `miniprogram/src/components/HeroBanner/` → `miniprogram/src/components/HeaderBand/`
- Rewrite: `miniprogram/src/components/HeaderBand/index.tsx`
- Rewrite: `miniprogram/src/components/HeaderBand/index.module.scss`
- Rename: `miniprogram/tests/components/HeroBanner.test.tsx` → `HeaderBand.test.tsx`
- Modify: `miniprogram/src/pages/index/index.tsx`
- Modify: `miniprogram/src/pages/report/index.tsx`

**Step 1: Rename directories and files**

```bash
cd D:\workspace\tiktok\safety-scout\miniprogram
git mv src/components/HeroBanner src/components/HeaderBand
git mv tests/components/HeroBanner.test.tsx tests/components/HeaderBand.test.tsx
```

**Step 2: Write failing tests**

Replace `tests/components/HeaderBand.test.tsx` entire contents with:

```tsx
/**
 * HeaderBand —— 顶部铭牌，每页都有。
 * 不再有 intro / metric 两种 mode；只有一个统一形态：
 *   SAFETY SCOUT            NO.xxx (optional)
 *   工地安全巡检系统          subtitle (optional, e.g. timestamp)
 *   ─────────────────────  (1px charcoal rule)
 */
import { render, screen } from '@testing-library/react';
import { HeaderBand } from '../../src/components/HeaderBand';

describe('HeaderBand', () => {
  it('renders the brand mark every time', () => {
    render(<HeaderBand />);
    expect(screen.getByText('SAFETY SCOUT')).toBeInTheDocument();
    expect(screen.getByText('工地安全巡检系统')).toBeInTheDocument();
  });

  it('renders optional identifier (e.g. NO.2026-05-20-0001) when provided', () => {
    render(<HeaderBand identifier="NO.2026-05-20-0001" />);
    expect(screen.getByText('NO.2026-05-20-0001')).toBeInTheDocument();
  });

  it('renders optional subtitle (e.g. timestamp) when provided', () => {
    render(<HeaderBand subtitle="2026·05·20  14:32" />);
    expect(screen.getByText('2026·05·20  14:32')).toBeInTheDocument();
  });

  it('omits identifier line when not provided', () => {
    render(<HeaderBand />);
    expect(screen.queryByText(/^NO\./)).not.toBeInTheDocument();
  });
});
```

**Step 3: Run tests to verify they fail**

Command: `pnpm test -- HeaderBand.test`
Expected: **FAIL** — old `HeroBanner` exports `HeroBanner`, not `HeaderBand`.

**Step 4: Rewrite `src/components/HeaderBand/index.tsx`**

```tsx
/**
 * HeaderBand —— 顶部铭牌。
 *
 * 每个页面都用同一份 banner：左侧是品牌（拉丁 + 中文两行），右侧可选 identifier
 * (NO.xxx 编号) + 可选 subtitle (一般是时间戳)。底部 1px charcoal rule 把
 * banner 和页面其它内容分开。
 *
 * 没有交互、没有 mode 切换，就是一个静态文档表头。
 */
import { View, Text } from '@tarojs/components';

import styles from './index.module.scss';

export interface HeaderBandProps {
  /** 编号 / 文档号；可选 (e.g. "NO.2026-05-20-0001") */
  identifier?: string;
  /** 副标 / 时间戳；可选 (e.g. "2026·05·20  14:32") */
  subtitle?: string;
}

export function HeaderBand({ identifier, subtitle }: HeaderBandProps) {
  return (
    <View className={styles.band}>
      <View className={styles.row}>
        <Text className={styles.brand}>SAFETY SCOUT</Text>
        {identifier && <Text className={styles.identifier}>{identifier}</Text>}
      </View>
      <View className={styles.row}>
        <Text className={styles.brandZh}>工地安全巡检系统</Text>
        {subtitle && <Text className={styles.subtitle}>{subtitle}</Text>}
      </View>
      <View className={styles.rule} />
    </View>
  );
}
```

**Step 5: Rewrite `src/components/HeaderBand/index.module.scss`**

```scss
// 顶部铭牌：两行 flex row + 底部 1px solid charcoal rule。
// padding 模拟文档报头留白，rule 让 header 区域和正文 visually 切断。

.band {
  padding: var(--space-3) var(--space-3) var(--space-2);
  background-color: var(--color-paper);
}

.row {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-2);
}

.brand {
  font-family: var(--font-mono);
  font-size: 18px;
  font-weight: 500;
  letter-spacing: 3px;
  color: var(--color-charcoal);
}

.identifier {
  font-family: var(--font-mono);
  font-size: var(--fs-meta);
  font-weight: 400;
  letter-spacing: 1px;
  color: var(--color-eng-red);
}

.brandZh {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 400;
  letter-spacing: 2px;
  color: var(--color-charcoal);
}

.subtitle {
  font-family: var(--font-mono);
  font-size: var(--fs-meta);
  font-weight: 400;
  letter-spacing: 1px;
  color: var(--color-caliper-grey);
}

.rule {
  margin-top: var(--space-2);
  border-top: var(--border-charcoal);
}
```

**Step 6: Update the pages to use HeaderBand**

Edit `miniprogram/src/pages/index/index.tsx`:
- Change the import: `import { HeroBanner } from '../../components/HeroBanner';` → `import { HeaderBand } from '../../components/HeaderBand';`
- Replace the `<HeroBanner ... />` block with `<HeaderBand subtitle="拍照即查 · AI 30s 出报告" />`.

Edit `miniprogram/src/pages/report/index.tsx`:
- Change the import: `import { HeroBanner } from '../../components/HeroBanner';` → `import { HeaderBand } from '../../components/HeaderBand';`
- Replace the `<HeroBanner mode="metric" ... />` block with:

```tsx
<HeaderBand identifier={`NO.${formatIdentifier(report.created_at)}`} subtitle={meta} />
```

And add a helper at the bottom of the file:

```tsx
function formatIdentifier(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    // Production system would use a sequence number from the backend; for now,
    // a short hash of the ISO string is good enough to look like an identifier.
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

> The `meta` line already exists in report/index.tsx from Task 6 of the prior plan. It currently reads `${SEVERITY_LABEL[severity]} · ${relativeTime(report.created_at)}` — keep that string, just pass it to `subtitle` now.

**Step 7: Run tests to verify all pass**

Command: `pnpm test -- HeaderBand`
Expected: **PASS** — 4/4.

Then full suite: `pnpm test`
Expected: **60** (52 from Task 1+3+4 net deltas). The renamed test file replaces the prior HeroBanner test count (3 tests gone, 4 new = +1).

**Step 8: Run full gates + visual sanity build**

```bash
pnpm test && pnpm lint && npx tsc --noEmit && pnpm build:h5:dev
```
Expected: all green. Build clean.

**Step 9: Commit**

```bash
git -C /d/workspace/tiktok/safety-scout add -A miniprogram/src/components/HeaderBand miniprogram/tests/components/HeaderBand.test.tsx miniprogram/src/pages/index/index.tsx miniprogram/src/pages/report/index.tsx
git -C /d/workspace/tiktok/safety-scout commit -m "feat(miniprogram): HeaderBand replaces HeroBanner (dossier top band)"
```

> `git mv` should have staged the renames; verify with `git status` before commit.

---

## Task 6: HazardCard rewrite + delete PlainWarningCard

**Files:**
- Rewrite: `miniprogram/src/components/HazardCard/index.tsx`
- Rewrite: `miniprogram/src/components/HazardCard/index.module.scss`
- Rewrite: `miniprogram/tests/components/HazardCard.test.tsx`
- **Delete**: `miniprogram/src/components/PlainWarningCard/`
- **Delete**: `miniprogram/tests/components/PlainWarningCard.test.tsx`
- Modify: `miniprogram/src/pages/report/index.tsx` (remove PlainWarningCard import/usage)

**Step 1: Rewrite HazardCard test for new shape**

Replace `miniprogram/tests/components/HazardCard.test.tsx` with:

```tsx
/**
 * HazardCard (dossier) —— 编号 + severity 条带 + 三栏 (现象/依据/整改)。
 */
import { render, screen } from '@testing-library/react';
import { HazardCard } from '../../src/components/HazardCard';
import { SEVERITY_COLOR } from '../../src/utils/severity';
import type { Hazard } from '../../src/types/report';

function makeHazard(overrides: Partial<Hazard> = {}): Hazard {
  return {
    category_code: 'H1',
    category_name: '高处作业',
    description: '高处作业未挂安全带',
    severity: 'high',
    regulation: 'GB 50656-2011 §3.2',
    suggestion: '立即停工配发安全带',
    ...overrides,
  };
}

describe('HazardCard (dossier)', () => {
  it('renders numbered identifier "01" with severity tag "HIGH"', () => {
    render(<HazardCard hazard={makeHazard()} index={1} total={3} />);
    expect(screen.getByText('01')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
  });

  it('renders 现象 / 依据 / 整改 three labeled rows', () => {
    render(<HazardCard hazard={makeHazard()} index={1} total={3} />);
    expect(screen.getByText('现象')).toBeInTheDocument();
    expect(screen.getByText('依据')).toBeInTheDocument();
    expect(screen.getByText('整改')).toBeInTheDocument();
    expect(screen.getByText('高处作业未挂安全带')).toBeInTheDocument();
    expect(screen.getByText('GB 50656-2011 §3.2')).toBeInTheDocument();
    expect(screen.getByText('立即停工配发安全带')).toBeInTheDocument();
  });

  it('omits 依据 row when regulation is empty', () => {
    render(<HazardCard hazard={makeHazard({ regulation: '' })} index={1} total={3} />);
    expect(screen.queryByText('依据')).not.toBeInTheDocument();
  });

  it('severity stripe element carries severity color', () => {
    const { container } = render(<HazardCard hazard={makeHazard()} index={1} total={3} />);
    const stripe = container.querySelector('[data-severity-stripe="high"]') as HTMLElement;
    expect(stripe).not.toBeNull();
    expect(stripe.style.backgroundColor.toLowerCase()).toContain(SEVERITY_COLOR.high.toLowerCase().slice(1));
    // tolerant: jsdom may normalize to rgb(); just check the hex digits appear somewhere
  });
});
```

> The existing `HazardCard.test.tsx` exercises the old shape (severity-pill, expand-regulation-toggle, integrated suggestion). We're throwing it out — write the new test from scratch.

**Step 2: Run tests to verify they fail**

Command: `pnpm test -- HazardCard.test`
Expected: **FAIL** — the new structure (numbered, three labeled rows, stripe data attribute) doesn't exist yet.

**Step 3: Rewrite `HazardCard/index.tsx`**

```tsx
/**
 * HazardCard (dossier) —— 编号 + severity 条带 + 三栏标签。
 *
 * 形态：
 *   ┌──────────────────────────────────────┐
 *   │ 01 ·  HIGH  ·····················     │   ← header rule，编号 + severity tag
 *   │ 现象  |  高处作业未挂安全带          │
 *   │ 依据  |  GB 50656-2011 §3.2          │
 *   │ 整改  |  立即停工配发安全带          │
 *   │ ╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲ │   ← bottom hazard-tape on severity color
 *   └──────────────────────────────────────┘
 *
 * 没有 expand toggle —— 直接展开。规范条款为空就省略整行。
 */
import { View, Text } from '@tarojs/components';

import { SEVERITY_COLOR, SEVERITY_LABEL } from '../../utils/severity';
import type { Hazard } from '../../types/report';

import styles from './index.module.scss';

export interface HazardCardProps {
  hazard: Hazard;
  index?: number;
  total?: number;
}

const SEVERITY_TAG: Record<Hazard['severity'], string> = {
  high: 'HIGH',
  medium: 'MEDIUM',
  low: 'LOW',
};

export function HazardCard({ hazard, index, total }: HazardCardProps) {
  const hasIndex = typeof index === 'number';
  const hasRegulation = hazard.regulation.length > 0;
  return (
    <View className={styles.card} data-category={hazard.category_code}>
      <View className={styles.header}>
        {hasIndex && (
          <Text className={styles.index}>{String(index).padStart(2, '0')}</Text>
        )}
        <Text className={styles.dot}>·</Text>
        <Text className={styles.tag} style={{ color: SEVERITY_COLOR[hazard.severity] }}>
          {SEVERITY_TAG[hazard.severity]}
        </Text>
        <Text className={styles.headerRule}>
          {'·'.repeat(40)}
        </Text>
        {hasIndex && typeof total === 'number' && (
          <Text className={styles.indexOfTotal}>{`/ ${String(total).padStart(2, '0')}`}</Text>
        )}
      </View>

      <View className={styles.field}>
        <Text className={styles.fieldLabel}>现象</Text>
        <Text className={styles.fieldDivider}>|</Text>
        <Text className={styles.fieldValue}>{hazard.description}</Text>
      </View>

      {hasRegulation && (
        <View className={styles.field}>
          <Text className={styles.fieldLabel}>依据</Text>
          <Text className={styles.fieldDivider}>|</Text>
          <Text className={styles.fieldValue}>{hazard.regulation}</Text>
        </View>
      )}

      <View className={styles.field}>
        <Text className={styles.fieldLabel}>整改</Text>
        <Text className={styles.fieldDivider}>|</Text>
        <Text className={styles.fieldValue}>{hazard.suggestion}</Text>
      </View>

      <View
        className={styles.stripe}
        data-severity-stripe={hazard.severity}
        style={{ backgroundColor: SEVERITY_COLOR[hazard.severity] }}
      />
      <Text className={styles.metaTag} style={{ color: SEVERITY_COLOR[hazard.severity] }}>
        {SEVERITY_LABEL[hazard.severity]} · {hazard.category_name}
      </Text>
    </View>
  );
}
```

**Step 4: Rewrite `HazardCard/index.module.scss`**

```scss
// Dossier hazard card：no rounded corners, no shadow.
// Header (编号 + tag) + 3 field rows + severity stripe at bottom.

.card {
  padding: var(--space-3);
  background-color: var(--color-paper);
  border-top: var(--border-charcoal);
  position: relative;
}

.header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: var(--space-2);
  font-family: var(--font-mono);
}

.index {
  font-size: 22px;
  font-weight: 500;
  color: var(--color-charcoal);
}

.dot {
  font-size: 22px;
  color: var(--color-caliper-grey);
}

.tag {
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 2px;
}

.headerRule {
  flex: 1;
  font-size: 14px;
  color: var(--color-caliper-grey);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: clip;
}

.indexOfTotal {
  font-size: 14px;
  color: var(--color-caliper-grey);
}

.field {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px dashed var(--color-caliper-grey);

  &:last-of-type {
    border-bottom: none;
  }
}

.fieldLabel {
  flex-shrink: 0;
  width: 48px;
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  color: var(--color-charcoal);
}

.fieldDivider {
  flex-shrink: 0;
  font-family: var(--font-mono);
  color: var(--color-caliper-grey);
}

.fieldValue {
  flex: 1;
  font-family: var(--font-body);
  font-size: var(--fs-body);
  line-height: 1.45;
  color: var(--color-charcoal);
}

.stripe {
  margin-top: var(--space-2);
  height: 6px;
  // 警示斜条 pattern 在 H5 上通过 background-image 渲染；weapp 上简化为纯色块
  background-image: linear-gradient(
    135deg,
    transparent 0,
    transparent 4px,
    rgba(0, 0, 0, 0.18) 4px,
    rgba(0, 0, 0, 0.18) 8px
  );
  background-size: 8px 8px;
}

.metaTag {
  display: block;
  margin-top: var(--space-1);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 1px;
  text-align: right;
}
```

**Step 5: Delete PlainWarningCard**

```bash
cd D:\workspace\tiktok\safety-scout
git rm -r miniprogram/src/components/PlainWarningCard
git rm miniprogram/tests/components/PlainWarningCard.test.tsx
```

**Step 6: Remove PlainWarningCard from report page**

Edit `miniprogram/src/pages/report/index.tsx`:
- Remove the import line: `import { PlainWarningCard } from '../../components/PlainWarningCard';`
- Remove the JSX block:
  ```tsx
  <PlainWarningCard
    text={report.plain_warning}
    severity={severity}
  />
  ```
- The `report.plain_warning` text and `severity` will surface differently in Task 8 (when we add the report's hero metric block); for now, the warning text is gone from the rendered page. That's intentional — Task 8 puts it back in the new layout.

**Step 7: Run tests to verify all pass**

Commands:
```bash
pnpm test -- HazardCard
pnpm test
```
Expected: HazardCard suite 4/4 pass; full suite passes with PlainWarningCard tests deleted. Net test count after this task: prior 60 - 2 (PlainWarningCard) = 58 + 4 (new HazardCard) - 4 (old HazardCard) = **58**.

**Step 8: Run full gates**

```bash
pnpm test && pnpm lint && npx tsc --noEmit
```
Expected: all green.

**Step 9: Commit**

```bash
git -C /d/workspace/tiktok/safety-scout add -A miniprogram/src/components/HazardCard miniprogram/tests/components/HazardCard.test.tsx miniprogram/src/pages/report/index.tsx
git -C /d/workspace/tiktok/safety-scout commit -m "feat(miniprogram): HazardCard dossier rewrite + drop PlainWarningCard"
```

---

## Task 7: ProgressIndicator — monospace readout

**Files:**
- Rewrite: `miniprogram/src/components/ProgressIndicator/index.tsx`
- Rewrite: `miniprogram/src/components/ProgressIndicator/index.module.scss`
- Rewrite: `miniprogram/tests/components/ProgressIndicator.test.tsx`

**Step 1: Write failing tests**

Replace `tests/components/ProgressIndicator.test.tsx` contents with:

```tsx
/**
 * ProgressIndicator (dossier) —— monospace readout, no spinner.
 *
 * 形态：
 *   READING ················ 12s
 *   01  拍照已就绪
 *   02  AI 识别中  ◀ active row
 *   03  报告生成中
 */
import { render, screen } from '@testing-library/react';
import { ProgressIndicator } from '../../src/components/ProgressIndicator';

describe('ProgressIndicator (dossier)', () => {
  it('renders all three numbered step labels', () => {
    render(<ProgressIndicator currentStep={2} elapsedMs={5000} />);
    expect(screen.getByText('01')).toBeInTheDocument();
    expect(screen.getByText('02')).toBeInTheDocument();
    expect(screen.getByText('03')).toBeInTheDocument();
    expect(screen.getByText('拍照已就绪')).toBeInTheDocument();
    expect(screen.getByText('AI 识别中')).toBeInTheDocument();
    expect(screen.getByText('报告生成中')).toBeInTheDocument();
  });

  it('shows elapsed seconds during step 2', () => {
    render(<ProgressIndicator currentStep={2} elapsedMs={5000} />);
    expect(screen.getByText(/5s/)).toBeInTheDocument();
  });

  it('marks the active step with data-state="active"', () => {
    const { container } = render(<ProgressIndicator currentStep={2} elapsedMs={0} />);
    const activeRows = container.querySelectorAll('[data-state="active"]');
    expect(activeRows.length).toBeGreaterThan(0);
  });
});
```

**Step 2: Run tests to verify they fail**

Command: `pnpm test -- ProgressIndicator`
Expected: **FAIL** — text content differs (was "拍照成功" / "AI 分析中" / "报告就绪").

**Step 3: Rewrite `ProgressIndicator/index.tsx`**

```tsx
import { View, Text } from '@tarojs/components';

import styles from './index.module.scss';

export interface ProgressIndicatorProps {
  /** 当前步骤：1=拍照已就绪 2=AI 识别中 3=报告生成中 */
  currentStep: 1 | 2 | 3;
  /** 已耗时（毫秒），步骤 2 显示 */
  elapsedMs?: number;
}

const STEPS = [
  { key: 1, label: '拍照已就绪' },
  { key: 2, label: 'AI 识别中' },
  { key: 3, label: '报告生成中' },
] as const;

export function ProgressIndicator({ currentStep, elapsedMs }: ProgressIndicatorProps) {
  const secs = typeof elapsedMs === 'number' ? Math.floor(elapsedMs / 1000) : 0;
  const dotsCount = 16 + (secs % 8);  // mild text-tick so the user knows it's alive
  return (
    <View className={styles.container}>
      <View className={styles.readout}>
        <Text className={styles.readoutLabel}>READING</Text>
        <Text className={styles.readoutDots}>{'·'.repeat(dotsCount)}</Text>
        {currentStep === 2 && <Text className={styles.readoutTime}>{secs}s</Text>}
      </View>

      <View className={styles.steps}>
        {STEPS.map((s) => {
          const isDone = s.key < currentStep;
          const isActive = s.key === currentStep;
          const state = isDone ? 'done' : isActive ? 'active' : 'pending';
          return (
            <View key={s.key} className={styles.step} data-state={state}>
              <Text className={styles.stepIndex}>{String(s.key).padStart(2, '0')}</Text>
              <Text className={styles.stepLabel}>{s.label}</Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}
```

**Step 4: Rewrite `ProgressIndicator/index.module.scss`**

```scss
// Dossier readout：等宽字 + 滴答 dots + numbered step rows.
.container {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6) var(--space-3);
  background-color: var(--color-paper);
  min-height: 100vh;
}

.readout {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-family: var(--font-mono);
  border-top: var(--border-charcoal);
  border-bottom: var(--border-charcoal);
  padding: var(--space-2) 0;
}

.readoutLabel {
  font-size: 14px;
  letter-spacing: 3px;
  color: var(--color-charcoal);
}

.readoutDots {
  flex: 1;
  font-size: 14px;
  color: var(--color-caliper-grey);
  overflow: hidden;
  white-space: nowrap;
}

.readoutTime {
  font-size: 14px;
  color: var(--color-eng-red);
}

.steps {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.step {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  font-family: var(--font-mono);

  &[data-state='done'] {
    color: var(--color-caliper-grey);
  }
  &[data-state='active'] {
    color: var(--color-eng-red);
  }
  &[data-state='pending'] {
    color: var(--color-caliper-grey);
    opacity: 0.5;
  }
}

.stepIndex {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 500;
}

.stepLabel {
  font-family: var(--font-body);
  font-size: var(--fs-body);
  letter-spacing: 1px;
}
```

**Step 5: Run tests to verify all pass**

Command: `pnpm test -- ProgressIndicator`
Expected: **PASS** — 3/3.

Full suite: `pnpm test`
Expected: **58** (no net test count change vs Task 6).

**Step 6: Run full gates**

```bash
pnpm test && pnpm lint && npx tsc --noEmit
```
Expected: all green.

**Step 7: Commit**

```bash
git -C /d/workspace/tiktok/safety-scout add miniprogram/src/components/ProgressIndicator miniprogram/tests/components/ProgressIndicator.test.tsx
git -C /d/workspace/tiktok/safety-scout commit -m "feat(miniprogram): ProgressIndicator dossier readout style"
```

---

## Task 8: Pages + desktop chrome

**Files:**
- Rewrite: `miniprogram/src/pages/index/index.tsx`
- Rewrite: `miniprogram/src/pages/index/index.module.scss`
- Rewrite: `miniprogram/src/pages/report/index.tsx`
- Rewrite: `miniprogram/src/pages/report/index.module.scss`
- Modify: `miniprogram/src/app.scss` (desktop chrome details)

> No unit tests for pages — the visual gate is Task 9 e2e screenshots.

**Step 1: Rewrite `pages/index/index.tsx`**

```tsx
import Taro from '@tarojs/taro';
import { View, Text } from '@tarojs/components';
import { useState } from 'react';

import { BigButton } from '../../components/BigButton';
import { HeaderBand } from '../../components/HeaderBand';
import { captureImage } from '../../hooks/useImageCapture';
import { createInspection } from '../../api/inspections';
import { mapApiError } from '../../utils/errorMessage';

import styles from './index.module.scss';

const SHOT_TIPS = [
  '贴近隐患位置，保持光线充足',
  '画面含工人 / 护栏 / 电箱 等关键元素',
  '距离 1–3m 为佳',
];

export default function IndexPage() {
  const [uploading, setUploading] = useState(false);

  const handleTap = async () => {
    if (uploading) return;
    let image;
    try { image = await captureImage(); } catch (_e) { return; }
    setUploading(true);
    try {
      const resp = await createInspection(image.tempFilePath);
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
      <HeaderBand subtitle="拍照即查 · AI 30s 出报告" />

      <View className={styles.titleBlock}>
        <Text className={styles.h1}>工地隐患识别</Text>
        <Text className={styles.h1Latin}>AI · SITE HAZARD INSPECTION</Text>
      </View>

      <BigButton
        text="拍摄现场照片"
        subtitle="CAPTURE INSPECTION PHOTO"
        prefixGlyph="plus-square"
        onTap={handleTap}
        loading={uploading}
      />

      <View className={styles.section}>
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

      <View className={styles.footer}>
        <Text className={styles.footerText}>⌖ AI ENGINE v3 · Claude Vision · ~30s/帧</Text>
      </View>
    </View>
  );
}
```

**Step 2: Rewrite `pages/index/index.module.scss`**

```scss
// 首页 dossier 布局：HeaderBand + 大标题 + 按钮 + 编号 tips + footer。
.page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--color-paper);
}

.titleBlock {
  padding: var(--space-4) var(--space-3) var(--space-2);
}

.h1 {
  display: block;
  font-family: var(--font-display);
  font-size: var(--fs-h1);
  font-weight: 700;
  letter-spacing: 4px;
  color: var(--color-charcoal);
  line-height: 1.1;
}

.h1Latin {
  display: block;
  margin-top: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow);
  font-weight: 400;
  letter-spacing: 3px;
  color: var(--color-caliper-grey);
}

.section {
  padding: var(--space-3);
}

.sectionRule {
  border-top: var(--border-charcoal);
  padding-top: var(--space-1);
  margin-bottom: var(--space-2);
}

.sectionLabel {
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow);
  letter-spacing: 3px;
  color: var(--color-charcoal);
}

.tipRow {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-1) 0;
  font-family: var(--font-body);
}

.tipIndex {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 500;
  color: var(--color-eng-red);
}

.tipText {
  font-size: var(--fs-body);
  color: var(--color-charcoal);
  line-height: 1.4;
}

.footer {
  margin-top: auto;
  padding: var(--space-3);
  border-top: var(--border-charcoal);
}

.footerText {
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow);
  letter-spacing: 2px;
  color: var(--color-caliper-grey);
}

// Tablet / desktop H5：容器居中 + 1px charcoal 边框 (前一版 box-shadow 在这里删掉，dossier 不用 floating card)
@media (min-width: 768px) {
  .page {
    max-width: 640px;
    margin: 0 auto;
    border-left: var(--border-charcoal);
    border-right: var(--border-charcoal);
  }
}
@media (min-width: 1024px) {
  .page {
    max-width: 720px;
  }
}
```

**Step 3: Rewrite `pages/report/index.tsx`**

Keep the polling logic, ErrorView, formatIdentifier helper (from Task 5). Rewrite the `SucceededReport` function:

```tsx
function SucceededReport({ report }: { report: ReportPayload }) {
  const sorted = sortBySeverity(report.hazards);
  const severity = report.overall_severity;
  const meta = `${SEVERITY_LABEL[severity]} · ${relativeTime(report.created_at)}`;
  return (
    <View className={styles.page}>
      <HeaderBand
        identifier={`NO.${formatIdentifier(report.created_at)}`}
        subtitle={meta}
      />

      <View className={styles.titleBlock}>
        <Text className={styles.eyebrow}>INSPECTION REPORT</Text>
        <Text className={styles.h1}>现场巡检报告</Text>
      </View>

      <View className={styles.hero}>
        <View className={styles.heroLeft}>
          <Text className={styles.heroCount} style={{ color: SEVERITY_COLOR[severity] }}>
            {sorted.length}
          </Text>
          <Text className={styles.heroCountLabel}>项隐患待整改</Text>
        </View>
        <View className={styles.heroRight}>
          <Text className={styles.heroSeverity} style={{ color: SEVERITY_COLOR[severity] }}>
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

      <View className={styles.footer}>
        <Text className={styles.footerText}>⌖ AI ENGINE v3 · Claude Vision</Text>
      </View>
    </View>
  );
}
```

Remove the old `pageHeader / pageEyebrow / pageTitle / summaryCard` JSX block; it's replaced by `titleBlock + hero + summarySection`.

**Step 4: Rewrite `pages/report/index.module.scss`**

```scss
.page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--color-paper);
  padding-bottom: var(--space-5);
}

.titleBlock {
  padding: var(--space-4) var(--space-3) var(--space-2);
}

.eyebrow {
  display: block;
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow);
  letter-spacing: 3px;
  color: var(--color-caliper-grey);
}

.h1 {
  display: block;
  margin-top: var(--space-1);
  font-family: var(--font-display);
  font-size: var(--fs-h1);
  font-weight: 700;
  letter-spacing: 3px;
  color: var(--color-charcoal);
  line-height: 1.1;
}

.hero {
  display: flex;
  border-top: var(--border-charcoal);
  border-bottom: var(--border-charcoal);
  margin: var(--space-3) var(--space-3) 0;
  padding: var(--space-3) 0;
  gap: var(--space-3);
}

.heroLeft, .heroRight {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.heroCount {
  font-family: var(--font-condensed);
  font-size: var(--fs-display);
  font-weight: 700;
  letter-spacing: -2px;
  line-height: 1;
}

.heroCountLabel,
.heroSeverityLabel {
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow);
  letter-spacing: 2px;
  color: var(--color-caliper-grey);
}

.heroSeverity {
  font-family: var(--font-display);
  font-size: var(--fs-h2);
  font-weight: 700;
  letter-spacing: 2px;
}

.summarySection {
  padding: var(--space-3);
}

.summaryLabel {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-bottom: var(--space-1);
}

.summaryLabelBar {
  color: var(--color-charcoal);
  font-family: var(--font-mono);
}

.summaryLabelText {
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow);
  letter-spacing: 3px;
  color: var(--color-charcoal);
}

.summaryText {
  display: block;
  font-family: var(--font-body);
  font-size: var(--fs-body);
  line-height: 1.5;
  color: var(--color-charcoal);
}

.warning {
  display: block;
  margin-top: var(--space-2);
  font-family: var(--font-body);
  font-size: var(--fs-body);
  line-height: 1.5;
  color: var(--color-eng-red);
}

.sectionRule {
  padding: var(--space-3);
  border-top: var(--border-charcoal);
  margin-top: var(--space-2);
}

.sectionLabel {
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow);
  letter-spacing: 3px;
  color: var(--color-charcoal);
}

.footer {
  margin-top: auto;
  padding: var(--space-3);
  border-top: var(--border-charcoal);
}

.footerText {
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow);
  letter-spacing: 2px;
  color: var(--color-caliper-grey);
}

// Error states (preserve from prior file)
.errorView {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 40px;
  background-color: var(--color-paper);
  gap: var(--space-2);
}
.errorText {
  font-family: var(--font-display);
  font-size: 30px;
  color: var(--color-charcoal);
  text-align: center;
  line-height: 1.35;
  font-weight: 700;
}
.retryHint {
  font-family: var(--font-mono);
  font-size: var(--fs-eyebrow);
  color: var(--color-caliper-grey);
  letter-spacing: 2px;
}

@media (min-width: 768px) {
  .page {
    max-width: 640px;
    margin: 0 auto;
    border-left: var(--border-charcoal);
    border-right: var(--border-charcoal);
  }
}
@media (min-width: 1024px) {
  .page {
    max-width: 720px;
  }
}
```

> Note: the `ErrorView` JSX in the file already uses `styles.errorView`, `styles.errorText`, `styles.retryHint` — those classes are preserved. The `<Icon name="x-circle" ... />` color uses old `#FF3B30`; update its color prop to `var(--color-eng-red)` won't work in JSX (inline style only accepts literal values); leave as `#C8281C` literal:
>
> `<Icon name="x-circle" size={48} color="#C8281C" />`

**Step 5: Update `src/app.scss` desktop chrome**

Final `src/app.scss`:

```scss
@import './styles/fonts.scss';
@import './styles/tokens.scss';

page {
  font-family: var(--font-body);
  background-color: var(--color-paper);
  color: var(--color-charcoal);
}

// Desktop: paper-darker backdrop reveals the container as a document on a desk
@media (min-width: 768px) {
  body {
    background-color: var(--color-paper-backdrop);
    margin: 0;
  }
}
```

> The 480px max-width container from `85e6434` is overridden by the per-page `@media` blocks in this Task 8's SCSS. We do NOT need the box-shadow chrome anymore — the 1px charcoal border on each page gives the document-edge feel that the shadow was trying to approximate.

**Step 6: Run quality gates**

```bash
pnpm test && pnpm lint && npx tsc --noEmit && pnpm build:h5:dev
```
Expected: all green. Tests **58**, build clean.

**Step 7: Commit**

```bash
git -C /d/workspace/tiktok/safety-scout add miniprogram/src/pages miniprogram/src/app.scss
git -C /d/workspace/tiktok/safety-scout commit -m "feat(miniprogram): dossier page layouts + desktop chrome (1px charcoal border)"
```

---

## Task 9: E2E + visual verification

**Files:**
- Modify: `miniprogram/tests/e2e/h5-smoke.mjs` (add desktop-viewport screenshot)

**Step 1: Update smoke script to take two screenshots**

In `tests/e2e/h5-smoke.mjs`, find the section that creates the browser page (around line 110-115) and the screenshot save (around line 143). Modify so that **after** the mobile screenshot, we resize to desktop and screenshot again:

Add right before the close of the `try` block (after `console.log('screenshot saved: ...')` of the existing mobile shot):

```javascript
    // Second screenshot at desktop viewport — verifies dossier desktop chrome
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.waitForTimeout(200);  // let media query reflow settle
    const DESKTOP_SHOT = SCREENSHOT_PATH.replace('.png', '-desktop.png');
    await page.screenshot({ path: DESKTOP_SHOT, fullPage: true });
    console.log(`  screenshot saved: ${DESKTOP_SHOT}`);
```

If `SCREENSHOT_PATH` ends `h5-smoke.png`, the new file will be `h5-smoke-desktop.png` in the same directory.

> Note: `setViewportSize` is playwright-core's API on the Page object; verify the import is `chromium` from `playwright-core`. Already is.

**Step 2: Run e2e**

```bash
cd D:\workspace\tiktok\safety-scout\miniprogram && pnpm build:h5:dev && pnpm test:e2e:h5
```
Expected: exit 0; both screenshots written.

**Step 3: Inspect screenshots (manual / controller eyeball)**

Open `tests/e2e/h5-smoke.png` (390×844 mobile) — should show:
- HeaderBand at top: SAFETY SCOUT + NO is absent here (home page has no identifier) + 工地安全巡检系统 + 拍照即查 subtitle + 1px charcoal rule
- Big "工地隐患识别" Source Han Serif title + AI · SITE HAZARD eyebrow
- Charcoal square button with ⊕ glyph + 拍摄现场照片 / CAPTURE INSPECTION PHOTO
- "拍摄要点" section with 01/02/03 numbered list (red numbers)
- Footer band with ⌖ AI ENGINE

Open `tests/e2e/h5-smoke-desktop.png` (1280×800 desktop) — should show:
- Paper-darker (#E8E2D4) backdrop visible on left + right margins
- 640-720px wide centered container with 1px charcoal borders left + right
- Same content as mobile, in a wider rendering

If any of these look wrong, report back specifically what's off — usually a one-line fix.

**Step 4: Full quality gates**

```bash
pnpm test && pnpm lint && npx tsc --noEmit
```
Expected: all green; tests **58/58/0**.

Verify no skipped tests:
```bash
pnpm test 2>&1 | grep -E "(Tests:|skipped|todo)"
```
Expected: `Tests: 58 passed, 58 total` and nothing skipped.

**Step 5: Commit (if step 1 actually modified the smoke script)**

```bash
git -C /d/workspace/tiktok/safety-scout add miniprogram/tests/e2e/h5-smoke.mjs
git -C /d/workspace/tiktok/safety-scout commit -m "test(miniprogram): smoke e2e screenshots at both mobile and desktop viewports"
```

---

## Acceptance criteria

After all 9 tasks land:

- [ ] `pnpm test` 58/58, 0 skipped, 0 failed
- [ ] `pnpm lint` 0 errors
- [ ] `npx tsc --noEmit` 0 errors
- [ ] `pnpm build:h5:dev` clean
- [ ] `pnpm test:e2e:h5` produces both `h5-smoke.png` (mobile) and `h5-smoke-desktop.png` (desktop) and exits 0
- [ ] Mobile screenshot: paper background, charcoal text, IBM Plex + Songti (or Source Han Serif if you dropped the woff2), numbered list pattern, NO emoji
- [ ] Desktop screenshot: paper-darker backdrop visible on margins, 640-720px container with 1px charcoal borders, no rounded corners
- [ ] No `PlainWarningCard` references anywhere: `grep -rn "PlainWarningCard" miniprogram/src` returns nothing
- [ ] No `helmet` icon references anywhere: `grep -rn "helmet" miniprogram/src` returns nothing
- [ ] Severity palette is dossier-engineering (red `#C8281C`, amber `#E07B1F`, green `#3D7C3D`) — verify in `src/utils/severity.ts`

## Rollback (if user changes mind mid-execution)

Each task = one commit. To revert any phase: `git revert <sha>`. To revert the entire redesign back to `6b1231e` (the design doc only): `git reset --hard 6b1231e` (destructive — confirm before running).
