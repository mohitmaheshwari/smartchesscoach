# Human Chess Intelligence — Stage 4 Report

Date: 2026-08-31

## Outcome

Stage 4 is implemented and shadow-ready. Game Review now receives the same evidence-backed player context as Play with Coach and the canonical move decision returns a typed causal/personal explanation.

It is not deployed and it does not change production-visible text by default. Visible rollout requires `CAUSAL_PERSONAL_CAPTIONS_ENABLED=1`.

## What changed

- Added `CaptionExplanation` to the canonical `MoveTeachingDecision` with:
  - verified board explanation;
  - optional evidence-backed player connection;
  - transferable instruction;
  - confidence, provenance, and personal-evidence metadata;
  - explicit shadow/visible rollout state.
- Added one shared, read-only player-caption context loader in `coach_conductor.py`.
- Wired Game Review to load motif, opening, concept, strong-opening, identity, and active-focus evidence once per game.
- Added a shadow-only mode: the connection is measured without changing the caption.
- Changed the enabled Stage 4 composition rule: player memory frames the board explanation and never replaces it.
- Added a final verifier after personalization. A failed personal board claim is removed while the verified base explanation survives.
- Extended central WHY enrichment to the measured “stronger move here” and “made things harder” shells when a verified `best_move_why` fact exists.
- Reused canonical principle cues for tactical threads; otherwise a verified best-move-purpose fact becomes a next-game scan. Missing facts remain silent.
- Bumped stored review schema to V5 coaching version 138 so regenerated reviews can carry the new structured contract.

No new caption engine, principle catalog, player profile, threshold, database collection, or LLM runtime path was added.

## Production-shaped evidence

### Existing caption baseline

A 500-game production sample contained 2,446 mistake/blunder captions:

- 2,216 included a WHY under the existing audit heuristic;
- 230 failed it (9.4%);
- the largest weak shell was a recommendation without a causal purpose.

This was the pre-change baseline, not a release threshold.

### Verified gold corpus

Source: `human_chess_stage4_gold_corpus_2026-08-31.json`.

- 946 stored gold rows;
- 906 verified or verified-after-correction;
- 429 unique verified positions after removing 477 duplicate reviews;
- 234 positions already map to a deterministic clean situation;
- 195 require deeper causal classification and remain deferred.

The legacy broad labels do not cover calculation depth, time management, traps, pawn structure, or a clean positional taxonomy. Stage 4 therefore does not pretend the 429 positions are a complete gold set.

### Mohit real-user shadow

Source: `human_chess_stage4_personal_caption_shadow_2026-08-31.json`.

The audit used the latest 30 analyzed games for the account, stored PGNs, and stored engine evidence only:

- 300 coach-worthy moves processed;
- 300/300 had a board explanation and passed the current claim verifier;
- 186 had a verified better-move-purpose fact;
- 194 had a fact-grounded transferable instruction;
- 55 had an eligible personal-history connection;
- those connections appeared in 25 of 30 games;
- 13 still had a generic recommendation shell;
- 0 of those 13 had an available `best_move_why` fact, so they are evidence-coverage debt rather than an unfixed renderer branch.

All 55 personal connections came from verified motif history in this sample: 45 “walked into” recurrences and 10 missed opportunities. Concept/opening connections did not fire in these 30 games and must not be claimed as validated by this run.

The shadow audit performed zero database writes and zero engine runs. It exported no caption, FEN, game, move, user, or reviewer text.

## Verification

- 8/8 focused Stage 4 tests pass.
- Syntax checks pass for all changed backend modules and audit scripts.
- An additional focused regression run produced 83 passes.
- That wider run also produced six pre-existing boundary failures in untouched forced-recapture/CoachExtras/Socratic behavior.
- Thirty-four live-endpoint tests were inconclusive because their base URL was empty and no server was supplied.

The new tests prove:

1. shadow context does not change visible captions;
2. enabled personalization preserves the board explanation;
3. a false personalized board claim is removed by the final verifier;
4. no player evidence means no personal claim;
5. clean corpus labels use legal board/exchange truth.

The new user-facing instruction sentence passes the ChessGuru voice rules: plain language, no centipawn/material confusion, no unexplained label, and a concrete next-time action.

## Honest limits

- “300/300 verified” means the current deterministic claim verifier found no supported claim violation. It is not a claim of perfect semantic chess understanding.
- 106 of 300 sampled moves lack enough verified evidence for a specific transferable instruction.
- The gold corpus is deep in six legacy categories but incomplete for several coaching dimensions.
- Blind human preference review remains an external final-stage input, as approved; it was not simulated.
- The compatibility `/coach/decryption/per-move` fallback and Game Moments narrator still exist, but the main Review UI continues to prefer the canonical `move.caption`.

## Rollout handoff

For Claude's later deployment pass:

1. deploy with `CAUSAL_PERSONAL_CAPTIONS_ENABLED=0`;
2. regenerate/internal-read V5 version 138 and confirm `caption_explanation` is present;
3. run `run_stage4_caption_shadow.py` in the deployed tree and compare with the locked snapshot;
4. enable the flag for internal accounts only;
5. verify final-caption truth plus the separate habit line;
6. roll back by setting the flag to `0` if any personal framing is unsupported or distracting.

Do not enable globally from the current evidence. The next evidence task is to classify the 195 deferred gold positions and review a blinded packet of the 55 eligible personal connections.
