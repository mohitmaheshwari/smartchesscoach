# Acquisition Readiness Phase 6 - Hook Behavior Slice 11 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** SOURCE CORRECTED AFTER REVIEW - independent re-review pending

## Bounded change

`Layout` now keeps the prior unread count in a ref rather than render state.
Notification polling therefore remains on one stable 30-second interval instead
of restarting and immediately requesting again after every unread-count update.
The browser-notification callback follows the current navigator without making
route changes restart the interval. Versioned request ownership prevents older
overlapping polls from publishing, and `Mark all read` invalidates outstanding
reads while its mutation is in progress. Late responses after cleanup cannot
publish UI state.

## Behavioral proof

```text
focused: 1 suite / 3 tests passed
full:    41 suites / 189 tests passed
ordinary production build: exit 0
strict production build: exit 1, 54 hook findings
Layout findings: 0
```

The focused tests prove the interval boundary without duplicate notifications,
prove route/navigate identity changes do not restart polling while notification
clicks use the latest navigator, and prove a pre-read response cannot restore
unread UI after `Mark all read`. The prior implementation fails these request
ownership and interval contracts.

This is the exact reduction from 55 to 54. Remaining hook debt keeps the strict
build and `AR-QA-006` open. No endpoint, backend, database, dependency, lint
suppression, push, deployment, or acquisition-score change is included.
