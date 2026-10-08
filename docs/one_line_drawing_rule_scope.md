# One rule for drawing the engine's line

## Why this exists

Mohit, 2026-10-06, after the fifth arrow fix in a row:

> "why we are not able to show up the full idea, do we have to do it for all
> positions?? i thought you understood the idea"

He is right, and the count says so. `caption_pipeline.py` holds **eight** arrow
builders chosen between at **22** call sites:

```
_check_attack_arrows        _mate_geometry_arrows
_reply_attack_arrows        _abandoned_defender_arrows
_line_sequence_arrows       _punishment_arrows
winning_plan_arrows         recommended_move_arrows
```

Four of those were written on 2026-10-06, each in response to one screenshot.
That is the whole problem: every new card shape finds another gap, because the
eighth builder repeats the bug the first one had instead of sharing the logic.

His idea has been one rule throughout:

> Take the engine's line from here. Draw it to its payoff — the move, the
> forced replies, and the capture or mate that is the point.

That rule already covers every case we hit today:

| card | same rule, different payoff |
|---|---|
| `Rc8#` | payoff = the mate |
| `Bxf2+` | payoff = the recapture that wins the piece back |
| `Be5` | payoff = the capture after the chase |
| `Bb3` | payoff = what they win |
| `bxc5` | payoff = the capture |

## What changes

One primitive, `draw_engine_line(board, line, max_arrows)`, owning everything
the scattered builders learned separately:

- **payoff ranking**: mate > material recovered after a sacrifice > net
  material won > forcing move. v199 had to add the recapture rule to
  `_line_sequence_arrows` alone; `winning_plan_arrows` still cannot see mate.
- **the victim's flight** — the piece running, so a chase reads as a chase
  (v195, `winning_plan_arrows` only).
- **the hunters** — our moves that attack the square it stands on, which is
  what made the a8 bishop appear (v195, `winning_plan_arrows` only).
- **our piece's route** — so no arrow starts where our piece has not arrived
  (v196, `winning_plan_arrows` only).
- **net-gain guard** — a recapture is not a win (v193,
  `winning_plan_arrows` only).
- **colours**: blue ours, palegrey theirs, green the payoff
  (`_line_sequence_arrows` only).

Six of the eight builders already take a line and become callers that supply
one. Two do not and stay as they are:

- `_mate_geometry_arrows` draws coverage on the board AFTER the mating move,
  not a sequence.
- `_reply_attack_arrows` draws what a reply threatens from where it lands.

## What must not regress

Every behaviour below is pinned by a test today and must still hold:

- `_check_attack_arrows` output on MISSED_FORK — three tests assert the exact
  pairs and the FEN it ships with.
- `_punishment_arrows` measured at 2% bad / 0 illegal over 400 games.
- The played board carries the plan (v194) but the best-move surface keeps its
  own FEN.
- Sacrifice lines reach the recapture, not the first check (v199).
- No arrow starts from a square our piece has not reached (v196).
- A queen trade is never drawn as winning a queen (v193).

## How we will know

- The full regression stays at its baseline of 7 pre-existing failures.
- Every arrow suite passes unchanged: `test_line_sequence_arrows`,
  `test_winning_plan_arrows`, `test_punishment_arrows`,
  `test_mate_geometry_arrows`, `test_abandoned_defender_arrows`,
  `test_recommended_move_is_drawn`, `test_teach_arrow_matches_rendered_board`,
  `test_sacrifice_line_reaches_its_payoff`.
- Corpus coverage does not fall: 236 plans / 156 abandoned-defender pictures /
  151 back-rank warnings measured over 400 games before the change.

## What this does NOT do

It does not add a new card shape or change any wording. If coverage rises it
is because a builder gained logic another one already had — which is the point
— but the aim is one rule, not more arrows.
