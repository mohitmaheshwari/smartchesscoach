# Making the silent detectors speak — scope

*Draft for sign-off. Mohit, 2026-10-17: "about reaching nobody, i can't have
that done, you need to help me get all those detectors non-silent."*

## What it is

Today 48 of our 70 registered detectors compute an opinion about a move and
throw it away. They are marked `shadow`, which means they are allowed to run
but not allowed to change a single word a player reads. This work takes the
ones that have something worth saying and lets them say it.

It is not one change. A detector is silent for three different reasons, and
every one of them has to be cleared before a player sees anything:

1. **It has no permission.** The quality lock keeps a detector silent until
   its claims have been checked. That is the rule that stopped us shipping a
   king-safety detector that was wrong about one fire in four.
2. **It has no words.** Only 15 of the 48 appear in any content file at all.
   For most of them there is no sentence written for them to say, so giving
   them permission would ship nothing.
3. **It has nowhere to appear.** Nothing a player looks at currently reads a
   concept detector's verdict.

Clearing only one of the three changes nothing. That is the main thing this
document is for.

## What the user sees

Nothing new on its own page. A detector that has earned permission adds one
sentence to a card the player already reads, on the move it fired on:

```
  Game review — move 11

    You played Nc3.
    ┌──────────────────────────────────────────────┐
    │  Your last piece came off the back rank, and │
    │  it was the best move on the board.          │   <-- the detector's sentence
    └──────────────────────────────────────────────┘
    Before a plan, get everyone off the back rank.    <-- the principle it teaches
```

One sentence. On a move. In the player's own game. Nothing else changes.

## In scope

- The detectors that **actually fire**. Measured over 200 games: 22 of 48 fire
  at all, and 7 fire often enough to be worth the work:

  | detector | fires on | what it claims |
  |---|---|---|
  | `coached_development` | 78% of games | a piece left the back rank, and it was the best move |
  | `opening_center` | 72% of games | a pawn took the centre |
  | `concept_central_pawn_break` | 32% of games | a pawn break in the centre |
  | `concept_rook_open_file` | 25% of games | a rook moved to a file with no pawns |
  | `opening_castling` | 26% of games | the king castled |
  | `opening_plan_play` | 24% of games | the move matched the authored plan |
  | `endgame_king_centralization` | 20% of games | the king walked towards the middle in an endgame |

- **Proof before permission, by board and engine only.** Every claim above is
  decidable: "a knight left b1" is a fact about the board, "it was the best
  move" is a fact from the engine. Neither needs an opinion. The lock permits
  exactly these two adjudicators and forbids a model, so the evidence can be
  produced without a review queue.
- **Caption grade, not plan grade.** Caption grade lets a detector add a
  sentence. Plan grade lets it decide what a player trains for weeks. We are
  asking for the first.
- **One written sentence per detector**, plus the principle it teaches, in the
  central caption layer — not in the detector.

## Explicitly out of scope

- The 26 detectors that never fired in 200 games, including all 20
  `endgame_curriculum__*`, Lucena, Philidor and rule-of-square. They are silent
  because they never speak, not because they are gagged. Widening them is a
  different job with a different risk.
- **Plan grade for anything.** Nothing here earns the right to set a player's
  training focus.
- Any detector whose claim needs a judgement — "was this a fork worth
  teaching" — because the lock requires a human for those and we do not have a
  review queue running.
- Changing the lock, its thresholds, or its list of permitted adjudicators.
- New detectors. None.

## Success criteria

- A player's game review carries at least one detector sentence on **most
  games** — the 7 above cover 78% / 72% / 32% of games, so coverage is there
  if the evidence passes.
- Every promoted detector has evidence on file meeting the caption bar: 95%
  precision, 95% Wilson lower bound at or above 85%, at least 50 checked
  fires, at least 20 true negatives, and no critical false claim.
- **A promoted detector that is wrong in front of a player is a failure even
  if the numbers passed.** One flagged false sentence sends the detector back
  to shadow, not into a tuning cycle.
- Zero change to what anybody trains on. If a focus or a plan moves, this work
  overstepped.

## What we already know, and what it cost

The honest part. When I first measured these detectors I reported two things
that were wrong, and both are the reason this document exists:

- I called them with the wrong signature and reported "43 of 48 never fire".
  They need the move number, the real move history and the engine's verdict,
  or they return nothing. Through the real runner, 22 fire and `coached_development`
  alone fires on 78% of games.
- I scored their accuracy at 99% against engine loss. That number is
  **circular**: `coached_development` only says "applied" when the move WAS the
  engine's best, so the engine was always going to agree. The test could not
  have failed. Real evidence has to check the claim — did a piece actually
  leave the back rank — not whether the move was good.

## Open questions

1. **Where does the sentence go?** Game review is the obvious surface. Home is
   the other. One of them, not both, for V1.
2. **What happens when two detectors fire on the same move?** Seven detectors
   over roughly 40 moves will collide. Proposal: one sentence per move, by
   fixed priority, decided before any of this ships.
3. **Does `opening_plan_play` belong here?** It claims the move matched an
   authored plan, which is only as good as the authoring. It may need the
   content audit first.
4. **Do we say anything when a detector says "wrong"?** 64 of 981 fires were
   negative verdicts, and those scored far better than chance. They are the
   teachable ones — but a negative sentence is held to a higher bar than a
   compliment, and this V1 proposes compliments only.
