# King-Safety Detector - Data Lock

**Date:** 2026-08-28
**Decision:** Consolidate Chess Brain onto canonical board-state facts and grade
only a played-versus-best reduction in specific king-safety issues.

## Before state

The quality-gate baseline had already found 145 concerning fires among 590
king-safety verifier cases. A fresh read-only production sample of 300 analyses
contained 9,443 user-move positions. The current Chess Brain detector fired
3,339 times (11.13 per game):

- 2,311 fires had cp_loss <= 50.
- 382 fires had cp_loss 51-100.
- 646 fires had cp_loss > 100.

The source explains the volume. It labels any post-move position with broad
pawn-cover or king-zone geometry, without proving the user's move caused the
issue or that the engine best move addressed it. It also infers castling from
the king's file alone.

## Attribution bake-off

Three contracts were measured:

1. **Unsafe after any move (current):** 3,339 fires / 300 games. Rejected
   because existing position pressure is attributed to unrelated moves.
2. **State entry or numeric worsening:** 326 fires / 300 games, including 209
   at <=50cp. Rejected because geometry worsening can be harmless or compensated.
3. **Played versus engine best:** played leaves a threshold king-safety issue
   and best has a lower value for that issue. This produced 305 fires / 300
   games; adding the existing 100cp causal-error floor left 120.

The third contract still included pure king endgames. A 400-analysis phase
bake-off produced 133 candidates before phase gating:

- 60 remained when canonical endgames were excluded.
- 68 remained when an opponent queen was required.
- 56 remained when both gates were required.

Queen presence was too strict for a verified multi-piece king-zone attack, but
useful for pawn-shelter claims. The selected subtype policy is:

- **pawn_shield:** at least two missing shelter pawns and opponent queen present;
- **king_zone_attack:** at least three unique enemy pieces attack the king zone.

Both subtypes exclude positions where GamePhaseCalculator marks is_endgame.

## Cross-issue counterfactual

Comparing only one metric can call best "safer" when it merely swaps a weak
shield for an attacked king square. The final counterfactual therefore requires
the effective best-move issue set to be a strict subset of the played-move issue
set.

On a fresh 500-analysis production sample:

- the broad phase/subtype contract produced 113 candidates;
- strict issue-set reduction produced 90 candidates (0.18 per game);
- 65 were pawn-shield candidates;
- 25 were king-zone-attack candidates;
- all were opening through late-middlegame under the canonical phase model.

These are audit candidates, not verified semantic positives.

## Locked contract

1. services.board_state_describer owns pawn-shelter and king-zone geometry.
2. Chess Brain does not recalculate those facts.
3. The detector requires a legal played move and legal engine best move.
4. The detector requires cp_loss >= the shared 100cp causal-error floor.
5. Canonical endgames are excluded via GamePhaseCalculator.is_endgame.
6. Pawn-shield claims require an opponent queen.
7. King-zone claims require at least three unique enemy attackers.
8. The best-move effective issue set must be a strict subset of the played
   issue set.
9. The detector reports only issue IDs removed by the best move.

The missing-pawn threshold (2), attacker threshold (3), and phase cutoff are
inherited from existing canonical modules. No new numeric geometry threshold
was selected.

## Authorization

brain:king_safety_detector remains Disabled. The repair cannot promote it
without blinded semantic review and an independent opportunity denominator.

No production data was written.
