# Detector semantic-gold adjudication protocol

Status: LOCKED 2026-08-27

## Purpose

This protocol decides whether a detector's exact player-facing claim is true.
It does not judge whether the move was good in general. A high centipawn loss,
a Lichess theme, or agreement with another implementation can nominate a case,
but cannot label it.

## Unit of review

One case is one detector claim at one ply:

- `case_id` and immutable `detector_quality_id`;
- source kind, source ID, source snapshot/month, and checksum when available;
- game/player split key stored as a one-way research identifier;
- FEN before, played move, FEN after, side to move;
- exact structured claim and the exact player-facing surface it would unlock;
- engine best move and PV as supporting evidence, never the semantic label;
- opportunity label: positive, negative/non-opportunity, or adversarial;
- reviewer verdict: true, false, uncertain, or invalid_case;
- false-claim severity: critical, material, pedagogical, or wording-only;
- reviewer rationale naming pieces, squares and the refuting/confirming line.

## Review sequence

1. Confirm the FEN, side to move and move legality.
2. State the detector's exact claim without reading its implementation.
3. Walk origin square, destination square, changed lines, attackers, defenders,
   legal replies, zwischenzugs and forced continuations.
4. Consult stored/tablebase/Stockfish evidence only after the board claim is
   stated, to test consequence and best-line assertions.
5. Mark `true` only when the semantic claim—not merely related geometry—is
   demonstrated.
6. Mark `false` when one legal counterexample refutes the claim.
7. Mark `uncertain` when the evidence cannot distinguish the claim. Uncertain
   cases never count as correct and cannot promote a detector.

## Independence

- The case selector may use the detector; the adjudicator may not use detector
  output beyond the claim being tested.
- Geometry verification and semantic adjudication are separate decisions.
- An LLM may organize evidence but is never the final truth judge.
- Promotion packets require a blinded chess reviewer independent of the
  detector implementation. Critical/adversarial disagreements require a
  second reviewer; unresolved cases are `uncertain`.
- Related positions from the same game, player, puzzle, or generated family
  stay in one split. Tuning and held-out validation cannot share that unit.

## Sampling

- Fires are stratified by rating band, phase, result direction, source, and
  detector confidence where available.
- Negative cases are selected from positions where the detector's prerequisites
  nearly hold, not arbitrary quiet moves.
- Recall opportunities come from independent theme/tablebase/manual candidate
  mining, then receive this same adjudication before the detector is run.
- External puzzles retain puzzle ID and the theme-bearing solution ply. The
  first solution move is not assumed to carry every puzzle theme.

## Promotion calculation

- Precision denominator: true + false + uncertain detector fires.
- Recall denominator: independently adjudicated positive opportunities.
- Invalid cases are reported but excluded from both denominators.
- Wilson lower bounds and sample floors come from
  `docs/detector_quality_threshold_lock_2026_08_27.md`.
- Any critical false claim fails the adversarial gate regardless of aggregate
  precision.

## Initial authorization consequences

- `piece_safety/simple_hang` may be Plan-grade only while its documented
  260-case semantic packet and preserved opportunity set remain reproducible.
- D_live's implementation agreement is regression evidence, not independent
  semantic promotion evidence.
- Caption shape geometry is not causal attribution evidence.
- King safety, trapped piece, rule of square, zero-fire lesson detectors, and
  broad concept attribution remain Shadow until new packets clear the gate.
