# Trapped-Piece Detector - Implementation Evidence

**Date:** 2026-08-27
**Decision:** Repaired and kept **Disabled**.

## Implemented

- services.board_concepts.trapped_pieces remains the canonical board fact.
- Escape safety now follows the named piece's destination instead of global
  material hanging elsewhere on the board.
- A capture made while escaping receives material credit, so a profitable
  trade is not called a trapped loss.
- services.board_concepts.newly_trapped_pieces owns the before/after state
  change used by move attribution.
- services.concept_attribution consumes that fact instead of rebuilding it.
- Chess Brain consumes the same fact and fires only when:
  - the played move creates a fresh trapped state;
  - the engine best move avoids every fresh trapped state;
  - cp_loss is available and at least the locked 100cp floor.
- The detector registration now requires an engine best move.
- The main Chess Brain orchestrator supplies cp_loss in detector context.

## Verification

The focused truth and quality suite passed **21 tests**. New adversarial tests
cover:

- a classic genuinely trapped knight;
- a profitable capture-and-trade escape;
- an unrelated hanging piece that must not contaminate mobility;
- played-versus-best move causality;
- the engine consequence gate;
- missing consequence data;
- checkmate not being relabeled as a trapped queen;
- required best-move registration; and
- a source guard proving Chess Brain is an adapter.

A broader Chess Brain run produced **47 passes, 3 skips and 2 unrelated
failures**. Both failures are stale registry-count assertions expecting five
strategic detectors although the current registry contains twenty. They do not
exercise trapped-piece behavior and were not modified in this repair.

## Production evidence

The measurements and rejected formulas are recorded in
docs/trapped_piece_detector_data_lock_2026_08_27.md.

Before-state sampling showed 985 fires in 5,795 positions, including 624 at
<=50cp and 895 immediately capturable pieces. The selected canonical formula,
best-move counterfactual and consequence gate left seven candidates in the
300-analysis / 10,044-position measurement. Those seven are candidate audit
items, not seven verified positives.

## Authorization

brain:trapped_piece_detector remains **Disabled**. It may not write captions,
plans, mastery, prompts or player state. Reconsideration requires:

1. blinded semantic review of the residual candidates and hard negatives;
2. an independently constructed opportunity denominator; and
3. the review counts and accuracy floors already locked by the detector quality
   gate.

No deployment, backfill, database write or production mutation was performed.
