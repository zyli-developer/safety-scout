---
target: docs/plans/2026-05-22-unified-modern-minimal/
total_score: 28
p0_count: 0
p1_count: 3
timestamp: 2026-05-24T12-55-14Z
slug: docs-plans-2026-05-22-unified-modern-minimal
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 4 | Polling page is best in show: 3-state tracker, flowing line, livelog citing JGJ80-2016, elapsed/ETA bar, explicit "可离开本页". |
| 2 | Match System / Real World | 3 | 引用规范 + 整改建议 read like real Chinese construction-safety language. Loses a point for `STEP 1/3`, `SHA 604ae0…f6082e`, `Claude Sonnet 4.6 · v0.3.1`, `Prompt v3` leaking dev-chrome into the 安全员 surface. |
| 3 | User Control and Freedom | 3 | Polling has cancel; detail has pager; home has 新建巡检. No back affordance on report.html, no undo on chip filters, no undo on step-checklist tap. |
| 4 | Consistency and Standards | 3 | Strong system unification (one `:root` repeated across 7 files). But "报告" nav label routes to history (label/route mismatch), and filter chips on report.html (inverted on press) vs toolbar selects on history.html (dropdown ghost buttons) are two visual languages for one filter concept. |
| 5 | Error Prevention | 2 | "仍然强制分析" reject-state CTA has no risk copy. Step-checklist on report-detail toggles `step--done` on full-row click — one stray tap marks a 整改 step done with no undo. |
| 6 | Recognition Rather Than Recall | 3 | Severity color + label + dot triple-redundant (good). But 4 toolbar selects on history.html collapse to identical chevron buttons; user must read each to recall what it filters. |
| 7 | Flexibility and Efficiency | 2 | No keyboard hints, no shortcut on history search, no bulk action on history rows, no "重新分析 same photo" inside detail. Pager exists; no `j/k` or arrow-key affordance shown. |
| 8 | Aesthetic and Minimalist Design | 3 | Whitespace + single-accent discipline + hairline borders all good. Costs a point for desktop report's sticky right rail with 3 near-redundant cards (严重度分布 / 本次输出 / 类别覆盖). |
| 9 | Error Recovery | 3 | empty-error.html earns this: real error code, local-queue confirmation, tips. Loses a point because home dropzone asserts contract (`≤10MB / JPG·PNG`) with no inline error path shown. |
| 10 | Help and Documentation | 2 | Three "提示" blocks scattered with three different class names (`.state__hint`, `.tips`, `.dropzone__hint`). No first-run onboarding. No hazard taxonomy reference. |
| **Total** | | **28/40** | **Good — solid foundation; weak areas (Error Prevention, Flexibility) and the dev-chrome bleed are the drag.** |

## Anti-Patterns Verdict

**Start here.** Does this look AI-generated?

**LLM assessment.** A category-fluent product designer (Linear/Stripe/Notion grad) trusts it for ~10 seconds, pauses on closer look. The biggest tell is mono-eyebrow / dev-chrome overload: `STEP 1/3`, `SHA 604ae0…f6082e`, `Claude Sonnet 4.6 · 平均 29s · v0.3.1`, `ID f3a2c1d0`, `Prompt v3` show up in user-facing chrome on most screens. Real construction-safety apps do not show a model version or commit hash to a 50-year-old 包工头. The `SS` square brand mark in `--accent` is the most generic 2024 SaaS chip imaginable. The serif-ish `--font-display` on `.reg__quote` puts the strongest typographic voice on the quoted standard instead of the actionable 整改建议 — wrong hierarchy. Hero photo placeholders use `linear-gradient(135deg, …)` lifestyle gradients, not skeletons, which sells a glossy-photography aesthetic the real app won't have.

**Deterministic scan** (`detect.mjs --json`). 2 findings, both real:

| File | Line | Rule | Verdict |
|---|---:|---|---|
| `polling.html` | 151 | `layout-transition` — animating `width` on `.elapsed__fill` | **Confirmed.** Cheap fix: animate `transform: scaleX()` from a fixed-width parent, or accept it for a mockup but exclude from production code. |
| `report-detail.html` | 168 | `side-tab` — `border-left:3px solid var(--accent)` on `.reg__quote` | **Likely false positive.** The element is a `<blockquote>`; a 3px left bar on a real blockquote is the canonical editorial pull-quote pattern (NYT, Monocle, FT do this), not the AI-slop card-stripe. The detector can't distinguish. The deeper issue Assessment A found is unrelated: `font-family:var(--font-display)` on the quote body, which steals visual weight from the actionable 整改建议. |

**Visual overlays.** No browser injection attempted (mockups are local file://; live-server flow skipped for a static review). Detector output stands as the deterministic signal.

## Overall Impression

This is a real production-quality system, not a sketch. The single `:root` block reused across 7 files, the disciplined accent budget, the hairline-border + tabular-mono numeric vocabulary, and especially the polling page's 3-state tracker + livelog are work a designer should be proud of. The drag is one consistent failure: the design imported a Linear/Stripe-dashboard register and forgot to translate it to a 工地安全员 register. Strip the SHA, the prompt version, the model name, the `STEP 1/3` eyebrow, the `SS` chip, and rewrite the report-page CTA hierarchy so "分享给班组" is primary and "重新分析" is hidden — and this jumps from 28/40 to ~33/40 without a single layout change. The single biggest opportunity: **the report page must end on an action (transmit to the crew), not on metadata (export, share, retry).**

## What's Working

1. **`polling.html` `.tracker` + `.livelog` combination.** Three-node horizontal tracker with done/active/pending states, flowing `linear-gradient` `::after` on the active line, explicit 42% elapsed bar, a livelog that cites `JGJ80-2016` to prove the model isn't generic vision prose, and a "不需要等在这页" release. Vertical reflow at `max-width:600px`. Complete state-disclosure system that turns the wait (the experience valley) into a trust-build.
2. **`report-detail.html` `.reg` block (despite the font finding).** 规范条款 in its own card with `JGJ80-2016 第 4.3.1 条` header, quoted body, AND a `.reg__interp` translating the standard into "本次现场实测：临边无任何刚性防护栏…". The interpretation line is the editorial move that makes the output read 中文施工安全语言 instead of vision-model prose.
3. **`history.html` row severity counts.** `H ×3` / `H ×1 L ×1` pills on each row let the user scan a day of inspections for severity profile without reading titles. The `.dayhead` sticky day separator (top:60px aligning to nav) makes the list scan well on desktop.

## Priority Issues

**[P1] Report-page hero CTA hierarchy is inverted.**
- *Why it matters*: a 安全员's job after seeing a high-risk report is to alert the crew, not to export a PDF. `导出 PDF` is currently `.btn--primary`; `分享给班组` is `.btn--ghost`. The peak-end experience ends on metadata + a button that doesn't match the job.
- *Fix*: swap them — `分享给班组` becomes primary orange, `导出 PDF` becomes ghost, `重新分析` becomes a small secondary in an overflow ("结果不准？") so it stops implying the verdict is unstable.
- *Suggested command*: `/impeccable clarify`

**[P1] Step-checklist tap target on `report-detail.html` is a footgun.**
- *Why it matters*: lines 473–475 toggle `step--done` on click of the whole `.step` row. One stray scroll-tap marks an integrity-critical step (e.g. "疏散临边作业人员") as 完成, with no undo and no confirm.
- *Fix*: only the `.step__check` checkbox toggles; require a confirm sheet when marking a high-severity step done; add an undo toast for ~5s.
- *Suggested command*: `/impeccable harden`

**[P1] Mono-eyebrow / dev-chrome overload bleeds into the product surface.**
- *Why it matters*: `STEP 1/3 · 拍照→等待→看报告`, `SHA 604ae0…f6082e`, `Claude Sonnet 4.6 · 平均 29s · v0.3.1`, `f3a2c1d0`, `Prompt v3` are visible on most user-facing pages. Most legible sign that the design imported a Linear/Stripe template without translating it to 安全员 register. 王师傅 does not need a model version.
- *Fix*: keep mono only for genuine numerics (time, counts, JGJ codes) and the dev footer; drop SHA from the user-facing sidebar; move model/version into "关于"; rewrite "STEP 1/3" as "第一步：拍照".
- *Suggested command*: `/impeccable quieter`

**[P2] `history.html` toolbar is 4 identical dropdown shells with no primary.**
- *Why it matters*: `.tselect × 4` (本周 / 所有严重度 / 所有类别 / 所有状态) plus search. No default chip applied; user reads every button to recall what it filters. Recognition fails.
- *Fix*: collapse to one "筛选" pill that opens a sheet, OR pre-apply the most-used combination (本周 · 所有严重度 · 待整改) as visible chips with `×` to remove. Recognition over recall.
- *Suggested command*: `/impeccable distill`

**[P2] `home.html` dropzone tries to serve mobile and desktop with the same chrome.**
- *Why it matters*: "拖入照片，或选择上传方式" is a desktop affordance shown on phones where there is no drag. "拍照" and "从相册选择" sit side by side at `btn--big`; 王师傅's thumb will mis-hit ~30%.
- *Fix*: `@media (pointer:coarse)` — hide the drag instruction, make the entire dropzone the 拍照 button, drop "从相册选择" to a small secondary link below.
- *Suggested command*: `/impeccable adapt`

**[P3] Report-page sticky right rail (`.sidepanel`) has 3 near-redundant cards.**
- *Why it matters*: 严重度分布 + 类别覆盖 both encode `H 3 / M 0 / L 0` in different shapes; 本次输出 is dev metadata that doesn't help a 安全员 reading this report.
- *Fix*: merge into one "本次扫描概要" card (severity bar + 类别 chips); collapse SHA / model / prompt version into "技术细节" disclosure or move to "关于".
- *Suggested command*: `/impeccable distill`

## Persona Red Flags

**王师傅 (50 岁, 视力一般, 单手手持工地手机, 不熟 app)**:
- `home.html`: dropzone has 5 layered text elements around one button; "从相册选择" same visual weight as "拍照" — thumb mis-hit.
- Top nav "巡检 / 报告" — tap "报告", land on a page titled "巡检报告"; label/route mismatch.
- `polling.html` works for him: big photo, big circles, clear release line.
- `report.html`: orange severity tag and big warning sentence land. Primary "导出 PDF" is meaningless on his phone; he wants to send to 张工长 but has to read 3 buttons to find "分享给班组".
- `history.html`: 4 chevron buttons at 12px chevron, unclear which filters what.
- `empty-error.html` reject: "仍然强制分析" with no warning copy — he'll tap it.

**Project manager / 技术员 (desktop review, prints PDF, forwards)**:
- `home.html` on 1440 desktop reads as Notion-class and trustworthy.
- `report.html` sticky right rail with severity + metrics matches his mental model.
- `report-detail.html` tabs (规范条款 / 整改建议 / 处置记录) match "what's the regulation, what's the action, what's the status".
- **Print is broken.** No `@media print` rule in any file. Orange tag, sticky elements, `backdrop-filter` topnav will render badly on printed PDF for the site board. Crumbs like `f3a2c1d0 · 2026-05-22 14:08` are useful in browser, meaningless on paper.
- Export PDF has no preview, no per-hazard selection.

**First-timer (just installed, no 巡检 history)**:
- Lands on `home.html`; sees `今日巡检 7 / 3 / 5 / 2` with no actual 巡检 yet (seeded data). Needs an empty state: "还没开始今天的巡检 · 点上方拍照按钮".
- `最近巡检` card likewise needs an empty state.
- `empty-error.html` `state--empty` ("拍下第一张现场照片 · 看示例报告") is the right first-run screen but is currently hidden behind a prototype state-switcher. In product, `home.html` must detect zero-巡检 state and render it.
- "看示例报告" is the single best onboarding move in the whole set; should be primary (not ghost) until first inspection completes.

## Minor Observations

1. `polling.html` (line 198) drops `aria-current` from both nav links; should mark "巡检" as the active section since polling is inside the 巡检 flow.
2. `report.html` near line 350: `JGJ80-2016 第 4.3.1 条 ;<br>JGJ59-2011…` — semicolon + `<br>` is awkward; use `·` separator consistent with the rest.
3. `report-detail.html` sets `.aside{position:sticky;top:80px}` globally before the `@media (max-width:980px)` override. Reorder so default is non-sticky and sticky applies only at min-width, to avoid screen-reader announcing a non-sticky region as sticky on mobile.
4. `polling.html` `.shot__badge` sits at `bottom:-10px`; can clip on iOS Safari with `viewport-fit=cover` + bottom safe area.
5. Mockup tokens (`--fg / --border / --sev-*`, 冷白 `oklch(99% 0.002 240)`) diverge from current `tokens.scss` (`--ink / --line / --high / --med / --low`, 暖白 `#FAFAF8`). Migration is deliberate but uncalled-out; needs an alias layer in `tokens.scss` before mockup-to-code work begins.
6. `history.html` (line 360) uses `pill--low` for "通过" (zero hazards). "low risk" ≠ "no risk"; add `pill--ok` or `pill--clean`.
7. No `:focus-visible` styles on `.btn / .chip / .swbtn / .tab`. Keyboard users get browser default outline, which clashes with the rest of the system.
8. Detector flag on `.reg__quote` is a false positive (real `<blockquote>`), but the `font-family:var(--font-display)` on it IS a real misemphasis — see [P1] dev-chrome cleanup or use `/impeccable typeset` to redistribute display weight to the 整改建议 callout.

## Questions to Consider

1. **If the safety officer's job ends with "tell the crew", why does the report end with "导出 PDF"?** Could the entire report compress to a one-tap WeChat-forward message (photo + 1 severity line + 整改 next step + 关键规范条款)? That changes the report from a document to a transmission.
2. **Is the polling page even necessary if the average is 29 seconds?** Push notification + a permanent "巡检中…" pill in the top nav of whatever page the user is on lets them keep using history while the model works. The polling page is beautifully designed for a problem you might design away.
3. **Why is "重新分析" a top-level CTA on the report?** Every appearance whispers "we might be wrong". On a tool where trust is fragile (vision model + safety stakes) the implicit message is corrosive. Hide it behind a "结果不准？" disclosure.
4. **What does "已闭环" mean to 王师傅 vs to the technician vs to the model?** Does ticking all 4 整改 steps auto-flip the report to 已闭环, and does that trigger the re-photograph workflow promised in step 4? The closed-loop interaction is the highest-leverage move the design hasn't made first-class.
