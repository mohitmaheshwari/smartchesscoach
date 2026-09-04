# Hidden Opportunities Phase 3A.2 — Forcing Tempo Result

**Status:** PASS — SHADOW ONLY  
**Date:** 2026-09-03  
**Scope:** second causal proof family; no player-facing rollout

## What was implemented

`caption_facts.py` now composes six generic forcing-tempo mechanisms from the
canonical dual-branch trace. Each proof contains exact setup, constraint, and
payoff steps; persistent physical-piece identities; the positive branch edge;
an independently checkable material payoff; and a deterministic fingerprint.

Target/line proof ownership is checked first, preventing duplicate or
contradictory facts. Escape-based proofs also use a final-position legal-
capture guard, closing the same four-ply horizon class previously found in the
target/line family.

## Independent architecture result

The standalone oracle rebuilt the positions and every move from raw FEN and
SAN. It independently checked captures, checks, legal reply counts, attacked
squares, physical-piece continuity, branch material, material yield, horizon
survival, and proof determinism.

| Gate | Result |
| --- | --- |
| Locked packet | 100 positions |
| Forcing-family gold | 8 positions |
| Owned by stricter target/line proof | 2 |
| New forcing proofs | 6/6 remaining |
| Composed family coverage | 8/8 |
| False fires across non-opportunities | 0/76 |
| Precision on architecture packet | 100% |
| Wilson lower bound | 60.97% |
| Branch reversals | 6/6 rejected |
| Legal horizon-recapture regression | rejected |
| Focused branch/proof tests | 37 passed |
| Protected surface authorizations | none |
| Fresh engine / production read / database write | 0 / 0 / 0 |

The machine record is
`backend/data/corpus_snapshots/hidden_opportunities_phase3a2_forcing_tempo_validation_v2_2026-09-03.json`.

V2 uses the shared exact legal-exchange resolver for material-payoff chains.
The independent population result is unchanged at three candidates; only the
proof semantics and fingerprints are correctly versioned.

## Independent offline population census

The existing 80-game full audit and 100-case cause packet were scanned after
excluding architecture-gold overlaps and duplicate positions.

| Measurement | Result |
| --- | ---: |
| Cases scanned | 567 |
| Complete independent branch pairs | 563 |
| Architecture overlaps excluded | 3 |
| Post-horizon-guard candidate fires | 3 |
| Distinct candidate source games | 3 |
| Positive-edge near controls | 240 |
| Blinded controls selected | 30 |
| Blinded review cases | 33 |
| Caption fire minimum | 50 |
| Fire shortfall | 47 |

The three candidates are one profitable exchange-before-retreat and two
save-the-piece-with-check sequences. Candidate status, mechanism, proof,
cp-loss, source collection, stored classification, and identity are hidden
from the reviewer cases.

The reproducible packet is
`backend/data/detector_gold/forcing_tempo_causal_pre_promotion_review_v1.json`.
Its four deterministic privacy/gate tests pass. It is evidence to retain, not
evidence to promote.

## Why this is not visible

Six architecture positives and three unreviewed population candidates cannot
support a player-facing claim. The family remains Shadow until it has at least
50 independently reviewed fires, 20 reviewed true negatives, at least 95%
semantic precision, at least 85% Wilson lower bound, zero critical adversarial
errors, and an independent rendered-claim audit.

The later endgame and board-transformation slices are complete, but their
evidence remains separate. Unrelated samples are not combined to manufacture
the promotion minimum.
