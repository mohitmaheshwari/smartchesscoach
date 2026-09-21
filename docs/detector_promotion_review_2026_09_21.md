# Detector promotion review — 2026-09-21

**For: Mohit and Farhan. Decision required — I cannot make this one.**

## Why you are being asked

Measured on production today: of **36 topics users actually miss, exactly 1
can become a coaching plan.**

```
CAN become a coaching plan:  1   -> piece_safety
CANNOT:                     35   -> endgame_technique, king_safety, missed_mate,
                                    knight_outpost, queen_fork, clearance_then_check, ...
```

That is why the coach says the same sentence to everyone. From the
real-user report:

```
maheshjangid   268 analysed   coach: piece safety   focus: piece_safety
bhutramohit    606 analysed   coach: piece safety   focus: piece_safety
naveenlal.79    14 analysed   coach: piece safety   focus: piece_safety
```

A 606-game player and a 14-game player get the same coaching, because it is
the only coaching the gate permits. Everything built underneath — the phase
profile, the concept test, the curriculum — inherits that one-word
vocabulary.

`_AUTHORIZATIONS` is doing exactly what it was built to do. The queue behind
it has simply not moved since August.

## What is being proposed

Two detectors, chosen by measured volume and by where the evidence is
strongest. Neither has been promoted; `_AUTHORIZATIONS` is untouched.

| | `same_piece_better_square` | `endgame_loose_pawn_attack` |
|---|---|---|
| stored fires | 9,736 | 5,973 |
| players / games | 58 / 6,476 | 58 / 4,104 |
| reviewed fires | 200 | 200 |
| **semantic precision** | **100.0%** | **100.0%** |
| Wilson lower (z=1.96) | **98.12%** | **98.12%** |
| independent opportunities | 1,200 found | 1,200 found |
| semantic recall | 61.0% | 45.5% |
| true negatives tested | 60 | 60 |
| **detector fired on a true negative** | **0** | **0** |

For comparison, the one packet that passed
(`destination_safety_exact_plan_promotion_2026-09-01.json`): precision
100.0%, Wilson lower 98.12%, recall 82.5%, 0 fires in 60 true negatives.

**Precision and the adversarial result match the passing packet exactly.
Recall is lower. That is the honest gap, and it is discussed below.**

## What "verified" means here, and what it does not

The verifiers live in
`backend/scripts/build_promotion_packets_2026_09_21.py`. They are written
from each detector's stated claim and **do not import
`services/shape_detectors.py`**. Agreement is two implementations agreeing.

**It is machine verification of a board claim. No human has looked at these
positions.** That is precisely the judgement this review is for, and it is
not something the packet can supply.

### One thing I got wrong, recorded because it changes how to read this

My first verifier for `same_piece_better_square` additionally required the
extra target to be **undefended**, and required strictly more targets by
count. It measured **34.5% precision**, which I was about to report as a
detector failure.

It was not a detector failure. The detector counts any enemy non-king piece
and requires only a non-empty set difference — which is exactly what the
caption tells the player: *"it also hits the {piece} on {square}."* The
stricter verifier was testing a claim nobody makes. Corrected, the same 200
fires verify at 100%.

The lesson for this review: a precision number is only meaningful against
the claim the **caption** makes to the player, not against a stricter one an
engineer finds reasonable.

## The recall gap, honestly

61.0% and 45.5%, against 82.5% for the packet that passed.

Recall here is a **lower bound on quality, not an upper bound on coverage**.
The verifier models the caption's claim only; the shipped detector
additionally requires the moved piece to **survive** on the engine's square
(`_mover_dies_on_destination`). A position where the claim holds but the
piece is immediately lost satisfies the verifier and is correctly declined
by the detector — and counts against recall here.

So a share of the gap is a safety condition working. I have not separated
how much, and I am not going to assert a number I have not measured.

Checked separately so it cannot be blamed on bookkeeping: **27.5% of
analysed moves already carry more than one concept** (max 8), so recall is
not being depressed by single-label storage.

**If the review treats 82.5% as the bar, these do not clear it.** That is a
legitimate place to say no.

## Stated limitations

- `chess.Board.attackers()` is **pseudo-legal**: a pinned defender still
  counts as defending. "Undefended" is therefore conservative — it can
  suppress real fires (costing recall) but cannot invent them.
- Recall is measured over stored mistakes only. Positions never analysed are
  out of scope.
- No human review of the positions themselves.

## Why these two

`same_piece_better_square` is the **most-observed thing we refuse to coach**
— 9,736 instances across 58 players.

`endgame_loose_pawn_attack` is aimed at a measured gap. Phase profile for
`user_8b599930d7ef`, against 41–52 other players:

```
phase         you     median    rank
opening       5.9%     7.2%     better than 28 of 52
middlegame   11.6%    13.5%     better than 32 of 52
endgame      12.1%    11.1%     better than 13 of 41   <- below median
```

Endgame is the one phase where that account is worse than its peers, and
`endgame_technique` is currently blocked at the gate.

## The decision

For each detector, one of:

1. **Promote to Plan** — edit `_AUTHORIZATIONS` with `evidence_ref` pointing
   at the snapshot, plus rationale and limitations.
2. **Promote to Caption only** — the claim may be stated in a caption but
   may not drive a plan. Lower risk; does not unblock home.
3. **Reject** — say which number is short and what would satisfy it.

Snapshots:
- `backend/data/corpus_snapshots/same_piece_better_square_plan_promotion_2026-09-21.json`
- `backend/data/corpus_snapshots/endgame_loose_pawn_attack_plan_promotion_2026-09-21.json`

Regenerate with
`python backend/scripts/build_promotion_packets_2026_09_21.py` — read-only,
no production writes, no engine runs.

## Draft entries, for a human to paste, edit or discard

Not applied. Grades left as `PLAN` only because that is what is being
proposed; the reviewer sets them.

```python
"gap:piece_activity:same_piece_better_square": Authorization(
    grade=QualityGrade.PLAN,
    evidence_ref=(
        "backend/data/corpus_snapshots/"
        "same_piece_better_square_plan_promotion_2026-09-21.json"
    ),
    rationale=(
        "Same piece, same origin square; from the engine's destination it "
        "attacks an enemy non-king piece it does not attack from the played "
        "square. Verified by an independent implementation of the caption's "
        "claim on 200 stored fires: 100% semantic precision, Wilson lower "
        "98.12% at z=1.96, and 0 fires across 60 positions where the claim "
        "does not hold."
    ),
    limitations=(
        "Semantic recall measured at 61%; the shipped detector also requires "
        "the mover to survive on the destination, which the verifier does "
        "not model, so part of the shortfall is a safety condition working.",
        "Machine verification of a board claim only; no human reviewed the "
        "positions.",
    ),
),

"gap:endgame_technique:endgame_loose_pawn_attack": Authorization(
    grade=QualityGrade.PLAN,
    evidence_ref=(
        "backend/data/corpus_snapshots/"
        "endgame_loose_pawn_attack_plan_promotion_2026-09-21.json"
    ),
    rationale=(
        "At most 12 non-pawn pieces; the engine's best move is by a non-pawn "
        "piece that captures or lands attacking an undefended enemy pawn. "
        "Verified independently on 200 stored fires: 100% semantic precision, "
        "Wilson lower 98.12% at z=1.96, 0 fires in 60 true negatives."
    ),
    limitations=(
        "Semantic recall measured at 45.5%.",
        "'Undefended' uses pseudo-legal attacker counts, so a pinned defender "
        "suppresses a fire; conservative, never inventive.",
        "Machine verification only; no human reviewed the positions.",
    ),
),
```
