# Tempo loss in the opening — scope

Status: DRAFT, awaiting Mohit's sign-off. No code until then.
The blocking measurement is done — see the funnel. Ready for a yes/no.
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

**MEASURED 2026-09-19.** Ran `simple_hang`, both motif proofs and the mate
gate across all 383:

| what speaks | count |
|---|---|
| **RESIDUE — tempo is the best explanation we have** | **290 (75.7%)** |
| a hung piece speaks instead | 85 (22.2%) |
| a mate swing speaks instead | 4 (1.0%) |
| a missed motif speaks instead | 4 (1.0%) |

290 in 600 analyses is roughly one case every other game. **The gate is
answered: this is worth building.**

One honest caveat on that 290. It means *nothing else we have explains the
move* — not that tempo is the true cause. A move can be bad for a positional
reason we do not detect at all (a weakened square, a ruined structure), and
this would claim it as tempo. That is precisely the causal-attribution gap the
threshold lock names, and it is why the detector ships to shadow and earns its
grade through the review queue like every other one. The residue is a
**candidate** set, not a verified one.

**Then I looked at the cards, and three quarters of them were not tempo.**

Mohit asked to see the 290 rather than sign off on a number. Reading the first
eight showed the residue is not what I claimed:

| card | what the engine wants | is tempo the lesson? |
|---|---|---|
| `Ng4` | **O-O** | yes |
| `Qf5+` | `Qh5+` | no — same piece, better square |
| `Ndxf2` | `Ngxf2` | no — the other knight |
| `Bf5` | `Nxh1` | no — missed a rook |

Measured over 200 candidates:

| what the engine's answer is | share |
|---|---|
| a different, already-developed piece | 102 (51%) |
| the SAME piece, better square | 52 (26%) |
| **develops something / castles** | **46 (23%)** |

So **gate 6**: the engine's answer must be a piece leaving its starting square,
or castling. Without it three quarters of the queue would carry a tempo caption
on a move whose lesson is something else. ~67 of the 290 survive — about one
case in nine games, and every one of them is now actually about tempo:

    Ng4  -> engine wants O-O      knight g8->f6->g4
    Nb3  -> engine wants Bb5+     knight g1->f3->d4->b3
    Qd3  -> engine wants Nc3      queen  d1->f3->e4->d3, knight still on b1

The measured 290 was a real number answering the wrong question. The gate I had
written ("nothing simpler explains it") is not the same as "tempo explains it",
and only looking at the cards showed the difference.

---

## What has to be true for a claim to fire

1. Move number <= 12, and it is the player's move.
2. The piece is a knight, bishop or queen that has **already moved** this game.
3. At least 2 of the player's pieces are still on their starting squares.
4. **The engine says the move lost >= 100cp.**
5. **No simpler explanation fires** — no hang, no missed motif, no mate swing.
6. **The engine's preferred move develops a piece or castles.** Not the same
   piece on a better square, not another developed piece -- a piece coming off
   its starting square. This is the gate that makes the claim about tempo.
7. The caption states only what the board shows: where the piece was, where it
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
