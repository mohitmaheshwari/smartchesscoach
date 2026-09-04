# Hidden Opportunities Phase 3A.2 — Board Transformation Data Lock

**Status:** LOCKED FOR SHADOW IMPLEMENTATION  
**Date:** 2026-09-03  
**Family:** `board_transformations_with_payoff`

## Decision

A board-transformation proof must preserve both complete legal stored
branches, every move between setup and payoff, persistent physical-piece
identity, a positive played-versus-better material edge, and a positive
better-line gain after an exact legal exchange beyond the stored horizon.

The three generic mechanisms are:

- an intermediate exchange gives the threatened rook time to leave its
  capture line, after which the exact attacker is captured;
- a checking rook offer has exactly one legal reply—the king captures it—so
  the same queen can check and capture the interposing queen;
- a minor-piece capture and pawn recapture open the exact rook route; that
  same rook enters with check and later captures the exact piece.

These are exact line facts, not named motifs. The proof does not infer a
decoy, clearance, interference, attraction, zwischenzug, or sacrifice label.
Those names need their own canonical reviewed proof.

## Locked safeguards

- A `transformation_steps` tuple retains every stored move between setup and
  payoff. No shallow “last move wins a piece” projection is allowed.
- “Forced” is used only when the board has exactly one legal reply.
- The rook-opening case requires the pawn recapture to make the exact next
  rook capture legal; piece type or square resemblance is insufficient.
- The payoff target must be absent from the initiator's played branch.
- The canonical legal-exchange resolver pushes all legal captures on the
  payoff square and includes king legality, checks, pins, promotions and
  opened x-rays.
- Earlier target/line, forcing-tempo, and endgame owners run first. The final
  family cannot emit a duplicate proof.

No new cp-loss, depth, material, or move-count threshold was introduced.
The locked stored horizon supplies five plies in the three architecture
examples; runtime rules contain no position IDs.

## Promotion boundary

The architecture packet has only three fires. The independent population
census over 567 already-versioned cases found zero additional fires. Therefore
`review:board_transformation_causal_proof` remains Diagnostic/Shadow only,
with no Caption, Prompt, Plan, or Mastery authority.

No production read, database write, fresh engine run, or LLM judgment was
used in implementation or validation.
