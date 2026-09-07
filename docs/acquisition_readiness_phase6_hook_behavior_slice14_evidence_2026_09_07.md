# Acquisition Readiness Phase 6 - Hook Behavior Slice 14 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** CORRECTED AFTER REVIEW - exact-commit re-review pending

## Bounded change

The opening-learning surfaces now preserve current ownership without making
boards or autoplay timers restart on ordinary renders:

- `GuidedOpeningLesson` memoizes the optional main line and keeps one coach
  introduction for the current color instead of changing it on a rerender. Its
  autoplay reads the latest completion callback without restarting when a
  parent creates a fresh callback;
- `InteractivePractice` updates board orientation in place and routes board
  events through the latest opening-owned move handler. A changed opening
  invalidates the old backend session, requests, and delayed UI work before a
  new session may start;
- `TrapPractice` memoizes its setup and trap lines, initializes a recreated
  board from the current FEN, and routes user/opponent callbacks through their
  current trap-owned implementations. Trap changes and resets cancel all
  delayed work owned by the previous trap; and
- `OpeningLesson` no longer carries a second unreachable practice engine. The
  rendered `InteractivePractice` remains the single owner of opening practice.

## Behavioral evidence

`OpeningPracticeEffects.test.jsx` proves:

1. the guided coach introduction stays stable across an unrelated rerender;
2. a fresh parent completion callback does not restart guided autoplay;
3. changing the student's color updates the live practice board without
   destroying and recreating Chessground;
4. a prior opening's board event cannot reuse its backend session, while the
   replacement session attributes its result to the current opening;
5. an already-registered trap board event grades against the current trap
   after its prop identity changes;
6. an orientation-driven trap-board recreation keeps the live position; and
7. changing traps cancels the prior trap's delayed opponent move.

```text
focused before correction: 1 suite / 4 tests passed
focused after correction:  1 suite / 7 tests passed
full before correction:    44 suites / 197 tests passed
ordinary build before correction: exit 0
strict build before correction: exit 1, 36 hook findings
opening-learning findings after correction: 0
```

The first independent review withheld approval because the initial patch did
not invalidate an old backend opening session, let a fresh parent callback
restart guided autoplay, and left old trap timers alive. Those three defects
are corrected above rather than hidden by lint suppression. The exact-commit
full suite and build evidence, followed by independent re-review, remain the
acceptance gate. No backend, endpoint, database, dependency, lint suppression,
push, deployment, or product-score change is included.
