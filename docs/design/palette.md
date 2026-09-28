# Palette — the canonical colours

Measured 2026-09-28, before any cleanup, by `frontend/scripts/palette_report.js`:

- **21** Tailwind colour families in use
- **five greys** — gray 443, zinc 430, slate 212, neutral 5, stone 2 (1,092 uses)
- **four greens** — emerald 963, green 448, teal 23, lime 8 (1,442 uses)
- **164 distinct hardcoded hex values** (460 literals across 38 files)
- **170 arbitrary-value colour classes** (`bg-[#7fb069]`)
- most-used family is **amber at 1,226**, ahead of the brand green

(These are the script's own numbers over 324 files including CSS. An earlier
hand-grep of only `.jsx`/`.js` reported 108 distinct hex; the tool's figure is
the one to track, so the doc and the tool cannot drift apart.)

None of it is visible yet, because the busy pages happen to agree with one
another. It becomes visible the moment two of them disagree — neighbouring
cards with subtly different "neutral" backgrounds, which nobody can name and
everybody reads as cheap.

## The rule

**The canonical colour is the semantic token, not a favourite Tailwind family.**

Picking "zinc over gray" would just be a fifth opinion. The tokens already
exist and already encode the decisions, in `src/styles/pwc-theme.css`:

| use | token | Tailwind class |
|---|---|---|
| page background | `--background` (210 9% 4%) | `bg-background` |
| card / raised surface | `--card` (210 9% 9%) | `bg-card` |
| primary text | `--foreground` | `text-foreground` |
| secondary text | `--muted-foreground` (212 7% 57%) | `text-muted-foreground` |
| hairline / divider | `--border` (207 11% 16%) | `border-border` |
| brand accent | `--primary` (101 31% 55%, `#7fb069`) | `bg-primary` / `text-primary` |
| focus ring | `--ring` | `ring-ring` |
| coach interrupt only | `--pwc-warn` (amber) | — |

Board squares are their own pair and deliberately outside this scale:
`--cg-sq-light: #f0d9b5`, `--cg-sq-dark: #b58863` in `src/index.css`. That
brown is a recorded decision — *"Mohit likes the board we already render"* — and
the measured light/dark separation (2.29:1, against 1.58:1 for chessground's
bundled brown.css) is why the real lichess pair is used. **Do not swap it as
part of a palette tidy-up.** It is two variables, so a board theme remains a
two-line change if it is ever wanted deliberately.

## What counts as a violation

1. A raw Tailwind family where a token exists — `bg-zinc-900` instead of
   `bg-card`, `text-gray-400` instead of `text-muted-foreground`.
2. A hardcoded hex in JSX.
3. An arbitrary-value class, `bg-[#7fb069]` — that is `bg-primary`.

Semantic states (`red` for destructive, `amber` for the coach interrupt) are
fine and intentional. `--pwc-warn` is spent on exactly one thing; if the accent
is everywhere it stops meaning anything.

## How to use this

```bash
cd frontend && node scripts/palette_report.js
# and, once the number is down, pin it:
node scripts/palette_report.js --max-hex=80
```

This pass did **not** run a find-and-replace across 258 components. That cannot
be done safely without visual regression coverage, and a broken sweep is worse
than a measured backlog. The counter exists so the number is visible and can be
driven down deliberately.
