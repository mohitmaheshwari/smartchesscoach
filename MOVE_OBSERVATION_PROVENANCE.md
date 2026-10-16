# Which of the 630,349 move observations measure a chess decision?

**The question (Mohit, 2026-10-14):** *"Of those 630,349 move observations,
which fields genuinely measure a player's chess decisions, and which are simply
derived from Stockfish evaluations? We shouldn't replace one misleading
thinking score with another."*

**Method:** traced the writer of each field and read what it reads. Provenance,
not field names — field names are how the thinking score got its reputation.
Read-only; code from a worktree at `origin/working-code`.

**The canonical writer:** `services/move_observation_deriver.py` (1,075 lines,
`SCHEMA_VERSION = 20`), called by `analysis_worker.py` and
`scripts/backfill_move_observations.py`.

---

## The short answer

**Its own docstring is the headline:**

> *"Reads existing `stockfish_analysis.move_evaluations` (+ optional
> `decryption_v5_data`) and emits one structured **behavioral** observation per
> USER move… pure derivation from already-stored fields."*

A file that calls its output *behavioral* while naming engine analysis as its
input. That is the same mislabelling as the thinking score — **with one
important exception that rescues the whole collection.**

**`services/pgn_clock_parser.py` reads `[%clk 0:09:59.1]` annotations that
chess.com and Lichess embed in every PGN.** That is the real clock from the
real game. Stockfish cannot know it, cannot infer it, and it is populated on
**~500,000 moves**. It is the only true behavioural signal in the product —
and it is already there.

So: **two fields are real behaviour, eleven are objective facts about the
player's choice, four are hybrids, and the rest are engine output with
friendlier names.**

---

## Tier A — Real behaviour. Engine-independent. 

Stockfish cannot produce these at any depth.

| field | fill | source |
|---|---|---|
| `time_spent_seconds` | **79.6%** (501,863) | PGN `%clk` deltas |
| `time_left_seconds` | **82.2%** (518,100) | PGN `%clk` |

**This is the foundation of a real Player Understanding System.** How long
someone thought before a move is a fact about the person, not the position.

**And the one derived flag on top of it is the best-disciplined measurement in
the codebase.** `time_flag` (2,786 moves) classifies `snap_decision`,
`time_pressure_blunder`, `slow_paralysis`. From the source:

```
# Fast "for this player, in this game". Taken from the measured distribution of
# each move's time against the player's own median move in that game:
#     p10 0.27x   q1 0.52x   median 1.00x   q3 2.00x   p90 3.88x
# 0.25x is that p10 ... It flags 989 of 42,604 mistakes corpus-wide (2.3%).
# The looser cuts were measured too and rejected: 0.33x gives 2,051 (4.8%) and
# 0.52x gives 4,962 (11.6%) ... this is an accusation about how someone played
```

Within-player normalisation, threshold chosen *after* seeing the distribution,
looser cuts measured and explicitly rejected, and a stated reason about what we
are entitled to say to a person. `SCHEMA_VERSION` was bumped to 20 specifically
so the corrected rule reached the 12,333 of 16,723 rows that would otherwise
have kept the old one.

**Caveat:** `snap_decision` and `slow_paralysis` are pure Tier A.
`time_pressure_blunder` requires `quality == "blunder"`, so that one branch is
Tier C.

---

## Tier B — The player's choice, board-verifiable. Engine-independent.

Not psychology, but not engine opinion either: deterministic facts about what
the move *did*, computable with `python-chess` and no search. Objective, and
reproducible by anyone.

| field | fill | how |
|---|---|---|
| `was_capture`, `was_castle`, `was_check` | 100% | SAN / board |
| `move_san`, `move_uci`, `color`, `ply`, `phase` | 100% | the game record |
| `responded_to_threat` | 100% | `services/opponent_threat_detector.detect_threats` |
| `ignored_opponent_threat` | 100% | same |
| `piece_safety_decision` | 100% | SEE — static exchange evaluation, board arithmetic, **not** a search |
| `destination_safety_exact` | 100% | same family |

**A detail that matters:** the deriver's own manifest pins its dependencies by
SHA — `coach_play/coach_blunder_guard.py` (material safety) and
`services/opponent_threat_detector.py` (threats). Both are board analysers. And
`opponent_threat_detector` exists precisely because the analyzer's stored
`threat` field *"is null (which is ~always)"* — so threats are recomputed from
geometry rather than trusted from storage. That is the right call and it makes
these fields trustworthy.

---

## Tier C — Hybrid. The player's choice measured against an engine benchmark.

**These are the interesting ones and they need careful language.** They are
*not* the same as `cp_loss`, because they describe *how* someone chose rather
than what it cost. But they are not engine-free, so we must never present them
as pure observation.

| field | fill | behavioural half | engine half |
|---|---|---|---|
| `decision_register` | **35.7%** (224,801) | `cct_forcing` — did *they* play a forcing move; `cct_had_forcing_options` | `cct_best_was_forcing` — was the *engine's* best move forcing |
| `found_best_in_critical` | 100% | — | which moves were critical, and what was best |
| `was_critical_moment` | 100% | — | engine eval swing |
| `time_flag` (`time_pressure_blunder` branch only) | — | the clock | `quality == "blunder"` |

`decision_register` values across 40,000 sampled rows:

```
quiet_when_best_was_quiet        18,980
wrong_register                   18,088      45% of registered moves
forcing_when_best_was_forcing     2,932
```

**This is the closest thing we have to a calculation/decision measure** — "you
had forcing options, the best move was forcing, and you played quiet" is about
process, not outcome. It is worth building on.

**But a reliability warning, found in the codebase itself.**
`services/cognitive_gap_subtypes.py:11` states:

> *"Never trusts `cct_is_capture` / `cct_forcing` (SAN 'x' / '+' / '#'
> instead)"*

**One of `decision_register`'s three inputs is explicitly distrusted by another
service, which re-derives it from SAN.** Before this field underpins a coaching
claim, reconcile the two: either `cct_forcing` is sound and `cognitive_gap_subtypes`
is over-cautious, or it is not and `decision_register` inherits the fault.
**That is the single verification I would do before building on this field**,
and it is exactly the trap you named — replacing one misleading score with
another.

---

## Tier D — Engine output with a friendlier name.

Useful. Just not evidence about decision-making, and must never be labelled as
such.

| field | fill | note |
|---|---|---|
| `cp_loss`, `eval_before`, `eval_after` | 100% | raw engine |
| `execution_quality` | 99.5% | cp_loss banding |
| `severity` | 7.5% | cp_loss banding |
| `missed_free_piece`, `missed_opponent_blunder`, `punished_opponent_blunder` | 100% | engine comparison |
| `coaching_takeaway` | **100%** | **literally an f-string of cp_loss** |

`coaching_takeaway` deserves naming. It is the field that sounds most like
teaching and is the most purely engine-derived:

```python
return f"Blunder ({obs['cp_loss']}cp loss" + (f", {pat})." if pat else ").")
return f"Mistake ({obs['cp_loss']}cp loss)."
return f"Inaccuracy ({obs['cp_loss']}cp loss) — close to best but not quite."
```

A player told *"Mistake (150cp loss)"* has learned nothing about their chess.

---

## What this means for the Player Understanding System

**You asked for five things. Here is what each can honestly rest on today:**

| you want | can rest on | tier | honest status |
|---|---|---|---|
| what the player demonstrably does well | Tier B choice facts + rates over them | B | needs within-player re-derivation (the current strength picker uses a cohort) |
| what mistakes recur | `cognitive_gap` + decay | D + B | **already solid** — the strongest thing we have |
| which patterns they recognise or miss | detectors, Tier B | B | solid for tactics; detectors mostly congratulate (1,639 "applied" vs 5 "wrong") |
| what they've learned vs still need | `puzzle_attempts` (572, 20 users), focus cycles | behaviour | thin — 11 users have 5+ attempts |
| what to teach next, and why | focus picker + base-rated shapes | mixed | works; the "why" is the gap |

**And one thing you did not ask for, which I think is the most valuable
unused asset:** Tier A plus Tier B together support statements no competitor
can make and no engine can fake —

> *"On the moves where you had a forcing option, you took about two seconds and
> played a quiet move. On the moves you got right, you took nine."*

That is behaviour, position, and choice in one sentence, with no centipawns in
it. `time_spent_seconds` (500k moves) and `decision_register` (225k) already
hold everything needed, subject to the `cct_forcing` reconciliation above.

---

## Direct answers to your four concerns

**1. "Thinking scores are misleading."** Confirmed, and the file says so
itself: the denominator is the move count, two of five habits are
always-attributable catch-alls, and `MOVE_VERIFICATION` is annotated *"driven
by cp_loss"*. **Recommendation: stop computing habit scores from `cp_loss` and
compute them from Tier A + Tier B.** The five habit *names* can survive; their
inputs cannot.

**2. "Strengths are outdated."** Confirmed — all 39 are 104 days old,
`assign_strength()` has zero callers, and the derivation is a cohort z-score.
The refresher exists (`scripts/assign_strengths.py`) and is deliberately unrun
because the cohort version collapses 14 of 37 users onto one label.

**3. "We must verify what the fields actually measure."** Exactly right, and
this document is that verification. Two fields are real behaviour; eleven are
objective choice facts; four are hybrids, one of which has an internal
contradiction; the rest are engine output. **The collection is worth building
on — but only tier by tier.**

**4. "99,412 practice positions lack authored teaching."** Confirmed. 78.5% of
mistakes (king safety, piece safety, missed tactics) have unlimited practice
and no authored lesson, while the two gaps *with* content are the smallest two.

---

## On your update-trigger proposal

**"Every analyzed game can update evidence; five games can trigger a broader
reassessment"** — this is better than five-games-only and it matches what
exists. Per-game derivation already happens in `analysis_worker.py`.
`focus_outcome_shadow` already records a daily per-focus observation (21
consecutive days, 1,150 rows). `user_active_focus.review_after_measured_games`
already exists on 43 documents. So the per-game half is built, the
measurement history is built, and only the game-count trigger is missing.

**"Beginners can start from diagnostics and lesson results"** — necessary, not
optional: **58 of 128 accounts have no games at all.** `focus_source:
"diagnostic"` already exists in `routes/coach.py`.

---

## The one verification I would do before any homepage work

**Reconcile `cct_forcing`.** `decision_register` is the only field that
measures decision *process* at scale (224,801 rows), and one of its three
inputs is explicitly distrusted by `cognitive_gap_subtypes.py`, which re-derives
forcing-ness from SAN instead.

Concretely: recompute forcing-ness from SAN for a sample and compare against the
stored `cct_forcing`. If they agree, `decision_register` is sound and is the
backbone of the decision dimension. If they disagree, we know the error rate
before a single sentence is shown to a player.

That is a measurement, not a build, and it is the gate you asked for.
