# Punishment Resolver — Scope

**Status:** draft, awaiting Mohit sign-off
**Date:** 2026-09-24

## The problem in one sentence

Our captions say *what move was better* instead of *what the opponent
got*, because the WHY is selected from ~100 hand-written sentences
rather than derived from the board.

## Evidence this is real (measured, not asserted)

Taken from 2,500 analysed games / 24,577 engine-confirmed mistakes
(cp_loss >= 50). Full numbers in the session log.

- `R12_blunder.json` holds **~100 variants** in one flat priority list.
  Sorting them by what they actually are:
  | kind | count | example |
  |---|---|---|
  | consequence (what happened) | ~10 | `failure_hangs_piece` |
  | format (same sentence, different punctuation) | ~18 | `user_with_best_em_dash` |
  | scenario (named special case) | ~55 | `why_user_queen_chased` |
  | filler (not a reason) | ~11 | `bs_pieces_on_back_rank` |
- Because they compete in one list, **the outcome depends on list
  order, not on truth.** Proven: on one position (12.Qd3 in game
  e8bda807) three entries were eligible at once; making a *fourth*
  true fact available rerouted the caption to a WORSE one and the
  claim verifier then deleted it.
- That is the disease: **more truth produced a worse caption.**

## What we are building

One module, `services/punishment_resolver.py`. It answers a single
question from the board, in both directions:

- *we blundered* -> push our move, push `pv_after_played[0]`.
  What did their reply DO to us?
- *they blundered* -> push their move, push `pv_after_best[0]`.
  What would our reply DO to them?

Same function, sides swapped. It returns a **structured result, not a
string**:

```
Punishment(
    direction   = we_were_punished | we_missed_the_punishment
    mechanism   = MATE | WINS_MATERIAL | FORK | TRAPPED | FORCES_RETREAT | PROMOTES
    agent_move  = Bf5
    victim      = queen on d3
    payoff_cp   = 900
    line        = [Bf5, Qd1]        # the proof
)
```

### The one design rule that kills the disease

**Compute every mechanism, then rank by payoff. Never first-match-wins.**

```
MATE > WINS_MATERIAL > FORK > TRAPPED > PROMOTES > FORCES_RETREAT
```

Today the answer depends on a position in a JSON list. After this it
depends on a number. That single change makes "the system knows more"
imply "the caption gets better", which is currently false.

It also fixes "it gives check" for free: a check stops being a
competing template. The resolver keeps walking the line to the payoff
(`Rc8+ Ke7 Rc7+ Ke6 Rxa7` -> **wins the pawn back**), because material
outranks form.

## Coverage (measured before building)

| direction | coverage of all mistakes |
|---|---|
| 1 — punishment we received | 46.5% |
| + 2 — punishment we missed | **57.4%** |
| deep-PV re-test (pending) | TBD |

By severity, direction 1 only:

| band | n | measurable | nothing concrete |
|---|---|---|---|
| blunders >= 300 | 5,324 | ~62% | 25% |
| mistakes 100-299 | 9,983 | ~52% | 36% |
| inaccuracies 50-99 | 9,270 | ~28% | 41% |

The design covers the moves that matter and thins out on small ones,
which is the right shape.

## Two data bugs found on the way (fix independently)

1. **13.8% of mistakes have no stored engine line at all** — 670 of 674
   sampled have neither `pv_after_played` nor `pv_after_best`. Not an
   old-games artefact (47% of games are clean, 7% fully missing, rest
   partial), so the analyser drops PVs per-move under some condition.
   No resolver can explain those until this is fixed.
2. **Stored PVs are only 4 plies.** 3,243 of 3,978 sampled are exactly
   length 4, so any punishment needing 3+ opponent moves is invisible
   and silently files as "positional".

## Non-goals

- Not rewriting `caption_facts.py`. The board understanding is good and
  stays. This replaces the **selection** layer only.
- Not deleting `R12_blunder.json` on day one. It shrinks to **wording**:
  ~8 sentence shapes plus tone. The `select_variant` block goes away,
  because ranking replaces it.
- Not enumerating chess scenarios. Scenarios are unbounded; measurable
  consequences are not. Scenario text (e.g. `queen_chased`) becomes
  nicer *wording for a mechanism*, never a competitor to one.

## The honest-silence path (required, not optional)

~42% of mistakes have no derivable punishment in either direction.
That bucket is exactly where the current system invents things —
`"Before sacrificing in the endgame..."` fired on a move with
`is_sacrifice=False`; a promotion rendered as "you push the h-pawn,
claiming a little space".

Rule: **when no mechanism fires, say less, truthfully.** Name the
better move and, if and only if its payoff is derivable, what it
achieves. Never synthesise a story to fill the slot.

## How we know it worked

- Build a gold set of ~200 real mistakes with hand-written WHYs first.
- Run resolver and current path side by side over the same moves.
- Retire a variant only where the resolver wins on gold.
- Ship behind a flag, one mechanism at a time, starting with MATE and
  WINS_MATERIAL (clearest truth).

## Rollout

Default-off env flag -> A/B -> 10% -> 100% -> delete legacy variants.

## Open question for Mohit

57.4% verified coverage, possibly higher once the two data bugs are
fixed. Is that enough to justify the rewrite, or do you want the data
bugs fixed first and the coverage re-measured before we commit?
