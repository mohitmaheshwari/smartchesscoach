# A move that keeps a forced mate is not a mistake

## The card that started it

Mohit, 2026-10-05, on a K+2B vs K+P endgame: "i thought we fixed it, we
recognised this is an endgame theory to learn 2 bishps mate, but look at it".

The card read **"Bg5 — Blunder — Tactical · missed tactic"**, with
"You didn't calculate the opponent's response" and a grey box saying
"We can't show a clear reason here."

At depth 22 the engine says: **Be6 mates in 9. Ke6 mates in 10. Bg5 mates
in 20.** He was mating before the move and mating after it. The card called
that a blunder, and recommended a move that is not the engine's best either.

## What is actually wrong

`mate_info` is referenced **zero** times in the whole render path.
Severity comes from `cp_loss`, and in mate positions `cp_loss` is the
difference between two clamped mate scores. "Mate in 9 became mate in 20"
and "you dropped a rook" are the same number to this code.

Measured over the stored corpus, on the **rendered cards** — the text a
person actually sees:

- **3,966** cards are tiered as an error while the mover still has a forced
  mate
- **3,770** of those say **blunder**; 96 say mistake, 99 inaccuracy, 1 serious
- in **2,609** of them the mate got **faster** — the move was an improvement
  and we called it a blunder

Examples, with the clamped mate eval before and after:

```
game_417 m32 Kf4  blunder  9990 -> 9990   same mate distance
461511c5 m34 Bg3  blunder  9850 -> 9950   mate got FASTER
3da52c5e m36 Kg1  blunder  9950 -> 9950
3da52c5e m37 Kh1  blunder  9960 -> 9960
3da52c5e m38 Kg2  blunder  9970 -> 9970
```

Those last three are one player told "blunder" on three consecutive moves
while delivering mate.

This is a lower bound. 229,374 of 368,160 error-tier cards could not be
joined to an eval row at all, because `move_evaluations` stores only user
moves, so opponent cards are not counted here.

A separate, smaller count over the analysis worker's own stored
`evaluation` field gives 94 — that is a DIFFERENT field from the card
severity, and quoting it would understate the problem by forty times.

## What changes

One guard in `compute_severity_for_move`, beside the existing
"Mate dominance (v159)" block that already handles *played move is
checkmate*. The new case is *a forced mate existed before and still exists
after*.

A preserved forced mate is never `inaccuracy` / `mistake` / `serious` /
`blunder`. It becomes `good` for a user move and `context` for an opponent
move, exactly as the sibling mate guard does.

### How a mate is detected

From the white-POV evals the function already receives, converted to the
mover's POV. No new parameter, no new data source.

The threshold is read off the distribution, not chosen:

```
evals WITH a mate score : n=15,184  min=9650  p50=9950  max=10000
evals WITHOUT a mate    : n=176,928 min=0     p50=188   max=8308
overlap in either direction: 0 of 192,112 values
```

`9000` sits in the empty gap between 8308 and 9650.

Higher eval means shorter mate, verified rather than assumed: across 5,081
mate-preserved rows where the distance changed, eval order and mate order
agree **5,081 to 0**.

## What this does NOT do

- It does not teach the two-bishop mate. We have no such lesson:
  `basic_mates` holds only `queen_mate` and `rook_mate`, and nothing in the
  endgame data mentions two bishops. Two-bishop endgames appear in **41**
  rows out of **18,480** analyses (~0.2%), so review-time teaching for them
  would reach almost nobody. If it is worth teaching it belongs in the
  lesson curriculum, on demand.
- It does not add `K+B+B vs K` to `endgame_classifier.is_theoretical`.
  That whitelist already claims `K+N+B vs K` with no lesson behind it;
  adding another would assert a theory we cannot teach, and fail silently.
- It does not change `exact_endgame_service`, which returns `None` here by
  design — it speaks only when a move changes the outcome class
  (win -> draw / loss), never when technique degrades inside a win.

## How we know it worked

- A preserved mate never carries an error tier.
- The 90 faster-mate moves stop being called inaccuracies.
- Positions with no mate are untouched: no eval below 9000 is affected.
- Severity for the whole corpus is unchanged except on mate-preserved moves.
