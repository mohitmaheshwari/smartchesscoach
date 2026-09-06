# Acquisition Readiness Phase 6 — React Hook Behavior Pre-code Audit

**Date:** 2026-09-06

**Program:** `docs/acquisition_readiness_program_scope.md`

**Finding:** `AR-QA-006`

**Status:** PASS — bounded behavioral remediation may begin

## Problem reproduced

The normal production build completes with warnings. The same build with
`CI=true` exits 1 because CRA promotes ESLint warnings to errors.

The frozen inventory is **71 `react-hooks/exhaustive-deps` findings across 30
files**:

- 46 missing `useEffect` dependencies;
- 11 missing `useCallback` dependencies;
- 6 missing/unnecessary `useMemo` dependencies; and
- 8 unstable logical-expression dependencies.

The debt is concentrated but high-risk: `CoachPlay.jsx` has 15 findings,
`TrapPractice.jsx` has 9 and `LabClassic.jsx` has 8. Those three files account
for 32/71 findings. They are not suitable for an unreviewed mass edit.

## Chosen remediation order

1. Stable router/navigation identities.
2. Load/refetch callbacks, preserving exactly when identity changes trigger a
   request.
3. Prop-to-state synchronization and board configuration effects.
4. Keyboard/listener lifecycles and cleanup.
5. Memoized derived chess/review state.
6. Opening-practice callbacks and unstable arrays.
7. `CoachPlay`, `LabClassic` and `Reflect` only after characterization of their
   state-machine boundaries.

The first code slice contains only the two direct `navigate` dependencies in
`CoachReplay.jsx` and `DiagnosticPuzzles.jsx`. React Router documents the hook
value as the effect dependency; adding it does not change the request trigger
from the existing game/mount boundary.

## Rejected approaches

- Disable `react-hooks/exhaustive-deps` globally.
- Set `CI=false` for the build.
- Add 71 dependency names mechanically.
- Add blanket inline suppressions.
- Wrap every function in `useCallback` without deriving its closure inputs.
- Refactor the large state machines while clearing lint findings.

Each of those can produce a green build while preserving stale closures,
introducing request loops or changing game behavior.

## Acceptance contract

For every bounded group:

1. Exact before/after warning counts are recorded from `CI=true yarn build`.
2. No ESLint rule/configuration is weakened.
3. No new inline suppression is introduced without a named behavioral reason
   and a regression test.
4. Effect triggers and cleanup behavior are characterized before a callback
   or listener identity changes.
5. Player-facing requests do not duplicate on an unrelated render.
6. Identity changes that previously triggered reloads continue to do so.
7. The full 30-suite / 162-test frontend suite passes after each committed
   group.
8. The ordinary production build passes; the strict build must show the exact
   expected remaining debt until the final group reaches zero.
9. Independent review examines the behavior, not only the lint count.

## First-slice expected result

The first two direct navigation fixes must reduce the strict inventory from
71 to **69**, with no new finding and no change outside the two routed pages,
tests/evidence and the baseline status record.

## Change control

- no player-facing copy change;
- no backend or database change;
- no push or deployment;
- no claim that `AR-QA-006` is closed before all 71 findings are resolved and
  the strict build plus journey tests pass; and
- no acquisition score increase.
