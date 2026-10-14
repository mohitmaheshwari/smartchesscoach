# `cct_forcing` reconciliation — the tags are misaligned

**Date:** 2026-10-14 · Read-only. No code, record or flag modified.

**Verdict: the gate fails.** `decision_register` is **unsupported** and must
not underpin a coaching claim until the CCT tags are rebuilt. The clock fields
are untouched by the fault and are **safe**.

---

## 1. Method, and why a disagreement means what it means

The stored tags are computed with python-chess board truth —
`sim.is_check()` and `board_before.is_capture(move)` in
`services/cct_detector.py`. So the *definition* is sound and SAN parsing is not
an improvement on it.

The probe therefore recomputes each tag **from the same row's own `fen_before`
and `move_uci`**. A mismatch cannot be a definitional difference. It can only
mean the tag is attached to a different move than the one it describes.

`analysis_worker.py:1322` is the suspect:

```python
tagged_by_ply = {t["ply"]: t for t in tagged_user_moves}
for i, me in enumerate(move_evaluations):
    t = tagged_by_ply.get(i)
```

User-only CCT tags are keyed by their own ply and merged onto
`move_evaluations` by enumeration index. If those index spaces differ, a
correctly computed tag lands on the wrong row.

**Sample:** 600 games, **9,304 user moves** carrying CCT tags, **0 unreplayable
rows**.

---

## 2. Measurements

### Field-level — same definition on both sides, no caveat

| field | agree | false positive | false negative | **disagreement** |
|---|---|---|---|---|
| `cct_is_check` | 8,065 | 396 | 843 | **13.3%** |
| `cct_is_capture` | 6,038 | 1,563 | 1,703 | **35.1%** |
| `cct_had_forcing_options` | 7,072 | 1,027 | 1,205 | **24.0%** |

**`cct_is_capture` is the proof.** It is literally `board.is_capture(move)`. A
field computed that way cannot be 35% wrong about its own position. Errors run
in *both* directions in every field, which rules out a systematic one-way bug
and points at random misplacement.

### SAN is not the fix

| witness | agreement with board truth |
|---|---|
| SAN `+`/`#` vs `gives_check` | **9,304 / 9,304 (100%)** |
| SAN `x` vs `is_capture` | **9,304 / 9,304 (100%)** |

`services/cognitive_gap_subtypes.py:11` says *"Never trusts
`cct_is_capture` / `cct_forcing` (SAN 'x' / '+' / '#' instead)"*. **Its
instinct was right and its reason was wrong.** SAN and the board are
identical here, so switching to SAN changes nothing — the fault is the
join, not the primitive. Anyone adopting that service's workaround would
believe they had fixed this.

### Representative examples

Unambiguous cases failing in both directions:

| stored | truth | move | why it is unambiguous |
|---|---|---|---|
| `is_check = False` | check | **Bxf7+** | SAN ends in `+` |
| `is_check = True` | not check | **Nd5** | no check by any reading |
| `is_capture = False` | capture | **dxe5** | SAN contains `x` |
| `is_capture = True` | not capture | **Nf6** | quiet development move |
| `had_forcing_options = False` | options existed | **Qxd5** available | a capture was legal |

### It is not a constant offset

Best-fitting shift for each game's capture tags, over 405 usable games:

```
+0  136 games      -1  102      -2  77      +1  46
-3   29 games      +2   12      +3   3
```

Only a third of games fit shift zero, and the remainder scatter across ±3.
**There is no single realignment that repairs the corpus** — the tags must be
recomputed per game.

---

## 3. Played a forcing move vs had one available

The brief is right that these are different claims, and they fail differently.

| claim | field | status |
|---|---|---|
| "you **played** a forcing move" | `cct_forcing` (= check ∨ capture ∨ threat) | **unsupported** — its two verifiable components disagree at 13.3% and 35.1% |
| "a forcing move **was available**" | `cct_had_forcing_options` | **unsupported** — 24.0% disagreement; 1,205 moves where options existed and the tag said none |

The second is the more dangerous of the two for coaching, because *"you had a
forcing option and played quiet"* is an accusation about the player's judgement.
On 1,027 moves the tag claims options existed when none did.

---

## 4. Impact on `decision_register` and coaching conclusions

Recomputing the register with board-truth inputs, holding
`cct_best_was_forcing` constant (it needs the engine and cannot be
independently rebuilt):

```
same verdict                                      3,155   43.8%
wrong_register        -> quiet_when_best_was_quiet 1,177   16.3%
quiet_when_best_was_quiet -> wrong_register          851   11.8%
None                  -> quiet_when_best_was_quiet   491    6.8%
wrong_register        -> None                        435    6.0%
None                  -> wrong_register              373    5.2%
quiet_when_best_was_quiet -> None                    293    4.1%
forcing_when_best_was_forcing -> wrong_register      278    3.9%

verdict changes on 4,047 of 7,202 registered moves  = 56.2%
```

**1,177 moves are currently labelled `wrong_register` — "you played the wrong
kind of move" — where board truth says the player was right.** 851 run the
other way.

**Caveat, stated plainly:** my recompute treats forcing as `check ∨ capture`
and omits `creates_threat`, which the stored definition includes. That inflates
the 56.2%. The field-level figures in §2 carry no such caveat, and
`is_capture` at 35.1% is sufficient on its own.

**What this does and does not contaminate.** `decision_register` is written by
`move_observation_deriver` into `move_observations` (224,801 populated rows).
`cognitive_gap`, `cp_loss`, decay, the focus picker and the caption pipeline do
**not** read it — so **no shipped coaching text is currently wrong because of
this.** The damage is to the dimension we were about to build on, which is the
better outcome of the two.

---

## 5. The clock, by time control and phase — this part is sound

260,000 timed observations matched to a time control, **0 unmatched**.

| time control | phase | n | median | p90 | mistake+blunder |
|---|---|---|---|---|---|
| rapid | opening | 63,298 | 4.2s | 20.0s | 16.1% |
| rapid | middlegame | 56,763 | **6.7s** | 27.6s | **16.4%** |
| rapid | endgame | 25,064 | 3.0s | 13.3s | 8.5% |
| blitz | opening | 44,666 | 2.5s | 10.1s | 12.6% |
| blitz | middlegame | 42,394 | 4.0s | 13.8s | 15.4% |
| blitz | endgame | 17,402 | **1.7s** | 6.2s | 8.5% |

Every cell has thousands of observations. This is the densest trustworthy
behavioural data in the product.

**Where the behavioural flags concentrate:**

```
rapid / opening    / snap_decision            316
blitz / endgame    / time_pressure_blunder    210
blitz / middlegame / time_pressure_blunder    151
rapid / middlegame / snap_decision            118
rapid / opening    / slow_paralysis            83
```

**Two patterns worth a coach's attention:**

1. **Players spend least time in the endgame and most in the middlegame**, in
   both time controls. Endgame medians are *below* opening medians (3.0s vs
   4.2s rapid; 1.7s vs 2.5s blitz).
2. **`time_pressure_blunder` is concentrated in blitz endgames** — the single
   largest flag cell. That localises the clock problem precisely.

**Two confounds I will not paper over:**

- Endgames have fewer legal moves and more forced sequences, so spending less
  time there is partly *rational*. "You rush your endgames" is **not** supported
  by these medians alone; it needs a per-position-complexity control.
- The lower endgame mistake share (8.5%) may simply reflect fewer pieces and
  fewer ways to err, not better play.

**Data-quality note:** `games.time_control` holds mixed representations — the
word `"rapid"` and the number `"600"` both occur, which is why the table shows
both `rapid` and `rapid (10-30m)` rows. Harmless here; it would bite any
threshold placed on the raw field.

---

## 6. Which decision-making claims are safe, uncertain, unsupported

### Safe — say these

- **"You took N seconds on this move"** and comparisons against *the player's
  own pace in that game*. Sourced from PGN `%clk`, engine-independent, 79.6%
  populated.
- **`snap_decision` and `slow_paralysis`.** Within-player normalised, threshold
  taken from the measured distribution (p10 = 0.25×, flagging 2.3% of
  mistakes), looser cuts measured and rejected at 4.8% and 11.6%.
- **Phase and time-control splits of time spent**, as description, with the
  complexity confound stated.
- **What a move did on the board** — capture, check, castle, what it left
  undefended — when recomputed from the position rather than read from the CCT
  tags.

### Uncertain — measure before saying

- **`time_pressure_blunder`.** Its clock half is sound; its `quality == "blunder"`
  half is engine-derived. Usable as "you were low on the clock and this move
  cost you", not as a thinking claim.
- **"You rush your endgames."** Directionally visible, confounded by position
  complexity.
- **`found_best_in_critical`, `was_critical_moment`.** Engine-defined
  criticality. Fine as engine facts, not as attention measures.

### Unsupported — do not say

- **`decision_register` in any form.** 56.2% of verdicts change; both verifiable
  inputs are misaligned.
- **"You had a forcing option and played a quiet move."** 24.0% disagreement on
  whether options existed.
- **"You play forcing moves too often / too rarely."** Built on `cct_forcing`.
- **Anything from `thinking_scores`** as a thinking claim — separate finding,
  denominator is the move count and the file says so.

---

## 7. Recommended next steps

**1. Do not fix the merge — recompute the tags.** The shift varies per game, so
no realignment works. `cct_detector.tag_moves_with_cct` is sound; the join is
not. Recomputing CCT inside `move_observation_deriver` from each row's own
`fen_before` + `move_uci` removes the join entirely and makes the tags
self-consistent by construction. *(Estimate: contained. The deriver already
replays positions and already imports `chess`.)*

**2. Re-derive, then re-measure before trusting it.** The backfill skips rows at
the current `SCHEMA_VERSION`, so this needs a version bump or the corrected
tags reach only incidentally-stale rows — the same trap the v20 comment
records, where 12,333 of 16,723 rows would have been left behind.

**3. Keep `cct_best_was_forcing` quarantined.** It cannot be rebuilt from the
board. Until a re-derive proves it aligned, any register verdict depending on
it is still only as good as the old merge.

**4. Build the decision dimension on the clock first.** It is sound, dense
(260k observations), and already supports claims no engine can fake. It does
not depend on step 1.

**5. One cheap check I did not run:** whether the misalignment correlates with
games having opponent moves interleaved in `move_evaluations`. If user-only and
full-game indexing is the mechanism, games where the user is black should skew
differently from white. That would confirm the cause in one query — worth doing
before the rebuild, so the fix is aimed at a proven mechanism rather than a
plausible one.

---

## What this changes about earlier advice

In `MOVE_OBSERVATION_PROVENANCE.md` I called `decision_register` *"the closest
thing we have to a calculation/decision measure"* and *"worth building on"*,
subject to this reconciliation. **That judgement does not survive it.** I had
verified what the field computed, not whether its inputs described the move
they were attached to.

The provenance tiering itself stands: Tier A (clock) is sound, Tier B is sound
when recomputed from the board, Tier D is engine output. What moves is
`decision_register` — out of Tier C and into unsupported until rebuilt.
