# Acquisition Readiness Phase 6 - Hook Behavior Slice 12 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** SOURCE CORRECTED AFTER REVIEW - independent re-review pending

## Bounded change

`OpeningsOverview` now owns repertoire/profile loading by the current user ID.
At the start of each identity generation it clears all three account-owned
stores before requesting replacements. Its formerly private free-floating
loaders live inside cancellable effects, so a surviving page instance reloads
after an account change, late responses from the prior account cannot publish,
and a failed new-account load cannot reveal or mix the prior user's data.
Endgame categories use the same guarded effect pattern and are fetched only
when their tab first needs them.

## Evidence

```text
focused: 1 suite / 2 tests passed
full:    42 suites / 191 tests passed
ordinary production build: exit 0
strict production build: exit 1, 53 hook findings
OpeningsOverview findings: 0
```

The focused tests switch identity while an old response is pending and after a
complete old-account render. They prove late publication is rejected and prove
that three non-OK current-account responses leave no prior repertoire visible.
The old mount-only loader and the first correction both fail this complete
identity-ownership contract. This is the exact reduction from 54 to 53.
Remaining hook debt keeps `AR-QA-006` open. No endpoint, backend, database,
dependency, suppression, push, deployment, or score change is included.
