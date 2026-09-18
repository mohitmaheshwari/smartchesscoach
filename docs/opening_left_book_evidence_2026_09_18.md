# Opening "left book for a worse move" — evidence

Status: SHADOW. Not authorized to say anything to a player.
Detector: `gap:opening_knowledge:left_book_for_a_worse_move`

## Why this exists

`services/opening_deviation.py` has recorded, since 2026-05-19 and on 98.9%
of analyses (15,569 of 15,736), exactly where a player left theory and what
the book plays instead. It feeds the Lab review page.

Nothing in the coaching path ever read it. `classify_opening_knowledge`
works from board geometry alone — a flank pawn pushed two squares, a knight
or bishop retreating — and its own comment admits the approximation:
"We can't easily know from FEN alone if this specific piece moved before".
Everything it cannot name falls to `unverified_hint`: 2,722 of 3,379
opening observations, 81%.

So 4,005 named, checkable deviations sat in the database while the coaching
system said "unverified hint".

## What the claim is

Three stored facts, each checkable against any opening database:

1. this move is the recorded first departure from book;
2. it cost at least 100cp;
3. the book continuation is ALSO the stored engine best move.

Rendered:

> Through move 3 you were in the Italian Game. At move 4 you played Nxe5.
> The main line is c3, and it was also the strongest move here. Nxe5 cost
> you about 354cp.

## What it refuses to say, and why

| | count |
|---|---|
| stored deviations | 4,005 |
| ...that cost >= 100cp | 494 |
| ...**and** the book move is also the engine's best | **183** |

**Condition 2 exists because leaving book is not a mistake.** Measured over
2,500 deviations: median cost 15cp, and 62.6% cost under 30cp. Mohit's own d3
Italian leaves theory, recurs 41 times, and is sound. A detector firing on
"you left book" would scold a player for a good move almost nine times in ten.

**Condition 3 exists because the book move is often not the best move.** Of
the 494 costly deviations, the book move was the engine's top choice in only
181 (36.6%). In the rest, naming it points at a move that is not even the
strongest available — one real case castled in the Italian for -567cp where
the book says c3 and the engine says Bxf7. Confident and wrong is exactly how
`king_safety` reached 75.4% precision and shadow.

## Limits

- The book is shallow: median `in_book_through_user_move` is 0, maximum
  observed 6. Late departures are invisible. This will do nothing for a
  player who leaves theory at move 12.
- 183 fires corpus-wide. Enough for Caption review (bar: 50 reviewed fires),
  short of Plan-grade (bar: 200, plus >=60% recall).
- Coverage skews to common openings — Italian, Scotch, King's Indian.
- Existing observations are not backfilled; the subtype appears on analyses
  derived after this ships.

## To promote

Caption-grade needs 50 independently reviewed fires at >=95% semantic
precision, 20 non-opportunity cases, and an adversarial packet with zero
critical false claims. The review question is narrow: *given this position,
is it true that the player left this opening at this move, and that the named
book move is the strongest move here?* Both halves are verifiable against an
opening database and the stored engine line, which is what makes this the
cheapest promotion candidate on the board.

The review must be independent of whoever built the detector.
