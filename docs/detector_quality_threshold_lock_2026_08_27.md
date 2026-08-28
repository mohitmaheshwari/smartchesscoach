# Detector quality authorization — data lock (2026-08-27)

Status: LOCKED FROM MEASURED EVIDENCE

## Decision

Use four fail-closed states: `plan`, `caption`, `shadow`, and `disabled`.
Promotion is based on independently reviewed semantic examples, not firing
volume, implementation agreement, engine centipawn loss alone, or an external
theme tag.

## Candidate bake-off

| Candidate | Rule | What the measured corpus would do | Verdict |
|---|---|---|---|
| A — legacy | raw precision >=75%; 30 examples | Would tolerate the measured king-safety result (445/590 = 75.4%) and nearly tolerate rule-of-square (21/29 = 72.4%), despite obvious false coaching. | Rejected. The observed 24.6% king-safety concern rate proves this floor unsafe. |
| B — small raw sample | raw precision >=90%; 50 examples | Separates current weak detectors, but 45/50 passes while its 95% Wilson lower bound is only about 78.6%. | Rejected. It mistakes a small clean sample for reliable quality. |
| C — uncertainty-aware | surface-specific raw precision + Wilson lower bound + minimum reviewed opportunities + adversarial zero-critical-error gate | Keeps known weak detectors silent, permits coverage research, and makes stronger claims earn stronger evidence. | Selected. |

## Locked values

### Plan-grade

- independently reviewed semantic precision >=95%;
- 95% Wilson precision lower bound >=90%;
- at least 200 reviewed fires;
- semantic recall >=60% on at least 100 independently selected positive
  opportunities;
- at least 30 true negative/non-opportunity cases;
- zero critical false claims in the detector's adversarial regression packet;
- evidence split by game/player/source unit so related positions cannot leak;
- evidence must match the player-facing claim—not merely its geometry.

### Caption-grade

- independently reviewed semantic precision >=95%;
- 95% Wilson precision lower bound >=85%;
- at least 50 reviewed fires;
- at least 20 true negative/non-opportunity cases;
- zero critical false claims in the adversarial regression packet;
- no recall floor, because a caption detector may safely stay silent.

### Shadow and disabled

- `shadow`: detector may execute and emit diagnostics, but it cannot change a
  caption, active focus, improvement plan, mastery grade, or coaching prompt.
- `disabled`: detector does not execute in normal product paths because it is
  known unsafe, redundant, or operationally broken.
- unknown detector IDs are always `shadow`.

## Evidence behind the lock

- `simple_hang`: 96.9% documented semantic precision on 260 reviewed fires;
  its Wilson lower bound is about 94.0%. It clears the precision/sample side of
  Plan-grade; its 61.61% taxonomy recall clears the raw recall floor only when
  the underlying opportunity set is preserved and independently reviewable.
- D_live: 22,583 decisions across 149,886 v16 moves and 99.75% agreement with
  the independent implementation, but agreement is not semantic gold. It is
  strong regression evidence, not sufficient by itself for Plan promotion.
- Shape geometry: 382/382 sampled board-geometry checks passed (Wilson lower
  bound about 99.0%), but geometry does not prove causal attribution. Shape IDs
  remain Caption-grade candidates, not Plan-grade, until attribution review.
- King safety: 445/590 passed the built verifier, leaving 145 concerning fires
  (24.6%; precision 75.4%, Wilson lower bound about 71.8%). Shadow.
- Registered lesson detectors: rule-of-square had 8 concerning examples among
  29 fires (27.6%; precision 72.4%, Wilson lower bound about 54.3%); most other
  detectors fired only 0–2 times across 200 games. Shadow until gold exists.
- Broad concept attribution fired only 34 times on 1,200 generic mistakes
  (2.83%), with known rule-of-square and trapped-piece semantic errors. Shadow.

## Bounded Lichess pilot

On 2026-08-27 the original production validator sampled 1,000 Lichess puzzles
tagged `fork` from the 4,110,434-position local corpus:

- setup errors: 0;
- our fork evaluator accepted the second solution move in 753 (75.3%);
- it rejected 247 (24.7%);
- accepted tiers: 694 HIGH, 59 MEDIUM, 0 LOW.

That first result was a validator defect, not detector recall: it inspected
only the first player solution ply. After the validator was corrected to
replay every player ply, two independent 1,000-puzzle samples reached 99.6%
and 99.7% sequence-level agreement. In the latter: 766 matches were on the
first player ply, 231 were later, and only 3 tagged puzzles had no match.

A 1,000-puzzle negative control excluding the `fork` tag still produced 304
detector fires (30.4%), commonly on checks/mates with a secondary attacked
target. These are not automatic false positives because Lichess can omit
secondary themes, but the rate proves that tag absence is not a negative truth
label. Fork remains Shadow until independent review distinguishes true causal
forks from incidental check-plus-target geometry.

Review of disagreements shows many themes describe a later idea in a long
combination, an attraction/sacrifice, or a fork that appears after additional
moves. Therefore:

- Lichess themes are locked as positive-candidate mining and coverage research;
- a theme tag is not semantic gold for one selected ply;
- validators must replay the full solution and identify the theme-bearing ply;
- human/tablebase/board-verifier adjudication is required before promotion;
- the pilot size for a detector is opportunity-driven: continue sampling until
  it has the surface's reviewed-fire minimum and negative-case minimum, rather
  than choosing a fixed number of games.

A second pilot streamed and discarded 300 games (20,117 plies, zero parse
errors) from the checksum-pinned July 2026 standard-rated export. It produced
130 rule-of-square candidates and 46 opposition candidates, but only 3–7 fires
for each basic mating/opening-defense detector and zero for Lucena, Philidor,
trap detection, and opening play. This locks the corpus strategy: generic raw
games for frequent-pattern negatives and opportunity discovery; targeted
tablebase/generated strata for rare endgames; correct opening/history context
before spending a larger raw-game budget.

Full source and checksum record:
`docs/lichess_detector_corpus_provenance.md`.

## Rejected shortcuts

- Stockfish `cp_loss` as a detector truth label: it says a move was costly, not
  why it was costly.
- Lichess theme equality as truth: the pilot disproved one-ply equivalence.
- implementation-to-implementation agreement: duplicated logic can agree and
  still be wrong.
- “no user complaints”: absence of feedback is not evidence of correctness.

## Measurement method

Read-only production collection counts; existing detector audit reports;
board-verifier samples recorded in the review brief; and
`scripts/validate_fork_against_lichess.py --n 1000 --negative-n 1000
--show-mismatches 20`
against the production `lichess_puzzles` collection.
