# The game story, told in three parts: opening, middlegame, finish

Status: draft for Mohit's sign-off, 2026-10-21. No code yet.
Builds on `docs/game_story_on_screen_scope.md`, which is live.

## What it is

Today the story is a short list of moves that mattered. A coach tells a game
differently: how the opening went, what happened in the middle, and how it
ended. That includes the moments the player got away with, because a weak
opponent missing a chance does not make the move good.

This changes the story into three short parts, written for the player:

1. **Opening.** Which opening it was and how it went: played well, about
   level, or gone wrong, and the move that cost the most.
2. **Middlegame.** The sharp moments, good and bad. A tactic found, a piece
   trapped, a strong square taken, a mistake made. When the opponent did not
   punish a mistake, the line says so.
3. **The finish.** How the game ended, and whether it was finished cleanly.

## What the player sees

Mohit's game 56b6c294, played as Black, won by resignation. Every chess claim
below was checked on the board with the engine on 2026-10-21.

```
THE STORY OF THIS GAME                                        You won

OPENING  ·  Queen's Pawn Opening
  You came out of the opening about level.
  ✗  e5     This left your d5 pawn short of defenders. Nxd5 would
            have won it. Your opponent missed it.

MIDDLEGAME
  ✗  Nxg5   Bxc3 was stronger. Take their knight, and after bxc3
            your knight forks their queen and bishop from c3.
  ✓  Nh3+   They left something loose, and you took it.
  ✗  Ng5    This let Rh1 trap your queen. Your opponent missed it.

THE FINISH
  You stayed well ahead, and they resigned.
```

What each line rests on:

- **e5.** After 8.dxe5 Nxe5, d5 is attacked by the c3 knight and the queen,
  and defended only by the f6 knight. White's best was 9.Nxd5. White played
  9.Nxe5 and Black was better again.
- **Nxg5.** The stored label today says "A pin you could have played". There
  is no pin. Bxc3 bxc3 Nxc3 hits the queen on d1 and the bishop on e2.
- **Ng5.** The h3 knight was blocking the h-file in front of the queen on h4.
  After Ng5 Rh1, every one of the queen's eight squares is covered.
  White played f4 instead.

On home, the same story is cut to the opening line and the two moments that
matter most.

## What each part needs, and what already exists

| Part | Already there | Missing |
|---|---|---|
| Opening name | chess.com stores a name on every game | Shortening "Queens Pawn Opening Zukertort Chigorin Variation 3.e3" to "Queen's Pawn Opening". Lichess stores none, so the name comes from the moves instead, through the opening book that already names openings for captions. |
| Opening verdict | The player's evaluation after the opening, and every opening move's cost | The rule that turns those into a sentence |
| Left the book | Stored on every analysis: the move played and the book move | Only said when the book move is also the engine's best, as the existing left-book detector already requires |
| Middlegame mistakes | The current story moments | The "your opponent missed it" beat, and naming the real danger |
| Middlegame good moves | Eleven approved concept checks, including castling, a knight outpost, a rook on an open file or the seventh rank, and a central pawn break. Executed tactics such as a fork or a trapped piece. | Reading the concept results into the story. Today they are worked out only inside the review captions. |
| Stopped them castling | Nothing | A new check, proved on real games before it is trusted |
| The finish | How the game ended, and the evaluation at the end | The rule that turns those into a sentence |

## Measured on real games

The opening is measured on 1,000 recent games, and the missed chances on
3,000.

| Measured | Games |
|---|---|
| Opening named, chess.com | 939 of 939 |
| Opening named, lichess | 0 of 61 |
| Book exit stored | 1,000 of 1,000 |
| Clearly better after move ten | 223 |
| Clearly worse after move ten | 262 |
| At least one costly move in the first ten | 564 |
| A big chance given away that the opponent missed | 1,124 of 3,000 |
| A forced mate the player missed | 809 of 3,000 |
| A forced mate allowed that the opponent missed | 374 of 3,000 |

So "you played the opening well" will be honestly true in a minority of
games. The line must say what actually happened, not flatter.

## Fixes that come first

Both are wrong today on the live story and on review cards.

1. **The pin checker accepts pins that are not pins.** It treats a piece as
   pinned even when that piece can simply take the attacker, as with b2 and
   a bishop on c3. Of 1,457 stored "a pin you could have played" labels, 388
   rest on this mistake. The checker will refuse such pins. The 388 are
   relabelled with the idea the board proves, such as the fork above, or
   fall back to "a chance that went by". The affected captions are rebuilt.
2. **A mistake is named by the move it missed, not by the danger it walked
   into.** Ng5 is called a missed pin. Its real lesson is the trapped queen.
   When the punishing reply wins the queen or allows a forced mate, and the
   board proves it, that danger is the line.

## In scope

- The two fixes above.
- The opening line: a short name, a verdict, and the costliest move when
  there was one.
- The middlegame line: current moments plus "your opponent missed it",
  missed mates, allowed mates the opponent missed, and approved good moves.
- The finish line.
- The review page shows all three parts. Home shows the opening line and the
  top two moments.
- A test for every rule, and a measured run over real games before shipping.

## Out of scope

- The "stopped them castling" check. It is built and proved separately, then
  added as a good-move line once it holds up on real games.
- New opening teaching content.
- Play with Coach games.

## Success criteria

- Every claim in a story line is backed by the board or the engine. A sample
  of stories is checked by hand before shipping.
- No line names a pin that the board says does not exist.
- A lost game never leads with a compliment, as today.
- Every lichess game gets an opening name from its moves.

## Open questions

1. **How warm can the opening line be?** You wrote "a perfect Scandinavian".
   "Perfect" will be true very rarely. I suggest "You played the Scandinavian
   well" when no opening move cost anything noticeable for the player's
   rating and the position is level or better. Otherwise: "Your London went
   wrong early with h3." Do you want "perfect" kept for the rare game where
   every opening move was the engine's choice?
2. **Where the opening ends.** A fixed ten moves is simple and wrong for short
   or very sharp games. The product already has a phase measure built from
   the material left on the board. I recommend using it so the opening,
   middlegame and finish split the same way everywhere.

## Order of work

1. The pin checker fix and relabel, with the captions rebuilt.
2. Naming the real danger, and "your opponent missed it".
3. The opening line, including lichess names.
4. Good middlegame moves from the approved concept checks.
5. The finish line.
6. Separately: prove a "stopped them castling" check.
