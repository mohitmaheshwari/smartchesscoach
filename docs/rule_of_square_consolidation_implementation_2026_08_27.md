# Rule of the Square Consolidation - Implementation Evidence

**Date:** 2026-08-27
**Decision:** Implemented, verified, and kept **Disabled**.

## What changed

- `services/concept_detectors/rule_of_the_square.py` is the only source of
  rule-of-square chess truth.
- The canonical fact uses a finite legal push-versus-defending-king search. It
  handles pawn direction, a starting double push, blockers, legal king moves,
  attacking-king protection, and capture immediately after promotion.
- `services/endgame_detectors/rule_of_square_detector.py` is now a compatibility
  adapter with no independent board geometry.
- `caption_facts.py` now grades the played and best continuations through the
  canonical fact. Its former square geometry helpers were removed.
- The detector abstains on mutual pawn races and positions with extra pieces.

## Locked validation

The adversarial packet is stored in
`backend/data/detector_gold/rule_of_square_v1.json`. It covers both pawn
directions, immediate capture, a starting double push, a full-WDL claim-boundary
case, and the two principal abstention classes.

The scoped detector tranche passed **52 tests**. This included canonical fact,
consumer wiring, authorization-gate, exchange-truth, aligned-attribution,
and royal-fork regression tests.

## Production opportunity scan

A read-only sample of **200 production analyses** contained **6,416 move
positions**. Only **5** positions met the exact V1 K+P versus K eligibility
contract. All five were user-move positions from the same game
(`00954854-b13a-4ee2-8a98-e3ccd78ad39e`, moves 48-52).

This is one independent game unit, not five independent observations. It cannot
support a semantic precision or false-negative claim.

## Authorization decision

The following remain **Disabled**:

- `concept:endgame_rule_of_square`
- `legacy_endgame:rule_of_square`
- `principle:END_RULE_OF_SQUARE`

They may be reconsidered only after the review-count requirements in
`docs/detector_quality_threshold_lock_2026_08_27.md` are met across independent
games and source units. Consolidation removed contradictory implementations; it
did not manufacture the evidence needed for player-facing authorization.

No deployment, database write, backfill, or production mutation was performed.
