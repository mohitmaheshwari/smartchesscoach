# Acquisition Readiness Phase 6 - Hook Behavior Slice 16 Evidence

**Date:** 2026-09-07
**Scope:** `docs/acquisition_readiness_phase6_hook_behavior_precode_audit_2026_09_06.md`
**Status:** INDEPENDENTLY APPROVED

## Bounded change

Game Review and Lab navigation now keep one current owner for requests,
timers, game-scoped state, position commentary, and keyboard controls:

- `GameDecryptionV5` gives every game + requested-review-variant load a
  generation. A replacement load clears the prior game's optional content,
  board/navigation state, reflection state, plan state, timers, and playback;
- late V5, facts, thoughts, gold-caption, and position-read responses cannot
  write into a replacement game. The same ownership rule covers reflection
  saves, plan analysis, concept acknowledgement, feedback submission, and
  authoring export. Position reads are aborted when their move stops being
  current;
- a `generating` V5 response remains in the loading state, owns one retry
  timer, and loses that timer immediately when the game changes;
- Game Review keyboard controls use one installed listener which delegates to
  the current navigation implementation; and
- Lab V2 uses the same current-callback ownership pattern, avoiding listener
  churn while preserving Decrypt and Carry Forward navigation semantics.

Unsaved user reflections and in-progress action state belong to a game rather
than an A/B review variant. Variant reloads preserve them, and a returning
stored-thought response merges around an unsaved draft instead of erasing it.
All callback refs are now published from a committed layout effect rather than
being mutated during render.

No dependency was added and no hook warning was suppressed.

## Behavioral evidence

`GameDecryptionLoadEffects.test.jsx` proves:

1. a late prior-game V5 response cannot replace the current game's opening or
   move narrative;
2. the single keyboard listener advances through the current game's data;
3. `generating` keeps the coach-analysis loading state visible; and
4. switching games cancels the old retry rather than issuing another request;
5. a late non-OK authoring-facts response cannot apply coaching fields from
   the prior game;
6. an unsaved reflection survives a same-game validation-variant reload; and
7. a late save from the prior game cannot mutate the replacement review or
   show a false success toast.

`LabV2KeyboardEffects.test.jsx` proves:

1. the loaded PGN exposes four plies;
2. the right arrow reaches the current important move in Carry Forward;
3. the down arrow reaches the current game's final ply; and
4. exactly one Lab keyboard listener remains installed across both state
   transitions.

The first independent review withheld approval on four concrete lifecycle
gaps: the non-OK facts path, user-action response ownership, variant-draft
loss, and render-time ref mutation. The exact correction commit `82239628`
closed all four and was independently approved. The reviewer also confirmed
that the focused tests fail when transplanted to the pre-correction parent.

```text
focused Game Review + Lab: 2 suites / 6 tests passed, clean output
full frontend:             49 suites / 211 tests passed
ordinary build:            exit 0
strict build:              exit 1, exactly 23 exhaustive-deps findings
changed-source findings:   0
slice baseline:            32 findings
slice reduction:           5 findings
integrated branch total:   23 findings after the later Reflect slice
```

The 23 remaining findings are confined to `CoachPlay.jsx` and
`LabClassic.jsx`. No backend, endpoint contract, database, production flag,
push, deployment, or product-score change is included.
