# Acquisition Readiness Phase 6 - Hook Behavior Slice 9 Evidence

**Date:** 2026-09-06

**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`

**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

`CoachMovePanel` now separates move-interaction reset behavior from the
position-reading request. The board explanation is keyed to the exact selected
move, FEN, importance decision, and player color instead of only the numeric
move index. Analysis that arrives after a move is already selected can now make
that move reviewable and load its explanation.

Each position-reading request has a supersession guard. Changing the reviewed
position clears its prior reading, and a late response cannot replace the
current position's explanation or loading state.

## Behavioral proof

```text
Test Suites: 1 passed
Tests:       2 passed
```

The tests prove:

- a selected move that becomes important when analysis arrives triggers one
  request with the current FEN and player color even though its index did not
  change; and
- changing FEN at the same move index loads the current explanation, while a
  delayed response for the prior FEN cannot overwrite it.

Both assertions fail against the previous move-index-only effect.

## Debt measurement

```text
strict_build_exit=1
hook_findings=56
CoachMovePanel_findings=0
```

This is the exact reduction from 57 to 56. The strict build remains red until
the remaining bounded groups are resolved.

## Regression proof

```text
Test Suites: 39 passed, 39 total
Tests:       183 passed, 183 total
Snapshots:   0 total
ordinary production build: exit 0
```

Existing source-map, bundle-size and remaining Hook warnings are not counted
as green evidence.

## Change control

- no endpoint, copy, backend or database change;
- no new dependency or lint suppression;
- no push or deployment;
- no `AR-QA-006` closure; and
- no acquisition score change.
