# Community Game Coherent Walkthrough — Data Lock

**Status:** LOCKED BEFORE IMPLEMENTATION
**Date:** 2026-09-15
**Approved scope:** `docs/community_game_coherent_walkthrough_scope.md`

## 1. Evidence and execution boundary

The decision population is the same 60-game public Lichess sample used by the independently reviewed v2 packet. The measurement reproduced the existing 41 eligible games and 110 chapters before comparing any extension.

- Source release: `lichess_db_standard_rated_2026-08`, CC0-1.0.
- Release SHA-256: `6bf6fa8a5dee7bb81d1874ac312160060daf12f18a29dc2740a3bf6f5e5e6248`.
- Exact 8 MiB prefix SHA-256: `d8e9c900da9dbcd275a84e4fa08097fcca2c164ba183c04f2659929c10c8ab38`.
- Independently reviewed v2 packet SHA-256: `1d92050c950d3cfa2a17eae7b07208f2156096596b582f00254bef7b68def974`.
- Measurement fingerprint: `d841f9c1c2b1848e970b8d451a01dc84c8fdfb5b2a4a803a00444f072b5a8a8a`.
- Frozen measurement: `backend/data/corpus_snapshots/community_game_coherent_walkthrough_measurement_2026-09-15.json`.
- Frozen behavior baseline: `backend/data/corpus_snapshots/community_game_coherent_walkthrough_behavior_baseline_2026-09-15.json`.

The measurement made no production database access, engine run, tablebase probe, model call or player-visible change. Raw identity-bearing PGN was not retained. The behavior baseline used aggregate production reads only and retains no identity or game key.

## 2. What the population says

The 60 games contain 41 currently eligible studies and 110 current chapters. There are 27 checkmates, but the current selected studies include no terminal chapter. Candidate supply has a median of three moments and is not monotonic with game length: short games have a median of two, upper-middle-length games six, and the longest group three. Game length is therefore not a valid chapter-budget rule.

The role-first formula materially outperformed largest-loss ordering at the same three-chapter ceiling:

| Formula | Eligible | ≥2 principles | ≥2 phases | Reaches finish | Repeated chapters | Mate finish covered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Current ranking, cap 3 | 41 | 29 | 17 | 22 | 36 | 0 / 16 |
| Combined severity, cap 3 | 47 | 38 | 23 | 29 | 34 | 8 / 22 |
| Combined role-first, cap 3 | 47 | 40 | 33 | 37 | 16 | 22 / 22 |

Raising role-first from three to four chapters adds no eligible game, distinct-principle game, distinct-phase game or finish-reaching game. It raises repeated-principle chapters from 16 to 31. Five chapters adds no coverage and raises repetition to 44.

## 3. Locked story formula

The selected formula is `coherent_role_then_quality.v1`:

1. Admit only Caption-authorized, legally replayable facts.
2. Coalesce proof families at the same ply into one moment. A fork, alignment or free-piece proof enriches that moment; it does not create a duplicate chapter.
3. Reserve an exact terminal finish when one is admitted and relevant.
4. Select the climax from the existing verified Review quality ordering. Raw centipawn loss is only the final deterministic tie-breaker.
5. Select the earliest earlier moment that adds a distinct setup role, phase or primary principle.
6. Select at most one later consequence or finish that adds a distinct role, phase or primary principle.
7. Render the selected moments chronologically.
8. Stop at three. Stop at two when no third moment adds new teaching value. Never fill a visual slot.

A visible community walkthrough requires at least two chapters and at least two distinct authorized primary principles or proof families. A repeated occurrence of the same principle may appear only as concise reinforcement inside an existing chapter, never as a separate teaching chapter.

## 4. Family decisions

- `review:verified_single_game_cause` remains the general Caption-authorized fact source.
- `tactic:fork_with_stored_payoff`, `tactic:aligned_with_stored_payoff` and `tactic:free_piece_exact` are Caption-authorized specificity enrichments. Their measured unique contribution is small; their principal value is making an already-selected moment more teachable.
- `tactic:forced_mate_exact` remains available but did not fire in this population. It is not widened.
- `review:exact_endgame_result_change` remains Caption-authorized only when pinned tablebase evidence exists. No eligible position appeared here and none is inferred.
- Exact opening knowledge remains Shadow. No opening name, line claim or opening judgment reaches the walkthrough.
- Named endgame techniques remain outside this release unless separately promoted.
- A legal terminal checkmate is not silently treated as `tactic:forced_mate_exact`. Player-visible terminal language requires a new exact central Review fact and a separate Caption promotion packet. Until that promotion clears, terminal checkmates remain measured board facts and are excluded from visible chapters.

## 5. Locked quality rubric

The v3 packet is graded on separate axes; no aggregate score can hide a weak one:

- zero incorrect or overclaimed chapters;
- zero critical false claims;
- 100% legal, position-matched demonstrations;
- `correct_and_teachable` rate strictly above 71.8%;
- 100% pattern-, geometry- or idea-led headlines; no headline begins with SAN;
- zero studies that repeat a primary principle as separate chapters;
- coherent-story rate strictly above 9.8% (v2: 4/41), with numerator and denominator reported;
- assignment-worthy rate strictly above 48.8% (v2: 20/41), with numerator and denominator reported;
- after terminal-checkmate Caption promotion, every admitted checkmate study includes its exact finish; before promotion, no terminal claim is displayed.

## 6. Interaction and learning lock

`GuidedReviewMoment.jsx` owns prediction choices, hint and reveal. It contains no chess knowledge and cannot invent fallback copy. `GameDecryptionV5.jsx` owns watch-line playback and learner replay on its existing board. A chapter is interactive only when the admitted server projection contains a non-empty validated question, at least two position-relevant choices, a bounded hint, a legal demonstration and a replay target.

Completion records assisted learning only. It never changes mastery or transfer. A later unassisted game remains the only evidence that the lesson held.

## 7. Behavior and cohort lock

The production baseline contains two personal-review prescriptions, one start, zero completions and zero server-side review events. That population cannot support an honest conversion threshold. No percentage is invented.

The first three admin accounts are an isolated operability cohort, not a product-effect experiment. The implementation must record server-side start, predict, hint, reveal, watch, replay, completion and linked-next-action events. An ordinary-user expansion threshold is frozen only after those events exist; until then ordinary-user expansion is blocked.

Only one of the three intended admin accounts currently has both the canonical personalized-review enrollment and Phase 8 baseline. Before visibility, operations must capture honest pre-enrollment baselines and provision the remaining two through the existing access path. Code must not add a role bypass or a second allowlist.

## 8. Rejected choices

- Four or five chapters: no coverage gain and materially more repetition.
- Chapter count by game length: contradicted by candidate supply.
- Largest engine swing first: produces weaker phase and finish coherence.
- Generic opening or endgame labels: unauthorized.
- Treating terminal board state as an authorized caption: bypasses the evidence gate.
- A client-only analytics baseline: not an auditable server truth.
- An admin-role shortcut: duplicates and weakens canonical access control.
