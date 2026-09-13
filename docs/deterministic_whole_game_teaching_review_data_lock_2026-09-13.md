# Deterministic Whole-Game Teaching Review — Data Lock

**Date:** 2026-09-13
**Status:** LOCKED FROM MEASURED EVIDENCE
**Scope:** `docs/deterministic_whole_game_teaching_review_scope.md`
**Aggregate snapshot:** `backend/data/corpus_snapshots/deterministic_whole_game_teaching_review_census_2026-09-13.json`

## 1. Decision summary

1. Use **100 complete development games** and a separate **42-game unseen holdout**. The holdout contains exactly one eligible game from every eligible player and remains unopened until implementation and the development adjudication are frozen.
2. Preserve the live rating distribution in the development set: 19 / 11 / 30 / 31 / 9 games across the 600–799 / 800–999 / 1000–1199 / 1200–1399 / 1400–1500 bands.
3. Limit development contribution to three games per player. Together with the one-game holdout, no player contributes more than four games.
4. Keep the existing maximum of **three featured moments** and the deployed ranking switch. Whole-game composition may organize those moments by phase, but it may not introduce another importance score.
5. Treat the stored V5 phase on each move as the review phase source. Page reads do not infer or rewrite phase.
6. Opening identity is context, not proof of opening understanding. With all explicit opening teaching detectors currently Shadow, V1 cannot say an opening was perfect, mastered, mishandled or the cause of the result.
7. Named endgame ideas remain silent unless their current authorization permits the receiving surface. At lock time, only exact endgame result change is Caption-grade; rule of the square is Disabled and the other named endgame concepts are Shadow.
8. Reuse the compact Candidate-Aware card: no more than two collapsed explanatory sentences and 32 prose words, plus a separate memory cue of at most 18 words. The board carries the continuation.
9. Use a frozen structured complete-game adjudication rubric. Codex first reviews anonymized games without ChessGuru's visible captions, selected events, detector labels or answer key.
10. Keep the first visible historical cohort to one explicitly enrolled account and at most ten recent eligible games. The 100-game corpus is development evidence, not a production backfill authorization.

## 2. Frozen source population

The read-only production census used only analyses completed at or before `2026-09-13T08:26:28Z`.

Eligibility required:

- joined game and V5 analysis;
- player rating from 600 through 1500;
- non-empty source PGN;
- at least eight stored move entries;
- `move_san` and `fen_before` on every stored move entry.

This produced **6,897 games from 42 players**. All output was aggregate-only. No email, user ID, game ID, username, PGN, FEN, move or credential was printed or stored in the census snapshot.

The population is concentrated enough that an unbounded random sample is unsafe:

- one player supplies 1,119 eligible games;
- Chess.com supplies 6,640 of 6,897 games;
- 3,545 games reach all three stored phases, while 953 contain only an opening phase;
- rating-band counts are 1,330 / 757 / 2,097 / 2,123 / 590.

The frozen eligible-corpus SHA-256 is:

`1a302e7a618303cd2cb1895f9fd20ae079ba77921f402a21c1b4be45d4c0219f`

The digest binds the sorted internal game identities at the cutoff. The evidence packet exposes only new opaque signatures; it never versions those source identities.

## 3. Development and holdout design

### Selected design

Holdout selection happens first. For each of the 42 eligible players, choose the lowest stable SHA-256 ordering under the tag `whole-game-holdout-v1`. No holdout content may be shown to Codex, used in prompt examples, used to author predicates or used to tune selection before the development implementation is frozen.

Development selection then solves an exact capacity-constrained allocation:

- exclude every holdout game;
- preserve the population's largest-remainder rating allocation for 100 games;
- cap each player at three development games;
- use stable SHA-256 order under `whole-game-development-v1` within each player/rating cell;
- use max-flow to satisfy all rating demands rather than relying on band iteration order.

The exact allocation is:

| Rating band | Population | Development |
|---|---:|---:|
| 600–799 | 1,330 | 19 |
| 800–999 | 757 | 11 |
| 1000–1199 | 2,097 | 30 |
| 1200–1399 | 2,123 | 31 |
| 1400–1500 | 590 | 9 |

The resulting development set has:

- 100 games from 36 players;
- 53 games as Black and 47 as White;
- 14 opening-only, 25 opening+middlegame, 10 opening+endgame and 51 three-phase games;
- maximum three games from one player;
- SHA-256 `91f8aacdb0d121fce9258509c84cc2b4bd1a840c3d63224a182ed9e875044496`.

The holdout has:

- 42 games from all 42 eligible players;
- exactly one game per player;
- 18 Black and 24 White games;
- 10 opening-only, 7 opening+middlegame, 7 opening+endgame and 18 three-phase games;
- SHA-256 `87daa7089e35060cfaeb0164c9a0e741ad799634b74b94878f2f11dc5250020b`.

The development and holdout overlap is **zero**. Maximum combined contribution is four games from one player.

### Rejected designs

- **All 100 games for discovery and scoring:** rejected because every scored example would already have influenced the implementation.
- **A random 100/20 split by game:** rejected because prolific players could dominate both sides and leak the same personal patterns into development and holdout.
- **A 100/50 split:** rejected because only 42 eligible players exist; one holdout per player is the strongest available player-stratified design and produces 42, not 50.
- **Naive sequential quota filling:** rejected by the live dry-run. It returned only 87 games under the three-game cap because multi-band players were consumed before the thin upper band.
- **Equal 20-game rating bands:** rejected because it more than doubles the 1400–1500 share and understates the two largest live bands.
- **Minimum 15 per rating band:** rejected because it forced a four-development-game cap and 17% of the sample into a band that is only 8.6% of the live corpus.
- **Unlimited per-player contribution:** rejected because the largest account alone can supply the complete review.

## 4. Featured moments and central story

The maximum remains **three featured moments per game**. Zero, one, two or three are valid; the composer never pads a quiet game.

This inherits the measured Candidate-Aware lock:

- 3,981 of 4,141 candidate-bearing games, or 96.14%, contained no more than three complete candidates;
- the cap controls reading load without hiding ordinary candidate supply;
- hidden or Shadow candidates do not become visible merely to fill a phase.

Whole-game phase chapters are navigation and honesty states, not extra featured moments. “No authorized lesson found” and “phase not reached” are complete states.

The composer preserves the existing planner formula selected by the current rollout switch:

- `D_teaching_then_critical` in the baseline path;
- `E_transition_then_teaching` when the existing quality-V2 flag is enabled.

It may connect selected events chronologically and choose the highest-ranked selected event's existing principle as the surviving instruction. It may not create a third ranking formula, add phase bonuses, add opening/endgame quotas or rank by centipawn loss alone.

### Rejected alternatives

- **One featured moment per phase:** phase presence does not prove equal teaching value and would manufacture opening or endgame filler.
- **Highest engine loss:** magnitude does not identify a teachable cause and excludes good decisions and opponent opportunities.
- **Personal focus before authorization:** recurrence may influence a plan only where the event is already Plan-authorized.
- **A new Codex-derived ranking formula:** the 100-game review creates labels for a later measured bake-off; it does not authorize tuning before those labels exist.

## 5. Claim-strength and phase locks

### Phase owner

The review consumes the stored `decryption_v5_data.phase` emitted by the canonical V5 analysis path. It does not call any review-local phase detector. New analyses continue to use `game_decryption_v5_service.detect_phase`; existing analyses keep their stored version until an explicitly authorized regeneration.

### Opening

Canonical opening identity and exact move-history facts may be shown as context. The safe V1 forms are:

- “You reached the Italian Game.”
- “The stored authored line continues with Bb3 here.”
- “You left the stored line on move 7.”
- “I do not yet have an opening lesson I can prove from this game.”

The following are blocked unless a separate current authorization proves the exact claim:

- “You played the Italian perfectly.”
- “You understand this opening.”
- “This opening mistake caused the loss.”
- “You should have known the theory.”
- “I found no opening problem,” when that conclusion is based only on no detector firing.

At lock time every explicit opening teaching authorization is Shadow.

### Middlegame and tactics

Only player-authorized `TeachableEvent` contracts may enter a visible chapter. Current Caption/Plan families include exact destination safety, simple hang captioning, verified single-game cause, exact free piece, fork payoff, aligned payoff and forced mate. Their own scope limits remain binding.

### Endgame

`review:exact_endgame_result_change` is Caption-grade and may state a proven result change from stored exact evidence. Named rule-of-square content is Disabled. Opposition, king centralization, active rook, passed-pawn creation, Lucena, Philidor, stop-promotion and endgame geometry remain Shadow. V1 therefore says “no authorized endgame lesson” rather than guessing a principle.

### Good play and opponent opportunities

Good play needs a positive authorized event; low centipawn loss alone cannot establish understanding. Opponent opportunities use the same actor-aware cause contracts and must clearly say whose move and whose opportunity is being discussed.

## 6. Reading and interaction lock

The visible moment shape inherits the approved Candidate-Aware lock:

1. plain-language idea headline;
2. first short sentence: what the played choice allowed or prevented;
3. second short sentence: the stronger idea and its concrete purpose;
4. one board action;
5. separate memory cue.

Collapsed explanation limits:

- maximum two prose sentences;
- maximum 32 prose words;
- maximum 18 words in the separate memory cue.

Move notation is supporting evidence, not the headline. Conditions that change chess truth may never be truncated to meet a word budget; the detail moves to the board replay or the moment abstains.

Every featured moment must support:

- original-position reset;
- legal one-move-at-a-time replay;
- played-line replay when relevant;
- alternative-line replay when relevant;
- try, hint, reveal and retry states;
- answer hiding before commitment.

## 7. Frozen independent-review rubric

Codex receives each anonymized development game as a complete legal move history with stored engine evaluations and continuations. It does **not** receive ChessGuru's visible captions, selected moments, detector names, concept labels, question answer or planner rank.

For every game Codex records:

- phase reached: opening, middlegame and endgame;
- one proposed central story, or explicit “no provable central story”;
- up to three highest-value teaching moments;
- actor, ply and side to move;
- played decision and proposed alternative;
- causal chess fact;
- legal payoff/defense/recapture settlement;
- reusable memory cue;
- whether the moment is missed play, opponent opportunity, demonstrated knowledge or exact endgame truth;
- evidence verdict: `proved`, `contradicted`, `insufficient_stored_horizon` or `unsupported`;
- critical-false-claim flag.

Only after that file is frozen is it joined to ChessGuru output. Each proposed lesson receives exactly one disposition:

- `exact_match`;
- `causal_equivalent`;
- `same_move_wrong_reason`;
- `verified_fact_not_wired`;
- `detector_miss`;
- `fact_contract_incomplete`;
- `missing_concept_candidate`;
- `unsupported_residue`;
- `codex_interpretation_rejected`.

No row may disappear. A repeated gap can change product logic only after it becomes a shared deterministic predicate or canonical content extension with positive, hard-negative and adversarial tests. Exact sampled-game exceptions are forbidden.

## 8. Evaluation gates

### Chess truth and contract completeness

- zero critical actor, color, direction, legality, mate, material, exchange, recapture, promotion, x-ray and truncated-payoff failures;
- 100% legal replay;
- 100% evidence identity, version and provenance validation;
- 100% correct reached/not-reached phase state;
- 100% of featured moments contain a cause or authorized exact claim, a replayable line and a memory cue;
- page reads start zero engine, model or external tablebase-network processes.

Any critical false claim fails the release regardless of average performance.

Whole-game central-story and featured-lesson semantic precision inherits Caption-grade requirements:

- at least 95% independently reviewed semantic precision;
- Wilson 95% precision lower bound at least 85%;
- at least 50 reviewed visible claims;
- zero critical false claims.

### Useful-lesson coverage

Coverage is scored against only Codex lessons adjudicated `proved`. `Exact_match` and `causal_equivalent` count as covered. Unsupported and insufficient-horizon proposals are excluded from the denominator; same-move/wrong-reason is not covered.

The candidate must beat the frozen current-review baseline on paired per-game useful-lesson coverage with the lower bound of a player-clustered 95% bootstrap interval above zero. This is selected instead of inventing an absolute recall percentage before the first complete-game gold exists. Silence is reported separately and never converted into a false positive.

### Blinded usefulness and recognition

Reuse the approved Candidate-Aware thresholds:

- at least 60 blinded comparisons;
- at least 39 of 60 strict preferences for the whole-game version, excluding ties;
- Wilson 95% lower bound above 50%;
- no admitted cause family with a majority preferring baseline when at least ten examples exist;
- zero critical false claims.

Player recognition requires:

- at least 30 paired first attempts;
- an exact paired test with `p < 0.05`;
- post-review correct-rate Wilson 95% lower bound above 50%;
- no answer leakage;
- assistance, hint, reveal and replay recorded separately.

### Holdout

The 42-game holdout is evaluated once after code, templates, ranking behavior and development dispositions are frozen. It must independently satisfy every chess-truth and precision gate above. Its paired useful-lesson coverage improvement over the frozen current-review baseline must also have a player-clustered 95% bootstrap lower bound above zero.

There is no adjustable “generalization tolerance.” Failing a holdout gate blocks rollout; the holdout cannot be used as a second development set.

## 9. Canonical source map

| Responsibility | Canonical owner | Whole-game rule |
|---|---|---|
| Player-facing review | `/game/:gameId` → `LabV2` / `GameDecryptionV5` | Extend this surface only. |
| Game recommendation | existing review prescription/selection service | Whole-game composition does not select a different game. |
| Plan and chapters | `game_review_contracts.GameTeachingPlan`, `game_review_planner.py` | Preserve chapter contract, cap and formula switch. |
| Event projection | `game_review_event_adapter.py` | Only projected player-authorized events may speak. |
| Move decision and explanation | `caption_pipeline.MoveTeachingDecision`, `CaptionExplanation` | No parallel caption DTO or renderer. |
| Typed cause | `caption_facts.ReviewTeachingCause` | No new prose-only causal inference. |
| Position-relative questions | `teaching_reason_contracts.TeachingReasonBundle` | Question and answer derive from the same verified reason. |
| Detector visibility | `detector_quality.py` | Shadow, Disabled and unknown remain non-player-facing. |
| Phase | stored V5 move phase from `game_decryption_v5_service.py` | No read-time or review-local phase inference. |
| Opening identity | existing opening lookup/theory services | Identity and authored history are context, not mastery. |
| Opening teaching content | `opening_curriculum_engine.py` and its canonical data | Reference by identity; do not copy wording. |
| Traps | `trap_library.py` and canonical trap data | Reference only when authorized for the surface. |
| Exact endings | `exact_endgame_service.py` | Exact result authority only. |
| Named endgame lessons | existing canonical endgame teaching content | Content presence does not bypass detector grade. |
| Mastery and transfer | `concept_mastery_service.py` and existing learning evidence contracts | Guided review never proves organic transfer. |
| Replay | stored legal candidate/continuation evidence on the decision | Reads never launch analysis. |

`/replay/:gameId` has no product inbound reference beyond its router declaration and layout recognition. V1 keeps the URL as a compatibility redirect to the canonical game review and does not maintain `CoachReplay` as a second coaching implementation. Its backend endpoint is not deleted in this slice.

## 10. Historical cohort and authorization

The earlier measured production projection found 605 stored plans but only 53 current player-safe plans across 13 users. Supply—not raw analysed-game volume—is the runtime constraint.

The first visible run remains:

- one explicitly enrolled validation account;
- at most ten recent eligible games;
- dry-run and state report before any apply;
- original stored analysis immutable;
- idempotent plan/enrichment fingerprint;
- states reported as current, newly composed, partial, unsupported, stale, invalid and failed.

No broad historical backfill is authorized by this lock. The 100-game development packet and 42-game holdout are offline evidence artifacts, not production records. A larger cohort requires its own read-only population and cost report after the development and holdout gates pass.

## 11. What this lock authorizes

After the pre-code audit passes, implementation may:

- add a whole-game composer over existing safe plans and facts;
- add honest phase states and phase-to-phase connective copy;
- add the approved compact interactive moment presentation to the canonical review;
- redirect the overlapping frontend replay route to the canonical review;
- build the anonymized development/holdout packet tooling and frozen baseline comparison;
- run the 100-game development review;
- turn repeated verified gaps into shared deterministic predicates or canonical-content extensions with the existing promotion discipline;
- run the unseen holdout once after development freeze;
- prepare the one-account historical dry-run and authenticated journey.

It does not authorize a new detector registry, a new phase detector, a new caption engine, Shadow promotion, a runtime LLM/model/engine call, a broad historical backfill, wider rollout or production deployment.
