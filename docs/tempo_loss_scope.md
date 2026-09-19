# Tempo loss in the opening — scope

Status: DRAFT, awaiting Mohit's sign-off. No code until then.
Plain English. 2026-09-19.

---

## Where this came from

Reviewing a `left_book` card — *"You played Ng5 here and left the book. Nxd4 is
the move, and it is also what the engine plays"* — Mohit said the caption was
wrong twice over: never name the engine, and the real lesson is something else.

> *"maybe because it gives opponent tempo and you keep moving same piece
> multiple times in opening"*

The game proves him exactly right:

```
2. Nf3     knight g1 -> f3
4. Ng5     knight f3 -> g5     the same piece, again
5. Nf3     knight g5 -> f3     and straight back
```

Three knight moves to end up where it already was. Black used those moves for
`Nh6` and `Bc5`. And the d4 pawn White was down is still sitting there.

"You left theory" is a fact about a database. "Your knight went out and came
home while Black developed twice" is a fact about **their game**, and it
transfers to every game they will ever play.

---

## The rule this has to obey

Mohit's three, which are really one:

1. **The engine gates.** A detector may only speak about a move the engine says
   is actually bad.
2. **The board explains.** The why must be provable from the position.
3. **The caption names neither.** No "the engine says", no centipawns.

Rule 1 is not optional here, and the proof is on the board. The *identical*
pattern — knight's second move in the opening, pieces still at home:

| position | Ng5 |
|---|---|
| Two Knights (`1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6`) | **the engine's TOP move, +26cp** |
| the card's position (`1.e4 e5 2.Nf3 Nc6 3.d4 exd4`) | **not in the top four**; `Nxd4` is +25cp |

A geometry-only detector calls the Two Knights main line a beginner mistake.
This scope exists because Mohit caught that before it was built.

---

## What the player sees

    ┌──────────────────────────────────────────────┐
    │  [ board: knight on g5, arrow f3->g5 in red, │
    │            arrow f3->d4 in green ]           │
    │                                              │
    │  Your knight was already on f3. Ng5 moves    │
    │  it again — and two moves later it is back   │
    │  on f3, while Black got Nh6 and Bc5 in for   │
    │  free.                                       │
    │                                              │
    │  Nxd4 instead takes back the pawn you are    │
    │  down.                                       │
    └──────────────────────────────────────────────┘

Every clause is checkable against their own moves. Nothing is asserted that the
board does not show.

---

## The funnel, measured before designing it

600 analyses:

| gate | surviving | note |
|---|---|---|
| moved an already-developed piece, 2+ still at home | **1,452** | ~2.4 per game — pure noise, fires on good moves |
| **+ engine says it lost >=100cp** | **383** | the engine gate removes 74% |
| **+ the piece returned to a square it had left** | **27** | the clearest cases, but rare |

**1,452 is why rule 1 exists.** 383 is a workable volume. 27 is the shape that
proves itself.

---

## The gate that is NOT yet measured, and must be before any code

Of those 383, an unknown share are bad for a **different and simpler** reason.
One from the sample is `bishop c4->f7, cp_loss 379` — almost certainly a
bishop given away on f7. The lesson there is "you lost a bishop", not "you
moved it twice". Tempo is incidental.

So a third gate is required: **tempo only speaks when no simpler material
explanation does.** The same precedence the mate gate has over hangs, and that
`left_book` now has when a move drops a piece.

**First task, before writing the detector:** run `simple_hang`, the motif
proofs and the mate gate across those 383 and count how many are left. If the
residue is small the detector is not worth building; if it is most of them, it
is. That number decides whether this scope proceeds, and I do not have it yet.

---

## What has to be true for a claim to fire

1. Move number <= 12, and it is the player's move.
2. The piece is a knight, bishop or queen that has **already moved** this game.
3. At least 2 of the player's pieces are still on their starting squares.
4. **The engine says the move lost >= 100cp.**
5. **No simpler explanation fires** — no hang, no missed motif, no mate swing.
6. The caption states only what the board shows: where the piece was, where it
   went, where it ended up, and what the opponent developed meanwhile.

The "returned to a square it left" case (27) is a **stronger** variant, not a
requirement — when it holds, the caption can say so and the proof is complete.

---

## How we know it worked

- **Precision:** through the review queue like every other detector. Shadow
  first, and Mohit rules only the cases the board cannot settle.
- **The trap to watch:** a main-line move captioned as a beginner error. The
  Two Knights `Ng5` position goes in the regression pack as a case that must
  **never** fire.
- **Coverage claim to avoid:** this is not a replacement for `left_book` until
  measured. It is a candidate.

---

## Risks

- **Incidental attribution.** The biggest one, and it is gate 5. A move can be
  bad and also happen to be a repeat move. Unmeasured today.
- **Retreats that are correct.** A piece moving back because it was attacked is
  good play, not lost tempo. The engine gate covers most of this; the
  regression pack must include one.
- **Volume.** 383 in 600 analyses is roughly one every other game. If gate 5
  leaves 300 of them, it is a frequent claim and needs to be right.

---

## Not in this scope

- Replacing `left_book`. It stands down for material blunders already; whether
  tempo should take more of its ground is a later decision with data.
- Any player-facing caption. This lands in shadow, like everything else.
