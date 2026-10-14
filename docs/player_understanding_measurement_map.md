# Player Understanding System — scope

Status: DRAFT for sign-off. Measured 2026-10-14 against production
(`chess_coach`: 20,293 games, 19,570 analysed, 128 users, 630,639 move
observations). Read-only: no code, data or flag was changed to produce it.

Two corrections to earlier claims come first, because both changed a
conclusion.

This is the measurement map: for each of six dimensions, what the data can and
cannot support. It is not the feature scope. The feature scope for the player
understanding surface is [player_understanding_scope.md](player_understanding_scope.md)
(what the player sees, in/out of scope, success criteria); this file is the
evidence layer underneath it, and the two should be kept consistent.

---

## Correction 1 — the castling breakdown now reconciles

The earlier breakdown applied three overlapping tests to the same games, so a
short game that had *also* lost its castling rights was counted twice. That is
why 17 + 23 + 2 came to 42 against 40 games. Recounted in priority order, each
game in exactly one bucket:

| Of the 40 games where he never castled | Games |
|---|---|
| Game was over by move 15 — no time to castle | 17 |
| Lost the right early (by move 15), then played on | 10 |
| Lost the right later in the game | 11 |
| Had the right throughout a long game and never used it | **2** |
| Sum | **40** |

60 of the 100 games were castled. Win rate is 50% either way. The withdrawal
was correct and the honest figure is 2 games, not 40.

## Correction 2 — openings are identified; they are not *normalised*

"87 of 100 games have no opening" was true of his slice and false of the
product. He plays lichess, and the gap is per-platform:

| Platform | Games | Opening named |
|---|---|---|
| chess.com | 19,348 | 18,868 (98%) |
| lichess | 676 | **0 (0%)** |
| coach (PWC) | 271 | 7 (3%) |

Across all games `opening` is 96.7% populated, `opening_name` 93.0%, `eco`
94.4%. The real gap is downstream: chess.com names 4,056 distinct *variations*
("Alapin Sicilian Defense 2...Nc6 3.Nf3 d5"), the curriculum has 79 keys, and
`games.opening_key` is set on **8 of 20,293 games**. There is no join between
what players play and what can be taught.

---

## 1. Strengths and weaknesses

**Reliably measurable today.** Weakness naming works: `primary_weakness_picker`
has 3 route callers, and `move_observations.missed_pattern` covers 66,724 moves
over 332 user+topic pairs, 294 of them seen 5+ times. Board-verifiable,
engine-free behaviour is also solid when measured against the legal-move
opportunity set rather than as a raw share — capture preference 4.23×, check
preference 2.88×, undefended landing 3.58×, cheaper-capture 6.80×.

**Exists but disconnected.** `primary_strength_picker` has **0** route callers
while `primary_weakness_picker` has 3: the product can name what you are bad at
and not what you are good at. `assign_strength()` has no callers at all.
`routes/player.py` exposes 40 endpoints; the frontend references about 4 of
them — `/profile/strengths`, `/profile/strength-profile`, `/profile/weaknesses`,
`/weakness-ranking` and `/blind-spots` are each referenced **0** times.

**Additional data required.** An opportunity denominator stored per move. Every
honest trait figure in this session was computed by re-deriving the legal-move
set in a probe; nothing persists it, so no surface can show one. Plus opponent
rating as a baseline (see §6).

**Cannot be inferred reliably.** Anything from `thinking_scores` (19,501 docs).
The service documents its own invalidity: `opportunities` is the move count,
not real opportunities, so three of five habits are failure-indicators and
`MOVE_VERIFICATION` is "driven by cp_loss, always available". Its own comment
says not to read a per-habit score as "how good you are at X". Also: low
cp_loss is an engine output renamed, not a measured strength.

**Reuse.** `primary_weakness_picker`, `strength_profile_service`,
`behaviour_profile` (wired to `routes/home.py`), `move_observations`.

## 2. Tactical vision and pattern recognition

**Reliably measurable today.** The paired measures are the right shape and they
work: `missed_opponent_blunder` vs `punished_opponent_blunder` (what they took
against what was offered), `tactical_pattern_executed`, and `concept_used` on
318,418 moves. Exact board computations verified this session: mate-in-1 on the
board and not played, undefended 3+ point material left, which piece gets
dropped on a blunder. `motif_profile_service` is one of the few things wired
front-to-back (3 route callers, `/motif-profile` referenced 3× in the
frontend).

**Exists but disconnected.** `best_move_tactic_detector`, `pv_tactical_analyzer`
and `tactical_safety` have **0** route callers each; 7 provers have zero
callers. More fundamentally, the concept detectors only congratulate: 1,639
"applied" against 5 "wrong" across 12,365 moves. A recognition measure that
almost never records a failure cannot grade recognition.

**Additional data required.** None new. What is missing is a failure branch on
detectors that already run. Separately, `move_evaluations` stores only user
moves (0 of 12,365 opponent moves), so "did they see the threat" has no engine
backing on the opponent's move.

**Cannot be inferred reliably.** Whether a good tactical move came from
recognition, calculation or luck. `calculation_test.py` makes exactly this
point from 10,679 mistakes across 46 players: the game record shows where the
punishment landed, not how the player got there.

**Reuse.** `motif_profile_service`, `move_observations`, the exact-board probes
written this session.

## 3. Calculation and decision-making

**Reliably measurable today.** Clock behaviour is the strongest real-behaviour
signal in the product and it is engine-independent: 86% of PGNs carry `%clk`,
and `time_spent_seconds` is on 79.6% of 630,639 observation rows,
`time_left_seconds` on 82.2%. Exchange outcomes compute exactly from the board.

**Exists but disconnected.** Two items, and the first is the headline of this
whole mapping.

`calculation_test` is the only thing in the product that grades a *line*
instead of a move, on three axes kept deliberately separate
(`found_the_idea` / `sound_through` / `judged_the_end`). It is wired front to
back — `routes/calculation_test.py` → `CalculationTest.jsx` → `App.js`. It
holds **4 attempts, from 1 user, on one day**. Built, correct, reachable, and
nobody has been asked to use it.

`decision_register` (35.7% populated, ~225,000 moves) is **corrupt at source**.
`analysis_worker.py:1322` joins `tagged_by_ply` — keyed by halfmove, counting
both sides — to `enumerate(move_evaluations)`, which is positional in a
user-moves-only list. Two index spaces joined as one. 56.2% of register
verdicts change when it is fixed. `move_observation_deriver.py` already works
around it for `was_capture`/`was_forcing` (SAN as source of truth, 2026-07-02),
but `_classify_register` at line 211 still reads the raw `cct_forcing`,
`cct_best_was_forcing` and `cct_had_forcing_options`.

`time_flag` fires on 0.44% of moves. The clock data is present; the threshold
was never calibrated against the distribution.

**Additional data required.** None. The clock is in the PGN and already on 80%
of observation rows.

**Cannot be inferred reliably.** Calculation depth from a single move — a
player can see six half-moves and misjudge the end. `calculation_depth` as a
`cognitive_gap` is an engine classification of the mistake's shape, not a
measure of how deep anyone looked.

**Reuse.** `calculation_test` (and put it in front of users),
`pgn_clock_parser`, the `move_observations` clock fields.

## 4. Positional and opening understanding

**Reliably measurable today.** Opening identity on chess.com games (98%).
`user_opening_mastery` (755) and `opening_mastery` / `opening_mastery_tracker`
(8 and 7 route callers) are the best-wired subsystem in this mapping.
Material-based phase detection gives real per-phase accuracy; move-number
phases do not.

**Exists but disconnected.** Normalisation, as above: a crude substring match
already lands **13,177 of 18,875 games (70%)** on a curriculum key —
sicilian_defense 2,413, caro_kann 2,173, scandinavian 913, french 833, scotch
749 — and the unmatched tail is long and thin, the largest single entry being
107 games. `games.opening_key` is set on 8 games.

`user_opening_progress` is a trap worth naming: `times_applied_in_games > 0` on
8,172 rows, `times_practiced > 0` on **3**. It is a game-import tally, not a
teaching record, so opening *transfer* is unmeasurable today for the simple
reason that almost nothing has been taught. `personal_teaching_profile` has 0
callers. Only 41 of 79 openings are teachable and 16 have no tree.

**Additional data required.** `opening_key` written at import on both
platforms, from the recognizer that already exists, plus one 4,056→79 mapping
table. The lichess importer must write the opening fields it already receives.
This is one mapping, not a new data source — and per the single-source rule, no
new recognizer.

**Cannot be inferred reliably.** Positional understanding separated from
tactical ability, from results alone. `pawn_structure` and `piece_activity` are
engine-derived mistake shapes. Whether a player chose a plan or stumbled into
it.

**Reuse.** `opening_mastery`, `opening_mastery_tracker`, `user_opening_profile`,
`opening_curriculum.json`, the canonical recognizer.

## 5. Learning retention and transfer to real games

You were right to push back. Retention is not unmeasurable; one substrate is
already measuring it, and has been for months.

**Reliably measurable today.** `user_concept_understanding` is a real retention
state machine: 5,073 rows, 66 users, 254 concepts, written through to today.
States `shown` (3,146) → `monitoring` (1,073), with `streak_clean` ≥1 on 1,048
rows, `mastered_at` set on **1,037**, and `mastery_stripped_at` — a recorded
*regression* — on **251**. It joins to games through `last_evaluated_game_id`
(1,821 rows). Mastery by type: opening 467, tactical 230, middlegame 173,
defense 87, endgame 80. Twelve backend readers, three routes, and
`MasteryPanel.jsx` / `InGameMasteryPanel.jsx` on the frontend. On your own
account: 33 mastered, 42 stripped.

Transfer has a working join: `move_observations.derived_at` is a real datetime
on all 630,639 rows and `game_id` joins to `games.played_at_utc`. Before/after
is splittable — via the game, not the row.

And the verdict engine exists. `coaching_landed.py` (signed off 2026-09-28) run
over all 301 non-strength focus documents returns **238 of 301 with both a
before-rate and an after-rate**:

| Verdict | Count | What it means for us |
|---|---|---|
| never_returned | 91 | re-engagement; nothing to do with chess |
| came_back_unpractised | 65 | the ask was wrong, too hard, or unseen |
| practised_no_change | 58 | the diagnosis was wrong — act on this |
| **practised_and_moved** | **41** | it worked; tell the player |
| practised_and_worse | 26 | it worked against them; stop and look |
| not_yet_measurable | 20 | say nothing yet |

**Exists but disconnected.** `coaching_landed` has **zero production callers**
and the `coaching_landed` collection holds **0 documents**. Its own docstring
says of the success case: "say so — never yet said by this product." 41 players
have a measured success nobody has told them about. `focus_history` holds 62
closed cycles with `game_results` on all 62 — the milestone substrate — across
only 4 topics and 8 users, with a single reader (`focus_engine.py`).
`focus_outcome_shadow` holds 1,521 rows over 54 users and is shadow-graded.

**Additional data required — one field type, in four places.** String
timestamps are the single shared blocker across the retention substrates:

| Collection | Rows | Date fields | Stored as |
|---|---|---|---|
| `puzzle_attempts` | 572 | `created_at` | **string** |
| `user_concept_understanding` | 5,073 | `created_at`, `updated_at`, `mastered_at` (1,037), `mastery_stripped_at` (251) | **string** |
| `focus_history` | 62 | `started_at`, `graduated_at` | **string** |
| `learning_sessions` | 323 | `created_at`, `completed_at` | datetime |
| `user_opening_progress` | 8,175 | `last_practiced_at` | datetime |
| `move_observations` | 630,639 | `derived_at` | datetime |

A `{"$gte": <datetime>}` against a string matches nothing, so
`coaching_landed`'s practice count silently reads zero from `puzzle_attempts` —
its own comment anticipates this and calls it "wrong in the safe direction".
That contaminates the `came_back_unpractised` (65) and `practised_no_change`
(58) buckets, which is exactly the pair we would act on. Separately,
`puzzle_attempts` carries no `game_id` and no concept field beyond
`weakness_type` (426 rows, 13 values), so puzzle→game transfer has no join key.

**Cannot be inferred reliably.** *Why* a player improved:
`measure_coaching_contribution.py` finds no detectable effect, and with no
held-out comparison our teaching cannot be separated from ordinary play.
Misconception-level retention is genuinely absent — `user_misconceptions`,
`home_today_answers`, `concept_tests` and `concept_test_results` all hold 0
documents. Those four are the only places where "no data" is the right answer.

**Reuse.** `user_concept_understanding` + `concept_mastery_tracker`,
`coaching_landed` (wire it), the `move_observations`→`games` join,
`learning_sessions`.

## 6. Real improvement over time

**Reliably measurable today.** A per-pattern rate over any window, for 70 users
across 630,639 moves, from `derived_at` joined to `games.played_at_utc`. That
is the honest improvement measure and it works now. The mastered/stripped pair
in `user_concept_understanding` is a directional per-concept signal.
`improvement_proof_engine` is wired and `/progress/improvement-proof` is
referenced once in the frontend.

**Exists but disconnected.** `progress_chain` has 0 route callers. Of the
progress endpoints, `/progress/real`, `/progress/v2`, `/progress/journey`,
`/progress/coaching-report`, `/progress/full-profile`, `/progress/narrative`,
`/rating/trajectory` and `/heatmap` have **0** frontend references each; only
`/progress/complete-coaching` (4) and `/progress/improvement-proof` (1) are
called. `focus_history`'s 62 closed cycles are the milestone data the
progression design asked for, read by one service.

**Additional data required.** A frozen comparison basis. Rescaling one
candidate silently rescales every comparison, and differencing against the
stored baseline is already a known error; improvement needs a persisted
opportunity-adjusted denominator, which nothing stores. Opponent rating, for
the same reason: without it, a falling mistake rate and a falling opponent
strength are indistinguishable.

**Cannot be inferred reliably.** Rating change as evidence of our coaching —
ChessGuru is not live and the ~120 production users predate the features.
Improvement on anything with fewer than two independent observations.

**Reuse.** `improvement_proof_engine`, `progress_chain`, `focus_history`, the
`move_observations`→`games` join.

---

## Priority

Ordered by coaching value per unit of work. Each is a fix to something that
exists; none is a new detector or a new system.

1. **Fix `analysis_worker.py:1322`.** One join. Unblocks `decision_register`
   across ~225,000 moves and every calculation claim in §3. 56.2% of verdicts
   change.
2. **Store the four string date fields as datetimes, then backfill.** One field
   type. Unblocks every before/after in §5 and §6 and un-contaminates
   `coaching_landed`'s practice split. Deploy the code first, migrate after.
3. **Wire `coaching_landed`.** Written, tested, 238 computable verdicts
   already, including 41 successes nobody has been told about.
4. **Write `opening_key` at import on both platforms, plus the 4,056→79
   mapping.** Lands 70% of games on a teachable opening and fixes lichess's 0%.
5. **Calibrate `time_flag` from the `time_spent_seconds` distribution**
   (501,863 rows) instead of a threshold that fires on 0.44%. Histogram first.
6. **Derive `opponent_rating` from PGN `WhiteElo`/`BlackElo`** — present on
   96.3% of games, and the denominator both §1 and §6 need.
7. **Put `calculation_test` in front of users.** Built, wired, 4 attempts.

Explicitly not worth doing: `thinking_scores` as a skill measure; new
detectors, since promotion is measured as exhausted; `user_misconceptions` as a
retention route.

## Open question for sign-off

Items 1 and 2 both rewrite stored interpretations of games already analysed.
Item 1 changes 56.2% of `decision_register` verdicts and item 2 changes which
side of a focus window ~600 puzzle attempts fall on. Both are corrections, but
both move numbers a player may already have seen. Confirm whether they ship as
a silent correction or with something said to affected players.
