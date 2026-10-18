# What the data can support — behavioural measurement, Step 1

*Written for whoever designs the next behavioural detector. Everything here is
measured on production (`chess_coach`, 2026-10-18), not read off a schema. The
question a design needs answered is not which fields exist but what share of
rows carry them, because a field present on half the data cannot control for
anything.*

Sample: 19,921 analysed games, 6,535 move rows read in detail, 20,649 games
and 128 users in total.

---

## 1. What exists for every move

`game_analyses.stockfish_analysis.move_evaluations[]` — one row per move.

| what a design needs | field | share of rows |
|---|---|---|
| Position before / after | `fen_before`, `fen_after` | **100%** |
| The move played | `move` (SAN), `move_uci` | **100%** |
| Engine's choice | `best_move`, `best_move_uci` | **99.9%** |
| Decision quality | `cp_loss` | **100%** |
| Evaluation | `eval_before`, `eval_after`, `eval_swing` | **100%** |
| **Thinking time** | `time_spent_seconds` | **90%** |
| Move number | `move_number` | **100%** |
| Engine lines | `pv_after_best`, `pv_after_played` | 34% |
| Forcing-move context | `cct_is_check`, `cct_is_capture`, `cct_forcing`, `cct_had_forcing_options`, `cct_best_was_forcing` | 47% |
| Mate | `mate_info` | 7.4% |
| Gap label | `cognitive_gap`, `gap_confidence`, `gap_evidence` | 13–16% |
| Flags | `is_best`, `is_critical`, `is_turning_point`, `is_sacrifice`, `is_brilliant` | 99.5% |

### The three absences that constrain a design

**MultiPV does not exist. 0% of rows.** We store the best move and sometimes
its line; we never store the ranked alternatives. So *"examine the actual
decisions and opportunities"* cannot be answered from stored data. It needs an
engine pass. `backend/scripts/enrich_multipv.py` exists and has only ever been
run over ~50 games.

**Opponent moves have no engine truth. 0 rows.** `move_evaluations` stores the
user's moves only. Anything comparing the two players — or controlling for what
the opponent did — has to re-run an engine over the PGN.
`services/both_sides_review.py` does exactly that for one game at a time and
costs ~7s per game at depth 12.

**There is no measure of position difficulty.** Nothing stored is one. The
`cct_*` family (was a forcing move available, was the best move forcing, was it
a check or capture) is the closest thing on disk and sits on 47% of rows. A
difficulty measure has to be built before *"20 seconds in a simple position
means something different from 20 seconds in a complicated one"* can be tested.

---

## 2. The controls available at game level

`games` — 19,921 analysed.

| control | coverage | caution |
|---|---|---|
| `user_color`, `result`, `pgn`, `played_at_utc` | **100%** | — |
| `termination` | 98.6% | — |
| `opening_name` | 92.8% | per-platform: chess.com ~98%, lichess much lower |
| `user_rating` | 80.6% | — |
| **`opponent_rating`** | **48.6%** | **half the corpus cannot control for opponent strength** |
| `time_control` | 100% | **mixed semantics — see below** |

**`time_control` holds two different kinds of value.** Measured over 3,000
games: `rapid` 1888, `blitz` 564, `600` 209, `untimed` 105, `daily` 63,
`900+10` 60. Some rows carry the platform's *category*, others the actual
control. A design that groups on this field is grouping on two things at once.
The real control is the PGN's `[TimeControl]` tag, which is complete.

**Per-move clock is in the PGN for 74% of games** (`%clk`), and
`time_spent_seconds` is already derived onto 90% of move rows — so the clock
work does not need redoing.

---

## 3. Where behavioural data already lives

| collection | docs | what it holds |
|---|---|---|
| `move_observations` | 641,667 | per-move behavioural observations |
| `user_pattern_events` | 146,091 | pattern occurrences over time |
| `thinking_scores` | 19,854 | per-game habit scores |
| `user_concept_understanding` | 5,299 | mastery and regression per concept |
| `user_active_focus` | 345 | the one thing each player is working on |
| `player_identities` | 69 | `style_profile` — aggressive / positional / tactical / defensive |
| `coach_memory` | 126 | skills, weaknesses, decay |
| `detector_claims` | 19,355 | what detectors asserted |

---

## 4. `services/behaviour_profile.py` — what has already been tried

This file already implements two of the three validations, and records its
failures so they are not rebuilt.

### The test a trait must pass

Stable **within** a player across time (first half of their games against
second half) **and** spread **across** players. Both, not either.

### The six that passed

| trait | stability | player-facing meaning |
|---|---|---|
| `thinks_long` | 0.88 | stops and works when the position gets hard |
| `clock_front_loaded` | 0.87 | spends the clock early, finishes in a hurry |
| `error_rate` | 0.83 | *carried, never spoken* |
| `knowledge_breadth` | 0.77 | brings a wide range of ideas |
| `moves_fast` | 0.76 | plays a lot of moves instantly |
| `plays_on_when_lost` | 0.72 | plays on in lost positions |
| `throws_away_won_games` | 0.43 → 0.72 as the bar rose | lets won positions slip |

Cuts are quartiles of a measured population of 48 players. A player inside the
middle half is told **nothing** for that trait, which is why 80 of 128 users
currently see no trait at all.

`throws_away_won_games` needs `MIN_SAMPLE = 60` winning positions. Its
correlation climbed 0.41 → 0.43 → 0.44 → 0.59 → 0.72 as the bar rose from 10 to
150, exactly as Spearman-Brown predicts for attenuation — which is how a real
but noisy game-level trait is told apart from a non-trait.

### The fourteen that failed — do not rebuild these

| candidate | result |
|---|---|
| **aggression** | **0.23** as forcing-move share, **0.06** measured properly |
| too-passive | stable 0.58 but spread **0.009** — everyone identical |
| tilt (one blunder causing the next) | **0.18** — not real |
| errs-when-forcing | 0.28 |
| repeats-next-game | 0.68 |
| notices-threats | 0.65 |
| endgame-weighted | 0.64 |
| opportunism | 0.50 |
| comeback | 0.12 / 0.07 / 0.00 / 0.14 — **flat**; saving lost games is the opponent's doing |
| session fatigue | 0.13 / 0.31 / 0.14 / 0.22 — bounces |
| punches up | only 7 players at the lowest bar |

### The negative control that matters most

Tilt **between** games looked real: after-a-loss failure rate correlated 0.60
across halves and climbed 0.30 → 0.41 → 0.54 → 0.58 → 0.62 as the bar rose.
A control on games that did **not** follow a loss climbed *identically*. That
correlation was playing strength, not tilt — it appears on any set of games.

The honest measure is the **lift**: this player's failure rate after a loss
against their own rate otherwise. Median 1.09, quartiles 0.99 and 1.36, and 20
of 47 players more than a tenth worse after a loss. But the lift's own
stability is 0.39 over 31 players. Real population effect, unproven as a trait.

**This is the worked example of "separate skill from behaviour".** Any new
detector needs its equivalent control before it is believed.

---

## 5. The gap nothing here closes

**Validity has never been tested.** Every number above is stability or spread.
A measure can be perfectly reliable and measure the wrong thing — and the tilt
control above shows exactly how that happens. No trait has ever been checked
against a person who knows chess.

The apparatus exists and has never been used:

- `backend/scripts/build_blind_label_packet.py` — 13 entries × 8 clocked games,
  players chosen to carry both ends of every trait, base rates destroyed on
  purpose so it tests correctness and not prevalence
- `backend/scripts/score_blind_labels.py` — confirmed / not seen / contradicted
- `docs/blind_label_validation.md` — how to read each outcome

---

## 6. One contradiction to resolve before building anything

`style_profile` labels 27 users **"aggressive Player"** and renders it in the
Deep Memory panel, which is live in the Play-with-Coach sidebar.

Aggression is one of the fourteen that **failed**, twice, at 0.23 and 0.06.

Two systems make the same claim about a player; the one that failed its own
stability test is the one on screen. Reconciling that costs nothing and stops a
claim the data does not support.

---

## 7. What is buildable today, without an engine pass

Needs only fields at 90%+ coverage:

- `clock_back_loaded` — the other end of a trait already measured
- `trade_seeking` / `trade_avoidance` — captures and exchanges are in the PGN
- `opening_repetition` — `opening_name` at 92.8%
- `time_pressure_blunders` — `time_spent_seconds` × `cp_loss`, both complete

Needs an engine pass first (MultiPV):

- anything measuring **the choice among alternatives** rather than the outcome
- `complexity_seeking`, `simplification_seeking`, `material_greed`
- position difficulty, and therefore everything that controls for it
