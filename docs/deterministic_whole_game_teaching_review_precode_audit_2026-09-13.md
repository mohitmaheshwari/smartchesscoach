# Deterministic Whole-Game Teaching Review — Pre-Code Audit

**PRE-CODE AUDIT: PASS**
**Date:** 2026-09-13
**Scope:** `docs/deterministic_whole_game_teaching_review_scope.md`
**Data lock:** `docs/deterministic_whole_game_teaching_review_data_lock_2026-09-13.md`
**Aggregate evidence:** `backend/data/corpus_snapshots/deterministic_whole_game_teaching_review_census_2026-09-13.json`

## Six hard gates

1. **Literal UI mockup — PASS.** The approved scope shows the library reason, game story, opening state, interactive middlegame question, direct verdict, played and alternative replays, good-play acknowledgement, no-endgame state, exact-endgame interaction and final surviving instruction.
2. **Chess idea before notation — PASS.** Headlines describe the position's demand or reusable idea. SAN appears only inside the short causal explanation or on the board.
3. **Numeric choices are data-locked — PASS.** The 100/42 corpus, player caps, proportional rating cells, three-moment cap, reading limits, semantic precision, blinded preference and recognition rules all come from measured data or existing approved evidence locks. The naive sampler and arbitrary quota alternatives are explicitly rejected.
4. **Success changes behavior — PASS.** Review usefulness is not the finish line. The flow measures first-attempt recognition on a non-identical position, keeps assistance separate and leaves later unassisted games as the only transfer proof.
5. **Deferred work remains deferred — PASS.** No broad detector promotion, runtime LLM, live Maia/Otter, new full-game Stockfish pass, community review marketplace, broad historical backfill or production rollout enters this slice.
6. **Mohit sign-off — PASS.** Mohit explicitly chose EXTEND and then instructed “go ahead” after receiving the complete scope and confirming the 100-game independent-review plan.

## Source-of-truth audit

No new chess taxonomy, opening catalog, trap catalog, endgame catalog, detector registry, phase detector, caption engine, review selector or mastery system will be created.

The only genuinely new backend concept is **whole-game composition**: an orchestration contract that references existing safe events and phase states. It is not permitted to inspect a FEN to discover a tactic, name a concept, choose an opening line, decide chess correctness or manufacture causal prose.

| Concern | Owner | Audit rule |
|---|---|---|
| Player page | `LabV2` / `GameDecryptionV5` at `/game/:gameId` | All new presentation lands here. |
| Review selection | existing review prescription service | Composer receives a game; it never picks another. |
| Moment selection | `game_review_planner.py` | Keep the three-moment cap and current formula switch. |
| Safe event conversion | `game_review_event_adapter.py` | Composer consumes projected events, never raw detector candidates. |
| Decision/caption | `MoveTeachingDecision` and `CaptionExplanation` | Existing text and reason contracts remain canonical. |
| Causal fact | `caption_facts.ReviewTeachingCause` | A story cannot be grounded only in prose. |
| Question | `TeachingReasonBundle` | Prompt and answer use the same verified reason. |
| Visibility | `detector_quality.py` | Unknown, Shadow and Disabled never affect visible output. |
| Phase | stored V5 `phase` | No review-local inference or move-number fallback. |
| Knowledge | canonical opening, trap and endgame sources | Refer by identity; do not copy knowledge into the composer. |
| Exact ending | `exact_endgame_service.py` | Stored exact evidence only; no page-read network query. |
| Learning | existing concept mastery/evidence contracts | Guided review cannot become organic proof. |

The old `CoachReplay` frontend contains overlapping presentation and LLM-described board reading. It is not imported into the new composer. Its route becomes a compatibility redirect after a route test proves the canonical game ID is preserved.

## Forecasted bottleneck

The bottleneck is **authorized causal coverage**, not raw candidate volume:

- the eligible complete-game corpus has 6,897 games;
- a broad current-field scan found at least 15 candidate-looking stored moments even at the tenth percentile and a median of 34;
- the earlier public-projection census reduced 605 stored plans to only 53 player-safe plans across 13 users;
- every explicit opening teaching detector is Shadow;
- named endgame principles are Shadow or Disabled except exact result change.

Therefore the first implementation must make silence and unavailable phase lessons look deliberate. It must not promote detectors or treat unprojected stored facts as safe to make the page appear complete.

## Frozen implementation order

1. Add the aggregate corpus snapshot, data lock and this audit on the clean feature branch.
2. Add anonymized packet tooling that reproduces the frozen signatures and refuses overlap, identity fields, post-cutoff analyses or mismatched corpus fingerprints.
3. Export the 100-game development packet and sealed 42-game holdout without printing their chess content during export.
4. Freeze current Game Review output for both sets.
5. Add a typed whole-game composition contract over existing projected `GameTeachingPlan` chapters and stored phases.
6. Add deterministic honest phase states and central-story composition without new chess inference.
7. Project the contract through the existing Game Review API behind one existing account-isolated access decision and a new default-off surface flag only if no existing flag can express this rollout.
8. Add the phase story and interaction to `GameDecryptionV5`; reuse existing board replay/try controls.
9. Redirect `/replay/:gameId` to `/game/:gameId` while preserving the identifier.
10. Run focused backend, frontend and clean-base regression suites.
11. Blindly adjudicate all 100 development games using the frozen rubric.
12. Convert only repeated proved gaps into shared deterministic logic, with positive, hard-negative and adversarial tests; rerun all 100 after every accepted group.
13. Freeze implementation, templates, rankings and dispositions.
14. Open and score the 42-game holdout exactly once.
15. Prepare—not apply—the one-account historical dry-run and authenticated manual journey handoff.

## Contracts to define before rendering

The whole-game response must be typed before UI work and must include:

- schema and composer version;
- source plan ID, formula, fingerprint and V5 version;
- phase source and stored phase coverage;
- central-story state and supporting event references;
- opening, middlegame and endgame chapter state;
- ordered featured event references, never copied detector output;
- one surviving instruction with its source event;
- unavailable/unsupported reasons;
- deterministic presentation fingerprint.

The public projection must exclude internal detector diagnostics, answer keys, control assignments, raw user/game identifiers and hidden holdout information.

## Required tests

### Unit and contract

- deterministic equality for identical inputs;
- no selected events produces an honest no-lesson story;
- every reached phase has exactly one allowed state;
- unreached endgame cannot contain a lesson;
- stored phase is consumed without calling a phase detector;
- opening identity never becomes “perfect,” “understood,” “mistake” or causal-loss language without authorized evidence;
- opening detector Shadow output cannot alter story or questions;
- Disabled rule-of-square evidence cannot appear;
- exact-endgame result change can appear only with current provenance;
- actor and color remain correct for opponent opportunities;
- demonstrated knowledge needs positive authorized evidence;
- at most three featured moments;
- order follows game chronology after ranking;
- surviving instruction references one selected event;
- unsupported cause abstains;
- question, correct answer and explanation share one reason bundle;
- answer remains hidden before commitment;
- replay is legal and settles the claimed payoff;
- the collapsed copy obeys the 2-sentence/32-word and 18-word cue limits without truth truncation;
- public response contains no internal answer key, detector diagnostics or identity fields.

### Packet and independent-review

- eligibility reproduces the frozen corpus SHA at the fixed cutoff;
- development SHA and holdout SHA reproduce exactly;
- development contains 100 games and holdout 42;
- all rating quotas pass;
- development player cap is three;
- holdout player cap is one;
- overlap is zero;
- anonymizer rejects email, username, user ID, game ID, PGN headers and credentials;
- holdout reader refuses access before a signed implementation-freeze marker;
- adjudication requires one row per game and one disposition per proposed lesson;
- repeated source-game exception tables fail validation.

### API and persistence

- rollout off preserves the deployed response byte-for-byte where practical;
- unauthorized and non-enrolled accounts receive baseline behavior;
- enrolled account receives only current, authorized composition;
- stale plan, V5, event or detector versions fail closed;
- page reads launch no Stockfish, Maia, Otter, LLM or tablebase network process;
- historical dry-run has no writes;
- apply is idempotent, resumable and bounded to the named account and ten games;
- reconciliation reports current, new, partial, unsupported, stale, invalid and failed separately.

### Frontend

- literal story and all four phase states render;
- long copy moves to the board interaction instead of overflowing the card;
- try, hint, reveal, played replay, alternative replay and reset operate;
- right/wrong feedback is explicit;
- keyboard and touch interaction preserve board orientation;
- old replay URL redirects to canonical review with the same game ID;
- no second data fetch or legacy coaching narrative remains active after redirect;
- analytics record impression, phase open, first answer, hint, replay, retry and completion once.

### End-to-end

- one existing stored game completes library recommendation → reason → whole-game story → interactive moment → evidence write;
- one newly analysed game follows the same path without a separate full-game analysis;
- one game with no endgame says so;
- one exact ending uses stored exact truth;
- one opening-only game does not invent middlegame or endgame lessons;
- one opponent opportunity keeps actor and board orientation correct;
- one out-of-cohort account remains unchanged;
- a page reload reproduces the same presentation fingerprint.

## Data and privacy gate

The production reads are authorized only for anonymized stored evidence. The export must contain:

- opaque game and player signatures;
- rating band, color and coarse time-control class;
- legal position/move history;
- stored engine evaluation and continuation required for adjudication;
- current versioned exact evidence required to verify a claim.

It must not contain:

- email;
- internal or external user ID;
- internal or external game ID;
- player or opponent username;
- credentials;
- raw PGN headers;
- free-form feedback;
- unrelated profile or behavioral data.

The export is read-only. It performs no engine run, model call or production write.

## Stop conditions

Implementation stops and reports rather than weakening a guard if:

- any frozen signature cannot be reproduced;
- anonymization validation fails;
- a clean source contract cannot represent the story without duplicated truth;
- a visible claim depends on Shadow, Disabled or unknown authorization;
- replay cannot settle the causal claim from stored evidence;
- development has a critical false claim;
- a recurring Codex finding cannot be expressed as general deterministic logic;
- the holdout is opened before implementation freeze;
- a page read starts an engine, model or external truth request;
- the baseline path changes while rollout is off.

Proceeding to implementation in the isolated clean worktree.
