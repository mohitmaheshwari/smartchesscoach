# Trapped-Piece Detector - Data Lock

**Date:** 2026-08-27
**Decision:** Reuse canonical board-concept truth, correct its escape-loss
calculation, and require an engine-best counterfactual plus the existing 100cp
tactical-error floor.

## Decision being locked

The Chess Brain detector must identify an avoidable move that newly traps one
of the mover's own pieces. It must not relabel captures, sound sacrifices,
checks, mate, or ordinary attacked squares as trapped pieces.

## Before-state measurement

A read-only sample of 200 production analyses contained 5,795 user-move
positions. The old detector fired 985 times (4.925 fires per game):

- 624 fires had cp_loss <= 50.
- 109 fires had cp_loss 51-100.
- 252 fires had cp_loss > 100.
- 895 of 985 pieces could be captured immediately.
- 482 fires were captures and 157 gave check.

The source defect explains this distribution: after the user move was pushed,
the detector counted legal moves from the user's piece while it was the
opponent's turn. That count was always zero.

## Formula bake-off

The same move-level contract was tested with three escape-loss formulas on a
200-analysis production sample:

- **A - global material hung after an escape:** 51 fires; 30 at <=50cp.
  Rejected because another hanging piece can make every escape look unsafe.
- **B - opponent SEE on the escaped piece's destination:** 11 fires; 6 at
  <=50cp. Better attribution, but treats a profitable capture-and-trade as a
  trapped loss.
- **C - destination SEE minus material captured by the escape:** 9 fires; 6 at
  <=50cp. Selected as the canonical piece-loss formula because it follows the
  named piece and accounts for trading it rather than merely losing it.

Formula C was then combined with a required counterfactual: the played move
creates a new trapped state and Stockfish's best move does not. On 300
production analyses / 10,044 positions:

- 11 candidate fires remained.
- 4 had cp_loss 0-23.
- 0 had cp_loss 24-153.
- 7 had cp_loss >=154.

The low-loss cases were compensated or equivalent choices, so causal mistake
wording would be unsafe.

## Locked contract

1. services.board_concepts.trapped_pieces owns trapped-piece board truth.
2. Escape loss follows only the escaping piece's destination.
3. Material captured by the escape is credited before deciding it still loses
   at least TRAPPED_FLOOR_CP.
4. Move-level truth is a fresh trapped state, compared with the position before
   the move.
5. Chess Brain fires only when the engine best move avoids that fresh state.
6. Chess Brain requires cp_loss >= 100.

The 50cp, 100cp, and 150cp candidates retained the same seven fires in the
measured sample because the observed distribution had a 23-to-154cp gap.
The existing 100cp tactical-error floor was reused instead of creating a new
severity convention. This is a flat-range decision, not a claim that 100 is a
natural trapped-piece boundary.

## Authorization

This repair does not promote brain:trapped_piece_detector. It remains
Disabled until an independently reviewed semantic packet establishes
attribution precision and a stable opportunity/recall denominator.

No production data was written.
