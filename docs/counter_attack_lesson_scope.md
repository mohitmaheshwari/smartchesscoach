# Counter-attack: look for your own attack before you move

Status: DRAFT for sign-off. No code until Mohit says go.
Written 2026-10-10. Grew out of game_e8c293b5082b move 14 (Qxb7).

## The mindset we are teaching

> When something of yours is attacked, look at what YOU can attack before you
> move it.

That is the lesson. Not a fact about one position -- a thinking habit the
player takes into the next game.

Mohit, 2026-10-10: "counter attack is the mindset which i want to teach here,
along the facts."

## The mistake it targets

The player sees a piece is attacked and moves it. That is the reflex. It is
often right, and when it is wrong the player does not learn anything from the
engine saying "Nc3 was better" -- because they know why they moved: the piece
was attacked.

On the card that started this, the review said:

    Qxb7 doesn't change much here. Nc3 was better - it attacks the queen on d5.

Mohit: "i removed queen from c7 to b7 because it was attacked, and that's a
mistake too". Exactly. The card named the right fact -- Nc3 attacks the queen
on d5 -- and gave it no meaning. The missing words are "instead of running".

## When it fires

All four conditions, all read off the board. Stockfish decides the move is a
mistake and names the better move; the board explains why.

1. The engine flags the played move (its normal severity rules; this scope
   does not change them).
2. Before the move, one of our pieces is **under threat**: attacked, and
   either undefended or attacked by something cheaper. Pawns excluded -- a
   threatened pawn is a different lesson.
3. The played move **moves that piece**. This is the reflex we are naming.
4. The engine's better move **does not move it**.

That much is the parent shape: *you moved a piece you did not have to move*.

Then, for the counter-attack frame specifically:

5. The better move creates a **new** attack on an enemy piece worth at least
   as much as the piece we saved -- new meaning we were not already attacking
   it.

## What it says

When 1-5 hold, the card leads with the habit and proves it with the board:

> Your queen was attacked, so you moved her. Before moving an attacked piece,
> look at what you can attack. Nc3 attacks their queen. Then both queens are
> attacked -- if they take yours, you take theirs.
> **When something of yours is attacked, look for your own attack before you
> move it.**

When only 1-4 hold -- no counter-attack available -- the card still says "you
did not have to move it", but the frame is whatever the better move actually
does. It must NOT say "look for a counter-attack" when there is not one.

## What it must never say

- The counter-attack sentence without naming the piece attacked and the piece
  counter-attacked. Both come from the board or it does not ship.
- "Your piece was attacked" on its own. The player knows -- they moved it.
  That was the first version of this fix and Mohit rejected it on sight.
- A claim about king safety, queen activity or who is winning. All three were
  measured on the originating card and none of them held (see below).

## Measured, 1,200 games, 14,463 flagged user cards

    you moved an attacked piece (minor+), engine would not    626   4.3%
      ...and the better move counter-attacks                  172   1.2%
    pieces being saved: bishop 67, knight 61, rook 28, queen 16
    by severity: inaccuracy 0.8%, mistake 1.6%, blunder 1.6%

Like-for-like control, same minor-or-better bar:

    better move hits a minor+ when you saved a piece           33%
    better move hits a minor+ across all flagged cards         27%
    lift                                                     1.24x

**The 1.24x does not sink this, and the reason matters.** Lift tests whether a
feature is diagnostic, which is the right question for a detector and the
wrong one for a habit. A habit is worth teaching when it is true where we say
it (here: by construction, both pieces named from the board) and when players
systematically fail at it (here: 626 cards where they reacted and did not need
to). A 27% base rate means "look for your own attack" applies broadly -- which
makes the habit MORE worth drilling, not less.

## Three explanations that were tested and failed

Recorded so nobody re-derives them. All measured on the same corpus:

- **Queen activity** -- "their queen is doing more than yours". Static reach /
  targets / squares near the king: their queen ahead on 48% of firing cards vs
  47% of non-firing. A coin flip. Dynamic (captures and checks inside the
  line): theirs busier 22% vs 15%, but ours also rises 19% vs 12%, so there is
  no asymmetry.
- **King safety** -- on the originating card there are 0 checks in either
  engine line and 0 squares around either king attacked. The "their queen is
  dangerous near your king" story is false there.
- **"You are losing, so trade"** -- player worse by >1 pawn on 35% of firing
  cards vs 24% otherwise, and the median is +19, i.e. most are not losing.

## Open question for Mohit

On the 454 cards where 1-4 hold but there is no counter-attack, do we show the
"you did not have to move it" card at all, or stay silent? It is a true and
useful observation, but without the counter-attack it has no "instead, do
this" to offer beyond naming the engine's move.

## Depth

None. Conditions 2-5 are ply-0 and ply-1 geometry. Mohit, 2026-10-10: "12
plies is too much depth for a 1500". This needs zero.
