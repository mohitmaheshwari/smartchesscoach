# Acquisition Readiness Phase 6 - Hook Behavior Slice 15 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

`useCoachFlow.handleUserMove` now changes ownership when the user switches
between coached and pure-play modes. The profile write uses a functional state
update, so a profile arriving with move evaluation cannot overwrite a profile
already learned by the current hook. `AdminAuthoringReview.advance` is now a
stable callback owned by the current queue length, and approve/reject/skip all
depend on that single transition.

## Behavioral evidence

```text
focused: 2 suites / 2 tests passed
full:    46 suites / 199 tests passed
ordinary production build: exit 0
strict production build: exit 1, 32 hook findings
useCoachFlow/AdminAuthoringReview findings: 0
git diff --check: exit 0
```

The coach-flow test renders a live coached session, changes the same mounted
hook to pure play, and proves the next move commits directly without calling
the coaching-evaluation endpoint. This fails with the prior stale callback.
The authoring test proves a successful action advances exactly one item and
targets the current feedback id.

This is the exact reduction from 36 to 32. `AR-QA-006` remains open for the
review, Lab, and CoachPlay findings. No backend, endpoint, database, dependency,
lint suppression, push, deployment, or product-score change is included.
