# Hidden Opportunities Phase 3A.2 — Target/Line Payoff Data Lock

**Status:** LOCKED FOR SHADOW IMPLEMENTATION — V3 LEGAL-EXCHANGE GUARD  
**Date:** 2026-09-03  
**Family:** `target_and_line_geometry_with_payoff`

## Decision

The first causal proof family requires a complete legal played branch, a
complete legal better branch, a positive material difference in the better
branch, a typed setup → constraint → payoff chain, persistent physical-piece
identity, and an exact captured target worth at least a minor piece. The proof
may state only the generic target/line mechanism it reconstructs. A supporting
fork, pin, skewer, or loose-piece name is attached only when that existing
canonical proof owner independently verifies it.

The family remains **Shadow**. This architecture packet is not large enough to
grant Caption, Prompt, Plan, or Mastery authority.

## Why the payoff floor is 300cp

The locked 100-position packet measured three predeclared candidate floors:

| Minimum captured target | Fires | True opportunities | False fires | Precision | First-family recall | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Pawn or better (100cp) | 13 | 12 | 1 | 92.3% | 8/9 | Rejected |
| Minor piece or better (300cp) | 10 | 10 | 0 | 100% | 8/9 | Selected |
| Rook or better (500cp) | 7 | 7 | 0 | 100% | 6/9 | Rejected |

At 100cp, `0093c7dfa97e300cf68c` became a false story: `Be5` pressured
`f6`, but the stored horizon ended with the bishop taking only a pawn and did
not prove the larger payoff. At 500cp, two genuine minor-piece payoffs
disappeared. The 300cp floor is therefore the only measured candidate with no
false fire and no loss of first-family recall.

The V2 replay audit deliberately reclassified one human-gold opportunity as
**not provable from the stored horizon**. In `00906363fd88603401ce`, `Qf6`
really does begin a queen-winning idea, but the four-ply branch ends at
`Qxe7` while two legal rook recaptures still exist. The human chess idea stays
in gold; this proof family stays silent because its evidence stops too early.
“8/9 proved” is more honest than turning the ninth true idea into an
unsupported caption.

V3 keeps that rejection but replaces the deliberately pessimistic
"any legal recapture loses the capturing piece" rule with the canonical exact
legal-exchange resolver. The resolver pushes every legal capture on the
payoff square, includes pins, king legality, checks, promotions and newly
opened x-rays, and allows either side to stop. Thus `...Qxd4 Rxd4` does not
erase a payoff, while a genuinely profitable recapture still does.

This is not a replacement for the branch material comparison. Both gates are
required: the exact target must be meaningful, and the better branch must
finish materially ahead of the played branch inside the stored horizon.

## Canonical ownership

- `stored_line_verifier.py` owns legal replay, persistent piece identity,
  exact attacked squares, captures, checks, promotions, and relation changes.
- `caption_facts.py` owns branch comparison and causal-chain composition.
- Existing free-piece, fork, and aligned-tactic proof owners remain the only
  authorities for those motif names.
- `detector_quality.py` owns surface authorization.
- No renderer, planner, learner profile, curriculum catalog, or puzzle grader
  was added or bypassed.

## Promotion boundary

The existing detector-quality discipline requires at least 50 reviewed
positives and an 85% Wilson lower bound for Caption promotion. This packet has
10/10 precision but only a 72.25% Wilson lower bound. It also is an architecture
sample rather than a population holdout. Therefore `review:target_line_causal_proof`
is intentionally Shadow-only even though the locked packet is clean.

## Explicitly rejected shortcuts

- Geometry alone: rejected because it was already measured in 58/76
  non-opportunities.
- Best-branch material gain without the played comparison: rejected because
  the same payoff may exist in both branches.
- A positive `cp_loss` threshold: rejected as causal evidence; no new cp-loss
  threshold was introduced.
- Naming a fork, pin, skewer, clearance, or decoy from the generic chain:
  rejected unless the canonical named proof verifies it independently.
- Position IDs in runtime rules: prohibited. IDs appear only in tests and
  evidence packets.
- Fresh Stockfish, production access, or an LLM chess judgment: not used.
- A capture at the end of the stored horizon: accepted only when the complete
  legal exchange leaves the proved material yield positive; otherwise it is
  rejected.
