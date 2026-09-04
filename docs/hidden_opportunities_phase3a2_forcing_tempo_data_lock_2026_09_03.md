# Hidden Opportunities Phase 3A.2 — Forcing Tempo Data Lock

**Status:** LOCKED FOR SHADOW IMPLEMENTATION  
**Date:** 2026-09-03  
**Family:** `forcing_tempo_and_move_order`

## Decision

A forcing-tempo proof requires two complete legal stored branches, persistent
physical-piece identity, a positive material branch edge, and one exact typed
setup → constraint → payoff chain. It may prove only one of these generic
mechanisms:

- take a more valuable piece before retreating, with the recapture resolved;
- insert a check that moves the king which otherwise recaptures;
- force an exchange with a sole reply, then move the endangered piece;
- force a sole reply onto a square already controlled by the checking piece;
- move the endangered piece with check before it is taken;
- choose the capture order in which the same piece completes a profitable
  multi-capture route.

The proof does not infer a named zwischenzug, deflection, clearance, fork,
pin, skewer, or combination. Such a name still requires its canonical proof
owner. The family remains **Shadow**.

The current contract is `forcing_tempo_causal_proof.v2`. V2 resolves
material-payoff horizon captures through the canonical complete legal exchange
solver; escape/survival claims still fail if the piece can be captured at the
stored horizon.

## Canonical ownership and composition

The stricter target/line family is evaluated first. Two locked forcing cases
already satisfy that proof and remain owned by it:

- `03eccd1bf3d294170e7f`
- `039bd832a639d9c2f8ab`

The forcing builder returns no second proof for those positions. The composed
system covers all eight locked forcing cases with exactly one owner each.

## Horizon rule

“Not captured in the stored PV” is not equivalent to “saved.” For escape and
save-with-check mechanisms, the same physical piece must survive the complete
stored line. If the opponent is to move in the final stored position and has
a legal capture of that piece, the proof fails closed.

This rule was added after a legal adversarial case reproduced the leak:
`Re7+ Kf8 a3` stops immediately before `...Kxe7`. The old structural rule
would have called the rook saved; the locked rule rejects it.

## Threshold decision

No new cp-loss, material, check-count, or depth threshold was introduced.
Every mechanism has a chess-semantic boundary: exact identity, exact legal
reply count where “forced” is claimed, and a strictly positive material
payoff. The existing Caption promotion thresholds remain unchanged.

## Explicitly rejected shortcuts

- check presence without a branch outcome difference;
- a PV move being played by the king without proving the stated identity;
- calling a reply “forced” unless the legal reply count is exactly one;
- calling a piece saved when a legal horizon capture remains;
- treating any positive engine loss as a forcing-tempo explanation;
- adding position IDs to runtime rules;
- allowing a second detector to own an already-proved target/line case;
- using fresh Stockfish, production access, or an LLM chess judgment.

## Promotion boundary

The locked architecture packet contains only six new fires. Its 95% Wilson
lower bound is 60.97%, below the existing 85% Caption bar. A separate offline
census found only three additional candidates, leaving a 47-fire shortfall.
The quality ID `review:forcing_tempo_causal_proof` therefore remains
Diagnostic/Shadow only and has no Caption, Prompt, Plan, or Mastery authority.
