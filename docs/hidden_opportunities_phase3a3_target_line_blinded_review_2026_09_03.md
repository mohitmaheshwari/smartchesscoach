# Hidden Opportunities Phase 3A.3 — Target/Line Blinded Review

Date: 2026-09-03

## Outcome

The target/line proof family remains **Shadow**. Nothing in this review
authorizes captions, planning, mastery updates, deployment, or production
backfill.

The answer-key-free pass covered all 64 frozen cases before candidate/control
membership was revealed. The raw score was:

| Result | Count |
| --- | ---: |
| True positive | 32 |
| False positive | 2 |
| False negative within the sampled controls | 4 |
| True negative | 26 |
| Candidate precision | 94.12% |
| 95% Wilson lower bound | 80.91% |
| Critical false claims | 0 |

This misses both the 95% precision floor and the 85% Wilson floor. There are
also only 34 available candidate fires, below the required 50. The 30 controls
are sampled positive-edge near-controls rather than an opportunity-denominator
population, so their positive-capture rate is not detector recall.

The frozen response is
`backend/data/detector_gold/target_line_causal_blinded_codex_review_v1.json`.
The reproducible raw score is
`backend/data/corpus_snapshots/target_line_causal_blinded_codex_review_score_v1_2026-09-03.json`.

## Independence limit

This was a blinded second pass by the implementation agent, not review by an
independent chess reviewer. It is useful for finding defects and reviewer
mistakes, but it is not eligible promotion evidence. The raw verdicts were
frozen before unblinding and were not rewritten after the machine labels were
known.

## Post-unblind disagreement adjudication

Replaying the six disagreements with the machine proof visible, then applying
the independent legal-exchange horizon oracle, showed five mistakes in the
initial human pass and one real detector defect. These
corrections explain the result; they do not replace the raw blinded score.

### Initial reviewer overcalls

1. `744b40dde590a664c5d6` — `Nd5 Nxd5 exd5` is an equal knight exchange,
   not a positive target/line payoff.
2. `dc12a2798a102a91503a` — the white queen is captured in both stored
   branches. Choosing the other rook does not uniquely create the c-file
   target relation claimed by the better branch.
3. `0aecdec41cec8b456299` — `Rxf4+` is a direct capture. If it is teachable,
   its truth must come from the canonical free-capture or forcing proof family,
   not be invented as target/line geometry.
4. `fd82eb68e8c3c17b9bdf` — `Qf3 Ng4+ Qxg4` appears to win the knight, but
   the stored line ends with Black to move and `...Bxg4` is a legal exchange.
   After the recapture sequence, White has not safely won the target. The
   detector's horizon rejection was correct.

### Initial reviewer undercall

1. `e5875d9dd791aa191b80` — `exd5` removes the exact black pawn that takes
   the bishop after the played `Bc4`. The point is not merely winning a pawn;
   it is removing the future attacker and preventing the bishop loss.

### Genuine false positive

`36b1869b3d33c98a5f2d`: after `g3 Qd4 Qf4 Qxf4 gxf4`, the pawn does capture
the black queen, but White first gives up its own queen. The current
piece-local payoff function counts the pawn's capture without debiting the
queen used to induce it. That can turn an equal liquidation into a false
"positive material payoff" claim.

Required correction: a target-enters-controlled-square chain must prove a
positive **whole causal sequence** payoff, not only a positive yield for the
capturing piece.

## Settled diagnostic view

If the five human-review mistakes above are corrected after unblinding, the
diagnostic matrix becomes 33 true positives, 1 false positive, 0 false
negatives, and 30 true negatives. Candidate precision becomes 97.06% and the
Wilson lower bound becomes 85.08%. The sampled-control capture rate is not
population recall.

Those numbers show that the implementation is close, not that it is promoted:

- the correction was made after unblinding by the same agent;
- only 34 candidate fires exist, 16 short of the minimum;
- the real false positive still needs code-level correction;
- an independent blinded reviewer is still required;
- final rendered claims have not been audited.

## Locked next step

Make one narrow detector revision that:

1. debits material spent by the full causal sequence before accepting a
   target-enters-controlled-square payoff;
2. preserves the same-target and legal-horizon guards that correctly rejected
   the apparent knight win;
3. adds the real defect plus all five reviewer-error cases as
   adversarial regression tests;
4. rebuilds the packet only from the same versioned offline sources;
5. remains Shadow until at least 50 fires and a genuinely independent blinded
   review satisfy every promotion gate.

No production access, fresh Stockfish run, LLM call, commit, push, deployment,
or user-visible behavior change occurred in Phase 3A.3.
