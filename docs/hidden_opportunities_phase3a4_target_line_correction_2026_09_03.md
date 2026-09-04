# Hidden Opportunities Phase 3A.4 — Target/Line Correction

**Status:** IMPLEMENTED AND VERIFIED; SHADOW ONLY  
**Date:** 2026-09-03

## Result

Phase 3A.4 fixes the one evidence-proven defect found by the 64-case blinded
review: an equal queen liquidation could be presented as a positive target
payoff because the old calculation counted only the pawn that captured the
opposing queen.

The corrected `target_line_causal_proof.v4` evaluates the whole causal sequence
through the payoff:

- every initiator capture contributes material;
- every opponent capture debits material;
- an equal trade therefore contributes zero;
- the canonical piece-yield calculation supplies any legal recapture or
  end-of-horizon adjustment;
- the payoff is accepted only when the resulting sequence remains positive.

This rejects `g3 Qd4 Qf4 Qxf4 gxf4`: both queens disappear, so the sequence
does not prove a material win. It preserves
`f4 Qc5 Qxc5 bxc5 fxe5`: the queens trade equally and the pawn then wins the
knight, leaving a real positive payoff.

## A suspected defect that was deliberately not implemented

The first manual pass called `Qf3 Ng4+ Qxg4` a safe knight win. Regression
replay showed that the stored line ends with Black to move and `...Bxg4` is a
legal exchange. The canonical horizon evaluator values the apparent queen
capture at a loss, so the detector was correct to abstain.

The proposed same-target widening was removed before completion. This phase
does not weaken the existing same-target or horizon guards to satisfy a human
review mistake.

## Permanent adversarial coverage

Seven exact positions are now locked in regression tests:

1. the equal queen liquidation false positive is rejected;
2. the equal queen trade followed by a real knight win is preserved;
3. the apparent knight win with `...Bxg4` beyond the stored line is rejected;
4. removing the pawn that later takes the bishop is preserved;
5. an equal knight exchange is rejected;
6. a queen payoff available in both branches is rejected;
7. a direct capture owned by another proof family is not relabelled as generic
   target/line geometry.

## Offline evidence

The historical v1 packet, answer key, frozen response, and raw 94.12% score
remain reproducible and unchanged in meaning. The corrected detector uses a
new v2 blinded packet; no historical packet was overwritten.

| Measurement | V4 result |
| --- | ---: |
| Cases scanned | 567 |
| Complete branch pairs after exclusions | 563 |
| Candidate fires | 33 |
| Distinct candidate source units | 28 |
| Blinded controls | 30 |
| V2 packet cases | 63 |
| Fire minimum | 50 |
| Fire shortfall | 17 |

Every v2 case was already present in the frozen v1 review. Against the settled
same-agent adjudication, v4 selects 33/33 proved cases and rejects 30/30
controls. That is a useful post-tightening detector-quality scan, not an
independent promotion result.

The separate 100-position architecture validator reports:

| Gate | Result |
| --- | ---: |
| Proof fires | 10 |
| True opportunities | 10 |
| False positives across 76 non-opportunities | 0 |
| Precision | 100% |
| First-family recall | 88.89% |
| Wilson lower bound | 72.25% |
| Protected player-surface authorizations | 0 |

The one first-family abstention remains the previously documented position
whose stored line cannot prove the exchange beyond its horizon.

## Verification

- 5 focused adversarial tests covering 7 exact positions: passed.
- 50 target-line proof, packet, authorization, and historical-score tests:
  passed.
- 387 tests across all 33 backend files directly importing `caption_facts` or
  `detector_quality`: passed.
- Standalone v4 architecture validator: passed.
- Production reads / database writes / fresh engine runs / LLM calls: 0 / 0 /
  0 / 0.

## Promotion status

The detector remains `QualityGrade.SHADOW`. It has no authority over captions,
prompts, plans, mastery, learner profiles, puzzle grading, or public APIs.

Promotion remains blocked by:

1. 33 available fires versus the required 50;
2. no genuinely independent blinded review of v4;
3. no final rendered-claim audit.

No commit, push, deployment, feature-flag change, production backfill, or
user-visible behavior change occurred in Phase 3A.4.
