# Home Teaching Case V2 — Reason Architecture Data Lock

**Status:** LOCKED for implementation on the Mohit-only Home path
**Date:** 2026-09-02
**Measurement:** read-only replay of stored schema-18 positions; no Mongo writes and no Stockfish rerun.

## DECISION LOCKED: complete reason proof

**VALUE:** A submitted knight, bishop, rook or queen move is explainable only when the canonical destination-safety grader's two exchange proofs agree. Its destination explanation is exactly one of:

- `destination_unattacked`: the opponent has no legal capture of the moved piece on its destination;
- `safe_by_recapture`: an opponent capture is legal, but a deterministic legal capture–recapture line proves the destination does not lose the piece;
- `destination_loses_material`: both proofs agree that the opponent wins material on the destination;
- `unmeasured`: the move, position or proof family is unsupported, or the proofs disagree.

Situation, multi-target, counterattack and recapture components are added only when their own board predicates are true. Missing optional components are not treated as failed understanding.

**EVIDENCE:** All 5,760 eligible legal moves produced agreement between the two existing exchange proofs. Of 3,288 supported safe moves, 2,883 had no legal destination capture and 405 had a legal one-recapture explanation. There was no third unexplained safe category.

**REJECTED:** Requiring every move to have threat + counterattack + recapture. Only 663 safe moves had an incoming threat, 106 a counterattack and 405 a recapture line; making them mandatory would manufacture claims for most positions.

## DECISION LOCKED: multiple reasons and grading

**VALUE:** Store a list of independently proven reason components. Ask and grade each supported component separately. A move has no single `_expected_reason`. Controlled transfer requires the destination-safety component plus every component actually asked, without substantive help; optional components that were not supported are absent rather than wrong.

**EVIDENCE:** The replay produced ten distinct supported component combinations. The approved `R3d2` case legitimately contains threat, multi-target, counterattack and recapture facts, while 2,339 safe alternatives contain only an unattacked destination. One literal answer cannot represent both honestly.

**REJECTED:** Exact string match; accepting any one true statement as full understanding; requiring the same questions on every board.

## DECISION LOCKED: supported alternative moves

**VALUE:** Grade the exact legal move submitted by the player. Any eligible piece move with proof agreement receives its own destination reason bundle. The existing independent runtime soundness check remains separate. Pawn/king moves, proof disagreement and unsupported causal purposes return `unmeasured`, never “wrong reason.”

**EVIDENCE:** The 215 positions contained 3,288 supported safe legal alternatives and 2,472 failing legal moves. Every stored original fire rechecked as `fail` with proof agreement (215/215). A stored-best-move-only policy would reject real safe choices at scale.

**REJECTED:** Stored best move only; treating concept-safe as overall engine-sound; forcing unsupported moves into the stored answer's explanation.

## DECISION LOCKED: questions and distractors

**VALUE:** Each factual option is generated from the typed bundle. One accepted option states the proven relationship. Factual distractors must be false by a deterministic board predicate, and the bundle always includes an honest “I did not see/calculate this” response. If exactly one factual answer cannot be proven, that component is not asked.

The approved rook example is worded as “Which of your rooks did the queen on c2 attack?” rather than the exclusive “What did the queen threaten?” because the queen also attacks pawns on the board. This preserves the intended lesson while removing ambiguity found during gold verification.

**REJECTED:** Generic lesson copy; invented mate/plan claims; a distractor that is merely less important but still true; client-authored options.

## DECISION LOCKED: transfer pair and sparse evidence

**VALUE:** Reuse the deployed V1 pair rule: same quality ID/version, different game, normalized FEN and moved-piece type. A position with no supported eligible safe move fails closed. No broad-category fallback is introduced.

**EVIDENCE:** The prior lock found 13,556 strict pairs for Mohit's validation account. The new replay found supported safe eligible alternatives in 213 of 215 distinct promoted positions; two positions correctly fail closed.

## DECISION LOCKED: rollout gates

**VALUE:** No new percentage threshold is invented for V2. Player-facing V1 requires binary proof completeness, Plan authorization, zero pre-answer leakage and passing gold cases. Mohit-only enrollment remains. Wider-rollout completion/comprehension thresholds stay unlocked until real V2 sessions exist.

## Canonical schema

`ReasonBundle` is a derived view, not a new chess database:

```text
schema_version
semantic_version
position_fingerprint
move_uci / move_san
target_result
soundness                  # separate existing guard
components[]
  component_id
  kind                     # incoming_threat (including typed multi-target facts) |
                           # destination_safety | counterattack |
                           # one_recapture_calculation
  prompt
  public_choices[]         # stable id + player text
  accepted_choice_ids[]    # private
  facts                    # private typed squares/pieces/line
proof
  quality_id
  detector_version
  verifier_version
  authority
  fingerprint
```

The public pre-answer projection contains no bundle. After the move, it contains only the current component's prompt and public choices. Accepted IDs, facts, proof internals and later questions remain server-private.

## Measurement artifacts

- `backend/scripts/measure_home_teaching_reason_coverage.py`
- `backend/data/corpus_snapshots/home_teaching_reason_coverage_2026-09-02.json`
- `backend/data/detector_gold/home_teaching_case_v2_v1.json`
- Production aggregate fingerprint: `c1a81fc7e1af90697278211f820e4b383e4cd0cdca770dd97efa93d986db55b3`
