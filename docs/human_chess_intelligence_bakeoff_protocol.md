# Human Chess Intelligence — Pre-registered Bake-off Protocol

**Status:** REQUIRED PRE-CODE GATE  
**Date:** 2026-08-31  
**Parent scope:** `docs/human_chess_intelligence_layer_scope.md`

## 1. Purpose

This protocol determines where Fathom/Syzygy, Maia-2, and Otter create measurable product value before any of them become product authorities. It answers five decisions:

1. Which human-policy model best predicts the moves and errors of ChessGuru's 600–1500 players?
2. Does clock/history conditioning materially improve the diagnosis of “didn't know” versus “rushed”?
3. Can human-policy probabilities improve puzzle difficulty and distractor quality?
4. Can a human-policy model help select a move that is both sound and realistically findable?
5. Which endgame claims can Fathom prove exactly and therefore authorize?

The experiment does not authorize deployment. It produces a decision packet for a separate implementation gate.

## 2. Non-negotiable truth hierarchy

- Stockfish remains the source of truth for move soundness outside tablebase positions.
- Syzygy/Fathom is exact truth for supported tablebase positions.
- Maia-2 and Otter estimate human behavior; they never declare a move correct.
- Existing detector-quality authorization continues to control which named weakness may speak to a player.
- No model may infer emotion, effort, intention, confidence, or psychology from moves alone.
- A human-model score is evidence, not a learner diagnosis.

## 3. Reproducibility manifest

Every run must write an immutable manifest containing:

- corpus snapshot ID, query, game IDs, and a SHA-256 digest of the ordered IDs;
- exclusion counts and reasons;
- exact chronological split assignment per player;
- model repository, license, commit/release, weight hash, configuration, and device;
- Stockfish version and the stored-analysis schema version used;
- Syzygy tablebase source, maximum men, file hashes, and Fathom/python-chess version;
- random seeds, commands, runtime, machine class, and output hashes;
- code commit and dirty-worktree status.

Outputs must be versioned under `backend/data/corpus_snapshots/` or another already-approved evidence location. Credentials and production connection strings must never be written to an artifact.

## 4. Corpus and eligibility

### Core move corpus

Use external human games only. Exclude Play-with-Coach sessions, bots, malformed PGNs, duplicates, games without a stable user identity, and moves without the already-stored Stockfish evidence needed by the track.

The primary population is users whose observed rating is 600–1500. Results must also be reported by rating band, time control, color, game phase, and evidence availability. A user may never appear in both training/fitting and evaluation through duplicated games or positions.

### Clock-qualified corpus

Clock experiments use only games with reconstructable `%clk` evidence or a versioned equivalent. The undocumented production `games.human_model` field is not accepted until its producer, schema, reconstruction rules, and validation test are committed. Missing clock evidence is “not measured,” never zero time.

### Position deduplication

Normalize positions by full board state relevant to legal moves. Near-identical positions from the same game remain in one split. Exact duplicate positions must not cross fitting and evaluation splits.

### Split selection data lock

Before choosing minimum-games and train/test proportions, measure the per-user game histogram and temporal span. Select the least restrictive chronological split that provides a meaningful past window and future window for the largest defensible cohort. The histogram and candidate comparison must be versioned; no split threshold is chosen from intuition.

## 5. Baselines

Every claimed improvement must beat the relevant simple baseline:

- move prediction: legal-move frequency by rating band and opening/phase;
- future weakness prediction: recency-weighted raw named-mistake frequency;
- puzzle difficulty: current ChessGuru difficulty plus `cp_loss` alone;
- teachable move: Stockfish best move and the existing Play-with-Coach safe-candidate guard;
- distractors: current authored distractors;
- rushed-versus-knowledge: clock-pressure heuristic without a learned model;
- captions: current production V5 caption pipeline.

## 6. Track A — Fathom/Syzygy exact endgame truth

Build an offline evaluator over every eligible lesson, detector fixture, puzzle, and sampled real-game position with tablebase material.

For each legal move record WDL before and after the move, DTZ when available, the set of result-preserving moves, and probe provenance. Test:

- whether the authored answer preserves the claimed result;
- whether every alternative marked wrong actually changes the result or violates the stated teaching constraint;
- whether a detector's named endgame concept follows from the exact position rather than material count alone;
- whether a puzzle has multiple valid answers;
- whether a lesson's continuation remains valid after every supported learner deviation.

Primary outputs: exact-error count, ambiguous-answer count, unsupported-claim count, coverage by lesson family, and an adjudication list. A single false “only move” claim is a content blocker for that item.

## 7. Track B — human move and error prediction

Candidates:

- Maia-2 configurations appropriate to the observed time controls and player/opponent ratings;
- Otter without clock/history features where supported;
- Otter with real reconstructed clock/history features;
- the baselines in Section 5.

Evaluate on a chronologically held-out future segment per player. Report top-1/top-k move accuracy, negative log likelihood, Brier score, calibration error, legal-move failures, latency, throughput, memory, and coverage. For mistakes, measure ranking quality for the actual played error and calibration of “a serious error is likely here,” using stored Stockfish labels only as truth.

Do not select a winner from aggregate accuracy alone. The selected model must remain calibrated across rating bands and common time controls and must not materially degrade the 600–1000 group in order to improve the 1400–1500 group.

## 8. Track C — clock-conditioned diagnosis

For each clock-qualified move, compare the same position under observed clock evidence and a matched non-pressure counterfactual supported by the model. Measure whether clock conditioning improves held-out move prediction and serious-error prediction beyond the clock heuristic.

The allowed output is decision context such as “this error pattern becomes more likely when little time remains.” It is not “you panicked” or “you knew this.” A knowledge-gap claim still requires repeated position/concept evidence and an authorized detector.

The Otter clock path is rejected if clock conditioning does not add stable out-of-sample value, if reconstructed clocks fail validation, or if inference cost is disproportionate to the gain.

## 9. Track D — sound-and-findable move selection

Sample serious mistakes across rating bands, phases, and named detector families. Use the existing stored Stockfish evidence first. Run a bounded, separately versioned MultiPV probe only where the stored analysis cannot enumerate sound alternatives; do not re-analyze the full game corpus.

For each position:

1. establish the Stockfish-safe candidate set under several candidate loss bands;
2. rank only that safe set by human-policy probability for the player context;
3. compare Stockfish-best, existing safe-candidate guard, and sound-and-findable selection;
4. have blinded chess reviewers grade understandability and teaching value without seeing the selector.

The soundness band is chosen only after publishing the candidate histograms, preservation rates, and reviewer results. Human probability can rank safe moves; it can never make an unsafe move acceptable.

## 10. Track E — puzzle difficulty and distractors

Difficulty evaluation uses first, unassisted attempts only. Assisted attempts, retries, demonstrations, and revealed-board help are separate outcomes.

Compare predicted target-move probability against current difficulty and `cp_loss` for forecasting first-attempt success. Report calibration by player rating, concept, source pool, and whether the puzzle came from the player's own game. Test model-ranked legal alternatives as distractors, but admit them only when Stockfish/tablebase verifies the instructional answer and the distractor's failure explanation.

Do not overwrite historical difficulty during research. Produce shadow scores and a joined comparison artifact.

## 11. Track F — Game Review caption quality

Freeze the current production baseline: the 2026-08-31 sample found 254 of 2,442 mistake/blunder captions (10.4%) lacked a useful WHY. The dominant failure was “You played X; Y was stronger,” with no causal chess explanation.

Create a stratified gold set across rating, severity, detector family, phase, weakness-match state, and repetition. Each candidate caption is graded blindly on:

- factual correctness against the board and stored engine evidence;
- why the played move fails;
- what the better move accomplishes;
- plain language for 600–1500 players;
- a truthful connection to the player's demonstrated history;
- one transferable instruction;
- non-repetition within the same review.

A caption fails if any factual claim is false, if personalization is invented, or if it merely renames the engine result. Secondary `decryption_voice` prose must be audited because it can currently outrank the verified central caption in the UI.

Candidate generation must extend `build_move_teaching_decision`; it must not create another caption authority. Thresholds for promotion are selected only after the score distribution and failure classes are published.

## 12. Track G — board complexity and positional similarity

Complexity candidates must use explicit, auditable board features rather than move-number buckets: legal candidate count, forcing-move density, evaluation spread, tactical volatility, king exposure, hanging/loose pieces, and material/pawn tension. Compare candidate formulas on future-error prediction and calibration before locking one.

Similarity candidates must be compared against the current pattern/rating retrieval: exact/structural features, chess embeddings if legally and operationally suitable, and hybrid reranking. Reviewer relevance and transfer value matter more than geometric closeness alone. No “similar position” copy may ship until the selected method demonstrates semantic relevance.

## 13. Decision rules

Each track ends in exactly one verdict: ADOPT, ADOPT IN SHADOW ONLY, REJECT, or INCONCLUSIVE. A verdict must cite the frozen artifact and baseline comparison.

Reject a candidate that:

- creates or authorizes chess truth not verified by Stockfish/tablebase;
- cannot be reproduced from the manifest;
- has unacceptable legal-move, calibration, licensing, or latency behavior;
- improves aggregate performance while materially harming a core rating band;
- requires invented clock, history, or personalization evidence;
- adds no stable value over the simpler baseline.

## 14. Execution order and deliverables

1. Freeze schemas, provenance, eligibility counts, and split-candidate histograms.
2. Run Fathom content verification.
3. Run the Maia-2/Otter move-prediction bake-off.
4. Run the clock ablation only on validated clock data.
5. Run bounded MultiPV sound-and-findable evaluation.
6. Run shadow puzzle difficulty/distractor evaluation.
7. Run caption gold comparison and parallel-path audit.
8. Run complexity and similarity formula bake-offs.
9. Publish one decision packet with per-track verdicts, costs, risks, and recommended rollout.

No production write, user-facing model call, bulk Stockfish re-analysis, or deployment is authorized by this protocol.
