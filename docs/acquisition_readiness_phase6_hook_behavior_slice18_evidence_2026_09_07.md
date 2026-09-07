# Acquisition Readiness Phase 6 - Hook Behavior Slice 18 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

Lab Classic now derives its board navigation and move ownership from stable,
current inputs:

- `goToMove` is a committed callback over the current parsed moves and FENs;
- the Journey deep-link and autoplay effects depend on that callback rather
  than retaining the first render's board data;
- the analysis-queue poll depends on the scalar queue state, aborts on game or
  state replacement, and parses replacement analysis before publishing one
  coherent completion update;
- move-evaluation fallback identity is stable; and
- player-side classification is a callback dependency of every memoized
  milestone and error derivation that consumes it.

No warning was suppressed and no dependency was added.

## Behavioral evidence

`LabClassicEffects.test.jsx` proves:

1. `?move=2&src=journey` navigates to the student's second move using the
   current parsed game;
2. autoplay advances exactly one ply from the current game's board; and
3. an in-flight analysis-status response from a replaced game cannot refetch
   old analysis, announce completion, or write into the replacement view.

```text
focused Lab Classic: 1 suite / 3 tests passed, clean output
strict build:        exit 1, exactly 15 exhaustive-deps findings
changed source:      0 findings
baseline:            23 findings
reduction:           8 findings
remaining files:     CoachPlay.jsx only
```

The strict build remains intentionally red until the final Play-with-Coach
slice removes its 15 findings. No backend, endpoint contract, database,
production flag, push, deployment, or product-score change is included.
