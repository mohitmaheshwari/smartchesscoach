# Deterministic Whole-Game Teaching Review — Holdout Report

**Date:** 2026-09-13
**Status:** CHESS-TRUTH AND FACT-GENERALIZATION GATES PASS; RELEASE GATES REMAIN
**Frozen implementation:** 76a411306b0066b4e585f6f23f2d0df8a7306e7e

## Outcome

The deterministic whole-game review now has a complete local implementation:

- one central game story sourced from an authorized event;
- opening, middlegame and endgame phase cards using stored V5 phase identity;
- no more than three selected teaching moments from the existing planner;
- an honest no-lesson state that keeps the ordinary move review available;
- canonical /game/:gameId routing from the legacy replay URL;
- no read-time engine, model, tablebase-network or database write;
- no new runtime LLM dependency.

The shared fact layer improved on the frozen 100-game development corpus from
139 to 158 exact matches, or 63.47% to 72.15%. The improvement came from one
reusable immediate-reply material contract with positive, recapture,
same-loss-in-both-branches and invalid-line tests. It remains Shadow and cannot
reach a player until its own opportunity-level precision packet passes.

## One-time unseen holdout

The holdout was opened only after the implementation and 100-game
adjudication were frozen.

| Check | Result |
|---|---:|
| Games | 42 |
| Players | 42 |
| Development overlap | 0 |
| Games with a board-proved story | 38 |
| Honest no-story games | 4 |
| Board-proved moments | 90 |
| Critical false claims | 0 |
| Legal replay | 90/90 |
| Exact shared-fact matches | 72/90 (80.0%) |
| Different typed fact | 9/90 |
| No typed fact | 9/90 |

Development exact coverage was 72.15%; unseen holdout exact coverage is 80.0%.
The deterministic fact improvement therefore generalizes on this holdout
instead of collapsing.

All 90 proposed holdout moments were reviewed individually after legal replay.
The review checked actor and direction, captured piece and square,
capture/recapture settlement, mate direction, safe-capture recaptures and the
single fork's two targets. Four no-story games were also reviewed. No product
caption, detector label, selected event or identity was visible before that
adjudication was frozen.

## Stored-product baseline

A post-adjudication aggregate read found all 42 holdout games. Their stored
review contains 2,451 legacy caption or explanation rows, but zero typed
teachable-event rows and zero whole-game plan chapters.

That does **not** mean all 2,451 old captions are useless. A semantic,
same-ply comparison against the 90 frozen gold moments still requires a
separately authorized export of those product captions. That export was not
covered by the position-only production-data permission and was therefore not
performed.

The paired useful-lesson coverage gate remains open until that comparison is
completed. It is not silently treated as a zero baseline.

## Verification

- Backend feature, evidence and newly landed upstream regressions: 325 passed.
- Holdout identity wrapper: 2 passed.
- Holdout coverage wrapper: 1 passed.
- Frontend feature suites: 11 passed.
- Frontend production build: passed.
- Full frontend run: 266 passed and 2 unchanged ActivationHub tests failed;
  both failing files are byte-identical to origin/working-code.
- Repository HTTP flow script: inconclusive because no local backend was
  running.
- One upstream backend test could not collect because the local Python
  environment lacks bcrypt; the feature suites do not require it.

## Release decision

Do not enable this for the population yet. The following gates remain:

1. authorize and run the 90-row legacy-caption comparison, then calculate the
   precommitted paired coverage interval;
2. run the bounded production reconciliation dry-run for at most ten pilot
   games and preserve its exact selection SHA;
3. deploy with existing access gates closed, reconcile only the selected pilot
   after backup and restore proof, and complete one authenticated player
   journey;
4. collect the precommitted blinded usefulness and recognition evidence;
5. keep review:immediate_reply_material_loss Shadow until a separate
   opportunity-level false-positive review promotes it.

Holdout failures may block rollout. The holdout may not be used to tune
detectors, captions, ranking, thresholds or per-game exceptions.
