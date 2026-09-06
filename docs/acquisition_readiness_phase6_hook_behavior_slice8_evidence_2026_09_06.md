# Acquisition Readiness Phase 6 - Hook Behavior Slice 8 Evidence

**Date:** 2026-09-06

**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`

**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

`CoachPanel` now uses the opening-guide response for the position being loaded
when deciding whether engine candidates are appropriate. It no longer makes
that decision from the previous render's guidance. In-book positions suppress
candidates immediately; off-book positions request them from the existing
endpoint.

Each position load clears position-specific presentation state and owns a
supersession guard. When the session, FEN, or opening changes, a late response
from the old request cannot publish guidance, request old-position candidates,
publish a position read, or clear the loading state for the current request.

## Behavioral proof

```text
Test Suites: 1 passed
Tests:       2 passed
```

The tests prove:

- the first current response marked in-book makes no candidates request, then
  a new FEN explicitly marked off-book makes exactly one and displays it; and
- a delayed opening response for a superseded FEN cannot replace the current
  advice or initiate an additional candidates request.

Both assertions fail against the previous state-closure implementation.

## Debt measurement

```text
strict_build_exit=1
hook_findings=57
CoachPanel_findings=0
```

This is the exact reduction from 58 to 57. The strict build remains red until
the remaining bounded groups are resolved.

## Regression proof

```text
Test Suites: 38 passed, 38 total
Tests:       181 passed, 181 total
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
