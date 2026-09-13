# Deterministic Whole-Game Teaching Review — Holdout Report

**Date:** 2026-09-13
**Status:** CHESS-TRUTH PASSES; USEFUL-LESSON COVERAGE FAILS; RELEASE BLOCKED
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

A post-adjudication read found all 42 holdout games. Their stored review
contains 2,451 legacy caption or explanation rows, zero typed teachable-event
rows and zero whole-game plan chapters. A separately approved, read-only
export then retrieved only the 90 same-ply legacy caption rows needed for the
comparison. It contains no source game ID, user ID, account field, email,
credential or URL and records zero production writes, engine runs and model
calls.

The identity-free caption packet is SHA-256
`f4a08f9131a55b014e07a6bc24ed36f9d7ba7c4a4ab5ec4e2eec4731be0f4ca5`.
The complete 90-row adjudication and paired score is SHA-256
`92c3566af399633de96f8fcf2cbe8a7de616079f8346acd2d7d30c7dd4bcd8ad`.

Every row was read after the chess gold had been frozen. A legacy caption
counts only when its caption, explanation or visible principle teaches the
same causal reply, opportunity or mate direction. Naming the same move with a
different reason does not count.

| Legacy disposition | Count |
|---|---:|
| Exact match | 55 |
| Causal equivalent | 15 |
| Same move, wrong reason | 13 |
| Detector miss | 4 |
| Verified fact not wired | 2 |
| Missing concept candidate | 1 |
| **Useful legacy coverage** | **70/90 (77.78%)** |

Examples of uncovered legacy teaching include three captions that describe
defending against mate when the player actually had a forced mate, an ordinary
“check” caption that omits the legal rook capture of the checking piece, a
caption that praises a pin while the bishop can simply be taken, a caption
that praises a move which loses a knight on the next reply, and a fork caption
that mentions only check rather than the two attacked targets.

## Paired useful-lesson gate

The pure deterministic fact layer matches 72/90 gold moments (80.0%). This is
an **upper bound**, not a claim that 72 lessons reach the player: it includes
the new immediate-reply material family while that family remains Shadow.
The authorized player-visible subset cannot cover more of these gold moments
than the fact layer supplying it.

Four honest no-story games have no proved-lesson denominator. The locked
paired test therefore uses the remaining 38 games, which are also 38 distinct
players.

| Paired measure | Result |
|---|---:|
| Legacy macro coverage | 78.509% |
| Deterministic fact upper-bound macro coverage | 82.456% |
| Upper-bound paired improvement | +3.947 percentage points |
| Candidate upper bound better / tied / worse | 8 / 24 / 6 games |
| Player-clustered 95% bootstrap interval | **−6.140 to +14.474 points** |
| Locked requirement | lower bound above 0 |
| **Gate** | **FAIL** |

Because even the pointwise fact-layer upper bound fails the locked interval,
the authorized visible product cannot pass this release gate. Authorization
was not relaxed and Shadow evidence was not mislabeled as player-visible.

## Verification

- Backend feature, evidence and newly landed upstream regressions: 325 passed.
- Holdout identity wrapper: 2 passed.
- Holdout coverage wrapper: 1 passed.
- Frozen caption export and semantic paired-score tests: 2 passed.
- Frontend feature suites: 11 passed.
- Frontend production build: passed.
- Full frontend run: 266 passed and 2 unchanged ActivationHub tests failed;
  both failing files are byte-identical to origin/working-code.
- Repository HTTP flow script: inconclusive because no local backend was
  running.
- One upstream backend test could not collect because the local Python
  environment lacks bcrypt; the feature suites do not require it.

## Release decision

Do not enable or deploy this experience as a release candidate. Its decisive
precommitted useful-lesson gate failed. The implementation may remain isolated
behind closed flags, but reconciliation, pilot enrollment, usefulness testing
and recognition testing do not turn a failed coverage result into a pass.

The next valid evidence cycle is:

1. keep `review:immediate_reply_material_loss` Shadow until a separate
   opportunity-level false-positive review promotes it;
2. use a new development corpus—not these holdout examples—to improve shared
   deterministic coverage and authorized delivery;
3. freeze the revised implementation and evaluate it on a new untouched,
   player-stratified holdout with a newly frozen current-review baseline;
4. only after that paired interval passes, run the bounded reconciliation,
   authenticated pilot journey, blinded usefulness and recognition gates.

Holdout failures may block rollout. The holdout may not be used to tune
detectors, captions, ranking, thresholds or per-game exceptions.
