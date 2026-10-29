# The differential why engine — scope

**Status: DRAFT, awaiting Mohit's sign-off. No code written.**

Written 2026-10-29, after six attempts to add positional reasons to the why
button failed in one day, all of them the same way.

---

## The one-line version

Stop asking *what is true about the move you played*. Ask **what is true about
the engine's preferred moves and not true about yours** — and the reverse. A
fact that is true of both is not a reason.

---

## Why this, why now

The why button was run as the real endpoint over **320 faulted positions** —
both sides, 40 per severity tier, depth 18, 8 candidates, the same code path
`/api/coach/why/{game_id}/{move_number}` executes. It explained 242 and went
silent on 78.

| | asked | explained | silent |
|---|---|---|---|
| your inaccuracies | 40 | 22 | **18 (45%)** |
| their inaccuracies | 40 | 25 | 15 (38%) |
| their mistakes | 40 | 27 | 13 (33%) |
| your mistakes | 40 | 33 | 7 (18%) |
| serious + blunders, both sides | 160 | 135 | 25 (16%) |
| **all** | **320** | **242** | **78 (24%)** |

The silence tracks the band exactly, and the cause is visible in the mechanism
census: **`WINS_MATERIAL` produced 190 of the 242 answers**, `MATE` 14,
`FORCES_RETREAT` 32, `TRAPPED` 4, `PROMOTES` 2, and **`FORK` fired zero times
in 320 positions**. All six existing mechanisms ask *what changed hands*.
Blunders are material, so the material question answers them. Inaccuracies are
positional, so nothing in the list fits.

### The failure this scope exists to avoid

Six positional mechanisms were attempted on 2026-10-29 and five died with an
identical signature — **the engine's own best move had the same property**:

| family | the mistake | the engine's best | shared property |
|---|---|---|---|
| exposed own piece | Na4 | **Nd5** | vacates the same square |
| king pressure | Ka2 | **Kb1** | both raise it; White was in check with only those two moves |
| wing pawn push | b4 (59cp) | **h3** (0cp) | same position, same side, identical verdict |
| released attack | Kf3 | **Kf4** | releases the same square |
| released attack | Qf5+ | **Qh5+** | releases the same square |

That is not five coincidences. A property measured on one move is nearly
independent of the evaluation gap between two moves, so a good move shares it
about as often as a bad one. **The level was wrong, not the chess.**

---

## What it will be

Three layers. Each is deterministic; nothing decides what a move *means*.

### Layer 1 — the principle library

A principle is a pure function: `(board, move) → fact or nothing`. No engine,
no evaluation number, no LLM. Instant, and the same answer every time.

Four at launch, all four derived from one position
(`rnbqk2r/pppp1ppp/5n2/2b1p3/2P5/2N3P1/PP1PPP1P/R1BQKBNR w KQkq - 1 4`) and all
four verified on that position:

**1. `develops_a_minor`** — the move starts from a minor piece's home square
(b1/c1/f1/g1, or b8/c8/f8/g8).

**2. `frees_a_buried_minor`** — a minor of ours that had **zero** legal moves
before this move has at least one after it.

> This is "makes space for a minor to come out", read literally, and the
> literal reading is what makes it work. A first attempt counted the *total*
> squares available to minors still at home, and that version scored `e3` and
> `e4` as freeing moves, because both vacate e2 and hand the g1 knight one
> extra square — while burying the c1 bishop. A knight with f3 and h3 already
> does not need e2; a bishop with nothing needs a diagonal. **Zero to
> non-zero, per piece. Never a total.**

**3. `sells_a_square_forever`** — after this move, no pawn of ours can ever
control a named square again. A pawn guards a square from one rank behind it on
an adjacent file, so the test walks the two relevant files and asks whether
both pawns have marched past their guarding ranks. Permanent in the strict
sense: pawns do not go backwards.

**4. `buries_own_piece`** — a piece of ours that had legal moves before has
none after, or the move lands on the only open line of one of our own pieces.

### Layer 2 — the differential selector

**This is the "common strategy that wraps it all" and the heart of the design.**

For one position:

1. Take the engine's top *k* moves and the move played.
2. Run **every** principle against all of them.
3. Keep only the principles that **split** them:
   - true of the good moves, false of the played move → **"why the better move
     was better"** (`direction: missed`)
   - true of the played move, false of the good moves → **"what your move did"**
     (`direction: received`)
4. A principle that fires on both sides is **silent by construction.**

The negative control stops being a thing we remember to run afterwards and
becomes the thing that selects. The `Na4` failure below cannot happen: `Na4`
would be rejected not because someone noticed, but because it separates
nothing.

### Layer 3 — the ablation ranker

When more than one principle splits, rank by how much of the loss each one
accounts for: change that one thing, re-search, measure what comes back.

Verified on the `Nc6` position
(`rn3rk1/1ppq1pp1/3pb2p/p3p3/P1B1P2B/N1PP3P/1P3KP1/R2Q2N1 b - - 5 14`):
teleporting the knight to a6 and changing nothing else recovered **100%** of
the 64cp cost; to e7 recovered 0; to c5 recovered 137.

On the `e4` position it would have corrected me: I read the board and concluded
the blocked bishop diagonal was the reason. The ablation says the diagonal is
**14 of 66cp**. Had the ranking come from my reading, the card would have led
with a footnote.

**Two conditions on every probe, both learned the hard way:**

- **A fresh engine process per probe.** The same position evaluated twice in one
  session returned −28 and −40, because the transposition table carries between
  calls and the second look is informed by the first. With a fresh process the
  re-measure was byte-identical (0 difference on both re-checks).
- **Clear the en-passant square before teleporting a pawn.** Placing a pawn on
  the ep target square makes the position illegal, and the first run of the
  `e4` ablation reported every probe "invalid" for that reason alone.

### Then the sentence

The LLM phrases what the selector proved, and only that. This is the step your
requirement describes that **does not exist today** — the button's text comes
from twelve fixed templates in `_phrase`, with no model anywhere in the path.

---

## Worked example — the position Mohit brought

`rnbqk2r/pppp1ppp/5n2/2b1p3/2P5/2N3P1/PP1PPP1P/R1BQKBNR w KQkq - 1 4`, White
played **e4**.

**What the button says today:** *"Na4 chases their bishop."* `Na4` is the
engine's **sixth** choice at −15, fifty centipawns below best. The button walked
past `Nf3` (+35), `Bg2` (+29), `d3` (+15), `a3` (−3) and `e3` (−10) — none of
which chases or wins anything, so no mechanism fires — and stopped at the first
move it could describe. **On a positional move the current engine does not go
quiet; it recommends a worse move because that move has a story.**

**What the differential selector would say.** Engine order, fresh process per
position, graded on the canonical floors in `services/severity.py`:

| move | eval | cost | grade | principle |
|---|---|---|---|---|
| Nf3 | +35 | 0 | good | **develops a minor** |
| Bg2 | +29 | 6 | good | **develops a minor** |
| d3 | +15 | 20 | good | **frees c1 (0 → 5 squares)** |
| a3 | −3 | 38 | inaccuracy | none |
| e3 | −10 | 45 | inaccuracy | none |
| Na4 | −15 | 50 | inaccuracy | none |
| h3 | −18 | 53 | inaccuracy | none |
| **e4** | **−37** | **72** | inaccuracy | none |

**Eight moves, zero exceptions, split exactly at the 30cp line.** So the
`missed` answer is *get a piece out, or let one out*.

And the `received` answer is separate and also true: **e4 sells d4 for good.**
Pawns that can still come to guard d4 — before the move: `e2`. After `e4`:
**none**, because c4 and e4 have both marched past c3 and e3. Black already
controls d4 twice (bishop c5, pawn e5); White controls it zero times. If a
knight reaches d4, White's only attacker is a piece, and no White pawn can ever
challenge it.

Two different sentences, both true, from the two directions the engine already
has.

---

## The gates

**1. It must separate.** No principle may speak on a position where it is also
true of the engine's preferred moves. Enforced by the selector's design, not by
a review step.

**2. Phase.** "Get your minors out" is an opening statement. In a four-piece
endgame it talks nonsense. Every principle declares the phase it applies to.

**3. Subtract the non-mistakes first.** Measured: **13 of the 78** silent
positions were never mistakes — one stored at **8407cp** that a fresh depth-18
search calls the **best move in the position**, three where the played move is
the fresh engine's own choice, seven inside 30cp of best. Two gates: the played
move is the engine's own choice, or the position is a forced win both before and
after and only the mate distance moved. Asking "why was this wrong" about a move
that was not wrong is how fiction gets generated.

---

## The pass mark, fixed before any code

A principle enters the library only when, measured over **at least 200
positions** and every legal move in each:

1. **It separates.** It is true of engine-approved moves materially more often
   than of faulted ones, or the reverse, with the gap large enough not to be
   noise. A 19%-vs-4% split survived gating down to 1 position in 68, so the
   bar is on the gated number, never the raw one.
2. **It stays silent on the engine's own best move** — the test that killed five
   families in one day.
3. **It has a positive control.** A zero fire rate is only evidence when the
   principle is shown firing correctly somewhere. One agent reported 1-in-398
   precision today and then retracted it: the single fire was the position the
   test had been built from, seeded into its own control corpus.
4. **Its control corpus excludes the positions it was designed on**, and
   anything a few plies from them.

---

## What this will NOT do

- It will not invent a reason. When nothing separates, the answer is
  `found: false` and the card says so. That is the bug the button was built to
  remove and this must not reintroduce it.
- It will not read an evaluation number as a reason. "The eval dropped" is the
  thing we already know and cannot teach from.
- It will not rank by list position. Ranking is the ablation's measurement, so
  knowing one more fact can never route us to a worse answer.
- It will not grow the vocabulary where a horizon is the real problem.
  `_LINE_PLY = 6` in `punishment_resolver.py` means every current mechanism
  reads six plies; material landing at ply 20 is invisible to all of them, and
  that is a window, not a dictionary.
- It will not run on the page render. This lives behind the button, which is the
  only coaching path allowed to take seconds.

---

## Open questions for Mohit

1. **Which principle do we write after these four?** The audience is 600–1500,
   and that is a coaching judgement, not a computation. My own guess would be
   king safety, and I have no evidence for it.
2. **When both answers exist, does the card show both?** On the `e4` position
   there are two true, different sentences — "a piece was waiting to come out"
   and "you gave up d4 for good". Two sentences, or lead with one?
3. **Does the 60-word cap allow two?** It currently drops whole sentences.
4. **`e3` costs 45 and `e4` costs 72 — both grade `inaccuracy`.** The word is
   the same for a move that sells a central square and one that does not. Should
   the band stay as it is and let the reason carry the difference, or should the
   grade reflect it?
5. **How much engine time may one button press spend?** Today it is 5–7 seconds
   for 8 candidates plus a post-move line. Each ablation probe adds roughly 0.7s
   with a fresh process.

---

## Appendix — what has been measured, and what has not

**Verified this session**, with the command output in the session record:

- 320 positions through the real why path: 242 explained, 78 silent, per-tier
  table above; mechanism census including `FORK` at zero.
- The `Na4` answer on Mohit's `e4` position, from the real `explain()`.
- The eight-move table for that position, fresh engine per move, re-measured
  identically on `e3` and `e4`.
- The d4 pawn-geometry walk: `e2` before, none after `e4`, `e3` after `e3`.
- `develops_a_minor` / `frees_a_buried_minor` separating all eight moves at the
  30cp line, with the per-piece zero-to-non-zero definition.
- The `Nc6` ablation: a6 recovers 100% of 64cp, e7 recovers 0, c5 recovers 137.
- 13 of 78 silent positions are not mistakes by a fresh depth-18 search.
- `_LINE_PLY = 6` at `punishment_resolver.py:64`.

**Not verified:**

- That any of the four principles holds beyond the positions it was derived
  from. All four come from a single position, and every family that died today
  looked this clean on its first sample. **This is the gap the pass mark exists
  to close, and no code should ship before it is closed.**
- That the remaining ~52 of the 66cp on `e4` is specifically the cost of not
  developing. The null probe shows `e4` is worth about nothing against passing
  while `Nf3` is worth +63, which is consistent with it, but consistency is not
  proof.
- Whether `d3` outranks `e3` because it frees the bishop or because it keeps
  `e2–e3` in reserve. Both are true on the board; which carries the evaluation
  is unmeasured.
