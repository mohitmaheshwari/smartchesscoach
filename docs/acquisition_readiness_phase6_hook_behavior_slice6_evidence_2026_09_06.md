# Acquisition Readiness Phase 6 - Hook Behavior Slice 6 Evidence

**Date:** 2026-09-06

**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`

**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

`MissionRunner` now treats the URL mission ID and matching router state as the
load authority. A mission payload is reused only when its `mission_id` matches
the route. A route change with stale or absent navigation state loads the
current mission rather than carrying the prior mission forward.

The load is effect-owned, keyed to `missionId`, route mission, and route
session. Its cleanup marks an in-flight request superseded, so a late response
cannot fetch positions or write state for an old route. Position loading is
cleared in the same guarded `finally` path as page loading.

## Behavioral proof

```text
Test Suites: 1 passed
Tests:       3 passed
```

The tests prove:

- matching route state makes exactly one positions request and never calls
  `/missions/today`;
- stale mission state is rejected after a route change and the returned
  mission's positions are loaded; and
- resolving an old `/missions/today` request after a new route renders cannot
  request positions for the superseded mission.

## Debt measurement

```text
strict_build_exit=1
hook_findings=60
mission_runner_findings=0
```

This is the exact reduction from 61 to 60. The strict build remains red until
the remaining bounded groups are resolved.

## Regression proof

```text
Test Suites: 36 passed, 36 total
Tests:       175 passed, 175 total
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
