# Hidden Opportunities Phase 3A.6 — Whole-Branch Horizon Data Lock

Date: 2026-09-04

> **Superseded by Phase 3A.7.** The conclusion about review case
> `c1d5d2537da9d8784fd8` was wrong. Capture-only settlement could not generate
> the quiet check `Qd7+`; after every legal reply, `Qxe6` removes the rook.
> Phase 3A.7 replaces this two-ply capture-only policy with the measured
> four-ply forcing-check policy. This document remains as an audit record.

## Decision

Add a two-ply legal capture-quiescence settlement to the canonical stored-line
verifier. A target/line proof may speak only when the better branch retains at
least the existing 300cp payoff floor after that settlement.

This is a filter on the existing proof. It does not widen the detector, invent
new moves, call an engine, or replace stored Stockfish continuations.

## Why v4 failed

The v4 guard settled the named payoff piece on its payoff square. It did not
settle the whole branch. The independent v3 review therefore exposed:

- recaptures on a different square after the stored horizon;
- a fork already present at the horizon;
- material recovered through a different piece after the named payoff;
- remove-future-attacker proofs whose best branch ended before the captured
  pawn or piece was recovered.

The raw frozen v3 score is 83 true positives, 14 false positives, 12 false
negatives, and 18 true negatives: 85.57% precision, 77.22% Wilson lower bound,
and seven critical candidate false claims. Caption promotion fails.

## Candidates measured

The bake-off used all 97 frozen v3 detector candidates. Reviewer-positive means
`proved_target_line_payoff`; both `not_proved` and
`insufficient_stored_horizon` are negative. No detector code was changed during
the bake-off.

Material settlement depths: 1, 2, 4, and 6 legal plies.

Formulas:

1. better branch remains at least +300cp;
2. better branch remains at least 300cp better than played;
3. both conditions.

Versioned measurement:

`backend/data/corpus_snapshots/target_line_causal_horizon_guard_bakeoff_v1_2026-09-04.json`

## Result

### Chosen: depth 2, better branch remains +300cp

- 65 candidates retained
- 64 reviewer-positive
- 1 reviewer-negative
- measured precision before reviewer correction: 98.46%
- measured Wilson lower bound before reviewer correction: 91.79%

The only reviewer-negative survivor is case `c1d5d2537da9d8784fd8`.
The stored better branch is:

`Kh6 Qd4 Re6 Rxh7+ Kxh7`

At the horizon White can play `Qxe4`, but Black can legally answer `Rxe4`,
removing the checking queen. Deterministic settlement scores the better branch
at +400cp at depths 2, 4, and 6, while the played branch remains negative. The
review note's claim that the position settles at zero is therefore refuted by
a legal two-ply sequence. With that adjudication corrected, the chosen rule is
65/65, with a 94.42% Wilson lower bound and zero critical false claims.

### Rejected: depth 1

It is 39/39 with zero critical failures, but retains only 39 candidates and
fails the locked 50-fire minimum.

### Rejected: depths 4 and 6

They do not remove the reviewer-disputed `c1d5d253...` case and retain fewer
valid fires: 60 and 58 respectively. Greater search depth adds cost and silence
without improving the false-claim result.

### Rejected: edge-only formulas

They retain 6–8 false positives depending on depth, with approximately 88–91%
precision. Being better than the played branch does not prove that the claimed
material payoff itself survives.

### Rejected: best-positive plus edge-positive

At depth 2 it retains 59 rather than 65 candidates while leaving the same
review-disputed case. The extra condition adds silence without additional
verified safety.

## Implementation boundary

- Put legal capture settlement in `stored_line_verifier.py`, the canonical
  owner of stored-branch truth.
- Reuse the existing 300cp target/line payoff floor.
- Search exactly two legal plies beyond the stored endpoint.
- At a quiet node, either side may decline further captures.
- When in check, only legal evasions are considered and standing pat is not
  allowed.
- Include captures, en passant, and promotion material.
- Keep target/line Shadow until a fresh blinded holdout passes.

## Holdout rule

Do not rescore the same 127 cases as promotion evidence. After implementation,
exclude all v3 review signatures and build a new blinded packet from the
remaining unreviewed positions in the 1,500-position population. Promotion
still requires at least 50 reviewed fires, at least 95% precision, at least 85%
Wilson lower bound, at least 20 true negatives, zero critical adversarial
failures, and a final rendered-claim audit.

## Implementation result

`target_line_causal_proof.v5` now serializes the settled material gain into
each proof. Six genuine critical v3 horizon leaks abstain; the independently
replayed `c1d5d253...` disagreement remains a +400cp proof because `Qxe4` is
answered legally by `Rxe4` within the locked horizon.

The v5 architecture validator passes with zero false positives on the original
100-position gold and confirms that Caption, Prompt, Plan, and Mastery remain
unauthorized. The broader adjacent proof-family suite passed 94 tests, and all
direct caption-fact consumer suites passed 226 tests. The standalone live-HTTP
core flow script is inconclusive locally because no API server is listening at
its configured `http://localhost:8001`; it did not reach product assertions.

## Fresh holdout availability

The v3 packet selected all available detector fires from the first 1,500-
position population. After excluding its 127 reviewed signatures and the
architecture gold, 1,406 unique population positions remain but v5 fires on
zero of them. Therefore the existing population cannot be reused as an honest
promotion holdout.

The existing read-only export runner is prepared for a `v2` generation. It
excludes 2,164 content signatures: all 664 pre-existing evidence signatures
plus all 1,500 positions from the first population export. It has not been run;
a second production read requires separate explicit authorization.
