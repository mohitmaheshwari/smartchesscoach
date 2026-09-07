# Acquisition Readiness Phase 6 — Hook Behavior Slice 2 Evidence

**Date:** 2026-09-06

**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`

**Status:** SOURCE COMPLETE — independent review pending

## Bounded change

`MistakeFreeStreak` and `PreGameStreakPopup` each had a private fetch function
used only by one effect. The function was moved inside that effect so its
closure and trigger are explicit without introducing a memoized callback or a
new request identity.

The trigger contract remains:

- dashboard streak: load once for a user and reload when `userId` changes;
- pregame streak: do not load while closed, load when opened for a user, and
  reload when that user changes; and
- neither component refetches on an unrelated rerender.

## Behavioral proof

```text
Test Suites: 1 passed
Tests:       2 passed
```

The tests exercise closed → open, same-prop rerender and changed-user paths
with the repository-native React 19 `createRoot` harness.

## Debt measurement

```text
strict_build_exit=1
hook_findings=67
mistake_streak_findings=0
pregame_streak_findings=0
```

This is the exact reduction from 69 to 67. The strict build remains red until
the remaining bounded groups are resolved.

## Regression proof

```text
Test Suites: 32 passed, 32 total
Tests:       166 passed, 166 total
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
