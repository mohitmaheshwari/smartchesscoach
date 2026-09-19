# discovered_attack — Caption-grade promotion evidence (2026-09-19)

Status: PROPOSED. Plan-grade remains correctly blocked (no recall measurement).

Detector: `tactic:discovered_attack_with_stored_payoff`
Bar: `docs/detector_quality_threshold_lock_2026_08_27.md`
Reviewer: Mohit, via `/admin/detector-review`

---

## Why this one is different from the packets before it

`simple_hang`'s packet claimed 96.9% from "260 events re-checked with an
independently implemented SEE". Both implementations priced the destination
square and neither subtracted what the move had captured, so on a recapture
they agreed and were both wrong. 21.7% of its production fires were even
trades reported as hangs, found on 2026-09-18 by a human reading one card. See
the addendum in `docs/simple_hang_caption_promotion_2026_08_31.md`.

This packet does not repeat that. **The 52 precision fires are human semantic
review**, one position at a time, on real games, with the board and both engine
lines in front of the reviewer. Board verification is used for the negative and
adversarial sets — which the lock permits — and never for the precision figure.

---

## Scorecard against the locked Caption values

| Caption criterion | Required | Measured | Source |
|---|---|---|---|
| independently reviewed semantic precision | >=95% | **100%** | 52 human rulings |
| 95% Wilson precision lower bound | >=85% | **93.1%** | 52/52 |
| reviewed fires | >=50 | **52** | `detector_claim_rulings` |
| true negative / non-opportunity cases | >=20 | **30** | this packet |
| critical false claims (adversarial) | 0 | **0** | this packet |
| semantic recall | *no floor* | not measured | Caption sets no recall floor |

52 true, 0 wrong, 4 abstentions. Abstentions are excluded from the denominator
on purpose: a reviewer declining to call one is not evidence either way.

---

## What the reviewer was shown

Each card carried the position the claim is about, the move played (red arrow),
the move claimed better (green), **the line the move opens** (yellow), both
engine continuations as clickable move lists that walk the board, and the game
it came from. The reviewer answered one question: is this statement true?

---

## The four abstentions, and what they produced

Mohit marked 4 of 56 "unsure". All four were the same shape, and reading them
is what produced the gates this packet rests on:

| card | why it was hard | resolution |
|---|---|---|
| `Rc1 / Bf1` | target d7 defended by the queen on e6 | **not a fire** — wins nothing |
| `Nxf2 / Nxb2` | target d2 defended by the knight on f3 | **not a fire** — wins nothing |
| `e5 / Nxh7` | target h6 defended by the g7 pawn; nets +100 after a bishop-for-knight trade | **not a fire** — a trade, not a win |
| `Bxd7 / Bg5` | target h1 **undefended**, SEE 500 | **a true fire** |

Two gates came out of those and are now in the serving path:

1. **The detector's own `verified` flag is honoured.** `build_discovered_attack_proof`
   returns a bundle even when its independent verifier rejects the payoff. The
   queue had been rendering those as claims: 50 of 60 sampled (83%) were
   candidates the detector did not stand behind.
2. **The target must be winnable by >=200cp.** Chosen from the distribution,
   not by taste: of 11 claims, 8 won the target outright, 2 won 200-299, and
   exactly one sat at 100 — the `Nxh7` card above.

---

## True negatives (30, bar 20)

Drawn in corpus order from 2,537 engine-flagged mistakes (cp_loss >= 100)
across 400 analyses — not selected. Every one is a move the engine calls a
mistake where this detector stays silent:

- **2,488** have no vacated-ray geometry at all
- **41** open a ray, but the stored line never collects the target

Snapshot: `backend/data/corpus_snapshots/discovered_attack_caption_packet_2026_09_19.json`

---

## Adversarial packet (0 critical false claims)

The near-threshold set is the four abstentions above — positions that look
exactly like a discovered attack. Re-run against the serving path:

| case | expected | served | |
|---|---|---|---|
| `Rc1 / Bf1` | silent | silent | OK |
| `Nxf2 / Nxb2` | silent | silent | OK |
| `e5 / Nxh7` | silent | silent | OK |
| `Bxd7 / Bg5` | fires | fires | OK |

**Critical false claims: 0.**

---

## The caption this authorises

The detector has never had a player-facing caption; the grade authorises one.
Built only from board facts the detector already holds:

> Your own knight on e5 stands in front of your queen on f6. Nxf3+ moves it
> away with check, and the queen then looks straight at the rook on a1 — which
> nothing defends. When your own piece blocks your queen, rook or bishop, look
> at what sits at the far end of that line. That is a discovered attack.

Geometry, then what it uncovers, then the scan that transfers. The motif's name
is last, as a label for something the player has just been shown. 54-60 words,
inside the 60-word cap so the renderer cannot silently eat the closing
principle. Clean through `pwc_coaching_lint`, which now bans `engine`,
`computer`, `stockfish` and `centipawn` in anything a player reads.

---

## Limitations, stated

- **Caption surface only.** Plan-grade needs 200 reviewed fires and >=60%
  semantic recall on independently selected opportunities. Recall is not
  measured here at all.
- **The precision sample is not representative by construction.** The queue
  serves least-certain first, so a reviewer meets the hard cases before the
  easy ones. That can only depress a measured precision, never inflate it —
  but the 100% is over a sample skewed hard, not a random draw.
- **Negatives and adversarial cases are board-adjudicated**, not human semantic
  gold. They supplement the human precision figure; they do not substitute for
  it. This is the distinction `simple_hang`'s packet lost.
- **The filters are recent.** The 52 rulings span cards served before and after
  the `verified`-flag and winnable-target gates. Since both gates only remove
  claims, rulings made before them were on a strictly larger set — the measured
  precision is if anything conservative.
