# Caption quality — handover, 2026-09-24

Context for an agent working on caption quality. Everything below was
measured today against a restored copy of production, not inferred.

---

## First, a correction worth having up front

**The facts are not being thrown away on the caption path.** `extract_facts`
returns **99 keys** and the caption pipeline receives all of them —
`played_hangs_square`, `opp_reply_creates_fork`, `attacker_count`,
`threats_created`, `named_fork_evidence`, and so on. There is no lossy step to
undo here and nothing to recover.

(The lossy step is real but lives elsewhere: `move_observations` flattens a
move to a single `subtype` enum, which is why `Nxf3+` must choose between
"fork" and "discovered attack". That affects the focus/coaching layer, not
caption rendering.)

## The single most useful technique: check the promise

Take what the caption **literally says**, compute it on the board, count the
fires where it is false. No engine call, no model judgement.

This found five principles stating things the position did not support, with
false rates from 21% to 63%. Examples:

| principle | its claim | false on |
|---|---|---|
| `DEF_MOST_ATTACKED` | "multiple pieces attacked" | 62.7% |
| `MID_PAWN_BREAK` | "the pawn break opens the line" | 60.4% |
| `OP_LOOSE_KING_PAWNS` | "castle first, push later" | 25.2% |
| `OP_BISHOP_BLOCKED` | "this move blocks your bishop" | 23.4% |
| `END_KING_ACTIVE` | "walk it toward the centre" | 21.7% |

**Always pair it with a negative control.** Run the same check against every
position in the corpus, not only the fires. A check that cannot return False
scores a perfect record and means nothing — `TAC_HANGING_PIECE` passed at 0%
false against a check ("a loose piece exists somewhere") that is true almost
everywhere. Read two columns together:

```
false-on-fires low  + false-on-all high  -> the detector tells the truth
false-on-fires low  + false-on-all low   -> the check is vacuous
false-on-fires high                      -> the caption lies this often
```

## The recurring bug: the premise is tested, the accusation is not

Four instances found today, all the same shape. Look for it first in anything
new:

- `DEF_WALK_KING` — gated on "castling rights gone", which is equally true of
  a king that already castled and is safe. Promised pawn cover it did not
  deliver on 81.5% of fires.
- `OP_LOOSE_KING_PAWNS` — told already-castled kings to castle first, 25.2%.
- `ignored_king_attack` — 18.3% of the time the player had just **reduced**
  the pressure on their own king, one of them by eight squares, and was told
  they ignored the attack.
- `_p_op_same_piece_twice` — said "multiple pieces are still on their starting
  squares" when fewer than two were, 13.4%.

The pattern: the gate tests that a *situation* exists, then asserts the player
*failed at it*, without testing the failure.

## Where claim checks belong

`services/caption_claim_verifier.py`. Its contract is "right or silent" —
returning `(False, reason)` abstains and hands the move to the narrator, which
keeps coverage while dropping the unsupported claim. Follow the existing
`blunder_recapture_even_trade` / `blunder_best_move_cannot_rescue` pattern
rather than inventing a new mechanism.

## Do not spend time on the 35 caption principles

All of them are graded **shadow** (`caption=False`, `plan=False`). Not one has
ever reached a user. I spent most of a day there before checking. What
actually renders is the 7 caption-graded ids in `detector_quality._AUTHORIZATIONS`.

## Numbers you need to read any measurement here

- **56.4%** of all user moves are engine-approved (`cp_loss <= 20`). Without
  this denominator an agreement rate is unreadable: a detector firing at ~56%
  agreement carries *zero* information about move quality, not "pretty good".
- **6 of 35** predicates hard-gate on the engine: 3 require `played == best`
  (they can only ever congratulate — `TAC_PIN_PATTERN` 99.4%,
  `TAC_DISCOVERED_PATTERN` 100%), and 3 require `played != best` (their 0.0%
  agreement is **tautological** — never cite it as evidence of quality).
- `TAC_CHANGED_AFTER_MOVE` fires **1,826** times and is a catch-all whose only
  line is generic scanning advice. Deliberately not gated: it makes no specific
  claim to falsify.
- Caption word cap is 60 (`caption_config.json`); truncation cuts at a sentence
  boundary with **no ellipsis**, so a fallback must shed optional clauses and
  never the principle.

## Shipped today (all on `feat/band-aware-lesson-question`)

- `f5441b92` — `_p_tac_fork_pattern` built its output from a variable assigned
  nowhere. Every fork raised `NameError` and `_principles_violated` swallows
  bare exceptions, so a crash and a clean no-fire were indistinguishable. 60 of
  60 engine-endorsed forks raised. **Note:** this is the caption *principle*,
  not fork detection — `shape_detectors` / `fork_puzzle_proof` were always fine
  and carry the Lichess validation.
- `b210793c`, `a3325812` — seven promise gates, each on its own caption's words.
- `8f46fb87` — `ignored_king_attack`, plus a promotion packet awaiting signoff.
- `24a26654` — the verifier now refuses "X was better" when X still leaves the
  player **a queen down or worse** (3.8% of mistake captions). Threshold is
  Mohit's: at 600-1500, three pawns down is very winnable even though an engine
  calls it lost.

## Four mistakes I made — do not repeat them

1. **Summed across items instead of checking each.** Totalled bishop mobility
   across both bishops; `d2-d3` shuts in the c4 bishop while *freeing* the c1
   one, so the total rises on exactly the move being complained about. Fixing it
   dropped `OP_BISHOP_BLOCKED` from 62.3% false to 23.4%.
2. **Scored every fire against the `cue_best` wording.** Principles with
   `gate_policy: endorsement_preferred` render a different sentence
   (`cue_absent`: "Other plans this move. Generally …") when the engine wants
   something else, so engine-choice claims only apply when endorsement is
   actually `"best"`. This dropped `END_KING_ACTIVE` from 46.6% to 21.7%.
3. **Passed an empty `move_history_san`.** `extract_facts` only rebuilds
   `board_before.move_stack` when handed a history, so the four history-dependent
   predicates could never fire in my harness. I reported `OP_SAME_PIECE_TWICE`
   as dead when it fires on **9.1% of opening positions**. Replay the PGN.
4. **Compared two things that answer different questions.** Called
   `detect_knight_fork(board)` and read its output as "this move is a fork"; it
   takes only a board and answers "is a fork available", true on 42% of
   positions. Produced a meaningless number.

## Sanity rule

If a measurement says a long-standing detector is catastrophically broken,
suspect the harness first. Three of my six "the detector lies" findings today
were my own measurement error, caught before they became code.
