# Miniprogram UI Redesign — Site Inspection Dossier

**Date**: 2026-05-20
**Status**: Approved direction, ready for implementation plan
**Author**: zyli + Claude (`/frontend-design`)
**Supersedes**: `2026-05-20-miniprogram-ui-hero-banner-design.md` (the iOS HIG + hero-banner direction it described did not land aesthetically; user reported "ugly" after three rounds of iteration)

## Why we are pivoting

We tried iOS HIG (`66d4d4e`) → hero banner inside HIG (`2512ab4` + `9cc95fd`) → responsive container (`85e6434`). User reported "ugly" at each step. The latest H5 desktop screenshot (`tests/e2e/h5-smoke.png` + user's own browser screenshot at 1535×782 viewport) shows the core failure:

1. Helmet icon visually collides with the "Safety Scout" title text inside the banner card (the `gap: 16px` isn't enough at the rendered sizes)
2. The 480px centered container is mostly empty on desktop — too much dead grey space
3. The page reads as a generic "mobile app" — no identity, no construction-safety context
4. iOS HIG's soft palette + 16px radii + system fonts make it look indistinguishable from any other consumer Apple app

The issue is **the direction**, not the parameters. iOS HIG is designed for personal consumer apps inside Apple's ecosystem. Our audience is **construction-site safety officers** producing reports that get forwarded to crews — they need **authority, document-like density, professional Chinese-engineering language**, not Apple-app friendliness.

## Aesthetic direction: Site Inspection Dossier (工地许可证)

> Treat every screen as a **page from an official construction-inspection document**, not as a mobile app screen.

Mental model: when the safety officer screenshots a report and sends it to the foreman on WeChat, the receiver should see something that looks **stamped, numbered, and signed off** — the kind of artifact that, printed and chopped (盖章), would be accepted as the day's safety record.

This direction's load-bearing differentiators:
- **Authority** via document conventions (numbered headings, ruled separators, stamps, footers)
- **Density** via numbered lists (`01 · `, `02 · `) instead of bullets, ruled tables, dense Chinese
- **Engineering motifs** via measurement scales, NO.-style identifiers, monospace metadata
- **Specifically Chinese-engineering** — the visual language references 公文 / 工程报告 / 检查许可证, not generic "industrial design"

## Tokens

### Palette

| Role | Hex | Notes |
|---|---|---|
| Paper background | `#F4EFE5` | Main background — warm document paper, not the cool `#f2f2f7` iOS bg |
| Charcoal (primary text) | `#1A1A1A` | All body / title text; not pure black |
| Engineering red | `#C8281C` | Stamps, high-severity, NO. identifiers, critical actions — **not** the iOS `#FF3B30` (which glows on screen) |
| Survey blue | `#1A4B8C` | Meta info, secondary stamps, links if needed |
| Caliper grey | `#A8A096` | Rulers, scale ticks, separators, low-emphasis text |
| Warning amber | `#E07B1F` | Medium-severity hazards — replaces `#FF9500` |
| Pass green | `#3D7C3D` | Low-severity / verified status — replaces `#34C759` |

All severity colors keep their semantic role (`SEVERITY_COLOR.high/medium/low`) — we are just shifting the hexes.

### Type

**Latin + numerals (consistent across H5 + weapp via wx.loadFontFace where possible):**
- `IBM Plex Serif` — display, document title (e.g. "INSPECTION REPORT")
- `IBM Plex Mono` — numbers, identifiers (`NO.2026-05-20-0001`), timestamps, metadata
- `IBM Plex Sans Condensed` Bold — large numeric callouts ("3 项隐患")

**Chinese:**
- H5: `Source Han Serif SC` (思源宋体) self-hosted subset (~600KB for safety-officer-relevant character set) — official-document feel
- weapp fallback: `STSongti-SC`, `Songti SC`, `SimSun`, system serif cascade — visually similar within ~5%

**Why this combination is not AI-slop:**
- IBM Plex is a corporate-engineering font family — not Inter, not Roboto, not "system-ui"
- Source Han Serif gives Chinese authority that Source Han Sans (the lazy default) doesn't
- Plex Mono in numeric metadata is a strong tell that this is a technical / engineering surface, not a consumer app

### Spacing & geometry

- **Border-radius**: 0 for cards / panels, ≤ 4px for buttons (HIG's 12-16px softness is the enemy of document feel)
- **Borders**: 1px solid charcoal at 100% (sharper than HIG's `0 0 0 0.5px rgba(0,0,0,0.04)` shadow) — also use 1px dashed for "footnote" zones
- **Layout grid**: 8px base unit. Section-level rhythm = 24/32/48 (matches CAD-spacing intuition)

### Motion

**Deliberately minimal.** Static documents don't animate. Allowed:
- One-time stamp-down on the red NO. identifier on page load (~300ms, scale 1.15 → 1.0, opacity 0 → 1) — like an ink stamp landing
- Hover on button: paper-darkens 4% (no scale, no shadow lift)
- ProgressIndicator: monospace counter readout style (`READING ······ 12%`), no spinners, no pulses

No motion = part of the aesthetic. Static document feel is the differentiator.

## Layout grammars

### Header band — every page

```
┌─────────────────────────────────────────────────┐
│ SAFETY SCOUT                NO.2026-05-20-0001  │  ← Plex Mono left, red stamp-style right
│ 工地安全巡检系统             2026·05·20  14:32  │  ← Source Han Serif left, Plex Mono right
│ ───────────────────────────────────────────────  │  ← 1px charcoal solid rule
└─────────────────────────────────────────────────┘
```

Always present. Provides identity + identifier + timestamp regardless of page content.

### Home page

```
[Header band]

工地隐患识别                ← Source Han Serif Bold, 56px (h5) / 48px (weapp)
AI · SITE HAZARD            ← Plex Mono, 14px, all caps, caliper grey

┌─────────────────────────────────────────────────┐
│ ⊕  拍 摄 现 场 照 片                            │  ← Square button, charcoal bg, paper text
│    CAPTURE INSPECTION PHOTO                     │
└─────────────────────────────────────────────────┘

── 拍摄要点 ─────────────────────────────────────  ← Section rule with 中文 label

01  贴近隐患位置，保持光线充足
02  画面含工人 / 护栏 / 电箱 等关键元素
03  距离 1–3m 为佳

⌖ AI ENGINE v3 · Claude Vision · ~30s/帧        ← Footer band, mono, smaller
```

### Report page

```
[Header band — NO. updates to the inspection id]

INSPECTION REPORT           ← Plex Serif 24px, charcoal
现场巡检报告 · 第 0001 号    ← 中文 title, Source Han Serif Bold 40px

┌─────────────────────────────────────────────────┐
│                                                  │
│   3                          ⊘ 高 风 险          │  ← Massive Plex Sans Condensed Bold
│   ─── 项隐患待整改           ─── 风险等级判定    │     paired with ruled-line labels
│                                                  │
└─────────────────────────────────────────────────┘

▎ 现场总览                  ← left edge bar, charcoal
[summary text in 中文]

── 隐患明细 ─────────────────────────────────────

01 · HIGH ······································  ← Numbered + severity tag, Plex Mono
⊘ 高处作业未挂安全带
╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲╲  ← Hazard-tape stripe on severity color
现象  |  作业人员未系挂安全带操作钢架...
依据  |  GB 50656-2011 §3.2
整改  |  立即停工配发安全带并复核 ...

02 · MEDIUM ····································
[same structure]

[Footer band]
```

### Desktop chrome (H5 ≥ 1024px) — replaces current 480px max-width

Container: max-width 720 (not 480), centered.

Outside the container:
- Body bg: `#E8E2D4` (paper-tone backdrop, slightly darker than container's `#F4EFE5`)
- Left + right margins show **measurement scale**: faint `#A8A096` tick marks every 5mm-equivalent (CAD blueprint reference), at the container edges

Inside the container:
- 1px solid `#1A1A1A` border at the container edge (sharp document boundary)
- No box-shadow — we are deliberately NOT going for a "floating card" look. The container IS the document.

### Tablet (H5 768–1024px)

- Container max-width 640
- Measurement scale ticks hidden (would be too cramped)
- Otherwise same as desktop

### Phone (H5 < 768px / weapp always)

- Container full width
- No measurement scale (no margin to put it in)
- Header band → page → footer band stacked

## Component-level direction

| Component | Action | Notes |
|---|---|---|
| `HeroBanner` | **Repurpose entirely** | Becomes the **Header Band** (brand + identifier). API changes: drops `intro` / `metric` modes; takes `identifier?: string` + `subtitle?: string`. No icon prop. |
| `BigButton` | **Repurpose entirely** | Square (radius ≤ 4px), Plex Serif Chinese + Plex Sans English on two lines, charcoal bg, paper text. No icon prop (or `prefixGlyph?: '⊕' \| '⌖'`). |
| `HazardCard` | **Repurpose entirely** | Numbered card (`01 · HIGH`), striped tape on severity color, field rows `现象 / 依据 / 整改` separated by `|` characters or dotted rules |
| `PlainWarningCard` | **Delete** | The hero metric block on the report page takes over this role. One fewer component to maintain. |
| `ProgressIndicator` | **Repurpose entirely** | Monospace readout style: `READING ······ 12%` with stepping text, not a spinner. Steps still emit `currentStep` (1=queued, 2=processing) but render style is text-only. |
| `Icon` | **Extend** | Add: `stamp` (red round stamp shape), `plus-square` (⊕), `crosshair` (⌖), `slash-circle` (⊘), `tick` (numbered list separator). Remove no longer used: `helmet`. |
| Pages (`index`, `report`) | **Rewrite layouts** | Use new components + new tokens; structure follows the grammars above |

## Implementation strategy — token-first phased

Per user decision (in this conversation), implement in this order. Each phase = one (or two tight) commit(s). Each phase ends with `pnpm test` + `pnpm lint` + `npx tsc --noEmit` green.

1. **Tokens commit**: rewrite `src/utils/severity.ts` color constants; add new files `src/styles/tokens.scss` (palette + spacing + type-scale variables) and `src/styles/fonts.scss` (webfont declarations + Chinese fallback cascade). Adjust `src/app.scss` to import them, set body bg to paper backdrop. Verify weapp still works (system-font fallback).

2. **Webfonts commit**: ship `assets/fonts/` with self-hosted woff2 subsets:
   - `IBMPlexSerif-Bold.woff2` (~25KB)
   - `IBMPlexMono-Regular.woff2` (~22KB)
   - `IBMPlexMono-Medium.woff2` (~22KB)
   - `IBMPlexSansCondensed-Bold.woff2` (~28KB)
   - `SourceHanSerifSC-Bold-Subset.woff2` (~600KB, subset of ~3500 common chars + UI-relevant safety vocabulary)
   - Configure H5 `staticDirectory` to serve them; configure `@font-face` in `src/styles/fonts.scss` for H5 only (gated by `@supports` or by being inside an `:not(.weapp)` selector — to be confirmed by checking what scope Taro provides for H5-vs-weapp).
   - For weapp: `wx.loadFontFace` in `app.tsx`'s onLaunch to load `IBMPlexMono-Regular` only (single, smallest font; covers numeric metadata which is where the engineering feel matters most).

3. **BigButton + Icon commit**: rewrite `BigButton` to square charcoal-on-paper shape with Plex Serif + Sans pairing. Add new `Icon` paths (`stamp`, `plus-square`, `crosshair`, `slash-circle`, `tick`) and remove `helmet`. Update all callers.

4. **HeroBanner (now HeaderBand) commit**: rewrite `HeroBanner` component as the Header Band described above. Drop `intro` / `metric` modes; new API: `{ identifier?: string; subtitle?: string }`. Consider renaming the file to `HeaderBand` (breaking) or keeping the filename for minimal churn (recommend rename for clarity given the API is unrecognizable). Update the two page callers.

5. **HazardCard + delete PlainWarningCard commit**: rewrite `HazardCard` with numbered-tape style. Delete `PlainWarningCard` component + test + the import on the report page. Verify the report page still renders the warning content (it migrates into the new top metric block).

6. **ProgressIndicator commit**: rewrite as monospace readout. Keep the step API.

7. **Pages + desktop chrome commit**: rewrite `pages/index/index.tsx + .module.scss` and `pages/report/index.tsx + .module.scss` to use the new layout grammars. Update `app.scss` desktop chrome (paper backdrop, container border, optional measurement-scale ticks).

8. **E2E + visual gate commit**: bump `tests/e2e/h5-smoke.mjs` to also screenshot at a desktop viewport (1280×800). Confirm both screenshots look right (controller eyeballs). Fix any remaining issues. Possibly update unit tests that asserted on now-deleted DOM (PlainWarningCard tests get deleted; HazardCard test gets updated for the new structure).

Total: 7-8 commits. Each is independently testable. After phase 4 the screenshot will already look dramatically different from the current state.

## What we are deliberately NOT doing

- **No fade-in / motion choreography across page load** — static document. Only the stamp micro-moment.
- **No card hover lift effects** — static document.
- **No gradients** — anywhere. Solid colors only.
- **No emoji** — already removed; staying removed.
- **No icons beyond the 5 engineering glyphs listed** — restraint.
- **No drop shadows on the desktop container** — it is the document, not a card.
- **No light/dark mode toggle** — paper aesthetic is the brand; dark mode would require a separate dossier-on-blueprint variant which is out of scope.
- **No SCSS color-mix, var() recalcs, theming layers** — tokens are flat. YAGNI.

## Acceptance criteria

When this is shipped:
- Open H5 in browser at 1280×800 → see paper-tone backdrop + bordered document container + measurement-scale ticks at left/right margins + dossier-style header band + numbered list home page.
- Open at 390×844 (iPhone viewport) → same content stacked, no measurement scale, full-width.
- Tests green (`pnpm test` ≥ baseline, `pnpm lint`, `npx tsc --noEmit` all clean).
- Existing acceptance items from prior design (no "共识别 N 项" line, no emoji, no purple gradients) all still hold.
- Screenshot test runs at both viewports.

## Risk + rollback

**Risks:**
- Webfont loading on H5 could cause FOUT (Flash of Unstyled Text). Mitigation: use `font-display: swap`, accept transient unstyled paint.
- Source Han Serif subset coverage might miss safety-jargon characters. Mitigation: build subset against an actual list of glyphs used in current backend fixtures + a safety-vocabulary corpus.
- weapp's `wx.loadFontFace` is async; if it fails, Plex Mono numbers fall back to system mono (acceptable).
- The 7-8 commit sequence is reversible: each phase is independently `git revert`-able.

**Rollback** (if user changes mind mid-execution):
- Revert phases in reverse order. Phases 1-2 (tokens + fonts) are pure additions; revert them last.
- The prior aesthetic (iOS HIG + hero banner) is preserved in commits `868f590..85e6434` and can be re-checked-out by branching from there.

## Next step

Invoke `superpowers:writing-plans` to produce the step-by-step implementation plan from this design.
