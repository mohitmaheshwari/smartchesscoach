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

## Decisions taken

Mohit, 2026-10-17, answering the three open questions:

1. **Surface — both, starting with game review.** V1 puts the sentence on the
   move inside game review. Home follows once the sentences have been seen in
   a real review.
2. **Collisions — measured, then decided.** Over 150 games, 14% of his moves
   fire at least one detector and 98% of games carry one. Of the moves that
   fire, **89% fire exactly one detector**; 11% fire two and 0.4% fire three.
   The pairs that collide are near-synonyms, which is why two sentences would
   read as repetition rather than as two ideas:

   | collision | how often | both are saying |
   |---|---|---|
   | `opening_center` + `opening_plan_play` | 25 | you took the middle |
   | `coached_development` + `opening_plan_play` | 17 | you brought a piece out |
   | `coached_development` + `opening_development_with_tempo` | 12 | you brought a piece out |
   | `concept_rook_open_file` + `endgame_active_rook` | 10 | your rook got active |

   **One sentence per move, chosen by fixed priority.** The more specific
   detector wins, because "you brought a piece out and hit something" contains
   "you brought a piece out" and the reverse is not true.
3. **Corrections are in scope, not only compliments.** *"everything a coach is
   never shy to give negative too."* A correction says a different move was
   better, so it is held to the harder evidence: a FRESH depth-18 engine run,
   not the stored best move, and the better move must still be clearly better
   when looked at deeper. A correction that cannot clear that stays silent
   while its compliment may still ship.

## Open questions

1. **Does `opening_plan_play` belong here?** It claims the move matched an
   authored plan, so it is only as true as the authoring. It is excluded from
   the V1 evidence run until the opening content is audited.
2. **Wording.** Every sentence below is a draft and none ships before Mohit
   has read it.

## The sentences (DRAFT — nothing ships before Mohit reads these)

Simple English, one idea per sentence, no chess words a 700 player would have
to look up, no numbers, and a principle at the end that carries past this one
game. The correction says what was better and why, because a correction
without a why is just a verdict.

| detector | when you did it | when you did not |
|---|---|---|
| `coached_development` | **You brought a new piece into the game.** A piece left at home is a piece not helping you. | **A piece was still sitting at home, and bringing it out was better here.** A piece left at home is a piece not helping you. |
| `opening_center` | **Your pawn took a square in the middle.** The middle is the ground both sides want first. | **A pawn into the middle was stronger here.** The middle is the ground both sides want first. |
| `opening_castling` | **You castled, so your king is tucked away.** Get the king safe before the position opens up. | **Castling was the better move here.** Get the king safe before the position opens up. |
| `concept_rook_open_file` | **Your rook moved to a file with no pawns in the way.** Rooks want lines with nothing blocking them. | **Your rook belonged on the clear file here.** Rooks want lines with nothing blocking them. |
| `endgame_king_centralization` | **Your king stepped towards the middle.** When few pieces are left, the king turns into a fighter. | **Walking your king towards the middle was better here.** When few pieces are left, the king turns into a fighter. |
| `opening_development_with_tempo` | **You brought a piece out and attacked something at the same time.** A new piece that arrives with a threat gains you a free move. | **You could have brought a piece out and made a threat with it.** A new piece that arrives with a threat gains you a free move. |
| `concept_central_pawn_break` | **You pushed a pawn to challenge theirs in the middle.** When the middle is stuck, a pawn push is how you open it. | **Striking in the middle with a pawn was better here.** When the middle is stuck, a pawn push is how you open it. |

Rules these follow, from what has already been decided about caption voice:
no move names repeated back ("Nf3 puts your knight on f3"), no figures, no
tally of past failures, nothing dramatic, and the last sentence is the one a
player can still use in a game we never see.

## Evidence, measured (2026-10-17, 250-400 sampled games)

Compliments are settled by the board alone. Corrections were re-checked
against a FRESH depth-18 engine, never the stored best move.

### Compliments — what may speak

| detector | the sentence that was verified | fires | held | Wilson LB | verdict |
|---|---|---|---|---|---|
| `coached_development` | a knight or bishop left its home square | 286 | 286 | 98.7% | **PASS** |
| `opening_center` | a pawn landed on a centre square | 222 | 222 | 98.3% | **PASS** |
| `concept_rook_open_file` | a rook moved to a file with none of HIS pawns | 202 | 202 | 98.1% | **PASS** |
| `endgame_king_centralization` | with <=12 pieces, the king stepped towards the middle | 80 | 80 | — | **PASS, gated** |
| `opening_castling` | he castled | 61 | 61 | 94.1% | **PASS** |
| `concept_central_pawn_break` | a pawn moved in the middle files | 177 | 177 | 97.9% | **PASS** |
| `opening_development_with_tempo` | came out and hit something | 20 | 20 | 83.9% | short of the 50-fire floor |

Two of those were my errors, not the detectors':

- **`concept_rook_open_file`** scored 57% until the sentence was fixed. Of 121
  fires, 64% were fully open files and 36% half-open, and **not one** had a
  friendly pawn on the file. The detector means "none of YOUR pawns"; I had
  written "no pawns at all". With the sentence corrected: 202 of 202.
- **`concept_central_pawn_break`** scored 73% against "where the pawns meet".
  Every fire is a centre-file pawn move, but only 55 of 177 have enemy pawns
  in contact. "Break" overclaims for the rest.

One is a genuine detector limit, and it is the valuable one:

- **`endgame_king_centralization`** steps towards the middle on 100% of fires,
  but only 80 of 122 have 12 pieces or fewer left. The other 42 fire with 13
  to 21 pieces on the board, where walking the king to the middle is not
  endgame technique — it is how a player gets mated. **No wording saves that
  one; it needs the piece-count gate**, and the gate is a condition of
  promotion rather than a detail of the sentence.

Honest note on the two gated rows: the gate clause (piece count, pawn contact)
is **enforced**, not verified — it is true because we only fire when it holds.
What the evidence establishes independently is the detector's own half of the
sentence: the direction the king moved, and that the move was a centre-file
pawn move.

### Corrections — what may NOT speak yet

| detector | "a move of this kind was better", at depth 18 | result |
|---|---|---|
| `coached_development` | clearly better move exists | 37/40 = 92% |
| `coached_development` | **tighter**: it is the engine's TOP move | 36/40 = 90%, Wilson LB 77% |
| `opening_center` | clearly better move exists | 20/23 = 87% |
| `opening_center` | **tighter**: it is the engine's TOP move | 20/23 = 87%, Wilson LB 68% |

The bar is 95% with a Wilson lower bound of 85%. **Both miss, and tightening
the gate did not help** — it moved coached_development from 92% to 90%.

The cause is depth, not the idea. The detector decides a correction from the
best move stored at analysis time; at depth 18 the top move is often a
different one, and then "bringing a piece out was better here" is a claim
about a move the deeper engine does not endorse. Two honest ways forward, both
costed before either is chosen:

1. score the correction at the same depth it will be claimed at, or
2. soften the sentence so it stops claiming superiority.

Until one of those is done, **corrections stay silent while their compliments
ship.** Mohit asked for the negatives and the negatives are worth having; they
are not worth having at 90%.

## The corrections, re-measured cleanly (2026-10-17)

The first correction run reused one engine process across several hundred
positions, so Stockfish's table carried between unrelated boards. Re-run with
`ucinewgame` before every position, 400 games:

| detector | some move of this kind is clearly better | it IS the engine's top move |
|---|---|---|
| `coached_development` | 53/60 = 88% (LB 78%) | 54/60 = 90% (LB 80%) |
| `opening_center` | 31/37 = 84% (LB 69%) | 33/37 = 89% (LB 75%) |

**The flawed run and the clean run agree.** The method needed fixing; the
finding did not change. Corrections sit at 84-90% against a 95% bar, so they
cannot ship as they are.

### What a wrong correction looks like

Game `02ea7f59`, move 5, he played `dxe5`. The move stored as best at analysis
time was `Be2`, which develops a piece, so the correction fired:

> "A piece was still sitting at home, and bringing it out was better here."

At depth 18 the move order is `Qd3` +179, `Be3` +169, `Be2` +151, his `dxe5`
+90. The strongest move is a queen move that develops nothing. The card would
have pushed him towards a principle the position did not want.

### The fix: gate it, do not accept it

Do for corrections what the piece count does for the king: **verify at the
depth we claim at, at review time, and stay silent when it does not hold.**

- every correction printed has been checked against a fresh deep look, so the
  one-in-eight like `dxe6` and `Qh4` never reaches a player
- we lose about 1 correction in 8; the detector simply says nothing there
- cost is one engine check per correction candidate, about 0.3 per game,
  cached with the game

This is the honest way to give a coach its negatives: not by lowering the bar
to 88%, and not by staying silent, but by only speaking where the claim has
been checked.
