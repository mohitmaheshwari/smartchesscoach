# Scope — layout width and colour palette (frontend only)

Date: 2026-09-28. Asked for directly: *"I want you to fix the layout and colour
palettes, not the backend."* No backend files are touched.

## The problem, measured

Rendered at 1440×900 against the local dev server, default (dark) theme:

- Home, Lab and Progress leave roughly **45% of the viewport empty** on the
  right. The Play screen does not — it is a proper three-column layout.
- The frontend carries **108 distinct hardcoded hex values** across 32 files
  and **166 arbitrary-value colour classes** (`bg-[#7fb069]`), despite a token
  layer existing.
- **21 Tailwind colour families** are in use, including five greys
  (gray 443, zinc 427, slate 211, neutral, stone) and four greens
  (emerald 951, green 447, teal, lime).

## The layout cause — the design system is being overridden

`index.css` already defines the primitives:

```css
.cg-page       { width: min(100%, 1120px); }
.cg-page--wide { width: min(100%, 1320px); }
```

Five components use `cg-page--wide` correctly. Six others attach `cg-page` and
then clamp it *below* the system default with a hardcoded pixel width:

| file | current |
|---|---|
| `pages/HomePageNew.jsx` | `max-w-[900px]`, `max-w-[860px]`, `max-w-[980px]` |
| `pages/AllGames.jsx` | `max-w-[920px]` (plus `.experience-games-page { max-width: 52rem }` = 832px) |
| `pages/UnifiedProgress.jsx` | `max-w-[1040px]` ×2 |
| `pages/PersonalCurriculum.jsx` | `max-w-[720px]`, `max-w-[940px]` |
| `components/curriculum/CurriculumHome.jsx` | `max-w-[960px]` |
| `components/HomeLoadingSkeleton.jsx` | `max-w-[960px]` |

So this is not a redesign. It is deleting overrides so the pages get the width
the design system already specifies.

## What changes

1. **Remove the hardcoded `max-w-[…px]` from `cg-page` containers**, so they
   take the 1120px default; use `cg-page--wide` where the content is a grid
   rather than prose. Relax `.experience-games-page`'s 52rem clamp to match.
2. **Prose measure is untouched.** `.cg-title` (48rem) and `.cg-lede` (42rem)
   already cap line length, and inner blocks keep their own `max-w-[480px]`
   style constraints. Widening the page container does not widen paragraphs.
3. **Board coordinates stay, but recede.** Per-square labels are a decision
   taken twice (2026-06-03, size-gated 2026-06-27). They are kept and gated as
   before; only their opacity drops so they stop competing with the pieces.
4. **Canonical palette recorded, plus a counter.** One grey and one green are
   named in `docs/design/palette.md`, and
   `frontend/scripts/palette_report.js` prints the current violation counts so
   the number can be driven down and regressions are visible. **No mass
   find-and-replace across 258 components in this pass** — that cannot be done
   safely without visual regression coverage.
5. **The board's brown is left as the default.** `pwc-theme.css` records
   *"Mohit likes the board we already render"*. The alternate palette-matched
   pair is added as an opt-in class, not a silent override.

## Out of scope

Backend, the API request duplication (23 calls per page load, `auth/me` ×4),
the per-component colour sweep, and any change to the Play screen layout, which
is the one screen that already works.

## How it is verified

Screenshots at 1440×900 and 390×844, before and after, on the same routes and
the same dev server. Pass = measured content width increases on Home, Lab and
Progress, with no horizontal scroll at 390px and no change to the Play screen.
