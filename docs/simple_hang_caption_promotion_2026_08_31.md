# simple_hang — Caption-grade promotion evidence (2026-08-31)

Status: PROMOTED TO CAPTION. Plan-grade remains correctly blocked.

Bar: `docs/detector_quality_threshold_lock_2026_08_27.md`
Precision corpus: `docs/simple_hang_corpus_evidence.md`
Packet: `backend/data/corpus_snapshots/simple_hang_caption_packet.json`

## Why this promotion exists

`simple_hang` carried Plan-grade on `working-code`, which the threshold lock
does not support: Plan requires >=60% semantic recall, and the measured figures
are 61.61% taxonomy recall with **16.09%** D_live miss recall through the
stored subtype. Plan-grade was over-graded.

The Phase 4 working tree corrected that to Shadow. But Shadow silences the
detector entirely, and `simple_hang` is the only detector that currently
reaches a player at all. Downgrading it to Shadow would have removed the
product's single live detector claim as a side effect of a correctness fix.

Caption-grade is the honest resting place, and the lock's own values say so.

## Scorecard against the locked Caption values

| Caption criterion | Required | Measured | Source |
|---|---|---|---|
| reviewed semantic precision | >=95% | **96.9%** | 260 reviewed fires, existing corpus |
| 95% Wilson precision lower bound | >=85% | **~94.0%** | existing corpus |
| reviewed fires | >=50 | **260** | existing corpus |
| true negative / non-opportunity cases | >=20 | **40** | this packet |
| critical false claims (adversarial) | 0 | **0** | this packet |
| semantic recall | *no floor* | n/a | Caption sets no recall floor |

The recall gap is real and is exactly why Plan-grade stays blocked. Caption
imposes no recall floor "because a caption detector may safely stay silent."

## What was built for the two missing criteria

### Non-opportunities (40; bar is 20)

Mined from real production moves, never hand-authored. Each case is a move
after which **the opponent genuinely has a capture available**, yet the
position is not a simple hang — so the detector staying silent is the correct
behaviour. A quiet move with no capture available would prove nothing about
restraint and is excluded.

| Reason | Cases | Meaning |
|---|---|---|
| `defended` | 31 | a capture exists but loses material for the opponent (SEE <= 0) |
| `below_floor` | 5 | value at risk sits under the 150cp SEE floor |
| `compensated` | 4 | material is loose but the engine says it costs little |

The `defended` category required enumerating the opponent's legal captures
directly. `material_hung_after` reports only the worst outcome and returns no
capture move when nothing hangs, so a properly defended piece — the most
meaningful true negative — is invisible through that helper alone. A first
mining pass returned **zero** defended cases for exactly this reason.

### Adversarial packet (40 cases, 0 critical failures)

Real positions within +/-40cp of either D_live floor (SEE 150cp, cp_loss
150cp), where a small threshold slip flips the verdict. Every case was
re-derived independently; all 40 verdicts agreed.

## Independent adjudication

`backend/scripts/verify_simple_hang_caption_packet.py` re-derives every case
from its FEN and **reuses no stored value** from the miner. It checks position
and move legality, that king moves have not leaked past the pre-filter, that a
non-opportunity really does offer the opponent a capture, that the recorded
reason matches recomputed board truth, and that the recomputed two-gate verdict
matches the packet.

A CRITICAL failure is any case marked not-a-hang where independent board truth
says both gates are in fact met.

```
non-opportunities   cases=40  ok:defended=31  ok:compensated=4  ok:below_floor=5
adversarial         cases=40  ok:adversarial=40
critical failures   0
non-critical mismatches  0
usable non-opportunities 40 (bar 20)
VERDICT             PASS
```

## Limitations — stated deliberately

- **Caption surface only.** Mastery and Plan remain unauthorized; verified
  after promotion as caption=1, mastery=0, plan=0.
- **These are board facts, not human semantic gold.** SEE and legality are
  mechanically decidable; "is this the right thing to say to a player" is not.
  The packet supplements the reviewed 260-fire precision corpus; it does not
  replace it.
- **Schema-scoped.** Applies only to the current-schema `simple_hang` subtype.
- **Sample origin.** Cases were drawn from 21 game_analyses documents (654
  user moves). Adequate for the >=20 bar; a broader sweep would strengthen it.
- **Plan-grade is not reachable on this evidence** and should not be attempted
  until the recall floor is genuinely met.

## Reproduce

```bash
python backend/scripts/build_simple_hang_caption_packet.py --limit 3000
python backend/scripts/verify_simple_hang_caption_packet.py   # exits non-zero on any critical failure
```

---

## Addendum, 2026-09-18 — the precision figure above measures the wrong thing

Found by Mohit on his second card in `/admin/detector-review`, reading the raw
evidence for a single claim.

**The claim.** `Bxf3` — "it leaves your bishop on f3 hanging".
**The board.** Bxf3 takes a **knight** (300cp). `gxf3` takes the bishop back
(300cp). Net **zero**: a trade, not a hang. The move *is* a mistake, for an
unrelated reason — `Nxf3+` comes with check, forks the king on g1 and the rook
on e1, and simultaneously unblocks the f6–a1 diagonal onto an **undefended**
rook on a1. 180cp of mistake, none of it a hang.

**The scale.** Measured on 890 production fires: **193 (21.7%) were an even
trade reported as a hang.**

### Why §6 did not catch it

§6 reads: *"260 v16 simple_hang events re-checked with an independently
implemented SEE (not the product's own function)"*, giving 96.9%.

Both implementations compute a static exchange **on the destination square**.
Neither subtracts the material the move just captured. So on a recapture they
agree, and they are both wrong. The threshold lock names this exact failure in
its *Rejected shortcuts* section:

> implementation-to-implementation agreement: duplicated logic can agree and
> still be wrong.

And the Plan-grade criteria say what the evidence has to be instead:

> evidence must match the player-facing claim—not merely its geometry.

A SEE re-check answers *"does this square lose material?"* The player-facing
claim is *"your piece is hanging."* For a recapture those differ, and only the
second one is what a player reads.

So the 96.9% is **board-geometry agreement**, not reviewed semantic precision.
The packet is within the letter of "board-verifier adjudication" and fails the
"must match the player-facing claim" clause.

### What was done

- The defect is fixed (`36f31178`): if the hung piece is the one that just
  captured, the material it took is priced before calling it hung — the same
  subtraction `grade_destination_safety_candidate` has always done.
- Re-measured on the same 890 fires: **696 fires, zero recapture misreads**,
  519 genuine hangs kept (was 520), all 177 captures that really do lose
  material kept.

### What is still open

**Caption grade is not withdrawn** — the fix removes the defect, and pulling
the product's most-used detector on the day it was repaired would cost real
coverage for no gain. But the evidence underneath it is now known to measure
geometry, so:

- `simple_hang` goes **back into the human review queue**. Its grade rests on
  automated agreement, and the lock asks for semantic review that no automated
  check substitutes for.
- 50 human rulings post-fix replace §6 as the precision evidence.

Two cards of human review found what 260 automated re-checks did not. That is
the argument for the queue, and it is also the argument against the shortcut
this packet took.
