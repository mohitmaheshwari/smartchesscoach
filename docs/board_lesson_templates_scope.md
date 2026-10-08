# Board lesson templates

Mohit, 2026-10-07, after reading three cards in one King's Gambit game:
"captions are too long and really don't make sense... the idea of caption is
to explain what's on the board and the arrow to show what's on the board".
Then, on the family names: "dumb shit strings, 'another piece of yours is
taken', what is this lesson". And finally the shape he wants:

> "from the board pick the thing and end the lesson, these are our templates"

## What a card is

Two sentences. The first names a thing measured on the board. The second is
the lesson, and it is the same sentence every time that template fires,
because that is the part the player should still have in a week.

    Your pawn on e5 was attacked by the knight on f3 and nothing was defending it.
    Look at what they attack before you start your own plan.

The arrows are drawn from the SAME measured values as the first sentence --
the attackers it counted, the defender it named. Not from a separate builder.

## Why the arrows must share the slots

The cards he reported had a caption about one move and arrows about another:
`Nc4` said "runs into bxc4" and drew `f7->f5, e5->f6, d8->f6`. Both were
individually correct -- the sentence was board-verified, the arrows were legal
moves from a real engine line -- and nothing in the system compares them,
because an arrow carries no record of what it illustrates.

One `slots` object produces both. There is nothing to compare because there is
only one source.

## The six templates

Measured over 100 of his games, both sides, 5,913 plies at depth 16; 1,056
moves at cp_loss >= 100 after excluding 34 moves that delivered checkmate and
303 where the engine returned a mate score.

| # | id | board thing | lesson | n |
|---|----|-------------|--------|---|
| 1 | `hanging_ignored` | victim had more attackers than defenders BEFORE the move | Look at what they attack before you start your own plan. | 149 |
| 2 | `moved_the_guard` | the square the piece left was defending the victim | Before you move a piece, check what it is holding. | 76 |
| 3 | `landed_uncounted` | the piece that moved is the one taken | Count attackers and defenders before you put a piece on a square. | 155 |
| 4 | `opened_line` | the victim gained attackers only after the move | When a piece steps aside, look down the line it just left. | 11 |
| 5 | `capture_available` | the best move is a capture | Look at every capture before anything else. | 67+ |
| 6 | `king_square_theirs` | enemy lands beside our king where our king may not capture | A square next to your king is only safe if nothing of theirs guards it. | 78 |

536 of 1,056. The rest stay silent: 270 where material comes off level but the
position is worse, and 280 nobody can name yet. Filling those with "take a
breath and look at the whole board" is what the code does today and it is why
he is reading screenshots.

## Rules

- The victim is taken in the engine's own line. The counts are evidence for a
  capture the engine plays, never a prediction on their own.
- No template may fire without its slots. A missing slot is silence.
- The lesson sentence is fixed per template and authored in
  `data/captions/board_lessons.json`, so wording changes need no code.
- Simple English, short sentences, no chess jargon: the audience is 600-1500.
