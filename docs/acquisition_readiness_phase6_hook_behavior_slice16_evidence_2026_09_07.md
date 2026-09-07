# Acquisition Readiness Phase 6 - Hook Behavior Slice 16 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** SOURCE COMPLETE - independent review pending

## Bounded change

Game Review and Lab navigation now keep one current owner for requests,
timers, game-scoped state, position commentary, and keyboard controls:

- `GameDecryptionV5` gives every game + requested-review-variant load a
  generation. A replacement load clears the prior game's optional content,
  board/navigation state, reflection state, plan state, timers, and playback;
- late V5, facts, thoughts, gold-caption, and position-read responses cannot
  write into a replacement game. Position reads are aborted when their move
  stops being current;
- a `generating` V5 response remains in the loading state, owns one retry
  timer, and loses that timer immediately when the game changes;
- Game Review keyboard controls use one installed listener which delegates to
  the current navigation implementation; and
- Lab V2 uses the same current-callback ownership pattern, avoiding listener
  churn while preserving Decrypt and Carry Forward navigation semantics.

No dependency was added and no hook warning was suppressed.

## Behavioral evidence

`GameDecryptionLoadEffects.test.jsx` proves:

1. a late prior-game V5 response cannot replace the current game's opening or
   move narrative;
2. the single keyboard listener advances through the current game's data;
3. `generating` keeps the coach-analysis loading state visible; and
4. switching games cancels the old retry rather than issuing another request.

`LabV2KeyboardEffects.test.jsx` proves:

1. the loaded PGN exposes four plies;
2. the right arrow reaches the current important move in Carry Forward;
3. the down arrow reaches the current game's final ply; and
4. exactly one Lab keyboard listener remains installed across both state
   transitions.

```text
focused Game Review: 1 suite / 2 tests passed
focused Lab V2:      1 suite / 1 test passed
full frontend:       48 suites / 206 tests passed
ordinary build:      exit 0
strict build:        exit 1, exactly 27 exhaustive-deps findings
changed-source strict findings: 0
baseline:            32 findings
reduction:           5 findings
```

The 27 remaining findings are confined to `CoachPlay.jsx`, `LabClassic.jsx`,
and `Reflect.jsx`. No backend, endpoint contract, database, production flag,
push, deployment, or product-score change is included.
