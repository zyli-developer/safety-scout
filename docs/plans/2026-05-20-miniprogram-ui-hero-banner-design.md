# Miniprogram UI Redesign — Hero Banner

**Date**: 2026-05-20
**Status**: Approved, ready for implementation plan
**Author**: zyli + Claude (brainstorming)
**Prior art**: `66d4d4e refactor: 前端 UI 重做为 iOS HIG 风（去 emoji / 减颜色 / 减装饰）`

## Problem

Current pages (post-`66d4d4e`) are clean iOS HIG but read as "too empty / undesigned":

- **Index page**: gray background + large title + one blue button + one tip line. No visual anchor; looks half-finished.
- **Report page**: large title + grouped cards. Functional, but visually flat — no signal of "this is a finished safety report".

User feedback (multi-choice, this conversation): the pain is **"too sparse, like undesigned"**, not "wrong style" — so we stay inside iOS HIG and add density via a single new pattern rather than re-painting everything.

## Goal

Add a **Hero Banner** white-card pattern to the top of both pages that:

1. Increases visual density without adding interaction (no extra buttons / no extra screens — preserves the `拍照 → 等待 → 看报告` three-step product invariant in `CLAUDE.md`).
2. Stays inside iOS HIG (no warm colors, no illustrations, no emoji — does not roll back `66d4d4e`).
3. References the iOS Health / Fitness "metric banner" pattern that is itself canonical HIG.

## Non-goals

- ✋ Not redesigning `PlainWarningCard` / `HazardCard` / `ProgressIndicator` / `BigButton` — they just landed in `66d4d4e` and work.
- ✋ Not introducing new colors, no warm palette, no illustration style.
- ✋ Not adding any interaction (no banner click, no expand/collapse). Hero is pure display.
- ✋ Not adding history / settings / login.

## Visual spec

### Index page (`pages/index`)

```
┌─────────────────────────────────┐
│  (padding 60px top)             │
│                                 │
│  ┌───────────────────────────┐  │
│  │ [helmet      工地隐患识别  │  │ ← HeroBanner mode=intro
│  │  56×56]    拍一张，AI     │  │   white card, radius 16
│  │           30 秒出报告      │  │   padding 20×22
│  └───────────────────────────┘  │   subtle shadow
│                                 │
│  Safety Scout                   │ ← eyebrow 18px (was 22)
│  工地隐患识别                    │ ← large title 50px (was 56)
│                                 │
│  [ ⬜  拍照检查 ]                │ ← BigButton (unchanged)
│                                 │
│  贴近隐患位置拍摄…               │ ← tip (unchanged)
└─────────────────────────────────┘
```

**Banner params**:
- Container: `background:#fff; border-radius:16px; padding:20px 22px; margin:0 16px;`
- Shadow: reuse summaryCard's — `0 0 0 0.5px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.04)`
- Layout: flex row, gap 16px, align-items center
- Helmet icon: 56×56, stroke 1.5px, color `#007AFF` (systemBlue)
- Title (line 1): 18px / weight 600 / `#1c1c1e`
- Subtitle (line 2): 14px / weight 400 / `#8e8e93`, line-height 1.4

**Page diff vs current**:
- `padding-top`: 80 → 60
- `.header { margin-bottom }`: 48 → 32
- `.largeTitle { font-size }`: 56 → 50

### Report page (`pages/report`)

```
┌─────────────────────────────────┐
│ (padding 32px top)              │
│                                 │
│ ┌─────────────────────────────┐ │
│ │  ◯    3 项隐患               │ │ ← HeroBanner mode=metric
│ │ ring  中风险 · 2 分钟前      │ │   left: 64×64 severity ring
│ │ 64×64                       │ │   right: count + meta
│ └─────────────────────────────┘ │
│                                 │
│ 2026-05-20 14:32                │ ← eyebrow (timestamp, kept)
│ 隐患报告                         │ ← large title 50px
│                                 │
│ [PlainWarningCard]              │ ← unchanged
│ [Summary card]                  │ ← unchanged
│                                 │
│ 隐患明细                         │ ← section header (unchanged)
│ [HazardCard × N]                │ ← unchanged
└─────────────────────────────────┘
```

**Banner params**:
- Same chrome (white card, radius 16, padding 20×22, margin 0 16, shadow).
- Severity ring: 64×64, stroke 6px, color `SEVERITY_COLOR[overall_severity]`, fill `SEVERITY_TINT[overall_severity]`, centered icon (high → `x-circle`, medium → `alert-triangle`, low → `check-circle`).
- Count (line 1): `{N} 项隐患` 28px / weight 700 / `#1c1c1e`
- Meta (line 2): `{severityLabel} · {relativeTime}` 14px / weight 400 / `#8e8e93`

**Page diff vs current**:
- `.pageHeader { padding-top }`: 48 → 32
- Delete `.pageMeta` "共识别 N 项" line — info migrated into banner

## Components

### New: `src/components/HeroBanner/`

```ts
type HeroBannerProps =
  | { mode: 'intro'; icon: IconName; title: string; subtitle: string }
  | { mode: 'metric'; severity: Severity; count: number; meta: string };
```

- One component, two modes via discriminated union, shared card chrome in SCSS.
- No `children` prop — deliberate. Banner is a tightly-scoped pattern, not a generic slot.
- Files: `index.tsx`, `index.module.scss`.

### Modified: `src/components/Icon/index.tsx`

Add `helmet` icon — single-stroke outline:
- Outer dome arc (top half of an oval-ish shape, ~16×10 in 24-viewBox)
- Horizontal brim line below the dome
- One small visor arc near the front edge of the dome

24×24 viewBox, stroke 1.5px, `currentColor`, no fill.

### New: `src/utils/relativeTime.ts`

```ts
export function relativeTime(iso: string, now: Date = new Date()): string;
```

Output rules (Chinese):
- `< 60s` → `刚刚`
- `< 60min` → `N 分钟前`
- same calendar day → `今天 HH:mm`
- previous calendar day → `昨天 HH:mm`
- else → `YYYY-MM-DD HH:mm`

Pure function, deterministic when `now` is injected → unit-testable.

### Modified: `src/utils/severity.ts`

Add:
```ts
export const SEVERITY_LABEL: Record<Severity, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
};
```

## Tokens

All reused — **no new tokens**:
- Radius 16px (banner only; other cards keep 12px).
- Shadow `0 0 0 0.5px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.04)` — reused from summaryCard.
- Colors: `SEVERITY_COLOR` / `SEVERITY_TINT` / `#007AFF` / `#8e8e93` / `#1c1c1e` / `#f2f2f7` all existing.

## Testing

Per [[feedback_phase_unit_tests]] (mandatory, zero skip):

| File | Coverage |
|---|---|
| `tests/components/HeroBanner.test.tsx` | (new) intro mode renders title/subtitle/icon; metric mode renders count/meta; ring color via dynamic import of `SEVERITY_COLOR` (same pattern as PlainWarningCard.test) |
| `tests/utils/relativeTime.test.ts` | (new) 5 cases: 刚刚 / N 分钟前 / 今天 / 昨天 / 更早 |
| Existing page tests | Update if any asserts on the deleted "共识别 N 项" pageMeta |

Quality gates:
- `pnpm test` ≥ 39 + new, 0 skip, 0 fail
- `pnpm lint` 0 error
- `npx tsc --noEmit` 0 error
- `pnpm test:e2e:h5` passes; existing screenshot diff inspected manually for banner

## Risk / rollback

- **Risk**: Banner pattern could feel heavy if page also has many cards (report page already has summary card + plain warning card + N hazard cards). Mitigation: banner is visually distinct (radius 16 vs 12) and `margin-bottom 24px` separates it from the page header.
- **Rollback**: Single component + 2 page edits. Reverting is `git revert` of the implementation commit.

## Open questions

None — all 4 user decisions captured:
1. Pain is "太空 / 像没设计过"
2. Fill with "顶部 hero illustration + 一句 value prop 文案"
3. Tonality: "轻量线性 SVG，仍在 iOS HIG 调调内"
4. Hero icon: 头盔轮廓 + 护目镜弧线
5. Meta time: relative (刚刚 / N 分钟前 / 今天 HH:mm)
6. Scope: index + report both, no other pages

## Next step

Invoke `superpowers:writing-plans` to produce a step-by-step implementation plan from this design.
