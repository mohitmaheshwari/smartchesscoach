# Acquisition Readiness Phase 6 - Hook Behavior Slice 14 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

The opening-learning surfaces now preserve current ownership without making
boards or autoplay timers restart on ordinary renders:

- `GuidedOpeningLesson` memoizes the optional main line and keeps one coach
  introduction for the current color instead of changing it on a rerender;
- `InteractivePractice` updates board orientation in place and routes board
  events through the latest opening-owned move handler;
- `TrapPractice` memoizes its setup and trap lines, initializes a recreated
  board from the current FEN, and routes user/opponent callbacks through their
  current trap-owned implementations; and
- `OpeningLesson` no longer carries a second unreachable practice engine. The
  rendered `InteractivePractice` remains the single owner of opening practice.

## Behavioral evidence

`OpeningPracticeEffects.test.jsx` proves:

1. the guided coach introduction stays stable across an unrelated rerender;
2. changing the student's color updates the live practice board without
   destroying and recreating Chessground;
3. an already-registered board event attributes a later move to the current
   opening identity; and
4. an already-registered trap board event grades against the current trap
   after its prop identity changes.

```text
focused: 1 suite / 4 tests passed
full:    44 suites / 197 tests passed
ordinary production build: exit 0
strict production build: exit 1, 36 hook findings
opening-learning findings: 0
git diff --check: exit 0
```

This is the exact reduction from 51 to 36. `AR-QA-006` remains open for the
36 findings in CoachPlay, Lab/Review, authoring, and coach-flow code. No
backend, endpoint, database, dependency, lint suppression, push, deployment,
or product-score change is included.
