# Human Chess Intelligence — Stage 2 Sound-and-Findable Report

Date: 2026-08-31  
Status: offline research complete; no production behavior changed

## Decision

Take two candidate policies into blinded chess-coach review:

1. exact Stockfish-evaluation ties, ranked by Otter;
2. moves within 25cp of Stockfish best **and** preserving Stockfish's WDL outcome, ranked by Otter.

Do not promote a production soundness threshold yet. The 50–150cp candidates
lose too much WDL preservation, and the existing Play-with-Coach guard is not a
safe baseline.

## What was measured

The frozen 600–1500 corpus contained 18,386 stored move observations with
schema >=16 and cp_loss >=100. After rejecting one invalid position/move and
deduplicating 315 repeated legal positions, 18,070 opportunities remained.

The sample-size bake-off compared 270, 405, 540 and 675 positions. A sample of
540 was the first candidate to provide exactly 20 positions in every one of
the 27 rating-band x phase x error-band cells while retaining all 10 concept
families. The 675 candidate added only five positions per cell for 25% more
engine/model work. Therefore 540 was locked as the research sample, not as a
production threshold.

Eligibility resolved as:

| State | Positions |
|---|---:|
| Stratified sample | 540 |
| Missing validated numeric time control | 4 |
| PGN history did not reconstruct the exact stored position | 1 |
| Valid Stockfish + Otter evaluation population | **535** |

The first full run classified the history mismatch as a
`PolicyContractError`. The evaluator now rejects that case before inference;
a complete eligibility recheck produced 535 eligible positions and zero
provider failures. The 535 valid aggregate results are unchanged.

## Pinned provenance

- Stockfish 17.1 binary SHA-256:
  `38faa5883b03652f847a87ed168b1bfee81b361db9584dae59a51cb91e69d9d6`
- MultiPV: 12; depth: 16; threads: 1; hash: 64 MB; UCI WDL enabled
- Otter package: 0.2.0, history-only mode
- Otter model SHA-256:
  `53dc65068c88e298de5abe3dfd93141ea1e3bf795961a686f239b5574804757d`
- Frozen sample record SHA-256:
  `a0ba6d898f610db07c81d8aca6eeb0a90e95891b4fec42dec2a9a4fc87951687`
- Source revision:
  `4af8313c2575b1c2c7886f581504126f836c3c8f`

Stockfish alone defines candidate soundness. Otter only ranks legal moves
already inside the candidate set.

## Overall candidate-band results

| Candidate loss band | Positions with multiple candidates | Otter chooses a different move | Stockfish WDL outcome preserved | MultiPV truncation risk | Selected loss p90 |
|---:|---:|---:|---:|---:|---:|
| 0cp | 3.4% | 2.4% | **100.0%** | 0.0% | 0cp |
| 25cp | 38.7% | 23.9% | **99.6%** | 0.7% | 11cp |
| 50cp | 58.3% | 33.6% | 99.1% | 2.8% | 31cp |
| 75cp | 67.3% | 39.8% | 98.1% | 6.9% | 46cp |
| 100cp | 75.5% | 44.7% | 96.6% | 12.7% | 71cp |
| 150cp | 85.4% | 54.8% | 90.8% | 28.2% | 121cp |

The 25cp candidate is the useful frontier: it changes the selected move in
roughly one quarter of positions while almost always preserving the engine's
WDL outcome. It is still not safe enough as a cp-only rule. Review candidates
must also preserve the best move's WDL outcome position by position.

The exact-tie candidate is the control. Otter selected a different,
equal-evaluation move in 2.4% of positions with 100% WDL preservation.

## Segment findings

- At 25cp, rating-band WDL preservation was 99.4% for 1000–1399, 99.4% for
  1400–1500 and 100% for 600–999.
- At 25cp, phase preservation was 99.4% in endgames, 99.4% in middlegames and
  100% in openings.
- Named concept samples are smaller. Piece activity was the weakest 25cp slice
  at 96.5% WDL preservation (57 positions). That is another reason to require
  same-WDL filtering and blinded review rather than promote a global cp rule.
- Missed-tactic positions offered fewer alternatives: only 13.2% had multiple
  25cp candidates, versus 51.9% for opening-knowledge positions. A single
  promise such as “there is always an easier move” would be false.

## Current Play-with-Coach guard finding

The existing guard was run as implemented: depth 10, MultiPV 8, nominal
150cp soft band, hang filter, and the exception that tries to keep at least
four candidates.

Against the deeper pinned probe:

- only 86.0% of its human-ranked choices preserved the best move's WDL outcome;
- 11.9% exceeded the nominal 150cp band;
- the worst selected move was 99,442cp behind the deeper best line, a
  mate-scale disagreement;
- nine guard moves fell outside the deeper probe's top 12;
- only 523 of 535 positions had a guard move that could be compared.

The “minimum four candidates” exception means the 150cp value is not a safety
gate. This baseline must not be described or reused as verified soundness.

## Interpretation

The core product idea is supported: in many mistake positions, Stockfish has
more than one defensible move, and a human-policy model can identify a move
that players at the student's level are more likely to see. The result does
not prove that the move is easier to explain or better to teach.

That final claim requires blinded coaches to compare:

- Stockfish best;
- Otter-ranked exact ties;
- Otter-ranked <=25cp, same-WDL alternatives.

Reviewers must not see which selector produced a move. They grade
understandability, teachability, positional fit, and whether the explanation
can be expressed accurately for a 600–1500 player.

## Artifacts

- Aggregate evidence:
  `backend/data/corpus_snapshots/human_chess_sound_findable_bakeoff_2026-08-31.json`
- Privacy-minimized sample builder:
  `backend/scripts/build_sound_findable_sample.py`
- Bounded evaluator:
  `backend/scripts/run_sound_findable_bakeoff.py`
- Focused tests:
  `backend/tests/test_sound_findable_sample.py`
  and `backend/tests/test_sound_findable_bakeoff.py`

The opaque sample manifest remains inside the isolated server research
directory. It is referenced by hash; raw positions, moves, engine lines,
player identities, PGNs and FENs were not exported.

## Next gate

Generate a blinded internal review packet using only candidates that satisfy
the exact-tie or <=25cp plus same-WDL policies. Do not change Game Review,
puzzle answers, captions, or Play-with-Coach behavior until the reviewer
result is joined back to this evidence and the final soundness policy is
locked through data.
