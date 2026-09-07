# Hidden Opportunities Phase 3A.2 — Board Transformation Result

**Status:** PASS — SHADOW ONLY  
**Date:** 2026-09-03  
**Scope:** fourth and final causal proof family; no player-facing rollout

## Architecture result

The new typed contract carries an exact setup, all intervening transformation
steps, the exact payoff, complete played and better branch evidence, a
horizon-adjusted legal material gain, and a deterministic fingerprint.

| Gate | Result |
| --- | ---: |
| Locked packet | 100 positions |
| Board-transformation gold | 3 positions |
| Proof coverage | 3/3 |
| False fires across non-opportunities | 0/76 |
| Precision on architecture packet | 100% |
| Wilson lower bound | 43.85% |
| Branch reversals | 3/3 rejected |
| Exact intervening sequences retained | 3/3 |
| Focused branch/proof tests | 37 passed |
| Protected surface authorizations | 0 |
| Fresh engine / production read / database write | 0 / 0 / 0 |

The independent oracle replays every move from raw FEN and SAN, reconstructs
piece identities independently, verifies the rook routes are legal, and
solves the complete legal exchange on the final payoff square. The three
horizon-adjusted material gains are 100cp, 400cp and 100cp. The last value is
lower than the stored-line subtotal because `...Qxe5 Rxe5 ...Rxe5` wins 100cp
back; the proof records the resolved value rather than the attractive PV
headline.

The machine record is
`backend/data/corpus_snapshots/hidden_opportunities_phase3a2_board_transformation_validation_v1_2026-09-03.json`.

## Offline population result

| Measurement | Result |
| --- | ---: |
| Cases scanned | 567 |
| Complete independent branch pairs | 563 |
| Architecture overlaps excluded | 3 |
| Independent candidate fires | 0 |
| Positive-edge near controls | 243 |
| Blinded controls selected | 30 |
| Caption fire minimum | 50 |
| Fire shortfall | 50 |

The deterministic packet is
`backend/data/detector_gold/board_transformation_causal_pre_promotion_review_v1.json`.
It contains only blinded controls because the independent corpus produced no
candidate fires. That is retained as negative supply evidence; it is not
misrepresented as a promotion packet.

## Honest product boundary

The family proves that the architecture can preserve and verify these three
multi-step chess stories. It does not prove population coverage. It remains
in Shadow so no user can see a sparse, unreviewed, or mislabeled claim.

The combined Phase 3A.2 gate passes 53 tests. The broader deterministic
caption/review suite passes 351 tests with 26 skips and the same six recorded
baseline fixture failures; this phase adds zero failures.
