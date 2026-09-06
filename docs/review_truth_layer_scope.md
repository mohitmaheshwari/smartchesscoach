# Review Truth Layer — scope

**Status:** in progress
**Date:** 2026-09-06
**Author:** Claude (for Mohit)
**Trigger:** comparing our game review against an independent engine review on
lichess `qBNJQg3g` (bhutramohit, 2026-09-05) surfaced four defects. This scope
covers fixing them and proving the fix across all 744 analysed games for
`user_8b599930d7ef`.

---

## The problem in one sentence

Our per-move detection is as good as an independent reference — but the layer
that turns detection into words ships claims the game's own data contradicts,
and cannot say the one thing that mattered most in the reference game.

## What the user saw (the motivating game)

A 2+1 bullet game the player **won on the board and lost on the clock**: our own
cards record `mover_state_after: "winning"` and `stayed_winning: True` on **all
54** user moves after the "critical" move, minimum win probability 0.73, 1.00
from move 45. He queened a second pawn on move 53 and flagged on move 71.

Our review said:

> "You were winning. Move 16 flipped the game — and it never came back."

That is false, and it is false *against data we ourselves stored in the same
document*. It also never mentions the clock.

---

## The four defects

| # | Defect | Where | Status |
|---|--------|-------|--------|
| D1 | Mistake captions that never explain the **played** move — only the alternative, or nothing | `caption_pipeline` / `caption_fallback_tiers` | measuring |
| D2 | Narrative asserts collapse ("never came back") contradicting the game's own `stayed_winning` | `decryption_voice/player_decryption.py` | diagnosed |
| D3 | `time_collapse` is mapped to the blunder scenario; no time copy exists at all | `decryption_voice/truth_line.py:58` | diagnosed |
| D4 | Praise/soft framing on moves that lost real advantage, plus a dangling-subject grammar bug | `caption_fallback_tiers.py:78` | diagnosed |

### D1 — what "explains the played move" means

Three classes, measured structurally (not by keyword presence):

- `PLAYED_WHY` — names a consequence of the move the user actually played
  ("drops the pawn after Bxe5", "loses to Qxd3+", "leaves your bishop
  undefended"). **This is the only class that answers "why??".**
- `ALT_WHY_ONLY` — the only reason given is a benefit of the recommended move
  ("Nxd3+ was stronger — it trades his bishop"). The student still does not
  know what was wrong with their move.
- `NO_WHY` — verdict plus, at most, a generic principle.

### D3 — why it is structural, not a copy tweak

`game_reason_classifier` already returns `time_collapse` correctly, and
`termination` is populated on 14,767 of 15,029 stored games. The narrative layer
then throws that away:

```python
_REASON_TO_SCENARIO = { ..., "time_collapse": SCENARIO_BLUNDERED }
```

There is no `SCENARIO_TIME` in `IDENTITY_BY_SCENARIO`, `ANCHOR_PHRASES_BY_SCENARIO`,
`TRIGGER_BY_SCENARIO`, `STORY_BY_SCENARIO`, `PATTERN_BY_SCENARIO` or
`CARRY_FORWARD_BY_SCENARIO`. So "you had a won game and lost on the clock" is
unreachable by construction. D2 is largely a *symptom* of D3: blunder copy is
forced onto a game that no blunder decided.

---

## The fix

### 1. A truth gate for the narrative layer

`decryption_voice/validators.py` today validates **style** (word budgets, banned
engine vocabulary, concreteness). It does not validate **facts**. Captions have
both a style path and a per-FEN claim verifier; the narrative has only style.

Add `validate_narrative_claims(text, facts) -> list[str]`, checked on every
Truth / Player-Decryption render, where `facts` are derived from the same cards
the narrative describes:

| Claim in text | Requires |
|---|---|
| "never came back", "it never", "flipped the game", "gave it away", "cost everything" | NOT `stayed_winning_after_critical` |
| "You were winning" | `was_winning_at_some_point` |
| "ran out of time", "the clock" | `termination == "timeout"` |

On violation: fall back to a variant that is true for this game, exactly as the
caption layer falls back to the verified floor. Never ship the violating line.

### 2. `SCENARIO_TIME`

A sixth scenario with its own copy in all six pools, routed from
`time_collapse`, and split by whether the player was still winning when the flag
fell (the honest split: "you were winning when the flag fell" vs "the clock
caught a position already going wrong").

### 3. D4 grammar + framing

- `caption_fallback_tiers.py:78` — `f" Though {best} was a bit stronger, {why}."`
  renders "Though Be3 was a bit stronger, develops a piece." `best_move_why`
  returns bare verb phrases ("develops a piece", "wins a pawn", "takes the
  center"), so the clause has no subject. Add `it`.
- Add a `DANGLING_SUBJECT` rule to `scripts/pwc_coaching_lint.py` so this class
  cannot reach a screenshot again.

---

## Acceptance

Measured by re-rendering all 744 analysed games for `user_8b599930d7ef` on the
fixed code and comparing to the pre-fix baseline captured on the same corpus:

1. **Zero** narrative claims that fail `validate_narrative_claims`. This is a
   truth gate, so the bar is zero, not "fewer".
2. Every game with `termination == "timeout"` renders time copy, and no timeout
   game renders "blundered" identity copy.
3. `PLAYED_WHY` share of `mistake`/`blunder` captions strictly increases against
   baseline, with **no** increase in verifier rejections (i.e. we add real whys,
   not unverified ones).
4. `pwc_coaching_lint.py` clean on the rendered corpus.
5. The motivating game `qBNJQg3g` renders a review that names the clock and does
   not claim the game never came back.

Baseline and post-fix numbers are recorded in this document before merge.

## Out of scope

- The accuracy-formula divergence (we report 74.1% where a Lichess-style
  win-percentage formula reports 94.2% on the identical moves). Real, and a
  credibility exposure, but it is a product decision about which formula to
  show, not a defect to fix silently.
- Reconciling local `working-code` (131 behind / 11 ahead of origin). Flagged
  separately; this work branches from `origin/working-code`.

---

## Addendum, 2026-09-06 — what is actually IN the unexplained bucket

Measured on the 455 mistakes from this user's corpus that reach
`R16_board_state_fallback` / `HELD_FLOOR` with no played-move why. Recorded
because the intuitive answers (write positional detectors / fix tactical
routing) both turn out to be much smaller than they feel.

### Composition of the 455

| what is really going on | share |
|---|---|
| No material change **and** no meaningful geometry change | **65.5%** |
| Material heuristic fires but the engine prefers a quiet reply (nothing hangs) | 12.3% |
| No `pv_after_played` stored at all | 14.5% |
| **Confirmed tactical** — engine's actual reply IS a capture | **7.7%** |

Method: for every move, replay `fen_before` + played SAN, compute the best
static-exchange capture available to the opponent, then cross-check against the
engine's real first reply from the stored PV. A crude "opponent can win
material" screen said 26.8%; cross-checking against the engine's actual reply
cut that to 7.7%. **Do not quote the screen without the cross-check** — it
over-fires by more than 3x.

### Positional shapes present (differential, before vs after the played move)

| shape | count | share of 455 |
|---|---|---|
| piece went passive (mobility drop >= 4) | 27 | 5.9% |
| pawn move blocks own bishop (pawns on its colour >= 4 and rising) | 21 | 4.6% |
| gave up king shelter | 15 | 3.3% |
| rook left / lost its open file | 12 | 2.6% |
| self-blocking (own total mobility drop >= 6) | 10 | 2.2% |
| created doubled pawn | 7 | 1.5% |
| created isolated pawn | 5 | 1.1% |
| trapped the moved piece (>=4 squares down to <=1) | 4 | 0.9% |

**Union coverage: 7.5%.** Every measure above is board arithmetic computed
before and after the move, so a caption built on one is verifiable per-FEN and
will survive the claim gate. The mechanism is sound; the addressable volume is
small.

### Why these moves fall through today

`R12_blunder`'s trigger is permissive (`cp_loss >= 30`), so the rule IS
reached. The suppression is deliberate, per its own `_trigger_note`: a USER
move with `cp_loss < 250` and no why-clause is silenced. 388 of the 455 sit at
cp 100-199, so they are suppressed by design and land on the board-state
fallback. **The suppression is not the bug.** The bug is that we still label
these moves "mistake" to the player while having nothing concrete to say.

### Consequence for the roadmap

1. **Genuine defects worth fixing** — the 7.7% confirmed-tactical (a nameable
   cause we fail to state) and the 14.5% with no stored PV.
2. **Positional failure modes** — worth building, but scoped honestly at ~7.5%
   of this bucket, not as the answer to the 65% headline.
3. **The ~300 no-consequence moves are a product question, not an engineering
   one**: at cp 100-199 with no material and no geometry change, for a
   ~1000-1300 player, these are marginal engine preferences. Raising the
   user-move flagging bar would make the remaining flags mean more. Deliberately
   left undecided here — Mohit's call.

### Caveat on the headline metric

The PLAYED_WHY / ALT_WHY_ONLY / NO_WHY split comes from a structural text
classifier (`backend/scripts/caption_why_class.py`), hand-validated on 7
constructed cases and then on a 30-row stratified sample of real captions.
On that sample PLAYED_WHY precision was 10/10; two NO_WHY rows were really
ALT_WHY_ONLY (both stay inside the "does not explain the played move" bucket)
and one row should not have been in the denominator (played move == engine
best, yet flagged `serious`). Treat the headline as +/- 2pp, not exact.
