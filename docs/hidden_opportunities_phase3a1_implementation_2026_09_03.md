# Hidden Opportunities Phase 3A.1 — Differential Evidence Result

**Status:** PASS — shadow evidence only  
**Date:** 2026-09-03  
**Scope:** complete legal traces and objective differences for the stored played and better branches; no mechanism promotion, UI change, production mutation, engine rerun, or LLM authority

## Outcome

Phase 3A.1 now has one canonical evidence path. `stored_line_verifier.py` replays an already-stored line into typed ply events. `caption_facts.py` wraps the two complete traces and their objective difference without selecting a motif or writing prose. Existing `VerifiedLineCause` consumers receive their original V1 contract by default; richer V2 evidence is opt-in.

The locked 100-position packet produced evidence for all 100 positions and all 200 branches. A separate validation path replayed every emitted UCI move on a fresh `python-chess` board and independently reconstructed SAN and FEN. It agreed on all 200 traces.

## Evidence recorded per ply

- actor, UCI, SAN, origin, destination and moving piece;
- captured piece, capture square and fixed material value;
- promotion, check, mate and stalemate state;
- legal-reply count and exact sole reply when one exists;
- FEN before and after the move;
- changed attackers, defenders, geometric reach and king pins for occupied squares;
- lines opened or closed for stationary bishops, rooks and queens.

The branch wrapper records separate trace fingerprints, terminal results, net material edge, branch-only captures, check plies, sole-reply plies and promotion plies. These are facts for Phase 3A.2 proof families; none is yet a player-facing claim.

## The ambiguity defect fixed without visible drift

Five packet branches contain an opponent reply whose SAN can also parse as the leading move on the initial board, such as `Rxd8` followed by `Rxd8+`. The legacy normalizer could mistake that reply for a duplicated leading move. Rich evidence now resolves both stored formats by legal replay and prefers the documented continuation format. The default legacy cause selector deliberately keeps its previous behavior until a promoted causal proof replaces it, preventing an unreviewed narration change.

## Validation

| Gate | Result |
| --- | --- |
| New Phase 3A.1 tests | 14 passed, 0 failed |
| Locked corpus | 100/100 evidence packages |
| Stored branches | 200/200 complete |
| Independent oracle replay | 200/200 exact UCI, SAN and FEN matches |
| Typed events | 1,000 |
| Captures / checks / promotions | 294 / 111 / 5 |
| Sole-reply events | 22 |
| Relation / line-geometry changes | 6,538 / 1,119 after Phase 3A.2 identity enrichment |
| Existing default cause contracts changed | 0 |
| Legacy runtime packet drift | 0 across 100 positions |
| Comprehensive contract regression | 260 passed; the same 6 baseline failures remain |
| Compile and diff-integrity checks | passed |

The machine-readable result is `backend/data/corpus_snapshots/hidden_opportunities_phase3a1_validation_v1_2026-09-03.json`. Its source packet SHA-256 is `2fec4b84f8f192a138d4ab4048bbfe87eab5c46a343a0f948f6007c3e9081213`.

Phase 3A.2 subsequently enriched each occupied-square relationship with a
persistent physical-piece ID and exact attacked squares. The branch and legacy
compatibility gates were rerun after that schema change: 200/200 independent
traces still agree and default cause-contract drift remains zero. The seven
additional relation changes are the expected result of tracking identity and
pawn control rather than a change to stored chess moves.

## Non-regression inheritance

This phase does not replace the earlier work. Stage 1 branch-owned mate truth remains in the same isolated worktree and is still the first visible-claim regression family. Personalized review, caption, planner, puzzle-admission, curriculum, exact-endgame, human-policy and mastery owners remain unchanged. Phase 3A.1 adds only evidence they may consume later through their existing contracts.

## Honest boundary

This result proves that ChessGuru can reconstruct and compare the stored branches exactly. It does **not** prove that a fork, pin, clearance, zwischenzug, promotion race or positional mechanism has occurred. Those claims belong to Phase 3A.2 and remain blocked until each proof family passes blind gold, false-friend and incomplete-horizon gates.

No commit, push, deployment, regeneration, production read, production write or fresh Stockfish run was performed.
