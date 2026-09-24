# Show the move they played, then ask for the better one

**Status:** DRAFT, awaiting Mohit's signoff. No code written.
**Raised by:** Mohit, 2026-09-24, on a live `piece_safety` lesson.

---

## The problem, in one position

Mohit opened `/training?personalized=1&kind=concept&lesson=piece_safety`
and got this card:

    Undefended Pieces
    "Before you let go of a piece, look at the square it is landing on
     and ask what can capture there."
    Which move keeps every piece safe?

The position shown was from his own game
(`6rk/pppq1p1p/3p2r1/5N2/2P1Pp2/7Q/PPP3PP/R5K1 w`, game `ac3e90df`, move 21).

His objection, verbatim: *"right now at this stage my queen is not attacked,
so it's not undefended. I get it that my queen from the real game got
undefended, but it's not now."*

He is right. Checked on the board:

    white pieces attacked at the shown position : 2
      P g2   attacked by g6   defended by g1, h3
      N f5   attacked by d7   defended by h3, e4
    is the queen on h3 attacked?                : No

Nothing of his is undefended. Nothing is even loose. The card asks him to
find a safety problem that **does not exist on the board he is looking at.**

It exists one move later. He played `Nh6`; that knight was the only thing
blocking the d7-h3 diagonal, so `Qxh3` follows and the queen is gone. The
concept was derived from the position AFTER the mistake and printed over
the position BEFORE it.

There is a second, nastier layer. After `Nh6` the queen on h3 still looks
defended -- the g2 pawn guards it. It only loses because g2 is **pinned to
the white king by the rook on g6** and can never recapture. So a literal
"is every piece safe" test would PASS the losing move. The question does
not merely fail to describe the board; its own test endorses the blunder.

Third mismatch, for completeness: the stored `cognitive_gap` on that move is
`king_safety`, not `piece_safety`. The lesson served it under a concept its
own analysis never gave it.

## What Mohit proposed

> "It could have shown up as one-move blunders or undefended, showing the
> move that I had played, moving the knight as part of the puzzle itself,
> and then ask me: this is what you played, and what was a better move?"

So the card plays HIS move first, says *this is what you played*, and only
then asks for the improvement. The problem becomes visible before he is
asked about it.

## Why this is the right fix and not a patch

Today the card hides the thing it is teaching. The learner is asked a
question whose subject is off-screen. Playing the move puts the subject on
the board, and it does it with the one piece of material we have that no
puzzle site has: **it was his own move, in his own game.**

It also repairs the label honestly rather than by rewording. Once `Nh6` is
on the board, "your queen is now undefended" is TRUE. We stop having to
choose between a wrong label and a rewritten concept.

## What would change

1. The lesson item gains two fields: the SAN the player actually played, and
   the position after it. Both are already recoverable -- the item id is
   `personal:{game_id}:{move_number}`, so the played move is one lookup away
   in `move_evaluations`. No new data, no new collection, no re-analysis.
2. `_public_item` already passes unknown keys straight through, so the two
   fields reach the UI without a serializer change.
3. The card gets a first beat: the board animates the played move, with the
   line *"This is what you played."*
4. The question changes from "Which move keeps every piece safe?" to
   "What should you have played instead?"
5. The board then returns to the position before the move, because that is
   where the answer is legal.

## What does NOT change

- No change to which positions are selected, or to any detector.
- No change to grading: the accepted answer is still the engine's move.
- Non-personal lessons (Lichess-sourced, no played move) keep today's flow
  untouched. This beat only exists when we actually have the player's move.

## The part I would push back on

**Mohit's format fixes visibility. It does not by itself fix the label.**
For this card the real lesson is not "watch your undefended pieces" -- it is
"your knight on f5 was holding a diagonal; before you move a piece, ask what
it was holding." Playing `Nh6` makes the loss visible, but a card still
titled *Undefended Pieces* teaches the wrong habit for this position.

So I would treat the label as a separate decision, not smuggle it in here.

**The rewind is the real design risk.** Step 3 shows the position after the
move; step 5 needs the position before it. If that rewind is not obvious,
we have traded one confusion for another. This is the part to get right in
the mockup before any code -- per the standing rule that the card is the
product and the schema is implementation.

## How we would know it worked

- On every personalized card, the thing the question asks about is visible
  on the board at the moment it is asked. Today, measurably, it is not.
- The `card_looks_wrong` bucket in the missing-why queue stops filling with
  positions of this shape.
- Open question for Mohit: should the played move be animated, or shown as
  an arrow with the board left alone? Arrows are cheaper and do not need the
  rewind at all.

## Not in scope

- The slowness Mohit reported on the same screen. Unmeasured; separate.
- Teaching arrows for the pin and the blocked diagonal. Related and probably
  the more valuable half, but its own piece of work.
