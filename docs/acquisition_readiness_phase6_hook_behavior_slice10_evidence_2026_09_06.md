# Acquisition Readiness Phase 6 - Hook Behavior Slice 10 Evidence

**Date:** 2026-09-06

**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`

**Status:** SOURCE CORRECTED AFTER REVIEW - independent re-review pending

## Bounded change

`ActiveLessonPanel` now exposes a teaching-move validator bound to the current
session. Current parent callbacks live behind one latest-handler authority, so
re-rendering within that session neither leaves the board calling obsolete
handlers nor discards a valid in-flight result.

Every validation is versioned. Changing sessions or starting a newer
validation invalidates the older request, so a late response from a previous
lesson cannot publish feedback, call completion/validation handlers, or log a
current-session error. Callback churn within the same session transfers a
pending result to the current handlers. The panel's unused loading state was
removed, eliminating the stranded-state defect identified in review.

## Behavioral proof

```text
Test Suites: 1 passed
Tests:       3 passed
```

The tests prove:

- changing callback props while retaining the same session makes the global
  board bridge call only the latest handler; and
- an already pending result within the same session is delivered to the latest
  handler without starting a replacement validation; and
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
Tests:       186 passed, 186 total
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
