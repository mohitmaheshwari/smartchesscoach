# Pin and skewer drill — scope

Asked for by Mohit, 2026-10-03: *"yes please, make it from community and also
lichess puzzles"*, after we measured his tactics.

## Why this drill exists

Measured over 816 of his analysed games, 4,263 positions where the engine's best
move *was* a tactic:

| shape | chances | took | steady across his own games |
|---|---|---|---|
| pin | 1,471 | 44% | yes (41 / 46) |
| skewer | 1,053 | 42% | yes (42 / 42) |
| free piece | 855 | 83% | yes (85 / 81) |
| fork | 663 | 51% | **no** — no claim made |

Pins and skewers are 59% of every tactical chance he gets, and he converts a
little over four in ten. Free material he takes almost every time. So he sees
*material* and does not see *alignment*. That is the thing this drill trains,
and it is the only claim here that survived both controls — stability across
halves of his own games, and re-scoring as "best or equally good" to remove the
exact-match penalty that was quietly punishing pins.

## What the player sees

One card. The board, one question, and nothing else on screen.

```
┌─────────────────────────────────────────────┐
│                                             │
│   Two of their pieces are on one line.      │
│   The one in front is worth less.           │
│                                             │
│   Find the move that attacks the line.      │
│                                             │
│          [ the board, their move to play ]  │
│                                             │
│   One move is right here.                   │
│                                             │
│   From your game against rookmaster22       │
│   ·  25 March                               │
└─────────────────────────────────────────────┘
```

After the move, whether right or wrong, the second question:

```
┌─────────────────────────────────────────────┐
│   How did you pick it?                      │
│                                             │
│   ( ) I saw two of their pieces on one line │
│   ( ) It looked like a good attacking move  │
│   ( ) I was taking a piece                  │
└─────────────────────────────────────────────┘
```

Then the teaching, which is the same sentence every time because the pattern is
the same every time:

> When two of their pieces sit on one line, the back one cannot be defended by
> moving the front one. Look for the line before you look for the move.

### Why the question names the pattern

This is a drill on a known weakness, not a test. He is not being asked whether
he can spot that something is there — we already measured that he cannot, four
times in ten. He is being asked to execute once told where to look. Naming the
shape is the teaching; withholding it would just reproduce the miss.

The pin and skewer wordings differ in exactly one line, and that difference *is*
the lesson:

- **pin** — "The one in front is worth less." (the valuable piece is behind)
- **skewer** — "The bigger one is in front." (the valuable piece is in front)

A later stage can stop naming it and mix the two. Out of scope for version one.

## Where the positions come from

Three sources, in this order, because recognition is worth more than volume:

1. **His own games.** He was there. These carry the opponent's name and the date.
2. **Community** — other players' real games, from `community_puzzles` and
   `community_training_positions`.
3. **Lichess** — 253,487 pin and 101,531 skewer puzzles are *already* in
   `lichess_puzzles` (4.1M rows, imported by `scripts/import_lichess_puzzles.py`).
   Nothing new is imported.

Nothing new is extracted either. Positions from his games are already in the
pool: `community_training_positions` holds 1,984 of them. They are tagged by
cognitive gap (1,540 say `calculation_depth`) and only 2 say `pin`, so the
motif tag is what is missing — not the positions.

### One authority for "is this a pin"

`opportunity_gate.shape_of_best_move` decides, for every source. It is the same
function that measured the weakness, so the drill trains what was measured. Any
other answer would mean drilling one thing and reporting another.

This matters most for Lichess, whose own `themes` answer a different question.
Lichess tags a puzzle `pin` when a pin matters *anywhere in the solution line*;
the gate asks whether *this move creates* one. Measured on 400 of each, at the
correct offset:

- pin: gate confirms 40%
- skewer: gate confirms 69%

So the Lichess tag is a cheap pre-filter and the gate is the decision. In the
1000–1400 band that leaves roughly 31,000 confirmed pins and 24,000 skewers,
which is far more than this drill can ever use.

### The Lichess off-by-one, measured not assumed

In `lichess_puzzles`, `moves[0]` is **the opponent's move** and the player's
answer is `moves[1]`. Confirmed empirically rather than read off a spec:

| | gate confirms pin | gate confirms skewer |
|---|---|---|
| treating `moves[0]` as the answer | 8% | 2% |
| playing `moves[0]`, then `moves[1]` | **40%** | **69%** |

Getting this wrong would have shipped a drill whose every Lichess answer was one
move out, and it would have looked like a detector problem. This is the same
shape of bug as `pv_after_best` not containing the best move.

## Difficulty

His rating is about 1200 (`player_profiles.current_rating` 1199, recent games
1265). Lichess puzzle ratings for these shapes, measured first:

| | p10 | p25 | median | p75 |
|---|---|---|---|---|
| pin | 1065 | 1264 | 1553 | 1834 |
| skewer | 855 | 1004 | 1268 | 1626 |

Version one serves **1000–1400** and stores the band in config so it can move
without a code change. No adaptive difficulty, no puzzle rating for the player —
there is no evidence yet that the drill changes anything, and a progression
built on top of an unproven drill is two unproven things.

## Answers, grading, and what counts as solved

- The answer is **never** sent to the browser. Same rule as the calculation
  test: positions out, verdict back.
- Graded as the stored best move, or any move within 30cp of it where
  alternatives are known. The exact-match penalty is real — it cost pins about
  ten points in the measurement — and the drill must not repeat it.
- Attempts go to the existing `puzzle_attempts` collection. **`puzzle_id` is
  always written.** 55 legacy rows have a null id and are permanently
  unfilterable; that must not grow.
- A solved position is not shown again.

## The question lives in one file

`services/lesson_question_spec.py` owns questions, grading family and reason
options. Today `pin` is an *alias* onto the generic `missed_tactic` question
("There is a tactic in this position. Find it.") and `skewer` is absent
entirely. So this adds two real specs to that file and removes the alias. No new
question store, no copy in the route, no copy in the page.

## User-facing text

No numbers and no percentages anywhere the player can see — not in the card, not
in the summary, not in the empty state. Short sentences, common words, one idea
each. A test asserts it, because an authored string that drifts never errors.

## Out of scope for version one

- Fork. Its rate does not hold across halves of his own games (55% / 47% on 663
  chances), so there is nothing to claim and nothing to drill yet.
- Any adaptive or progressive difficulty.
- Showing the player a score, a rating or a percentage.
- A new collection. If version one needs one, that is a signal the design is
  wrong.
- Rolling this out to other players. Every number above is one person. The
  drill is built to be general, but nothing is claimed about anyone else until
  the same measurement is run for them.

## How we will know it worked

Not solve rate — a drill can be solved and teach nothing. The reading that
matters is the one that found the weakness: his gated take rate on pins and
skewers in *real games played after the drill*, against the 44% and 42% measured
here. That needs new games, so the check is weeks out, and the honest position
until then is that the drill is unproven.
