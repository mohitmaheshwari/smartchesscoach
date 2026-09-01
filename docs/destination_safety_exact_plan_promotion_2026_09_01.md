# Exact destination safety — Plan promotion (2026-09-01)

Status: **PROMOTED TO PLAN**

Quality ID: `gap:piece_safety:destination_safety_exact`

## Player-facing claim

The coach may say that the player moved a knight, bishop, rook, or queen to a
square where the opponent could immediately take that exact piece for a real
exchange loss. It may teach the concrete pre-move check: “After I choose my
move, can they take the piece I just moved?”

It may not infer that the player was careless, rushed, blind, unfamiliar with a
concept, or suffering from a broader calculation problem.

## Detector

The detector consumes one stored move evaluation. It does not call an engine or
model. It requires all of the following:

1. the move and position replay legally;
2. the moved piece is a knight, bishop, rook, or queen;
3. the opponent has a legal capture on that piece's destination;
4. exhaustive minimax over every legal capture and recapture on that square
   gives the opponent at least 150cp;
5. the already-stored Stockfish loss is at least 150cp; and
6. the already-stored first reply captures that exact moved piece.

The earlier least-valuable-attacker approximation was rejected. Its first
sealed run produced 197/200 semantic positives and one critical error in the
60-case adversarial packet. The runtime detector now uses exhaustive legal
exchange analysis; the audit was rerun from the beginning with a new packet
fingerprint.

## Locked evidence

The read-only audit scanned 166,681 SEE-backed observations without rerunning
Stockfish or writing to MongoDB. Full positions stayed on the database host;
the repository stores only the aggregate result and sealed packet fingerprint
in `backend/data/corpus_snapshots/destination_safety_exact_plan_promotion_2026-09-01.json`.

| Requirement | Locked bar | Result |
|---|---:|---:|
| Independently rebuilt semantic precision | >=95% | **200/200 = 100%** |
| 95% Wilson lower bound | >=90% | **98.12%** |
| Reviewed fires | >=200 | **200** |
| Semantic recall | >=60% on >=100 opportunities | **165/200 = 82.5%** |
| True negatives | >=30 | **60; 0 fires** |
| Critical adversarial errors | 0 | **0/60** |
| Game-unit separation | one reviewed fire per game | **200 games** |

Corpus population: 1,896 fires, 2,320 independently rebuilt positive
opportunities, and 22,803 independently rebuilt non-opportunities.

## Independence and provenance

`backend/scripts/audit_destination_safety_plan_promotion.py` independently
reconstructs every board and explores every legal destination-capture sequence.
It compares that semantic truth with the production candidate in
`backend/services/destination_safety_detector.py`. The common input is stored
Stockfish evidence; Stockfish was not rerun and its analysis was not treated as
the motif label.

The sealed packet seed is `20260901-destination-safety-plan-v1`; its SHA-256 is
`783e0d2c86cffec0a60b9ea0cf0d0cbb3aec722ac17a8d89dc83a12ff2974406`.

## Limitations

- This is a narrow destination-safety habit, not all of piece safety.
- Silence does not mean the move was safe in every other tactical sense.
- Plan and mastery may use only this exact fact. Other piece-safety subtypes
  keep their existing authorization grades.
- Promotion-capture exchanges are calculated for comparable measurement but
  stay silent for diagnosis and puzzle admission; that rare edge family was
  not represented in the sealed promotion packet.
