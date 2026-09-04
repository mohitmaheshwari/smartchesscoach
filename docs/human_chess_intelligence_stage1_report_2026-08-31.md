# Human Chess Intelligence — Stage 1 Decision Report

**Status:** COMPLETE FOR MOVE POLICY; CONTENT REPAIR REQUIRED  
**Date:** 2026-08-31  
**Production writes:** none  
**Stockfish runs:** none  
**Player-facing integration:** none

## Decision

Use **Otter with verified player history** as ChessGuru's leading human-behavior research model. Use **Maia-2 as the no-history benchmark/fallback candidate**. Do **not** use Otter's clock input to tell a player that they rushed: the held-out data does not support that diagnosis. Use **Fathom/Syzygy as exact endgame truth in shadow**, but repair the routed endgame curriculum before allowing tablebase-backed grading to speak.

The frozen evidence is `backend/data/corpus_snapshots/human_chess_stage1_bakeoff_2026-08-31.json`.

## What was actually measured

The evaluation used 30 players, each player's last five games, and only earlier games as history. All 3,609 stored observations joined back to their legal PGN trajectory. Exact repeated positions were deduplicated, leaving 3,362 held-out moves. No production game, FEN, PGN, email, or player ID was exported; inference ran next to MongoDB and only aggregates left the host.

No game was re-analyzed with Stockfish. Existing stored engine evidence remained the chess-truth source.

## Move prediction result

| Candidate | Coverage | Exact move first | Actual move in top five | NLL | Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rating/phase frequency baseline | 3,362 | 10.5% | 32.4% | 3.326 | 0.939 |
| Maia-2 Rapid | 3,362 | 51.8% | 89.2% | 1.478 | 0.615 |
| Maia-2 Blitz | 3,362 | 52.2% | 88.9% | 1.482 | 0.615 |
| Otter, verified history only | 3,257 | **55.7%** | **91.6%** | **1.351** | **0.580** |

Lower NLL and Brier are better. Otter history-only also won within every target rating band:

| Rating | Baseline top-1 | Maia-2 Rapid | Otter history-only |
| --- | ---: | ---: | ---: |
| 600–999 | 9.6% | 51.2% | **55.2%** |
| 1000–1399 | 12.6% | 53.1% | **57.4%** |
| 1400–1500 | 8.3% | 50.5% | **53.3%** |

This is behavioral prediction, not chess judgment. It proves that player history contains useful information about what a person is likely to play. It does not prove that Otter knows why a move was played or whether it is good.

## Clock result: do not diagnose “rushing”

The paired cohort contained 2,691 positions with validated history, numeric time control, and independently reconstructed pre-move clock.

| Otter ablation | Exact move first | NLL | Brier |
| --- | ---: | ---: | ---: |
| Neutral context | 52.1% | 1.506 | 0.632 |
| Clock only | 51.5% | 1.503 | 0.630 |
| History only | **55.8%** | **1.342** | **0.580** |
| History + observed clock | 55.2% | 1.350 | 0.583 |

Observed clock failed to improve top-1 accuracy over history-only in three of four pre-registered clock quartiles and made the overall NLL and Brier slightly worse. Its calibration improved, but that alone cannot justify a causal player-facing label.

**Verdict: REJECT clock-conditioned “you rushed” diagnosis.** Clock remains direct evidence for neutral statements such as “you had 12 seconds,” and can remain a shadow calibration input. A knowledge-versus-time diagnosis still needs repeated concept evidence and an authorized detector.

## Maia-2 result

The time-control-specific weights behaved in the expected direction: Rapid weights were better on Rapid games, and Blitz weights were better on Blitz games. Maia-2 covers positions without reconstructable personal history and substantially beats the simple baseline. It is therefore worth retaining as a fallback candidate and independent benchmark, not as a second chess authority.

**Verdict: ADOPT IN SHADOW ONLY.** A production design should not run Maia and Otter merely to have two models. Use Otter-history where its required evidence exists; use Maia only where a measured fallback policy demonstrates value.

## Fathom found real curriculum failures

The audit targeted the routed canonical source, `backend/data/coaching/endgame_theory_tree.json`: 18 lessons and 54 positions.

- 5 positions contain an invalid board state or authored move.
- 4 authored “correct” moves change an exact tablebase win into a draw or loss.
- 19 of 23 successfully probed moves preserve the exact result.
- 18 of those 23 positions have multiple result-preserving moves.
- 21 positions contain more than five pieces and require a larger tablebase or bounded stored-Stockfish verification.
- 5 Lucena/Philidor positions remain unresolved by the dependency-limited standalone Fathom probe and are explicitly listed in the snapshot.

This proves two product requirements:

1. Tablebase-backed lesson admission is valuable because current content contains objective errors.
2. Grading must accept the exact set of result-preserving moves, then apply any narrower teaching constraint explicitly. A single authored move must not automatically make every equivalent move “wrong.”

The nine definite blockers are retained with their exact FEN and authored move in the snapshot. They must be repaired with richer content; they are not a request to delete or hide the lessons.

**Verdict: ADOPT IN SHADOW ONLY.** The exact-truth method is accepted. Player-facing enforcement waits for repaired lessons, full dependency coverage, and explicit teaching-constraint tests.

## What Stage 1 does not prove

The following remain **INCONCLUSIVE**, not silently approved:

- puzzle difficulty from probability that a target move is found;
- realistic distractors;
- probability that any serious error will occur in a position;
- sound-and-findable move selection;
- “didn't know” versus “knew but rushed”;
- caption correctness or teaching quality;
- future weakness prediction and actual improvement.

Stored analysis contains the played move and best line, but not a verified Stockfish score for every legal candidate. Human probabilities cannot safely power those features until the bounded MultiPV step defines the sound candidate set.

## Architecture consequence

The evidence flow remains one-way:

`stored Stockfish or exact tablebase truth → authorized detector/concept → optional human-policy context → central teaching decision → caption/training/mastery`

Otter/Maia may answer “what might this player consider?” They may not answer “what is correct?”, invent a weakness, create a mastery event, or write a caption around an unverified move.

## Next build order

1. Repair all nine definite endgame blockers and complete the five unresolved rook-endgame proofs; add exact alternative-move grading.
2. Run the bounded MultiPV probe on a stratified serious-mistake sample only, using stored Stockfish everywhere else.
3. Measure sound-and-findable move selection, serious-error likelihood, puzzle difficulty, and distractors against their baselines.
4. Build the caption gold set around the existing 10.4% no-WHY failure baseline; extend `build_move_teaching_decision`, never a parallel narrator.
5. Run retrospective future-weakness prediction against recency-weighted raw frequency.
6. Only then write the production integration scope for the winning evidence paths.

No route, UI, production worker, mastery record, puzzle score, or caption has been changed by Stage 1.
