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
