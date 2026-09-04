# Hidden Opportunities Phase 3A.2 — Endgame Geometry Data Lock

**Status:** LOCKED FOR SHADOW IMPLEMENTATION  
**Date:** 2026-09-03  
**Family:** `exact_endgame_and_promotion_geometry`

## Decision

This family proves exact board resources visible in both complete stored
branches. It does **not** infer a win, draw, loss, named endgame technique, or
tablebase result unless separately supplied by the canonical Fathom service.

The current contract is `endgame_geometry_causal_proof.v2`. Where a mechanism
claims material, V2 resolves the complete legal exchange beyond the stored
horizon instead of treating the first nominal recapture as the whole truth.

The four generic mechanisms are:

- the same king follows a stored route and reaches an enemy pawn;
- pushing the same pawn immediately promotes inside the stored line, while
  the played branch reaches the same push too late;
- moving the king preserves a rook's line so it can exchange the checking
  rook later;
- choosing the other rook for the first capture preserves the original rook
  to capture the opponent's promoted piece.

## Why payoff types are separate

`00bb6cd1492bc5b6f355` ends with `Rxf6+`, but the final position permits both
`...Kxf6` and `...exf6`. Calling that a won rook would be false. The typed
payoff is therefore `checking_rook_exchange`, not `material_payoff`.

Promotion, pawn capture, checking-rook exchange, and promoted-piece capture
are separate contract values. The renderer cannot silently convert one into
another.

## Existing authority remains canonical

- `exact_endgame_service.py` remains the only authority for exact WDL changes
  from the pinned Fathom/Syzygy bundle.
- `stored_line_verifier.py` owns legal replay, promotion identity, physical-
  piece identity, checks, captures, and final FEN.
- `caption_facts.py` may compose only the generic resource proved by those
  facts.
- The target/line and forcing-tempo owners run first; duplicate ownership is
  rejected.

## Threshold decision

No piece-count cutoff, cp-loss cutoff, or arbitrary promotion distance was
introduced. The existing canonical phase classifier must call the position
an endgame. Every claimed step must occur in the complete legal stored line,
and survival claims receive the same final-position capture guard used by the
earlier families.

## Explicitly rejected shortcuts

- calling every engine-best endgame move a teachable geometry resource;
- treating a recapturable rook as material won;
- treating Stockfish evaluation as an exact tablebase result;
- naming opposition, key squares, triangulation, or a promotion race from a
  single line without its own reviewed proof;
- counting `=Q` text without tracking the same physical pawn;
- using different rooks interchangeably without persistent identity;
- adding a new numeric endgame boundary;
- using production access, a fresh engine run, or an LLM chess judgment.

## Promotion boundary

The architecture packet has four fires, 100% observed precision, and a 51.01%
Wilson lower bound. The independent population census found one additional
candidate, leaving a 49-fire shortfall. `review:endgame_geometry_causal_proof`
therefore remains Diagnostic/Shadow only with no Caption, Prompt, Plan, or
Mastery authority.
