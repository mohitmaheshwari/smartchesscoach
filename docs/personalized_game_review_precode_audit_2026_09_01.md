# Personalized Game Review Coach — Pre-Code Audit

**Date:** 2026-09-01  
**Verdict:** PASS for Phase 1 contracts

## Six audit gates

| Gate | Result | Evidence |
|---|---|---|
| 1. Literal UI mockup | **Pass** | `docs/personalized_game_review_coach_scope.md` `2 contains literal opening, chapter, reflection, reveal and next-action copy. |
| 2. Pattern/geometry leads | **Pass** | The signed UI names the pinned defender and open diagonal; SAN is local board evidence rather than the learning headline. |
| 3. Numeric choices are data-derived | **Pass for Phase 1 contracts; later behavior blocked** | `docs/personalized_game_review_phase0_data_lock_2026_09_01.md` measures structural opportunity and refuses to invent moment caps, planner weights, question winner or mastery thresholds. Phase 1 contracts contain none of those numbers. |
| 4. Success changes behavior | **Pass as the product definition** | The primary outcome is reduced recurrence on comparable later real-game opportunities, not page views or aggregate clicks. |
| 5. Deferred items remain deferred | **Pass** | Maia/Otter runtime, broad UI redesign, bulk regeneration, detector promotion, free-form chat and invented mastery remain outside Phase 1. |
| 6. Mohit signed off | **Pass** | Mohit explicitly approved the six architecture recommendations and instructed the work to proceed. |

## Additional signed pre-code requirements

| Requirement | Result | Evidence / gap |
|---|---|---|
| Source-of-truth inventory | **Pass** | Phase 0 locks move, reflection, opening, trap, endgame and learning ownership plus migration direction. |
| Detector authorization and coverage | **Pass** | The versioned aggregate snapshot records one Plan, six Shadow and five Disabled IDs plus `simple_hang` reach. |
| Endgame canonical owner | **Pass** | The theory tree wins on lesson coverage and legal checked positions. |
| Numeric architecture choices | **Pass by omission from Phase 1** | Contracts add no numeric selection or mastery behavior. Later phases remain blocked on their named experiments. |
| Current caption truth corpus | **Partial** | Stage 4 provides 429 unique verified positions and a 30-game real-user shadow, but it validates move explanations rather than complete review stories. |
| Representative full-game corpus | **Deferred gate, not a Phase 1 blocker** | Mohit moved validation to the final rollout stage. The packet must exist before the Phase 3 planner may leave shadow. |
| Independent coach annotations | **Deferred gate, explicitly approved** | Mohit explicitly moved Mohit/two-coach validation to the final internal rollout gate before any visible release. |
| Current output snapshots for consolidation parity | **Deferred gate, not a Phase 1 blocker** | Phase 1 changes no route or renderer. Full API/UI parity fixtures must exist before Phase 2 changes a live adapter. |

## Why the existing Stage 4 corpus is not enough

`human_chess_stage4_gold_corpus_2026-08-31.json` is valuable position-level truth. It can validate a caption’s board explanation. It does not label:

- which moments belong in one game story;
- what the opponent was trying;
- whether a reflection question is worth interrupting the player;
- which lesson should be selected from the whole game;
- whether a causal bridge between two moments is true.

Treating it as a full-review gold set would silently turn a move-caption benchmark into a planner benchmark.

## Recorded gate movement

Mohit explicitly instructed on 2026-09-01: move coach validation to the final rollout gate and start Phase 1.

The gates are therefore staged:

1. **Phase 1 now:** contracts, deterministic serializers, authorization guards and default-off parity only; no route, persistence or UI change.
2. **Before Phase 2 live adapters:** snapshot current Game Review, Reflect and Play with Coach response fixtures.
3. **Before Phase 3 planner leaves shadow:** create the anonymized, representative full-game packet.
4. **Final internal rollout gate:** Mohit and at least two coaches independently label and review the packet; adjudicate chess-truth disagreements against stored engine/board evidence.

```text
PRE-CODE AUDIT: PASS
Feature: Personalized Game Review Coach
Spec: docs/personalized_game_review_coach_spec.md
Proceeding to Phase 1 contracts only.
```
