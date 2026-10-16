# Controlled implementation plan — priorities 1 to 3

Status: PLAN ONLY, for sign-off. No code, data or flag has been changed.
Measured 2026-10-14 against production (`chess_coach`: 20,293 games, 19,570
analysed, 128 users, 630,695 move observations).

Companion to [player_understanding_measurement_map.md](player_understanding_measurement_map.md),
which is where these three priorities come from.

**Revision 2, 2026-10-14** — resolves the four issues raised on revision 1.
Three turned out worse than revision 1 said, and one of them stops a piece of
this work shipping. See §6. All figures below are revision-2 figures.

All measurements here were taken against **live production** through the SSH
tunnel on local port 27018 (verified: `ssh.exe` to `72.60.204.176`, server
`8a18e4f5fa93`, `chess_coach`, 20,297 games). Every probe was read-only. The
one exception, the restore test in §4.1, wrote only a throwaway database and
then removed it.

---

## 0. Four things the measurement changed about the plan

Read this first; each one altered a design decision.

1. **The CCT defect is bigger than I said, and "reaches nobody" was wrong.**
   78.5% of register verdicts change, not 56.2%. Revision 1 then claimed the
   defect reached no player. That held for `decision_register` (read only by
   its own writer) and for `coaching_takeaway` (read by nothing), but **not for
   `cct_held_initiative`**, and I had checked only for a frontend reference to
   the field name rather than tracing the strings derived from it.

   It does reach players. `game_mirror._cct_discipline_line` turns it into
   *"You kept the attack going after a miss in N different moments across these
   N games — real CCT discipline."* That line is appended to the mirror `story`
   at `game_mirror.py:998`, returned by `/coach/mirror-session` and
   `/home/dashboard-v2`, and rendered in `HomePageNew.jsx`. **37 users meet its
   exact gate today.** So there *is* a tester-facing conclusion built on the
   defect — see §4.3.

2. **`move_evaluations` has two shapes, not one.** Census over 1,000 games,
   every game in exactly one bucket: **948 user-moves-only (affected), 50
   ply-indexed, 2 matching neither shape — sum 1,000.** So **94.8% affected**,
   not the 85% revision 1 reported from a 300-game sample. The current code is
   *correct* for the 5% that are ply-indexed, so the shape must be detected per
   game; a blind recompute would break those 50.

3. **The date problem is 20 fields across 9 collections, not 3.** And the
   worst case is one I had not named: `user_active_focus` stores five fields
   as **mixed** types. Mixed is more dangerous than uniformly-string, because
   a range query returns a silently wrong *subset* rather than a clean zero.

4. **The normal write path builds learning events from observations.**
   `analysis_completion_evidence` calls `build_shadow_learning_event` on every
   derived result. So the backfill must not use it — see §1.6.

Also corrected: `focus_outcome_shadow` verdicts live under `resolution`, not
`verdict`. All 1,521 rows are populated (no_data 814, measurement_pending 268,
stuck 158, regressed 145, improved 136). My earlier "331 with verdicts" was
wrong in both directions.

---

## 1. Priority 1 — the CCT index defect

### 1.1 The defect, exactly

`services/cct_detector.tag_moves_with_cct` states its contract in its
docstring: `best_moves_san` is **indexed by ply** (every halfmove, both
colours) and each returned tag carries `ply`. `analysis_worker.py` violates it
twice.

```python
# backend/analysis_worker.py ~1308 — INPUT side
best_san_by_ply = []
for me in move_evaluations:            # user-only in 94.8% of games
    best_san_by_ply.append(me.get("best_move_san") or me.get("best_move"))

# ~1322 — MERGE-BACK side
tagged_by_ply = {t["ply"]: t for t in tagged_user_moves}
for i, me in enumerate(move_evaluations):
    t = tagged_by_ply.get(i)           # i is a position, t["ply"] is a halfmove
```

Inside the detector, `best_moves_san[ply]` then reads another move's best. That
SAN is usually illegal in the position, `board.parse_san` raises, the
`except (IllegalMoveError, InvalidMoveError, ValueError)` swallows it, and
`best_was_forcing` degrades to `False` with no error anywhere. Worse, the
user-only list is about half the length of the game, so for the entire back
half `ply < len(best_moves_san)` is false and there is no best move at all.

### 1.2 Proof — the control, not the hypothesis

Over 120 games of the affected shape, asking only "is this SAN legal in the
position where the detector checks it":

| Indexing | Legal | Illegal | No best move supplied |
|---|---|---|---|
| **Current** | 726 (20.0%) | 1,096 (30.1%) | 1,817 (49.9%) |
| **Corrected** | 3,639 (100.0%) | 0 (0.0%) | 0 (0.0%) |

If both rows had come back legal, the diagnosis would have been wrong and this
work unnecessary. That is the negative control the first claim lacked.

### 1.3 Exact affected data

| Location | Rows | Note |
|---|---|---|
| `game_analyses.…move_evaluations.cct_*` | 287,718 of 634,290 have `cct_forcing` present (45.4%) | 7 fields per row |
| `game_analyses.cct_held_initiative` | 17,766 games | derived from the same tags |
| `move_observations.decision_register` | 224,963 (35.7%) | exactly equals `cct_had_forcing_options` True — confirms the gate |
| `move_observations.coaching_takeaway` containing "wrong register" | 34,274 (5.43%), 57 users | written, read by nothing |
| `game_analyses.cct_held_initiative.count > 0` | 435 games, 45 users | **feeds a rendered coaching sentence** |
| `game_analyses.cct.cct_decisions > 0` | 13,640 games | gates that sentence (needs ≥2 per window) |

Current stored distribution of `decision_register`:
quiet_when_best_was_quiet 105,414 · wrong_register 102,795 ·
forcing_when_best_was_forcing 16,754.

**Not affected** (verified separately, because the regression test depends on
it): `missed_pattern`, `execution_quality`, `phase`, `was_capture`,
`was_forcing`. The first two come from the cp_loss path; the last two were
already moved to SAN-as-source-of-truth on 2026-07-02 precisely because these
CCT flags were untrustworthy. So `/progress/area-grades`, which reads
`missed_pattern` + `phase` + `execution_quality`, cannot move.

### 1.4 Dependencies — every reader

| Field | Readers (services/routes only) |
|---|---|
| `cct_forcing` | `cognitive_gap_subtypes.py`, `move_observation_deriver.py`, `analysis_worker.py` |
| `cct_best_was_forcing`, `cct_had_forcing_options` | `move_observation_deriver.py`, `analysis_worker.py` |
| `cct_is_capture`, `cct_is_check` | `cognitive_gap_subtypes.py`, `move_observation_deriver.py`, `analysis_worker.py` |
| `cct_creates_threat` | `data_freshness.py`, `analysis_worker.py` |
| `cct_played_forcing_when_best_was_forcing` | `analysis_worker.py` only |
| `decision_register` | `move_observation_deriver.py` (its own writer) only |
| `cct_held_initiative` | `coaching_library.py`, `game_mirror.py`, `routes/coach.py` — **player-facing, see §4.3** |
| `cct_aggregate` | `cct_detector.py`, `cct_voice.py`, `analysis_worker.py` |

### 1.5 Dry-run result, 150 games

Already run; writes nothing. 152 games were read, of which 2 matched neither
shape and were skipped, leaving **150 recomputed: 107 user-only + 43
ply-indexed**. 3,869 user moves compared. (Revision 1 printed these 43 beside
the separate 1,000-game census, which found 50 — two different samples, and
conflating them was the accounting error.)

| `decision_register` | Stored | Corrected |
|---|---|---|
| None (no decision to make) | 3,362 | 724 |
| forcing_when_best_was_forcing | 40 | 1,526 |
| quiet_when_best_was_quiet | 252 | 990 |
| wrong_register | 215 | 629 |

`cct_best_was_forcing` True: 78 → 2,074. Verdict changes on 3,039 of 3,869
moves (**78.5%**), and 2,675 of those changes are `None → a verdict`: the
defect was mostly *suppressing* the measure, not inverting it. `wrong_register`
as a share of decided moves falls from 42% to 25%, which is the direction a
real fix should move it — misalignment manufactures mismatch.

### 1.6 Migration plan

**Code (ships first, changes no stored data).**

1. Add two pure functions to `services/cct_detector.py` — beside the contract
   they serve, so there is one definition of the indexing rule rather than two:
   - `eval_shape(n_evals, n_plies, user_plies) -> "ply" | "user" | "unknown"`
   - `ply_indexed_bests(evals, user_plies, n_plies, shape) -> list[str|None]`
2. `analysis_worker.py` uses both, and merges back by mapping `ply → user-move
   ordinal` instead of `enumerate`. On `"unknown"`, skip CCT tagging for that
   game and log it — today it silently writes garbage.
3. Stamp `cct_alignment_version: 2` on the analysis document whenever tags are
   written. This is what makes the backfill resumable and the rollback
   selective. No existing document has it, so absence means version 1.
4. **Suppress `game_mirror._cct_discipline_line` for the duration.** It is the
   one player-facing claim built on the defect (§4.3), and it praises. Returning
   `""` from it is a one-line change that removes a sentence from the mirror
   story and touches nothing else. It comes back only after acceptance tests 10
   and 12.
5. **Drop the "wrong register" string**, per your decision. `_coaching_takeaway`
   stops emitting it, and the backfill unsets it on the 34,274 rows that carry
   it. It describes a mismatch without telling the player what to do, and
   nothing reads it.

**Backfill (after the code is deployed and verified — never before).**

`backend/scripts/backfill_cct_alignment.py`, default dry-run, `--apply` to
write, `--limit`, `--user`, `--resume`.

Per game: read `pgn` + `move_evaluations`, detect shape, recompute tags,
recompute `cct_aggregate` and `cct_held_initiative`, and recompute
`decision_register` for that game's `move_observations` rows.

Three constraints on how it writes, each one deliberate:

- **It calls `derive_observations_for_game` directly, never
  `analysis_completion_evidence`.** The deriver is pure — it contains no
  `insert_one`/`update_one` of any kind and returns documents. The completion
  path, by contrast, calls `build_shadow_learning_event` on every result. Going
  through it would manufacture learning events for games played months ago,
  which is exactly what must not happen.
- **It `$set`s only the CCT-derived fields** (the seven `cct_*`,
  `decision_register`, `coaching_takeaway` where and only where the current
  value is the "wrong register" string). It never deletes or rewrites a whole
  observation document, so nothing else on the row can move.
- **It touches no learning-state collection.** `user_concept_understanding`,
  `puzzle_attempts`, `learning_sessions`, `user_active_focus` and
  `focus_history` are out of its write scope entirely, asserted in the script
  rather than left to convention.

Games are never modified. `games` and the raw `stockfish_analysis` evaluations
(`cp_loss`, `best_move_san`, `eval_after`, `fen_before`) are read-only
throughout; only the `cct_*` interpretation layer on top of them is rewritten.

### 1.7 Rollback

1. Snapshot first (§4.1). Restore is the unconditional escape hatch.
2. Selective: every touched document carries `cct_alignment_version: 2`, so
   `{"cct_alignment_version": 2}` identifies the full change set, and the
   snapshot supplies the prior values for exactly those documents.
3. Code-only revert: reverting the `analysis_worker` commit restores old
   behaviour for *new* games without touching backfilled ones. Because nothing
   reads these fields on a player surface, a mixed-version corpus is safe to
   sit in while deciding.

### 1.8 Acceptance tests

| # | Test | Pass condition |
|---|---|---|
| 1 | Legality control re-run over 200 games, both shapes | corrected indexing 100% legal, 0 illegal, 0 missing |
| 2 | Ply-indexed games (the 15%) before vs after | **zero** changed fields — the fix must be a no-op where the old code was right |
| 3 | `eval_shape` unit tests | user-only, ply-indexed, and off-by-one lengths each classified correctly; unknown returns `"unknown"` and is skipped |
| 4 | Round-trip on one game | every tag's `ply` maps to the `move_evaluations` row whose `move_san` equals the tag's `move_san` — a maths check, not a label check |
| 5 | Regression: `/progress/area-grades` for 10 users, before vs after | byte-identical response |
| 6 | Regression: `backend/tests/test_all_flows.py` | no new failures against the pre-change baseline |
| 7 | Non-CCT fields on backfilled rows | `missed_pattern`, `execution_quality`, `phase`, `cp_loss` unchanged on every touched row |
| 8 | Corpus fingerprint, 400 games | only CCT-derived rows differ; diffed per row, not in aggregate |
| 9 | No artificial events | counts of `user_concept_understanding`, `puzzle_attempts`, `learning_sessions`, `user_active_focus`, `focus_history` identical before and after |
| 10 | Held-initiative base rate, recomputed | the corrected firing rate is measured over ≥1,000 games and reviewed before `_cct_discipline_line` is re-enabled. If it fires on nearly every game it is a constant, not a strength, and the sentence is retired rather than shipped |
| 11 | Mirror story, line suppressed | `/coach/mirror-session` for the 37 affected users returns a `story` identical to today minus the CCT sentence, and nothing else |
| 12 | Mirror story, line restored | after test 10 passes, the sentence reappears only for users whose recomputed count still clears the gate, and the count it quotes equals the recomputed value |

---

## 2. Priority 2 — date-type compatibility

### 2.1 Exact affected data

Discovered from the documents, not from a guess list. 20 fields, 9
collections, 53,430 values.

| Collection | Field | Rows | Stored as |
|---|---|---|---|
| `user_active_focus` | `started_at` | 301 | **MIXED** — str ISO-T aware ×234, datetime naive ×67 |
| | `locked_until` | 301 | **MIXED** — ×234 / ×67 |
| | `updated_at` | 340 | **MIXED** — ×262 / ×78 |
| | `created_at` | 339 | **MIXED** — ×315 / ×24 |
| | `closed_at` | 73 | **MIXED** — ×27 / ×46 |
| | `superseded_at` | 46 | str date-only |
| `user_concept_understanding` | `created_at`, `updated_at` | 5,074 each | str ISO-T aware |
| | `last_clean_game_at` | 1,668 | str ISO-T aware |
| | `mastered_at` | 1,037 | str ISO-T aware |
| | `mastery_stripped_at` | 251 | str ISO-T aware |
| `user_opening_progress` | `last_practiced_at` | 8,177 | **THREE formats** — str ISO-T ×2,905, **str dotted** ×93, datetime naive ×2 |
| `thinking_scores` | `calculated_at` | 19,508 | str ISO-T aware |
| `coaching_summaries` | `generated_at` | 8,799 | str ISO-T aware |
| `focus_outcome_shadow` | `observed_on` | 1,521 | str date-only |
| `puzzle_attempts` | `created_at` | 572 | str ISO-T aware |
| `focus_history` | `started_at`, `graduated_at` | 62 each | str ISO-T aware |
| `user_opening_mastery` | `created_at`, `updated_at` | 96 / 129 | str ISO-T aware |

Two formats deserve naming. The **dotted** `2026.04.15` values are chess.com's,
and `.` sorts above `-` in ASCII, so a string comparison puts every dotted date
after every ISO timestamp whatever day it names — the trap
`coaching_landed.py` documents as having already put 407 games on the wrong
side of 15 focus windows. And `learning_sessions` / `focus_outcome_shadow`
store **naive** datetimes, which compare fine inside Mongo but raise
`TypeError` against an aware datetime in Python.

### 2.2 Scope: which fields actually get converted

Converting all 20 is more risk than value. Convert the fields that gate a
retention or progress read:

- **In scope (Phase A): 15 fields, 5 collections, 23,377 values.** Revision 1
  said 13, miscounting its own list. Itemised so it reconciles:

  | Collection | Fields (with row counts) | Fields | Values |
  |---|---|---|---|
  | `user_active_focus` | `started_at` 301, `locked_until` 301, `updated_at` 340, `created_at` 339, `closed_at` 73, `superseded_at` 46 | 6 | 1,400 |
  | `user_concept_understanding` | `created_at` 5,074, `updated_at` 5,074, `last_clean_game_at` 1,668, `mastered_at` 1,037, `mastery_stripped_at` 251 | 5 | 13,104 |
  | `user_opening_progress` | `last_practiced_at` 8,177 | 1 | 8,177 |
  | `puzzle_attempts` | `created_at` 572 | 1 | 572 |
  | `focus_history` | `started_at` 62, `graduated_at` 62 | 2 | 124 |
  | **Total** | | **15** | **23,377** |
- **Deferred:** `thinking_scores.calculated_at` (19,508) — `thinking_scores` is
  on the do-not-build list, so converting it buys nothing;
  `coaching_summaries.generated_at`; `focus_outcome_shadow.observed_on` (a
  deliberate date-only partition key, with the real instant in `observed_at`);
  `user_opening_mastery`.

### 2.3 Migration plan — readers first, in three phases

**Phase A1 — tolerant readers, deployed alone.** One helper,
`services/time_fields.py`, exposing `as_datetime(value) -> datetime | None`:
accepts `datetime` (naive → UTC), ISO with `T` or space, date-only, and dotted
`YYYY.MM.DD`; returns `None` rather than raising. `coaching_landed._as_datetime`
already does most of this; it becomes an import of the shared helper rather
than a second copy. Every read of the 13 fields goes through it. Window
queries that currently hand Mongo a bare `$gte` are rewritten to fetch by
user/topic and filter in Python via the helper, so a mixed-type field can no
longer return a partial set.

Phase A1 is **independently valuable and independently revertable**: it makes
every read correct against the data as it stands today, before anything is
migrated. If the migration never happens, the bug is still fixed.

**Phase A2 — dry-run.** `backend/scripts/migrate_date_types.py`, dry-run by
default. Per field: count values, parse every one with the helper, and report
parsed / unparseable / already-datetime, with a sample of each. **Gate: the
migration does not proceed on any field with a single unparseable value.** For
`last_practiced_at` the report must show all three formats resolving, including
the 93 dotted ones.

**Phase A3 — apply, per field, resumable.** For each field, `$set` the parsed
`datetime` and copy the original string to `<field>_raw_v1` on the same
document. Nothing is destroyed: the original value survives on the row, which
is both the audit record and the cheapest rollback. Idempotent — a value
already a `datetime` is skipped.

### 2.4 Rollback

1. Snapshot (§4.1).
2. Per field, `<field>_raw_v1` restores the original value with a single
   `$set` from a field that is still on the document. No snapshot needed for
   this path, and it works field by field.
3. Phase A1 readers accept both types, so a partial or reverted migration is a
   supported state rather than an outage. This is why readers ship first.

### 2.5 Acceptance tests

| # | Test | Pass condition |
|---|---|---|
| 1 | `as_datetime` unit tests | aware ISO-T, naive ISO-space, date-only, dotted, `datetime` naive, `datetime` aware, `None`, `""`, and junk → correct value or `None`, never an exception |
| 2 | Ordering proof | the 93 dotted `last_practiced_at` values sort into the same order as their parsed datetimes — the specific bug being fixed |
| 3 | Dry-run gate | 0 unparseable across all 13 fields |
| 4 | Count conservation | per collection, document count and populated-field count identical before and after |
| 5 | Round-trip | for 200 sampled documents, `as_datetime(<field>_raw_v1) == <field>` |
| 6 | The real payoff | `coaching_landed` practice counts recomputed after migration: `came_back_unpractised` **falls** and the fall is explained by puzzle attempts that a `$gte` previously could not see |
| 7 | No artificial events | no document created in any learning collection; `mastered_at` and `mastery_stripped_at` change type but never value (test 5 covers the value) |
| 8 | Regression | `test_all_flows.py` green against baseline; `/progress/area-grades` and the focus endpoints byte-identical for 10 users |

---

## 3. Priority 3 — connect `coaching_landed`

### 3.1 What exists

`services/coaching_landed.py`, signed off 2026-09-28, tested in
`backend/tests/test_coaching_landed.py`, **zero production callers**, and the
`coaching_landed` collection holds **0 documents**. Run read-only over all 301
non-strength focus documents it returns a verdict for every one and a usable
before/after pair for 238:

never_returned 91 · came_back_unpractised 65 · practised_no_change 58 ·
**practised_and_moved 41** · practised_and_worse 26 · not_yet_measurable 20.

For comparison, the existing resolution path has produced 13 real verdicts in
total across all time (7 improved, 6 regressed), with 24 active focuses sitting
at `resolution: no_data`.

### 3.2 Where it attaches — no new system, no new loop

`server.py:174 focus_outcome_loop` already wakes daily and iterates every
active focus, calling `check_focus_outcome` on each. `evaluate_landing` goes
beside that existing call, and its record is upserted to `coaching_landed`
keyed on `(user_id, topic_key, cycle started_at)`. No new scheduler, no new
service, no new detector.

Two notes on correctness. The loop must run **after** Phase A1 (§2.3), or every
landing record written will carry the string-date zero in its
`practice_events`. And `evaluate_landing` currently builds `$in` lists of up to
5,000 game ids against `move_observations`; `games.game_id` is unindexed, so
the per-focus game lookup is built in Python from one pass rather than looked
up per focus.

### 3.3 What a player sees

Nothing on the homepage; its design is untouched, as instructed. Of the six
stages, five are diagnoses about *us* — the file's own `MEANS` map calls them
re-engagement, a wrong ask, a wrong diagnosis. Those go to the internal record
only (§4.2) and are never rendered.

Exactly one stage is a fact about the player: `practised_and_moved`. You asked
that it be shown only when sufficient, valid evidence supports the specific
improvement claim. I measured the evidence behind all 41 current cases, and
**it does not meet that bar. The player-facing line cannot ship in this piece
of work.**

Distribution across the 41 cases, looked at before choosing any threshold:

| | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| improvement in the pattern's rate | −66.5% | −40.7% | −18.0% | −12.3% | −10.5% |
| games since the focus started | 4 | 14 | 52 | 257 | **1,588** |
| **practice events** | **1** | **1** | **1** | **1** | **2** |

Two independent reasons that is not enough:

- **40 of the 41 rest on a single practice event.** Requiring two drops it to
  1 of 41; requiring three drops it to 0. "You practised this and it improved"
  cannot be said honestly off one puzzle, and attributing the change to our
  coaching off one event is the causal claim we have no basis for. Note the
  practice count is also understated until Phase A1 lands (§2.3) — so this
  number should be **re-measured after Phase A**, and the gate chosen then,
  from the corrected distribution.
- **The comparison window is unbounded.** `evaluate_landing` splits *all*
  analysed games before the focus start against *all* games after, so
  `games_since` reaches 1,588: for those players the "after" period is most of
  their career and the delta says nothing about the focus. This is a real
  defect in the service, not a display problem. A bounded window (the N games
  either side of the start) is needed before any delta is trustworthy.

**So Phase 3 ships the measurement only.** All six stages go to the internal
record; nothing is rendered; `COACHING_LANDED_RENDER_ENABLED` stays off and
unused. The display returns as its own scoped piece of work once (a) Phase A
has corrected the practice counts, (b) the window is bounded, and (c) the
re-measured distribution shows cases that clear a gate chosen from it. That
also settles the open question from revision 1 about which endpoint feeds the
post-game card: it is not needed yet.

### 3.4 Rollback

The write is a new collection and one call site. Dropping `coaching_landed`
and reverting the call removes it completely; nothing else reads it. The
player-facing line sits behind `COACHING_LANDED_RENDER_ENABLED`, default
**off**, so the measurement can accumulate for a fortnight before anything is
shown — and per the flag lesson, the flag gates only the render, never the
measurement, which is the mistake the shadow loop made in September.

### 3.5 Acceptance tests

| # | Test | Pass condition |
|---|---|---|
| 1 | Existing unit tests | `test_coaching_landed.py` green, unmodified |
| 2 | One loop pass on a copy of prod | 301 records written, stage distribution within a few of the read-only run above |
| 3 | Idempotence | a second pass on the same day updates in place; count stays 301 |
| 4 | No artificial events | zero documents created in `puzzle_attempts`, `learning_sessions`, `user_concept_understanding`, `user_active_focus`, `focus_history`; `evaluate_landing` is read-only by inspection and asserted in the test |
| 5 | The date dependency is real | `practice_events` for a known puzzle-solving user is 0 before Phase A1 and non-zero after — proves the ordering in §3.2 matters |
| 6 | Render stays dark | with the flag off, the post-game payload is byte-identical to today for 10 users |
| 7 | Flag on, one user | the line appears only for a `practised_and_moved` focus, contains no numbers, and passes `pwc_coaching_lint.py` |
| 8 | Regression | `test_all_flows.py` green; the loop's existing shadow and close behaviour unchanged, verified by diffing one pass's log and `focus_outcome_shadow` writes |

---

## 4. Cross-cutting

### 4.1 Snapshots — verified feasible

**Tested on production, 2026-10-14, as you asked.** Dumped
`chess_coach.focus_history` gzipped inside the mongo container, restored it
into a throwaway namespace, compared every document, dropped the throwaway and
removed the dump:

```
prod docs     : 62      restored docs : 62      counts match  : true
docs compared : 62      byte-identical: true (mismatches: 0)
throwaway dropped       removed /tmp/snap_20261014T150516Z
```

So the mechanism is proven, not assumed. Two corrections to revision 1's
assumptions about where it runs:

- **The dump must run on the server, not through the tunnel.** `mongodump` and
  `mongorestore` live in `chess-coach-mongodb` on `72.60.204.176`; the host
  disk is 193G with **93G free**. Revision 1 quoted "849G free of 1,007G",
  which is a *local* volume and irrelevant — the data is on the server.
- **Sizes, measured:** `game_analyses` 19,575 docs / 4,891 MB and
  `move_observations` 630,695 docs / 1,498 MB, so Phase 1's full dump is
  ~6.4 GB uncompressed. Phase A's five collections total ~6 MB.

Because 6.4 GB is a big dump to take for a change that touches a handful of
fields, the primary rollback for Phase 1 is a **targeted field-level
snapshot**: the old value of every field the backfill changes, written to
`interpretation_corrections` (§4.2) as it goes. That restores exactly what
changed, needs no 6.4 GB, and is the same record the audit requires. The full
gzipped dump is taken as well, once, as the disaster fallback — not as the
routine path.

Every snapshot is verified by restore-and-compare, as above, before its phase
is allowed to proceed. An unverified snapshot is not a rollback plan.

**Housekeeping, needs your say-so:** the server still holds
`chess_coach_restoretest_20260911T034109Z`, **1,907.8 MB** — 57% the size of
`chess_coach` itself (3,342.7 MB) — left over from a restore test on
2026-09-11 that was never dropped. I have not touched it. Shall I drop it?
Dropping a database on production is not something I will do unprompted.

### 4.2 The internal record of corrected interpretations

One collection, `interpretation_corrections`, written only by the migration
scripts: `{phase, collection, field, doc_key, old_value, new_value,
reason, script_version, applied_at}` (a real `datetime`). It is the audit trail
for what we changed and why, and it is what makes the §1.7 and §2.4 selective
rollbacks possible without re-deriving anything. Read by no coaching surface,
ever — it is a record for us.

### 4.3 Conclusions already presented to testers

Measured, not assumed:

- **One conclusion HAS been presented to testers, and revision 1 missed it.**
  `cct_held_initiative` reaches the screen through
  `game_mirror._cct_discipline_line` → mirror `story` →
  `/coach/mirror-session` and `/home/dashboard-v2` → `HomePageNew.jsx`. The
  sentence is *"You kept the attack going after a miss in N different moments
  across these N games — real CCT discipline."* It is a **congratulatory**
  claim, computed by `detect_held_initiative_segments(tagged_user_moves,
  move_evaluations)` from the same misaligned tags, so the count it quotes is
  not trustworthy. **37 users meet its gate** (≥2 qualifying games and ≥2 held
  moments in the window); 45 have at least one qualifying game.

  What I can and cannot say about it: the detector fires on **435 of 17,766
  games (2.4%)**, and where it fires it almost always fires once, so it is a
  rare signal rather than a constant. I have *not* measured whether the moments
  it names are real, and I am not going to assert either way. The honest
  position is that a praise sentence derived from a proven-misaligned input
  should not be shown until it is recomputed and its base rate checked — so
  **the line is suppressed for the duration of the fix** (§1.6) and restored
  only after acceptance test 10 below.

- **`decision_register` and `coaching_takeaway`: nothing to flag.** Read only
  by their own writer and by nothing at all respectively; all three `routes/`
  readers of `move_observations` use narrow projections that exclude them.
- **One thing to fix on the way past, unrelated to correctness.** The string
  `"Played in the wrong register — forcing vs quiet mismatch."` sits on 34,274
  rows for 57 users. If it is ever rendered it will fail the voice rules
  outright: "register" and "forcing vs quiet" are jargon for a 600–1500
  audience. Since the rows are being rewritten anyway, the string should be
  rewritten to plain English or dropped. I would drop it — it describes a
  mismatch without saying what the player should have done.
- **Dates: nothing presented, but one silent understatement.** The
  `came_back_unpractised` reading (65 players) is partly an artefact, so no
  wrong conclusion has been *shown*, but any internal read of it so far was
  too pessimistic. Worth a note in the corrections record.
- **Already corrected, in the measurement map:** the castling breakdown
  (17 + 23 + 2 over 40 games → disjoint buckets summing to 40, genuine figure
  2) and the opening-coverage claim (per-platform, and the gap is
  normalisation). Both were in a page shared with you and both are fixed there.

### 4.4 Sequence and gates

```
P1  code (+ suppress mirror line, drop wrong-register) ──► verify
      └─► dry-run ──► GATE ──► backfill ──► base-rate check ──► GATE ──► restore mirror line

P2  A1 tolerant readers ──► verify ──► A2 dry-run ──► GATE ──► A3 apply, field by field

P3  (needs A1 live) loop call ──► internal record only ──► STOP
      └─► re-measure the practice distribution ──► separate scoped work for any display
```

Every gate is a human look at a dry-run report, not a green test suite. Phase 3
cannot start before Phase A1 is live (§3.2), and now ends at the internal
record. Phases 1 and 2 are independent and can run in parallel.

### 4.5 Out of scope, explicitly

No new detector, scoring engine or coaching system. No change to `games` or to
raw Stockfish evaluations. No change to the homepage. No new puzzle, lesson,
mastery or focus record created by any migration. No change to
`thinking_scores`. `user_misconceptions` is not revived.

---

## 5. Your three decisions, as recorded

1. **Show verified improvement in the existing post-game card** — accepted as
   the destination. But the evidence to verify it does not exist yet (§3.3:
   40 of 41 cases rest on one practice event, and the comparison window is
   unbounded), so this piece of work ships the measurement and no display. The
   card is where it goes when the evidence clears a gate chosen from the
   corrected distribution.
2. **Remove the unused "wrong register" message** — done as specified, §1.6
   step 5: stop emitting it, unset the 34,274 existing rows.
3. **Keep the date migration to genuinely necessary fields** — held at the 15
   gating fields in §2.2. `thinking_scores.calculated_at` (19,508 rows) stays
   out: nothing should read `thinking_scores`, so converting it buys nothing.

## 6. Revision 2: the four issues resolved

| Issue raised | Resolution |
|---|---|
| Date-field count said 13, list showed 15 | **15 confirmed.** Itemised table in §2.2 that reconciles to 15 fields / 5 collections / 23,377 values. Revision 1 miscounted its own list. |
| Shape totals did not match sample sizes | **Fixed, and the number moved.** Clean 1,000-game census: 948 + 50 + 2 = 1,000, so **94.8% affected**, not 85%. The dry run is 150 recomputed (107 + 43) out of 152 read. Revision 1 printed the dry run's 43 next to the census and conflated two samples. |
| `cct_held_initiative` has backend readers — confirm it cannot indirectly influence player-facing coaching | **It can, and it does.** Traced to a rendered sentence for **37 users** (§4.3). Revision 1's "reaches nobody" is withdrawn; it was based on a frontend grep for the field name, not on the strings derived from it. The line is suppressed during the fix and restored only after a base-rate check. |
| `practised_and_moved` should display only on sufficient valid evidence | **It does not have it.** 40 of 41 cases rest on a single practice event; `games_since` reaches 1,588 because the comparison window is unbounded. **The display is cut from this work** (§3.3). |

Also fixed in passing: the restore mechanism is now **tested on production**
rather than asserted (§4.1), and revision 1's disk figures were from the wrong
machine.

Nothing is implemented until this revision is signed off.
