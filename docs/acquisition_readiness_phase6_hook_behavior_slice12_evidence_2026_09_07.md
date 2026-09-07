# Acquisition Readiness Phase 6 - Hook Behavior Slice 12 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

`OpeningsOverview` now owns repertoire/profile loading by the current user ID.
Its formerly private free-floating loaders live inside cancellable effects, so
a surviving page instance reloads after an account change and late responses
from the prior account cannot publish. Endgame categories use the same guarded
effect pattern and are fetched only when their tab first needs them.

## Evidence

```text
focused: 1 suite / 1 test passed
full:    42 suites / 190 tests passed
ordinary production build: exit 0
strict production build: exit 1, 53 hook findings
OpeningsOverview findings: 0
```

The focused test switches user identity while the first profile is pending,
proves the new account's 22-game repertoire appears, then resolves the prior
account's three-game profile and proves it cannot replace current content. The
old mount-only loader fails this contract. This is the exact reduction from 54
to 53. Remaining hook debt keeps `AR-QA-006` open. No endpoint, backend,
database, dependency, suppression, push, deployment, or score change is included.
