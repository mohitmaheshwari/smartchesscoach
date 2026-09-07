# Acquisition Readiness Phase 6 - Hook Behavior Slice 11 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

`Layout` now keeps the prior unread count in a ref rather than render state.
Notification polling therefore remains on one stable 30-second interval instead
of restarting and immediately requesting again after every unread-count update.
The browser-notification callback follows the current navigator, safely checks
browser support, and late responses after cleanup cannot publish UI state.

## Behavioral proof

```text
focused: 1 suite / 1 test passed
full:    41 suites / 187 tests passed
ordinary production build: exit 0
strict production build: exit 1, 54 hook findings
Layout findings: 0
```

The focused test proves the initial unread result produces one notification
request and one browser notification, produces no second request through
29,999 ms, and polls exactly once at 30,000 ms without notifying twice.
The prior state-dependent effect fails that request-count contract.

This is the exact reduction from 55 to 54. Remaining hook debt keeps the strict
build and `AR-QA-006` open. No endpoint, backend, database, dependency, lint
suppression, push, deployment, or acquisition-score change is included.
