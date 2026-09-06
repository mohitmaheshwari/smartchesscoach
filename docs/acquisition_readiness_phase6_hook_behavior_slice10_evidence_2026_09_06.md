# Acquisition Readiness Phase 6 - Hook Behavior Slice 10 Evidence

**Date:** 2026-09-06

**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`

**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

`ActiveLessonPanel` now exposes a teaching-move validator that is bound to the
current session and current parent callbacks. Re-rendering the panel without a
session-ID change no longer leaves the board calling obsolete handlers.

Every validation is versioned. Replacing the validator or starting a newer
validation invalidates the older request, so a late response from a previous
lesson cannot publish feedback, call completion/validation handlers, log a
current-session error, or clear the loading state owned by the current lesson.

## Behavioral proof

```text
Test Suites: 1 passed
Tests:       2 passed
```

The tests prove:

- changing callback props while retaining the same session makes the global
  board bridge call only the latest handler; and
- a delayed successful response from an old session cannot call its old
  handler or replace the feedback from the current session.

Both assertions fail against the previous session-ID-only bridge effect.

## Debt measurement

```text
strict_build_exit=1
hook_findings=55
OpeningTeachingPanel_findings=0
```

This is the exact reduction from 56 to 55. The strict build remains red until
the remaining bounded groups are resolved.

## Regression proof

```text
Test Suites: 40 passed, 40 total
Tests:       185 passed, 185 total
Snapshots:   0 total
ordinary production build: exit 0
```

The focused test supplies a test-only virtual router module because this
exported panel shares a file with a router-using offer component. Production
module resolution and dependencies are unchanged.

Existing source-map, bundle-size and remaining Hook warnings are not counted
as green evidence.

## Change control

- no endpoint, copy, backend or database change;
- no new dependency or lint suppression;
- no push or deployment;
- no `AR-QA-006` closure; and
- no acquisition score change.
