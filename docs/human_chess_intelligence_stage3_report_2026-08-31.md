# Human Chess Intelligence — Stage 3 Puzzle Intelligence Report

Date: 2026-08-31  
Status: offline research complete; prospective measurement implemented locally; no production behavior changed or deployed

## Decision

Stage 3 supports two shadow uses of Maia-2:

1. retain target-move probability as a **shadow practical-findability feature**;
2. use Maia-ranked legal alternatives as **distractor candidates**, but only after Stockfish or tablebase verification.

Do **not** replace the live puzzle difficulty labels, alter puzzle ordering, or
publish Maia-based difficulty yet. Historical attempts cannot support an
honest outcome calibration because they contain neither attempt-time rating
nor assistance status. The canonical training path now records those fields
prospectively in `puzzle_attempt.v2` so the promotion decision can later be
made from real first, unassisted attempts.

| Use | Verdict | Reason |
|---|---|---|
| Maia target probability as stored shadow evidence | **ADOPT IN SHADOW** | It measures something materially different from cp loss and the current label, with reproducible model provenance. |
| Maia score as a production difficulty label | **REJECT FOR NOW** | There is no clean historical outcome cohort against which to calibrate it. |
| Maia-ranked human-like distractor candidate | **SHADOW** | Candidates are plausible, but many are sound alternatives; Stockfish/tablebase must decide whether they are actually wrong. |
| Current difficulty or cp loss as “human difficulty” | **REJECT AS AN AUTHORITY** | Both correlate only weakly with Maia target-move probability in the sample. |
| Existing admitted answer set | **KEEP** | A deeper safety audit found no material engine-loss defect in the 360-position sample. |

These verdicts authorize no player-facing model call. Stockfish remains the
soundness authority and Maia remains derived evidence.

## 1. Historical measurement audit

The production audit found 400 stored puzzle-attempt rows. Of those:

| Cohort step | Rows |
|---|---:|
| Stored attempts | 400 |
| Outcome plus timestamp available | 310 |
| Earliest unique user/puzzle attempts | 205 |
| Repeat rows removed | 105 |
| Missing user or puzzle identifier | 90 |
| Users represented by inferred first attempts | 18 |
| Inferred first attempts joined to a current puzzle pool | 92 |
| Joined rows with legal target and admission evidence | 92 |
| Rows with known assistance status | **0** |
| Rows with attempt-time solver rating | **0** |

The 205 inferred first attempts contain 116 correct and 89 incorrect outcomes,
but every one has `support_unknown`. All 400 historical attempts are missing
attempt-time rating. Only 92 inferred first attempts join to a current pool;
113 are unmatched. This is not a defensible calibration cohort.

Therefore the Stage 3 outcome comparison was explicitly recorded as **not
performed**. Treating those rows as unassisted or assigning today's rating to
old attempts would manufacture evidence.

## 2. Prospective evidence contract

The canonical `/api/training/puzzle-attempt` writer now builds one normalized
`puzzle_attempt.v2` record. The server owns prior-attempt counting and rating
resolution; the training surface supplies its support state and submitted
move. New records preserve:

- `attempt_ordinal` and `is_first_attempt`;
- normalized `support_level`;
- `counts_as_independent_attempt`, true only for the first unassisted try;
- solver rating, rating source, and whether that value was measured or a fallback;
- real decision time in milliseconds, captured before move evaluation latency;
- surface, puzzle source, outcome, submitted move and move quality.

Unknown support fails closed and retries cannot enter the independent cohort.
A default rating remains visibly unmeasured rather than masquerading as player
evidence. Reveal-only actions are not recorded as successful attempts.

This contract is implemented but not deployed by this work. It begins the
clean calibration cohort only after the normal release process deploys it.

## 3. Pool opportunity and sample lock

The sample-time pool contained 12,225 `community_puzzles` and 38,490
`community_training_positions`. The read-only selector:

- excluded 134 quarantined rows;
- removed 7,297 same-answer duplicate positions;
- found no remaining same-position/different-answer conflict;
- retained 43,284 unique, legal, admitted opportunities.

Sample sizes 120, 240, 360 and 480 were compared across 12 cells:

`2 source pools × 3 current difficulty labels × 2 admission statuses`.

Every candidate covered all 12 cells and the same four available concept
families. A sample of 360 was locked because it supplies 30 positions per cell;
480 adds 33% computation without new segment coverage. This is a research
sample-size decision, not a future production threshold.

The privacy-minimized sample manifest remains in the isolated research
directory. Its record hash is:

`2ca4d90f2e27f50073b976f5f865415a5ffe70d961b93d5a21ae7ed70b8034a2`

No FEN, move, puzzle identifier, game identifier, or player trajectory was
exported into the aggregate repository snapshots.

## 4. Shadow Maia-2 result

All 360 positions completed with zero evaluator failures. At the representative
1200 rating:

| Measure | Result |
|---|---:|
| Target-answer probability, median | 30.6% |
| Target-answer probability, p25 / p75 | 9.7% / 58.2% |
| Best admitted answer's Maia rank, median | 1 |
| Best admitted answer's Maia rank, p90 | 6 |
| Current easiness label vs target probability, Spearman | **0.190** |
| `cp_loss` vs target probability, Spearman | **0.194** |
| Target probability non-decreasing across the rating grid | 57.8% |

The weak correlations show that current difficulty and cp loss are poor
proxies for human findability. They do not prove that Maia predicts real solve
rates better: that claim requires the prospective outcome cohort.

The non-monotonic result also blocks a simplistic rule such as “higher rating
always means a larger probability for this stored answer.” Model rating
buckets, multiple good ideas, and position-specific move preferences must be
handled explicitly during later calibration.

## 5. Distractor feasibility and safety

At rating 1200, the most likely Maia move outside the admitted answer set had:

| Engine check | Result |
|---|---:|
| Median loss | 169cp |
| Loss of at least 25cp | 86.1% |
| Loss of at least 50cp | 76.9% |
| Loss of at least 100cp | 65.3% |
| Loss of at least 150cp | 53.6% |
| Changed Stockfish WDL bucket | 46.1% |

This supports Maia as a scalable source of *tempting candidate moves*. It does
not support automatically labelling the top non-answer move as wrong. Roughly
14% were within 25cp of Stockfish best, and some may be legitimate alternative
solutions. A distractor may reach a player only when it is legal, outside the
verified acceptable set, engine/tablebase-rejected under the instructional
constraint, and paired with a verified failure explanation.

## 6. Admitted-answer drift audit

The combined depth-14 distractor search initially reported 97.78% WDL-bucket
preservation for the admitted answer set. Because root-move composition can
change a bounded engine search, every sampled answer was rechecked separately:

| Check | Result |
|---|---:|
| Accepted-answer-only depth-14 preservation | 98.33% |
| Shallow mismatches rechecked | 6 |
| Resolved at depth 20 | 5 |
| Still in a different coarse WDL bucket at depth 20 | 1 |
| Engine loss of the remaining answer | **9cp** |

The remaining item is a coarse WDL-boundary difference with negligible engine
loss, not a materially bad admitted move. No answer in this sample requires
quarantine from this audit. The disagreement between 8 combined-search and 6
answer-only shallow mismatches is itself evidence that bounded WDL argmax is
not a stable standalone ambiguity rule; cp/evaluation loss and deeper
confirmation must accompany it.

## 7. Pinned provenance

- Maia-2 package: 0.11.0, Rapid weights
- Maia model SHA-256:
  `65aae8465eed5e65df66a24ea7370715579f9e5435098d06fe18bdb1e267e997`
- Maia rating grid: 800, 1000, 1200, 1400
- Stockfish 17.1 binary SHA-256:
  `38faa5883b03652f847a87ed168b1bfee81b361db9584dae59a51cb91e69d9d6`
- Shadow run: depth 14, one thread, 64 MB hash, UCI WDL enabled
- Drift confirmation: accepted answers at depth 14; mismatches at depth 20
- Source revision:
  `4af8313c2575b1c2c7886f581504126f836c3c8f`

## 8. Verification

- Focused backend Stage 3 suite: **16 passed**
- Full 360-position Maia/Stockfish shadow run: **360 completed, 0 failures**
- Accepted-answer drift audit: **360 completed, 0 failures**
- Frontend production build: **compiled successfully**

The frontend build retained existing repository warnings, including a missing
third-party source map and pre-existing hook dependency warnings. No new
warning names `PrescribedTraining.jsx`.

## 9. Artifacts

- Historical aggregate audit:
  `backend/data/corpus_snapshots/human_chess_puzzle_stage3_data_audit_2026-08-31.json`
- Shadow difficulty and distractor aggregate:
  `backend/data/corpus_snapshots/human_chess_puzzle_stage3_shadow_bakeoff_2026-08-31.json`
- Deeper answer-drift aggregate:
  `backend/data/corpus_snapshots/human_chess_puzzle_stage3_admission_drift_2026-08-31.json`
- Audit, sample and evaluator scripts:
  `backend/scripts/audit_puzzle_stage3_data.py`,
  `backend/scripts/build_puzzle_stage3_sample.py`,
  `backend/scripts/run_puzzle_stage3_shadow_bakeoff.py`, and
  `backend/scripts/audit_puzzle_stage3_admission_drift.py`
- Canonical prospective contract:
  `backend/services/puzzle_attempt_evidence.py`,
  `backend/services/rating_resolver.py`,
  `backend/routes/training.py`, and
  `frontend/src/pages/PrescribedTraining.jsx`

## Next gate

After `puzzle_attempt.v2` is deployed, accumulate real first, unassisted,
measured-rating attempts. Then compare held-out outcome prediction for:

1. current difficulty label;
2. cp loss alone;
3. Maia target probability;
4. a calibrated combination learned only from the training partition.

The required cohort size and promotion threshold must be locked from the
resulting coverage and calibration curves, not chosen now. Until then, Maia
scores and distractors remain shadow evidence and the user-facing puzzle order
does not change.
