# Hanging-Piece Detector - Data Lock

**Date:** 2026-08-28
**Decision:** Make Chess Brain a causal adapter to the canonical board-mutating
legal-exchange truth and exclude pawn-only losses.

## Single-source audit

The central player-facing chess-semantics path is
`services.caption_facts.legal_exchange_gain`. It pushes legal captures on a
real board and therefore sees pins, checks, king captures, promotions and
newly opened x-rays. `coach_blunder_guard` has a related real-time opponent
soundness floor, but it serves a different hot-path policy and is not the
source for player-facing labels.

Chess Brain currently owns a third, weaker recognizer: attacked and undefended
piece geometry after any move. It ignores exchange value, move causality,
engine consequence and the best-move counterfactual. That recognizer will be
removed; Chess Brain will consume a structured view derived from
`legal_exchange_gain`.

## Production bake-off

A read-only random sample of 200 production analyses contained 6,316 eligible
user-move positions.

| Contract | Fires/candidates |
|---|---:|
| Current attacked-and-undefended geometry | 1,476 |
| Exact post-move legal loss, floor 100cp | 1,712 |
| Exact post-move legal loss, floor 150cp | 735 |
| Exact post-move legal loss, floor 300cp | 659 |
| Played-vs-best strict issue reduction, floor 100cp | 575 |
| Strict reduction, floor 150cp | 327 |
| Strict reduction, floor 300cp | 310 |
| Strict reduction + cp_loss >=100, floor 100cp | 301 |
| Strict reduction + cp_loss >=100, floor 150cp | 197 |
| Strict reduction + cp_loss >=100, floor 300cp | 187 |

The material distribution has a clear cliff between 100 and 150cp. A 100cp
floor includes pawn-only losses; 150cp removes them. Raising the floor from
150 to 300 removes only 10 more candidates (5.1%) while discarding legitimate
200cp outcomes such as a knight or bishop captured by a pawn.

A separate 120-analysis residual scan found 116 removed issues at the selected
contract: 61 involved the moved piece and 55 involved another piece left
exposed. Both are real coaching situations, so the adapter must preserve both
subtypes rather than only checking the destination square.

## Locked contract

1. `legal_exchange_gain` remains the canonical exchange truth.
2. A canonical helper derives all non-king pieces the side to move can win for
   at least a caller-supplied material floor.
3. Chess Brain does not count attackers or defenders itself.
4. The played move and engine best move must be legal and different.
5. cp_loss must reach the shared 100cp causal-mistake floor.
6. The hanging material gain must be at least 150cp, excluding pawn-only loss.
7. The best-move hanging-issue set must be a strict subset of the played-move
   issue set.
8. The result reports only issues removed by the best move, including the
   legal winning reply.

## Rejected candidates

- **Current geometry:** rejects sound defended exchanges and blames unrelated
  moves for pre-existing states.
- **Post-move exact truth only:** proves capturability but not move attribution.
- **100cp material floor:** produces pawn-only alerts that are too noisy for a
  hanging-piece coaching label.
- **300cp material floor:** loses meaningful minor-piece-for-pawn cases for
  little candidate reduction.
- **Moved piece only:** drops 47% of measured residual issues where the move
  left another own piece exposed.

## Authorization

`brain:hanging_piece_detector` remains Shadow. Production candidates are not
blinded semantic gold, and this repair does not authorize player-facing use.

No production data was written.
