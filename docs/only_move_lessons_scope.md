# Only-move lessons — the coach teaches the one move that wins

**Status: DRAFT, awaiting Mohit's sign-off. No code written.**
Written 2026-11-21. First example: game `181687cf`, move 49.

---

## 0. Existing surfaces audit

### The example

Game `181687cf` (lichess blitz, the player is White, 1354 vs 1352). Checked
against the lichess 7-piece tablebase on 2026-11-21:

| Move | Only winning move | Played | Result after it | Review says today |
|---|---|---|---|---|
| 49 | Kc5 (1 of 20) | e6 | draw | "Kc5 attacks the pawn on b5 … go looking for pawns nobody guards" |
| 50 | Kc5 or Rg5 | Rf6+ | draw | same pawn-grabbing reason |
| 51 | Kc5, Kxb5 or Rf1 | Rf7 | draw | "Kxb5 takes the pawn" |
| 53 | e7 (only) | Rg7+ | draw | "e7 moves your pawn out of danger" |
| 55 | Kc6 (only) | **Kc6 — found** | win | silent: "Kc6 answers the check, and it is the move to play here." |
| 62–69 | any mate | king shuffles | **drawn by repetition, rook vs bare king** | 69.Ke6: "Good move … a calm, safe spot" |

Black handed the win back after each of 49, 50, 51 and 53.

**The move-49 reason is wrong.** 49.Kxb5 (taking the pawn) is itself a draw:
Black answers ...Rh5, attacking e5 along the rank, and the king is too far
away. After 49.Kc5 every Black reply loses; against the same ...Rh5, White
wins by putting the king next to the pawn (Kd4, Kd5 or Kd6), while Kxb5
still only draws. The real idea: *the king's job is the passed pawn, not the
extra pawn.*

### What already exists

| Piece | State (verified 2026-11-21) |
|---|---|
| Only-move flag | `best_is_only_move` in `stockfish_service.py`: best move is 150+ cp better than the second (`ONLY_MOVE_CP = 150`). **Computed only for inaccuracies, mistakes and blunders** — a found only-move is never flagged. Only consumer: one fact passed to the AI caption writer (`llm_caption.py:313`). |
| Play any line board | **Live** on `/game/:id` and the academy coach board. Student moves any piece; Stockfish in the browser answers; the server writes the words and a "why" sentence for mistakes. |
| Tap-only reflection | Live in the coach plan and game review (ReflectFlow): board taps plus a cause reply, no typing. |
| Exact endgame (tablebase) review | Built, **off in prod**: `EXACT_ENDGAME_REVIEW_ENABLED=false`, `SYZYGY_MAX_MEN=0`, no tables provisioned. |
| Rook mate lesson | `rook_mate` in `endgame_theory_tree.json` (3 positions), and `rook_checkmate` in `endgames.json`. |
| A lesson on "the king walks with the passed pawn" in rook endings | **Missing.** Rook lessons are Lucena, Philidor, Rook Activity. |
| Show-then-ask endgame demonstrations | Separate draft scope (`endgame_demonstrations_scope.md`, 09-19, not signed). Curriculum positions, not the player's own games. No overlap in surface; it could share the step-through board later. |
| "A draw you could have won" headline | `game_coach_summary.py:663`. Says nothing about *where* or *how*. |

### How often it happens (600 most recent analysed games, 19,930 player moves)

| Case | Moves | Games |
|---|---|---|
| Only move **missed**, player was winning (+2 or better) | 444 | 247 (41%) |
| … of those with 7 or fewer pieces (tablebase can check) | 14 | — |
| Only move missed, not winning | 211 | 158 |
| Only move **found** | not measurable — the flag isn't computed for good moves | — |
| Game ended not won with the player's rook or queen against a bare king | 4 | 4 (all draws) |

Caveats: "winning" assumes `eval_before` is from White's side. I haven't
checked that for games where the player is Black. A 150 cp gap is not the
same as "the only move that keeps the win". +900 vs +700 passes the gap but
both moves win. Both points are in section 6.

### Decision: EXTEND

The surfaces exist: review cards, the line board, the reflection flow, the
curriculum. This feature joins them on the moves that deserve it. It is not a
new page.

---

## 1. What it is

Some positions have only one move that wins. Finding it is a real test of
chess knowledge, and missing it is the clearest lesson a game can give. When
that happens in a player's game, the review stops on that position and
teaches it. The player plays the position again on the board. Whatever they
try, the coach plays the opponent's best defence, so they *see* why their move
fails. Hints come as questions. When they find the winning move, they must
use the same idea once more to prove it wasn't a guess. They leave with one
sentence they keep. A few days later they get the same idea in a different
position. If they found the move in the game, they get a short version: "you
found it — do you know why?" Separately, when a game ends drawn with a rook or
queen against a bare king, the review says so plainly and links to the rook
mate lesson.

## 2. What the user sees

### A. Missed only move (move 49)

On the review card for 49.e6:

```
┌──────────────────────────────────────────────────┐
│  Only one move won here                           │
│  You were winning. One move kept the win;         │
│  every other move lets Black draw.                │
│                                                   │
│            [ Find it on the board ]               │
└──────────────────────────────────────────────────┘
```

Tapping it opens the position on the line board, with the game move hidden:

```
┌──────────────────────────────────────────────────┐
│  From your game · move 49                         │
│  White to play. Only one move wins.               │
│  [board: before 49.e6]                            │
│  Move a piece to try.            [ Show a hint ]  │
└──────────────────────────────────────────────────┘
```

**They try a wrong move.** The coach plays Black's best defence on the board:

```
  You played e6.  Black answers Rh5.
  "The rook gets behind your pawn, and your king is too far
   away to help. This is a draw now."
                          [ Try again ]
```

```
  You played Kxb5.  Black answers Rh5.
  "Your king went for the other pawn. Now the rook attacks e5
   and your king can't get back in time. Still a draw."
                          [ Try again ]
```

**Hints, one at a time, as questions:**

```
  Hint 1   Which pawn will win you the game?
  Hint 2   Where does your king need to be for that pawn to queen?
  Hint 3   [arrow b4 → c5]
```

**They find Kc5.** The coach plays the same defence:

```
  Kc5 — that's the one.  Black answers Rh5 again.
  "Same idea once more: where does your king go now?"
```

They must find Kd4, Kd5 or Kd6. Then the board plays the win out a few moves
and shows the sentence to keep:

```
  ✓ "In rook endings, your king walks with the passed pawn.
     Take other pawns only when the king is already there."

  Coming back in a few days with a new position.
```

### B. Found only move (move 55)

```
┌──────────────────────────────────────────────────┐
│  Only one move won here, and you found it         │
│  Kc6. Do you know why the others fail?            │
│            [ Try another move and see ]           │
└──────────────────────────────────────────────────┘
```

The same line board, with the coach answering whatever they try.

### C. Basic win not converted (end of the game)

The game summary headline changes from "A draw you could have won." to:

```
┌──────────────────────────────────────────────────┐
│  You had king and rook against a lone king,       │
│  and it ended in a draw.                          │
│  That ending is always a win. It takes a few      │
│  minutes to learn the method.                     │
│            [ Learn the rook mate ]                │
└──────────────────────────────────────────────────┘
```

The last card (69.Ke6) no longer says "Good move". It says the position was
repeated and the game was drawn, with a rook still on the board.

## 3. In scope (V1)

- The only-move flag is computed for **every** player move, not only mistakes,
  so a found only-move can be detected.
- The flag means "the only move that keeps the result". It is defined on
  win/draw/loss classes, not on a raw centipawn gap. The definition is locked
  from data (section 6, Q1).
- When 7 or fewer pieces are left, the tablebase confirms the verdict before a
  card is shown (lichess API or local tables, Q3). If the tablebase disagrees,
  no card.
- At most **one** only-move lesson per game: the most important miss, or the
  found one if nothing was missed.
- **Missed card (A):** the "Find it on the board" entry, using the existing
  line board with the game move hidden.
- On each wrong try the coach plays the best defence on the board. The
  sentence comes from the existing line-board words and why engine.
- **Hint ladder:** 2 question hints and 1 arrow. The questions are generated
  only where the position matches a checked family (V1: the king supports the
  passed pawn). Otherwise there is just the arrow.
- **Prove-it step:** after the winning move, the coach plays the best defence.
  If the next move is again only one (or a small set), the player must find
  it.
- **Found card (B)**, using the same board.
- **Basic win not converted (C):** game-end detector for a not-won result with
  the player's rook or queen against a bare king; new headline; last-card
  wording; link to `rook_mate`.
- Fix the move-49-type wrong reason: when the tablebase shows that taking the
  named pawn also draws, the caption may not claim "go take the pawn".
- Events recorded: card shown, board opened, each try, hints used, found
  (yes/no), prove-it passed (yes/no).

## 4. Explicitly out of scope (V1)

- **The return-in-a-few-days position (Step 5).** V1 says "coming back"
  only if the return is built. It needs a matched-position source (own games
  or Lichess puzzles by theme) and a scheduler. It comes next, after V1 shows
  players open the board.
- Hint questions for families other than "the king supports the passed pawn".
  More families are added one at a time, each checked on positions first.
- A new curriculum lesson for "the king walks with the passed pawn". V1
  teaches from the player's own position only.
- Provisioning local Syzygy tables in prod (see Q3).
- Home-page callout for only-move lessons.
- The coach (academy) version. Coaches can already open any position on the
  coach board.
- Queen against a bare king and other basic wins beyond the rook/queen vs
  bare king check.
- Changing how the move is graded (blunder/mistake). Only the words and the
  teaching flow change.

## 5. Success criteria

Measured over the first 4 weeks after launch, on players shown a missed card:

- **≥ 30%** tap "Find it on the board".
- Of those, **≥ 50%** find the winning move (hints allowed), and **≥ 50%** of
  finders pass the prove-it step.
- **Zero** cards where the tablebase (≤7 pieces) disagrees with the claim.
  Checked offline on every card shown.
- For C: **every** game ending in rook or queen against a bare king, not won,
  gets the new headline. Checked on the 4 known games and every new one.

## 6. Open questions

1. **What counts as "only move"?**
   *Why open:* the current 150 cp gap fires on 41% of games when the player
   was winning. That is probably too many to be "the one move that mattered".
   It also counts +900 vs +700 (both winning) as an only move.
   *Unblock:* recompute on win/draw/loss classes over the same 600 games,
   read 30 fires by hand, then lock with `/lock-via-data`.
2. **Is `eval_before` from White's side for every game?**
   *Why open:* the winning filter assumes it; not checked for games where the
   player is Black.
   *Unblock:* check 5 such games against the stored mate info.
3. **Tablebase source: the lichess API or local tables?**
   *Why open:* the API is free and covers 7 pieces, but it is an outside
   service, called at analysis time. Local tables were judged not worth it on
   10-19 (only 14 of 444 misses have 7 or fewer pieces). Mohit's call.
   *Unblock:* Mohit decides.
4. **One lesson per game, or more?**
   *Why open:* this game had four misses of the same idea. One lesson teaches
   it; four repeat it.
   *Unblock:* Mohit decides. Default: one, the first miss.
5. **Hint wording for positions outside the checked family.**
   *Why open:* automatic "why" questions for any position are not solved. V1
   falls back to the arrow.
   *Unblock:* measure how many of the 444 misses fall in the king-supports-pawn
   family.

## 7. Pre-code requirements

- Mohit signs off on this document.
- Q1 locked from data: the only-move definition, with 30 hand-read fires.
- Q2 checked.
- Q3 decided by Mohit.
- The computing cost of the extra pass on every player move is measured.
  It is not a design limit (11-12 rule), but the time per game must be known
  before a deploy.
- `/audit-pre-code` passes.
