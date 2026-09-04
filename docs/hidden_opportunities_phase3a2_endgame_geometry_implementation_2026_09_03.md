# Hidden Opportunities Phase 3A.2 — Endgame Geometry Result

**Status:** PASS — SHADOW ONLY  
**Date:** 2026-09-03  
**Scope:** third causal proof family; no player-facing rollout

## Architecture result

The new typed proof family reconstructs four endgame resources while leaving
all exact-result authority with Fathom/Syzygy. Each proof contains a complete
dual-branch trace, physical-piece identities, typed setup/constraint/payoff
steps, a specific payoff kind, and a deterministic fingerprint.

| Gate | Result |
| --- | --- |
| Locked packet | 100 positions |
| Endgame-family gold | 4 positions |
| Proof coverage | 4/4 |
| False fires across non-opportunities | 0/76 |
| Precision on architecture packet | 100% |
| Wilson lower bound | 51.01% |
| Branch reversals | 4/4 rejected |
| Exact-WDL claims emitted | 0 |
| Focused branch/proof tests | 37 passed |
| Protected surface authorizations | none |
| Fresh engine / production read / database write | 0 / 0 / 0 |

The independent oracle counts promotion material explicitly, verifies the
same pawn and rook identities across branches, and records the legal
recaptures after the rook-exchange resource. All three proof-family validators
remain green after the shared oracle correction.

The machine record is
`backend/data/corpus_snapshots/hidden_opportunities_phase3a2_endgame_geometry_validation_v2_2026-09-03.json`.

V2 uses the shared exact legal-exchange resolver where a proof claims a
material payoff. The one-candidate population result is unchanged; the proof
version now records the stricter semantics.

## Offline population result

| Measurement | Result |
| --- | ---: |
| Cases scanned | 567 |
| Complete independent branch pairs | 563 |
| Architecture overlaps excluded | 3 |
| Candidate fires | 1 |
| Distinct candidate source games | 1 |
| Positive-edge near controls | 242 |
| Blinded controls selected | 30 |
| Blinded review cases | 31 |
| Caption fire minimum | 50 |
| Fire shortfall | 49 |

The candidate is an immediate passed-pawn push that promotes in the better
branch while the played branch spends the needed tempo on the other pawn.
Its blinded packet is
`backend/data/detector_gold/endgame_geometry_causal_pre_promotion_review_v1.json`.
The packet's four determinism, privacy, gate, and side-effect tests pass.

## Honest boundary

These exact board facts are internally useful, but they are not yet captions.
The family needs the existing promotion evidence minimum, independent chess
adjudication, zero critical adversarial errors, and a rendered-claim audit
before any player sees it.

The final board-transformation slice is complete and preserves this family’s
ownership and regression gates.
