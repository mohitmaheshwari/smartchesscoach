# ChessGuru — Personal Coaching Intelligence Audit

**Date:** 2026-10-14 · **Method:** read-only. Code read from a worktree at
`origin/working-code` (both local checkouts were stale — 144 and 46 commits
behind). Figures from the production database `chess_coach` and the deployed
container's own environment. No code, data or flag was modified.

**Companion document:** `CHESSGURU_AUDIT.md` (same date) covers the feature
inventory, scale and the delivery problem. This one does not restate it.

---

## 0. The frame

Nothing below means much without this.

| | |
|---|---|
| accounts | 128 (125 `user`, 1 `admin`, 2 `super_admin`) |
| **no games at all** | **58** |
| 1–4 analysed | 12 |
| 5–14 analysed | 4 |
| 15+ analysed (past the entry bar) | 54 |

**Two different home pages ship to ordinary users.** Calling
`build_player_curriculum` for every account: 77 `user` accounts get the
fallthrough dashboard, **48 get `CurriculumHome`**, and all 3 staff accounts get
`CurriculumHome`. `PERSONAL_CURRICULUM_ENABLED=true` but
`PERSONAL_CURRICULUM_ROLES=admin,super_admin` — and that role list is **not**
what gates this path, since 48 plain users reach it anyway.

**Consequence for every recommendation here: a surface mounted in only one
component reaches at most half the users.** This is the single most repeated
failure in the codebase and it is cheap to avoid.

Flags that change what a player sees:

```
PERSONAL_CURRICULUM_ENABLED=true     ROLES=admin,super_admin
COACHING_CONTEXT_V1_ENABLED=true     ROLES=admin,super_admin   <- staff only
PWC_UNIFIED_EXPERIENCE_V1_ENABLED=false  ROLES=admin,super_admin
DISTILLED_CAPTIONS_ENABLED=1
PWC_GAP_ENRICHMENT=true
```

---

## 1. Existing capabilities we should preserve

1. **One composition point for all coaching prose.**
   `services/caption_pipeline.build_move_teaching_decision` is used by game
   review *and* live Play with Coach, and `.githooks/pre-commit` blocks
   coaching prose written outside it. This is the best architectural decision
   in the system. Do not add a second path.
2. **Per-claim verification.** `services/caption_claim_verifier.py` checks
   rendered sentences against the board.
3. **The weakness engine.** `cognitive_gap` per move, recency decay
   (`pattern_decay_service`), a focus picker with a daily cron, and — since
   2026-10-07 — focus cycles that actually close.
4. **`move_observations`.** 630,349 rows, 40 fields per move, 70 users. The
   richest and most under-used asset in the product. See §1.4.
5. **Engine depth.** `PUNISHMENT_DEPTH 18`, `PUNISHMENT_PV_PLIES 12`.
6. **Import.** Median **3 minutes** from import to analysed (p90 5, max 25) on
   October games. Fast and healthy.

---

## 1b. The five dimensions

### 1. Strengths — *Partially implemented*

**What exists:** `services/primary_strength_picker.py` with
`_METRIC_LABEL` (7) and `_PATTERN_LABEL` (12) — **19 producible labels**.
`assign_strength()` writes a `type: "strength"` row into `user_active_focus`.
39 exist.

**Genuinely measurable:** blunder/mistake rate, best-move rate, critical-moment
find rate, threat response, blunder punish rate, and twelve pattern rates
(forks, pins, hidden attacks, free pawns…).

**Three problems, all verified:**

- **Nothing refreshes them.** `assign_strength()` has **zero callers anywhere**
  in the codebase. All 39 stored strengths date from 2026-07-02 — 104 days old.
  The first line a player reads about themselves is from July.
- **The derivation is a cross-player comparison.** Rows carry `cohort_mean`,
  `cohort_stddev`, `z_score`. The stored narrative is unshippable three times
  over: *"you land at 4.6%, vs the cohort average of 6.7% at your rating… that
  is +0.9σ"* — a percentage, a cohort, and sigma notation for a 1200 player.
- **It may not discriminate.** A dry-run refresh (`scripts/assign_strengths.py`,
  written and deliberately **not** run) would change 19 of 37 strengths and
  collapse 14 of them onto the single label *"Best-move accuracy in critical
  moments"*. That is the signature of a metric that does not separate players.

**Recommendation:** re-derive within-player — *"of everything I watch, this is
what you are best at"* — which says the same thing without a cohort, then run
the refresher. Do not refresh the cohort version; it would entrench the
comparison.

### 2. Weaknesses — *Already works.* The strongest dimension.

**What exists:** `cognitive_gap` on every user move in
`game_analyses.stockfish_analysis.move_evaluations`;
`services/pattern_decay_service.py` (recency-weighted, `user_pattern_decay` 128
rows); `services/primary_weakness_picker.py` with `assign_focus`,
`check_focus_outcome`, `close_focus`; `user_active_focus` (49 active weakness
focuses); `focus_outcome_shadow` (1,150 daily observations over 21 consecutive
days, 331 carrying a real verdict).

**Measured distribution** over 7,795 user moves in 1,500 games:

```
king_safety        27.8%      opening_knowledge  11.3%
piece_safety       27.1%      endgame_technique   8.6%
missed_tactic      23.6%      tactical_oversight  1.6%
```

**Under what conditions** is partly answerable: `subtype_histogram`,
`severity_weighted_count`, `phase`, and — from `move_observations` —
`time_flag` (`snap_decision`, `time_pressure_blunder`, `slow_paralysis`).

**The loop now closes.** 20 focuses carry a measured `current_metric`, 7 are
`completed`, 6 `escalated`. Before 2026-10-07 the figure was zero for all 327
rows, because `focus_outcome_loop` measured every focus daily and discarded the
result.

### 3. Chess understanding — *split*

**Tactics and geometry — Already works.** Verified detectors for forks, pins,
skewers, discovered and hidden attacks, trapped pieces, back rank. `pin`/`skewer`
disambiguated by material alignment (`services/motif_alignment.py`).

**Authored teaching content — Partially implemented**, and thin where it
matters:

| | |
|---|---|
| `opening_curriculum.json` | 79 entries, **26 with a usable tree** |
| `traps.json` | ~60 traps across 28 openings |
| `endgames.json` | 6 topics × 9 = **54 lessons** |
| `pattern_catalog.json` | 35 patterns, median 78-char description, **`example_fen` null on all 35** |

A pattern that cannot be shown is not taught. Giving those 35 an
`example_fen` is the smallest change with the widest reach in this document.

**Known detector-side issue (from prior measurement):** concept detectors
overwhelmingly *congratulate* — 1,639 "applied" against 5 "wrong" across 12,365
moves — so they confirm success and cannot teach.

### 4. Decision-making — *Exists but disconnected.* The central finding.

Your brief says: *do not infer a player's thinking process from engine
evaluations alone.* **The service that reports "thinking habits" does exactly
that, and its own comment admits it.**

`services/thinking_score.py` tracks five habits — `threat_awareness`,
`tactical_vision`, `move_verification`, `king_safety`, `patience` — across
19,495 `thinking_scores` documents. From the file:

```python
# `opportunities` is the move count, not real opportunities. So
# tactical_vision, king_safety and patience are failure-indicators ...
# while threat_awareness and move_verification are the always-attributable
# catch-alls. Do not read a per-habit score as "how good you are at X"
ThinkingHabit.MOVE_VERIFICATION: True,  # driven by cp_loss, always available
```

The denominator is the move count, so a "habit score" is approximately accuracy
with a psychological label. This also explains a separate measurement: habit
series are **flat** across 120+ games (trend/noise 1.46; pooling the raw counts
instead of averaging per-game scores changed nothing, 1.45). They are flat
because they are not measuring a habit.

**But the real data exists, in a different store.** `time_spent_seconds` is
**0% populated** in `game_analyses.move_evaluations` — and in
`move_observations`:

```
time_spent_seconds   501,863   79.6%       <- real behaviour
time_left_seconds    518,100   82.2%
decision_register    224,801   35.7%
time_flag              2,786    0.4%       snap_decision 1,256
                                           time_pressure_blunder 1,224
                                           slow_paralysis 306
(control — engine-derived fields are ~100%: cp_loss, execution_quality,
 found_best_in_critical, responded_to_threat, was_critical_moment, was_forcing)
```

`decision_register` is a genuine decision classification — *did you pick the
right kind of move* — not an evaluation:

```
quiet_when_best_was_quiet        18,980
wrong_register                   18,088      <- 45% of registered moves
forcing_when_best_was_forcing     2,932
```

**So the honest decision-making profile is already derivable:** half a million
timed moves, 2,786 behavioural flags, 224k register judgements, across 70 users.
`move_observations` has 12+ readers (`behaviour_profile.py`,
`behavioural_stats.py`, `coaching_landed.py`, `focus_*`), so it is not orphaned.

**One more real signal:** `guardian_overrides` — 22 Play-with-Coach sessions
where the coach warned the player and they played the move anyway. That is
observed behaviour, not inference.

**And the right instrument exists, unused.**
`services/lesson_question_spec.py` holds, per category, a question
(*"What did you check before choosing the move?"*), real belief options, and an
authored correction for each wrong belief. Asking the player what they were
checking is the **only** way to separate "knew it and slipped" from "never
knew". `user_misconceptions` and `home_today_answers` both hold **0 rows** —
nobody has ever answered.

### 5. Improvement — *Partially implemented, with real risk of false claims*

**What exists and is correct:**
`scripts/measure_coaching_contribution.py` — a within-user
difference-in-differences using the player's *untaught* gap categories as the
control. `check_focus_outcome` re-derives **both** halves in the same run.
`services/progress_chain.py` builds a per-cycle verdict chain requiring agreement
across observations on one metric.

**What it says today:** **no detectable effect.** That is the expected answer
while the product is not yet live — the ~120 accounts predate the features.

**The chain's reach:** 53 of 128 users have any chain; across 102 cycle rows,
74 "still watching", 15 "did not move", 7 "got better", 6 "got worse". **More
focuses did not move than moved.**

---

## 2. Reassessment every five games

### What triggers reassessment today — *time, not games*

| trigger | cadence | file |
|---|---|---|
| focus assignment | daily 03:00 cron | `scripts/assign_focuses.py` via `/root/scripts/run_assign_focuses.sh` |
| outcome measurement | **every 6 hours** | `focus_outcome_loop` in `server.py` |
| lock expiry | `locked_until`, 14 days | `primary_weakness_picker` |
| hard stop | `FOCUS_MAX_DAYS = 28` → `time_boxed` / `repick` | `close_focus` |
| decay refresh | per page load / batch | `pattern_decay_service` |

**Nothing is game-count triggered.** A player who imports 40 games tomorrow
gets the same treatment as one who plays none.

### Five-game batching can reuse what exists — *Partially implemented*

Three pieces are already there:

- **The intent is already modelled.** `user_active_focus.review_after_measured_games`
  exists on 43 documents. Somebody designed game-count review and it was never
  wired to a trigger.
- **The evaluator exists and must not be duplicated.** `check_focus_outcome` is
  the single evaluator; a prior attempt to build a parallel service was thrown
  away. It already measures both halves with the same function.
- **The measurement history exists.** `focus_outcome_shadow` holds 21 days of
  daily per-focus observations, so "what changed since five games ago" is an
  aggregation, not new instrumentation.

### Your edge cases, against real numbers

| case | status | evidence |
|---|---|---|
| **failed analysis** | real — must exclude | **776 of 20,080** queue rows `failed` (3.9%) |
| **duplicate imports** | handled at import | `journey_service` dedupes on `url` **or** `pgn` per user |
| **insufficient evidence** | already enforced | `MIN_DECISIONS_FOR_PROOF` in `_pic_proof_rates`; 29 of 49 focuses legitimately return `no_data`/`measurement_pending` |
| **time controls** | *Missing* | `time_control` and `time_control_category` are stored; no evidence any assessment filters on them |
| **opponent ratings** | *Missing* | `opponent_rating`, `rating_gap` stored; not used in focus selection |
| **ordering** | **fixed 2026-10-10** | `played_at_utc` repaired. Before it, **445 games sat in the "after" window of 16 of 49 focuses having been played before the focus started**. A string compare put chess.com dotted dates after every ISO timestamp. A nightly top-up now runs at 03:20 because the repair decayed within hours |

**Recommendation:** trigger on *eligible* newly-analysed games — exclude failed
analysis and duplicates, require a minimum decision count — and keep
`check_focus_outcome` as the only evaluator. Preserving unfinished activities is
already natural: `close_focus` leaves a focus `active` and extends the lock
unless the verdict is terminal.

---

## 3. Personalized game teaching — *Partially implemented*

**Selection — exists.** `GET /api/lab-coach-pick` picks the best unreviewed game
by the decay model; `services/coach_selected_review_service.py` holds review
prescriptions; `services/focus_game_service.py` links a game to a focus.

**Classification — exists, and is already careful.** `move_story` (punishment /
opportunity / neither) decides arrows *and* captions. `opportunity_gate.v2`
asks the gated question — *was the engine's best move actually a tactic* —
giving 51.7% where the loose question gave 11.2%.

**Your warning is correct and already measured.** Not every classified move is
a teaching moment. Base-rating three candidate shapes against all 27,324 user
moves:

```
best move was a check             39% in gap vs 10% everywhere   4.09x   usable
landed where it was undefended    31% vs  9%                     3.58x   usable
landed where something cheaper
  could take it                    9% vs  1%                     6.80x   usable
---
king had <=2 safe squares         57% vs 59%                     0.97x   REJECTED
moved a piece that was guarding
  something                       32% vs 24%                     1.36x   REJECTED
```

The two rejects matter: the second had the **largest raw share** of any
piece-safety shape, and the first was reported as a finding, written into a
lesson and built into a detector before anyone checked the base rate. A castled
king has its own pawns in front of it, so "cramped" is the normal state of a
*safe* king.

**Explanation — the ceiling is the problem.** From the companion audit: over
2,383 engine-flagged moves, the engine's line explains 28%, deterministic board
families could explain a further 40.5%, and **31.5% have no explanation
available at all**. Of cards describing only the better move, **79.9% have no
computed fact about the played move**. The caption layer is not choosing badly —
for four cards in five there is nothing to choose from.

**Interactive teaching — the pieces exist, unconnected.**

| piece | status |
|---|---|
| question + belief options + authored correction | `lesson_question_spec.py` — **exists, 0 answers recorded** |
| board with the player's own move named | 2,126 positions for one user; `played_move` on 100% of both pools |
| trap / endgame lesson dispatcher | `teaching_engine.py` — traps entered in **55 of 234 offers**; 11 of 18 traps never fired |
| count-the-escape-squares quiz | `escape_squares_service.py` — **never answered by anyone** (field absent across all 498 sessions, which carry 107 distinct fields) |
| others' games | `community_puzzles` 51k, `community_training_positions` 53k |

**Missing:** a pause-think-reveal flow on the review path. The ingredients are
all present; nothing sequences them.

---

## 4. Teaching new knowledge — *Missing for the gaps that matter*

The asymmetry is the finding:

```
ways to practise:  52,341 training positions + 47,071 puzzles  = 99,412
things that teach: 54 endgame lessons + 26 teachable openings + ~60 traps = ~140
```

And the gaps with authored content are the **smallest two**:

| gap | share of mistakes | authored teaching |
|---|---|---|
| king_safety | 27.8% | **none** |
| piece_safety | 27.1% | **none** |
| missed_tactic | 23.6% | **none** |
| opening_knowledge | 11.3% | 26 teachable openings |
| endgame_technique | 8.6% | 54 lessons |

**78.5% of every mistake your users make has unlimited practice and nothing
that teaches the idea.**

**Can the curriculum balance repair / discover / reinforce?** Not today.

- **Repair** — works. The focus engine does this well.
- **Reinforce** — partly. `user_teaching_memory` (29,974 rows) and
  `coach_memory` (126 of 128 users) exist; `principle_cue` carries a habit
  reminder on 34% of mistake cards.
- **Discover** — *Missing*. There is no proactive track that introduces a
  concept the player has not met, for the three gaps that are 78.5% of their
  mistakes. `lesson_question_spec` can *detect* "never knew" and nothing
  currently answers it.

**Two lessons are justified by the data** (4.09x and 3.58x/6.80x above): *look
at every check first*, and *look at the square before you put a piece on it*.
`king_safety` earns none until something in it survives a base rate.

---

## 5. The homepage — requirement → existing system

| requirement | existing system | status |
|---|---|---|
| short evidence-based assessment | `home_session.build_session`, `coach_opening_words` | **Already works** |
| genuine strengths | `primary_strength_picker` | **Exists but disconnected** — 104 days stale, zero callers, cohort-derived |
| recurring weaknesses + recent change | `pattern_decay_service`, `user_active_focus`, `focus_outcome_shadow` | **Already works** |
| one clear coaching priority | the focus picker + `focus_why` | **Already works** |
| a selected interactive game to study | `lab-coach-pick` + `lesson_question_spec` + own-game positions | **Partially implemented** — selection and content exist, no interactive flow |
| new knowledge worth learning | openings/endgames only | **Missing** for the top three gaps |
| real improvement evidence | `progress_chain`, `check_focus_outcome` | **Partially implemented** — 53/128 have a chain; 74 of 102 rows "still watching" |
| a guided next session | `session_chooser` + `build_blocks` (supply-checked hrefs) | **Already works** |

### By player state

| state | count | what is honestly available |
|---|---|---|
| no games | **58** | diagnostic result only. `focus_source: "diagnostic"` exists in `routes/coach.py` — the one path that can give day-one content |
| diagnostic only | 38 have had a learning session (270 completed) | a focus without game evidence; say so rather than implying game-derived insight |
| a few games (1–14) | 16 | decay works at low N; strengths and chains do not. Do not show a strength from 3 games |
| 15+ analysed | **54** | everything above |

**Avoiding a third coaching system:** `home_session.py` is already the
assembler and `build_move_teaching_decision` the composer. Everything here
should route through those two. During this session I wrote a third
mechanism (`grounded_habits.py`) and deleted it after finding its two
base-rated habits were, almost word for word, the two `principle_cue` strings
that already ship.

---

## 6. Functional gaps vs presentation gaps

**Functional — something must be computed or wired:**

1. Decision-making is read from `cp_loss` instead of `move_observations` (*Exists but disconnected*)
2. Strengths never refresh — zero callers (*Exists but disconnected*)
3. Strength derivation is cross-player (*Partially implemented*)
4. No discover track for the top three gaps (*Missing*)
5. No game-count reassessment trigger (*Partially implemented* — field exists)
6. Time control and opponent rating unused in assessment (*Missing*)
7. 31.5% of flagged moves have no explanation available (*Partially implemented*)
8. No pause-think-reveal flow (*Partially implemented*)

**Presentation — the data exists and reads badly:**

1. Two homes; a surface in one reaches half the users
2. `principle_cue` repeats — **72% of game reviews repeat the same cue**, worst case 24 times in one review; 28 strings, two covering 85% of instances
3. **24% of shown cue instances use a term never defined** — "loose piece" alone on 469 cards
4. `example_fen` null on all 35 catalog patterns
5. Strength narrative renders percentages, a cohort and sigma
6. 3% of cues cite the engine (*"Engine agrees"*); 5% open with a hedge

---

## 7. Risks of inaccurate or misleading progress claims

Ordered by how badly each would mislead a player.

1. **Differencing against the stored baseline.** `baseline_metric` was written
   by whatever the detector looked like then. On production this read **13
   improved / 0 regressed**; re-deriving the before-half with current code gave
   **4 improved / 3 stuck / 6 regressed**. The entire apparent effect was ours.
   Both halves must be measured by the same function in the same run.
2. **`FocusResolutionBanner`.** Baselines against the **lifetime** average,
   which includes the games being measured, and can fire on one game. Currently
   imported nowhere — but it would make a false claim the first time it fired.
3. **Mixed metric bases.** On 2026-09-21 all 32 shadow observations were written
   with `metric_name: None`, producing deltas of +97%, +236%, +382%, +473%. A
   438% regression is not a chess fact. Never chain across metric names;
   `..._misses_per_decision` is per-decision while `..._per_game` is per-game.
4. **Single-observation verdicts.** 23 of 30 focus verdicts never flip, but 17
   of 18 outlier readings fall on that one bad day. Require agreement.
5. **Reading habit scores as ability.** The code says not to; the denominator
   is the move count.
6. **Publishing a contribution figure.** The within-user measure finds no
   detectable effect. Any number published from this data today would be invented.
7. **A progress chain that is mostly "still watching"** (74 of 102) read as
   progress.
8. **Analysis failures are silent.** 776 failed rows; a game that fails simply
   never gains a review, with no indication to the player. *(Unverified: I did
   not trace the failure path to the UI.)*

---

## 8. Minimum changes to deliver the vision

Ordered by player value per unit of work. None requires a new coaching system.

**1. Point the thinking surface at the behavioural data.** *(functional, contained)*
`move_observations` already holds 501,863 timed moves, 224,801 register
judgements and 2,786 behavioural flags with 12 readers. The "thinking habits"
surface reads `cp_loss` instead. This single change is the difference between a
decision-making profile and accuracy with a psychological label — and it is
what your brief asks for.

**2. Mount every new home surface in both components.** *(presentation, trivial)*
Otherwise it reaches at most half of 125 users.

**3. Dedupe `principle_cue` per game review and rewrite six jargon terms.**
*(presentation, contained)* 72% of reviews currently repeat a cue. Scope with
numbers: `docs/principle_cue_quality_scope.md`.

**4. Give the 35 catalog patterns an `example_fen`.** *(functional, small)*
Smallest change with the widest reach; the catalog is already wired into coach
memory.

**5. Re-derive strengths within-player, then run the refresher.**
*(functional, medium)* `scripts/assign_strengths.py` is written and tested and
deliberately unrun — the cohort version would collapse 14 of 37 users onto one
label.

**6. Trigger reassessment on five *eligible* newly-analysed games.**
*(functional, medium)* Reuse `check_focus_outcome`; honour
`review_after_measured_games`; exclude the 3.9% failed and duplicates; require
`MIN_DECISIONS_FOR_PROOF`. Do not build a second evaluator.

**7. Ask before telling, on the review path.** *(functional, medium)*
`lesson_question_spec` already holds the question, the belief options and the
correction. It has **0 answers**. This is the only instrument that separates
"knew it and slipped" from "never knew" — and that distinction decides whether
the next quarter is content or interruption. Until it has data, that choice is
an assumption.

**8. Write two lessons, not seven.** *(content, medium)* *Look at every check
first* (39% of missed tactics, 4.09x) and *look at the square before you put a
piece on it* (40% of piece-safety mistakes, 3.58x/6.80x). `king_safety` gets
none until something in it survives a base rate.

---

## Challenges to the brief

**"Reassess every five games" may be the wrong unit for half your users.**
58 of 128 have no games at all, and only 54 are past 15 analysed. A game-count
trigger is right for the active 54 and does nothing for the other 74. The
diagnostic path is the only lever for them, and it is where day-one experience
is decided.

**"Continuously adapts their training" is already true and already invisible.**
The focus loop measures every active focus every six hours and closes cycles.
The problem was never cadence; it was that the result reached nobody for weeks.
Adding a faster trigger to a surface that does not render will not help.

**Be careful what "understands the player" claims.** The system genuinely knows
which mistakes recur and when. It does **not** know what the player was
thinking — and the one mechanism that could ask has zero rows. A homepage that
asserts a thinking profile today would be inferring psychology from centipawns.

---

## Verified vs unverified

**Verified in this audit:** the two-home split and its per-user counts; all
flag values; `move_observations` field population with an engine-derived
control; `decision_register` and `time_flag` value distributions;
`time_spent_seconds` absent from `game_analyses`; strength staleness and zero
callers; focus outcome state; import latency and failure count; onboarding
session counts; `thinking_score.py`'s own comments.

**Carried from prior measurement this week** (same database, same method): gap
distribution over 7,795 moves; the five base rates; caption shell and
`principle_cue` figures; cue repetition and jargon shares; content counts;
progress-chain reach.

**From the companion audit, not re-verified here:** the 31.5% explanation
ceiling and the 79.9% no-played-move-fact figure.

**Unverified:** whether analysis failures surface to the player; whether LLM
narration is active for ordinary users; what `PERSONAL_CURRICULUM_ROLES`
actually gates, given 48 non-staff users bypass it.
