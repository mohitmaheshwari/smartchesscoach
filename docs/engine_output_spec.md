# The engine's output: a specification

Mohit, 2026-10-22:

> "our engine is our backbone and spine"
>
> "you have to analyse the moves better with stockfish and give better engine
> outputs so our LLM can do a good job there"

This describes what the engine should produce for every move a player made.
It is not about captions. Prose is downstream and belongs to the LLM; this
document is about the facts handed to it.

Everything here is measured. Where a number appears, the scan that produced
it is named so it can be re-run and disagreed with.

---

## 1. What the engine's job is

For every move a player made, produce everything true and teachable about why
it was worse than the alternative, as structured facts, each provable either
on the board or in the engine's own lines.

Not one sentence. Not one reason. Everything true, ranked, with its evidence
attached — because the LLM, holding the player's history, is better placed to
choose which truth this player needs than an if-chain is.

## 2. Six things an explanation needs

| | what it answers | today |
|---|---|---|
| 1 | **How big is this** — mate, material or positional | have it |
| 2 | **What the played move allows** — their reply and what it collects | 4 plies |
| 3 | **What the better move achieves** | 2 shapes, ~27% |
| 4 | **The difference between the two futures** | the framework does this |
| 5 | **How certain any of it is** — forced, or one of several? | **nothing** |
| 6 | **What pattern this is an instance of** | coarse, 82% |

Rows 3 and 5 are where the engine is silent, and row 5 decides whether a
caption may say "they win your rook" or must say "they might".

---

## 3. What is already paid for and thrown away

Measured over 1,657 flagged moves (`flagged_fields.py`), 8,831 move
evaluations (`engine_output_audit.py`), and a clean cost run on 80 disjoint
positions (`engine_cost2.py`).

### 3.1 The principal variation is cut to a quarter

One search at depth 18 already returns a **median of 18 plies**; 90% of
positions return 12 or more. The service slices it to 4, and 89% of stored
flagged moves carry exactly 4 plies.

**Storing more costs nothing.** It is the same `info["pv"]` from the same
search. A mistake whose punishment lands on move three currently has a stored
line that does not reach it.

### 3.2 `opp_replies` is computed and never stored

`MoveEvaluation` declares `opp_replies` (the opponent's top replies with
evals) and `opp_reply_is_clear` (does the top reply beat the second by more
than the tie margin). The database has **0%** of both.

This is the only field that distinguishes *"they win your rook"* from *"they
might win your rook"* — a forced punishment from a coin flip between four
equal replies. It costs **1.34x** to compute fresh (0.881s → 1.182s per
position, 70s → 95s per game) and nothing at all if captured where it is
already calculated.

### 3.3 `threat` is present on 91.7% and nothing consumes it

Stockfish records what the opponent threatens after the played move. It is
present on 91.7% of flagged moves — and on **94% of the cards that no purpose
can currently explain**. It is the richest unused signal in the system.

### 3.4 Nothing records what else was playable

The engine reports one best move and never says whether it was the only move
or one of four equally good ones. Those are different lessons, and the second
is far more common at 600–1500. MultiPV costs **3.05x** for three lines,
4.05x for four.

---

## 4. What the better move achieves: the purpose vocabulary

Derived by reasoning over 23 mined positions, then measured on 7,346 flagged
cards (`purpose_prevalence.py`). Not invented — every entry came from a real
position first.

| | purpose | share | proof |
|---|---|---|---|
| A | moves the attacked piece to safety | 14.1% | attackers/defenders, both sides of the move |
| B | defends the attacked piece | 6.9% | the moved piece now attacks the target square |
| C | a pawn attacks a piece, gaining time | 6.4% | pawn move; its new attacks hit a piece worth more |
| D | attacks a piece that cannot escape | 21.7% | **split required — see below** |
| E | stops their passed pawn | 3.5% | the pawn's path; a square newly covered |
| G | denies their counterplay | 4.3% | checks in their line after played vs after best |
| H | activates the rook | 6.3% | open file, or more enemy pawns attacked |
| I | avoids a square they attack | 14.4% | played square is losing, best square is not |
| J | trades off their dangerous piece | 5.9% | equal-value exchange offered, safely |
| K | check that worsens the king | 7.1% | king's legal squares before vs after |
| | **at least one purpose** | **61.7%** | |
| | two or more purposes | 23.5% | |

Three findings carry more weight than the individual rates:

**The vocabulary is about danger and time, not development.** The top three —
attack something that cannot get away, do not step where they attack, move
the attacked piece — are 50.2% between them. Development is one of only two
things the engine can say today and did not appear once in 23 mined
positions.

**On 23.5% of cards there is more than one true thing to say.** Today's
`_best_purpose` is an if-chain returning the first match, so it discards
content it has already found on nearly a quarter of cards. The output must be
a list, ranked, not a winner.

**Two entries do not survive scrutiny.** `F` (supports our passed pawn) fires
on 0.4%, 28 cards — not worth a detector; fold into `E`. `D` is the largest
number and the least disciplined probe: it merges *an enemy piece is hanging*
with *every retreat lands on a square we attack*. Those are different lessons
and the name overclaims on the first. **`D` must be split and each half
measured before anything is built on 21.7%.** The trapped half belongs in
`game_ledger`'s already-proven `queen_trapped` / `rook_trapped`.

---

## 5. The residue: 38.3% that no purpose explains

Sampled 191 cards from 2,124 (`residue_mine.py`), stratified, and read on the
board. It is not a long tail of exotica. It is two mechanisms the vocabulary
does not yet name.

### 5.1 They had a threat and the move ignored it — 94% of the residue

Every residue card carries the engine's `threat`, and the shape repeats:

```
Nec6   best Nxc4   177cp   THREAT: Bxe6    the e6 bishop is hanging and the move ignores it
Ng5    best d4     167cp   THREAT: Bxg5    the move puts the knight where the bishop takes it
Qxe5   best Bxe5   108cp   THREAT: Qf4     recaptured with the wrong piece
```

The missing purpose is **"the better move answers what they are threatening"**
— and its evidence already exists in a stored field.

### 5.2 Mate, in both directions — 23% of the residue

`mate_info` carries `before` and `after`, and the transition between them is
the entire lesson:

```
before set, after None   you HAD a forced mate and missed it      (Rh2, mate in 4)
before None, after set   you WALKED INTO a forced mate            (Ke2, mate in 10)
```

These are the highest-stakes cards in the corpus — 8,000 to 10,000cp — and
the material vocabulary cannot touch them by construction.

---

## 6. The output

Per analysed move. Fields marked **new** do not exist today.

```
size        cp_loss, eval_before, eval_after
            mate_before, mate_after              (exists; the TRANSITION is new)
            category: mate | material | positional

lines       pv_after_played     full PV, not 4 plies      new, FREE
            pv_after_best       full PV, not 4 plies      new, FREE

certainty   opp_replies[]       {san, eval_cp}            new, computed+dropped
            opp_reply_is_clear  bool                      new, computed+dropped
            best_was_only_move  bool                      new, 3.05x  (optional)

threat      threat              what they threaten        exists, unconsumed
            best_answers_threat bool                      new, board-checkable

purposes    purpose[]           ranked list, each with    new
                                {kind, squares, pieces,
                                 proof, confidence}

pattern     cognitive_gap       exists, coarse
            motif               where a verified prover exists
```

### 6.1 The floor: what is emitted for EVERY move

Measured over 8,831 move evaluations, the engine is silent on most of the
game:

| | moves | no line | no best line | no threat |
|---|---|---|---|---|
| good (cp_loss < 50) | 6,160 | **91.8%** | 91.8% | 92.7% |
| small (50–99) | 1,014 | 32.1% | 32.1% | 32.1% |
| flagged (100+) | 1,657 | 7.1% | 7.2% | 8.3% |

Good moves are **70% of all moves**, and on 91.8% of them the engine outputs
an eval and nothing else. Two-thirds of a player's game comes back blank.

This is not a search cost. `eval_after` is stored on **100%** of moves, so the
search ran on every one of them and the principal variation was in the same
result object — then discarded. It is the 4-ply truncation again, at four
times the scale.

So the floor, emitted for every move whether good, small or flagged, and
every item of it always computable and always true:

```
the move        piece, from, to, is_capture, is_check, is_promotion
                what it now attacks, what it stopped covering
the position    material balance, phase, piece count
                what hangs for each side, before and after
the engine      eval_before, eval_after, cp_loss
                pv_after_played      (free — the search already found it)
                pv_after_best        (free)
                threat               (free)
the alternative the better move, and the same descriptive facts about it
```

None of that requires an interpretation. The board always has an answer to
"what did this piece start attacking, and what did it stop defending".

Above the floor sit the named purposes (§4) and the mechanisms (§5), which
are claims and must be proven. **A move with no provable purpose still comes
back with its floor** — never with nothing.

This also closes a gap the product has quietly carried: a good move currently
gets no facts at all, so nothing can tell a player what they got *right*.
The floor gives that surface its material for the first time.

### Rules that bind every field

1. **Each fact carries its own proof.** A purpose names the squares and pieces
   it rests on, so a verifier can re-check it without re-deriving it.
2. **Several facts, ranked — never one winner.** 23.5% of cards have more than
   one true thing to say.
3. **Pins never come from ray geometry.** 388 of 1,457 stored `missed_pin`
   labels were pins the front piece could simply capture. Any pin routes
   through `aligned_tactic_puzzle_proof.verify_created_alignment`.
4. **Detectors stay pure and callable outside the caption render**, so the
   facts are available at analysis time to the game story and tags, not only
   when a card renders.
5. **The engine emits for every move. It never returns nothing.** An earlier
   draft of this document said the opposite — that an unprovable fact is
   simply not emitted, and that "this is the one place silence is right".
   Mohit, 2026-10-22: *"when you say engine is ready, it should not throw in
   silent moves, engine should give us something for everything."* He is
   right, and the exception was wrong: an engine that returns nothing hands
   the LLM nothing, and the LLM then either invents or goes quiet.

   The rule that replaces it: **never guess, always describe.** A purpose
   that cannot be proven is not claimed — but the board facts underneath it
   are always available and always true, so the floor below is emitted for
   every single move. See §6.1.

---

## 7. Cost

Measured on 80 disjoint positions, depth 18, Threads=1, a fresh engine per
configuration so no warm hash flatters a later run.

| | per position | vs now | per 80-move game |
|---|---|---|---|
| today | 0.881s | 1.00x | 70s |
| **+ full PVs** | 0.881s | **1.00x** | **70s** |
| **+ opp_replies** | 1.182s | **1.34x** | 95s |
| + MultiPV 3 | 2.682s | 3.05x | 215s |
| + MultiPV 4 | 3.566s | 4.05x | 285s |

**The first two are nearly free and carry most of the value.** Full PVs cost
nothing at all — the search already found them. `opp_replies` costs a third
more and is the only thing that tells a caption whether a punishment is
forced.

MultiPV is the expensive one and the only genuinely optional item. It buys
"was this the only move", which is a real lesson, at three times the analysis
budget. It should be decided on its own evidence, not bundled.

---

## 8. Order of work

1. **Emit the floor for every move** (§6.1). The single biggest item and it
   is free: the engine is silent on 91.8% of good moves, which are 70% of the
   game, and the search that produced their eval already found the line. This
   is what "the engine gives us something for everything" means in practice.
2. **Store the full PV.** Free, and it widens the input to every downstream
   consumer at once.
3. **Store `opp_replies` and `opp_reply_is_clear`.** Already computed; 1.34x
   if recomputed.
4. **Split `D`** into hanging and trapped, measure each, reuse `game_ledger`
   for the trapped half.
5. **Build the purpose list** as ranked structured output: A, B, C, E, G, H,
   I, J, K plus the two halves of D. Drop F.
6. **Add "answers their threat"** — 94% of the residue, evidence already
   stored.
7. **Add the mate transition** — missed mate and walked-into mate, 23% of the
   residue, evidence already stored.
8. **Re-measure coverage.** The bar is the share of flagged moves where the
   engine can state all six things with proof. Today that is bounded by row 3
   at roughly a quarter.
9. **Decide MultiPV separately**, on its own cost and its own evidence.

Steps 1, 2, 3, 6 and 7 are plumbing of facts the engine already produces
and then discards. Steps 4 and 5 are the real new work.

The ordering is deliberate: step 1 alone takes the engine from speaking about
30% of a game to speaking about all of it, and costs nothing.

---

## 9. What is deliberately not here

**Captions, templates and gold.** The LLM writes the text from these facts
plus the player's history. This document stops at the facts.

**Routing.** Good facts that lose their slot to filler change nothing —
measured by another session as 1,054 filler-bearing cards, 90 of them with a
concrete why that lost anyway. That is a real problem and a separate one.

**Opponent cards.** `cp_loss` is 0 on them and `opponent_move_evaluations` can
be empty, so a facts-only architecture cannot fix them until that data exists.
Sizing that is its own measurement.
