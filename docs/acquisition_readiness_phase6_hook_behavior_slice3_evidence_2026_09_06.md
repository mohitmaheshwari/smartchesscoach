# Acquisition Readiness Phase 6 — Hook Behavior Slice 3 Evidence

**Date:** 2026-09-06

**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`

**Status:** SOURCE COMPLETE — independent review pending

## Bounded change

`Lab` and `AdminOpenings` each expose a load function that is also used by an
explicit user action. Those functions are now stable callbacks with the
minimum truthful dependencies:

- `Lab.fetchGameData` depends on `gameId`, so it loads once for the current
  game, reloads once when the route changes, and remains callable by Refresh;
- `AdminOpenings.fetchOpenings` has no render-state dependency; its initial
  selection uses a functional state update, so choosing the first returned
  opening cannot recreate the callback or reload the catalog.

No request, response, route, player copy or refresh behavior changed.

## Behavioral proof

```text
Test Suites: 1 passed
Tests:       2 passed
```

The tests prove an unrelated rerender does not repeat either load, a changed
Lab game identity performs exactly the two expected game/analysis requests,
and the opening catalog remains a single request when the first selection
lands.

## Debt measurement

```text
strict_build_exit=1
hook_findings=65
lab_findings=0
admin_openings_findings=0
```

This is the exact reduction from 67 to 65. The strict build remains red until
the remaining bounded groups are resolved.

## Regression proof

```text
Test Suites: 33 passed, 33 total
Tests:       168 passed, 168 total
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
