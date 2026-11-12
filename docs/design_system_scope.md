# Scope — the design system, and making it stick

Date: 2026-11-12. Asked for: *"i don't like UX really… it's not premium… do
what you recommend, i need an excellent UX"*. The chessboard is explicitly out
of scope — Mohit likes it and `--cg-sq-light/dark` do not change.

## What is actually wrong

Measured today against `origin/working-code`, by
`frontend/scripts/palette_report.js` and by counting classes in `src`:

| | now | what a premium UI spends |
|---|---|---|
| arbitrary pixel font sizes | **38** — incl. `text-[10.5px]` ×72, `text-[12.5px]` ×53 | ~6 named steps |
| border radii in heavy use | **6** + `rounded-[28px]`, `[24px]` | 2–3 |
| shadow treatments | **8**, four one-off arbitrary | 2–3 |
| grey families | **5** (slate 336, gray 474, zinc 456, neutral, stone) = 1,272 uses | 1 |
| green families | **4** (emerald 1,030, green 443, teal, lime) = 1,509 uses | 1 |
| distinct hardcoded hex | **209** across 44 files | ~0 |

It is not that the design is bad. There isn't one. Premium reads as restraint,
and half-pixel font sizes are the tell: `10.5px` is not a decision, it is
someone nudging a number until one component looked right.

**The root cause is in `tailwind.config.js`: there is no `fontSize` scale at
all.** Nothing names the right answer, so `text-[Npx]` is the path of least
resistance. `borderRadius` names three steps while the code uses six. The only
`boxShadow` entries are four coloured glows, so neutral elevation has no name
either.

## Why this is not a rewrite

On 2026-09-28 I shipped `palette_report.js` and recorded **164** distinct hex
values. Today it is **209**, and arbitrary colour classes went 170 → 182. It
drifted ~27% worse in six weeks with the measurement sitting in the repo.

Nobody ignored it on purpose; it was never *enforced*. A rewrite that is not
enforced returns here within a quarter. So the deliverable is a system plus a
gate, not new screens.

## What changes

1. **A named type scale** in `tailwind.config.js` — six steps with line
   heights, floor raised to 12px. 10px and 10.5px body text is admin-tool
   density and is the single biggest reason the product reads cheap.
2. **Three radii** and **three neutral elevations**, named. `rounded-full`
   stays for pills — that is a shape, not a scale step.
3. **One accent: green.** `--cg-accent: #7fb069` is already the brand. Amber
   currently outranks it 1,315 to 1,030; amber keeps exactly one job (the
   coach interrupting before a move) as `pwc-theme.css` already states.
4. **A build-time gate** so none of it can drift: `palette_report.js
   --max-hex`, plus a check that fails on new `text-[Npx]`.
5. **One reference screen**: `components/academy/ParentReport.jsx`. Chosen
   because it is the screen a paying parent judges, it is 95 lines, and it is
   already the most disciplined component in the app — so the system will show
   rather than hide.

## Out of scope

The chessboard squares. Meghanshu's `New-Updation` restyle (photographic
background, cyan accent) — measured at 265 distinct hex against our 209, and
it moves away from the flat, quiet, opaque look Mohit named as the benchmark.
His nav improvement was taken separately in `892cf70b`. The other 73 pages:
they migrate when touched, not in one sweep, because a sweep cannot be
visually regression-tested here.

## How it is verified

Token values are asserted in a test, not eyeballed. The reference screen is
rendered before and after at 1440×900. The gate is proven to fail on a
deliberate violation and pass on the tree — a gate never shown failing is not
a gate.
