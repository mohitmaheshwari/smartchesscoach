# Acquisition Readiness Phase 6 - Hook Behavior Slice 13 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** APPROVED - independent review found no material issue

## Bounded change

`LichessBoard` now keeps initialization-only values behind a current snapshot,
preserving its deliberate recreation boundary instead of adding rapidly
changing FEN/arrows to the constructor effect. Its update path now treats
`showDests` and `movableColor` as control changes, calculates destinations for
the requested color, and preserves that exact color after a FEN change.

## Evidence

```text
focused: 1 suite / 2 tests passed
full:    43 suites / 193 tests passed
ordinary production build: exit 0
strict production build: exit 1, 51 hook findings
LichessBoard findings: 0
```

The tests prove a new FEN retains `movableColor=black` with legal black
destinations instead of changing to `both`, and prove `showDests=false` updates
the live instance to an empty destination map without recreating Chessground.
Both fail against the previous update path. This is the exact reduction from
53 to 51. Remaining debt keeps `AR-QA-006` open. No backend, endpoint,
database, dependency, suppression, push, deployment, or score change is included.
