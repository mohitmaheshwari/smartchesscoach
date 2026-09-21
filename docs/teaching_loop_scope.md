# Teaching Loop — Scope

Status: **DRAFT — awaiting Mohit signoff.** No code until signed off.
Author: Claude, 2026-09-21. Verified against `origin/working-code` @ `83d2cc1b`.

---

## The loop Mohit described

> "A user learns more when you take him through his game where he made the
> mistake. Take his reflection, understand he really understood the concept,
> then throw similar puzzles at him for those issues. Understand has he
> improved there, then move to the next one. Coaches do that."

1. **Find** the mistake in his own game
2. **Teach** it there, with a caption that explains why
3. **Check** he understood
4. **Drill** it with similar puzzles
5. **Measure** whether he still does it in new games
6. **Graduate** to the next concept; teach new concepts live while he plays

---

## 0. Existing surfaces audit

Done before anything else, per the standing rule. Every claim below is a
grep or a query against `origin/working-code`, not an adoption number —
ChessGuru is not live, so usage counts are not evidence either way.

### What already exists for each step

| Step | Where it lives | State |
|---|---|---|
| 1. Find | detectors, then `user_pattern_events` (`pattern_id`, `outcome`, `opportunity`, `cp_loss`, `fen_before`) | **Works** |
| 2. Teach | `caption_pipeline.py`, then `game_decryption_v5_service.py` | **Works** — this is the caption work in flight |
| 3. Check understood | `routes/reflect.py`, writes `reflection_sessions` (intent, quick tags, `awareness_gap_type`) | **Writes rich, reads thin** — all 5 consumers read it as a count or rate; none read the stated cause |
| 4. Drill | `community_puzzles` + `community_training_positions`, tagged `issue_type` / `skill_id` | **Works** — pool is large and tagged |
| 5. Measure | `concept_mastery_tracker.update_user_mastery_for_game`, called from `analysis_worker.py` | **Works** — streak / clean / mastered, idempotent via `last_evaluated_game_id` |
| 6. Graduate | same tracker: `streak_clean >= streak_required` (default 3) sets `acknowledged=True` and `mastered_at` | **Works** |

**Five of six steps are built.** This scope is not a new product. It is a
join.

### The overlaps that matter

**a) Two mastery systems, one dead.**
`services/mastery_gate_service.py` defines per-topic thresholds
(`piece_safety`: 75% over 3 sessions, or a 5-game clean streak) and a
`suggest_next_focus`. It has **zero live call sites** — the only two
references in the backend are comments, in `routes/coach_play.py:8230` and
`services/mission_scoreboard.py:384`.

`services/concept_mastery_tracker.py` does the same job, is keyed on
`concept_id` rather than a coarse `focus_area`, is idempotent, and actually
runs on every analyzed game.

**b) A teaching record exists, but it is a counter, not a log.**
`game_decryption_v5_service.py:4701` does `$inc: {shown_count: 1}` on
`user_concept_understanding` whenever a concept renders with
`needs_acknowledgment`. It is load-bearing already — line 3569 changes the
prompt wording at `shown_count >= 3`, and `v5_learning_tracker.py:296`
queries `shown_count >= 3, acknowledged: False`.

It stores one integer and one `updated_at` that is overwritten on every
render. The tracker's own docstring already names the consequence:
*"shown_count climbing without bound (2223 for a single concept on Mohit's
account)."*

**c) `move_observations` (113 code references) already holds the per-move
substrate** — `concept_used`, `coaching_takeaway`, `missed_pattern`,
`cp_loss`, `phase`, `game_id`, `derived_at`. Nothing new is needed to
observe behaviour.

**d) The concept join key exists under three spellings.** Puzzle attempts
carry it as `weakness_type` (`routes/training.py`) and as
`weakness_type = skill_id` (`routes/training_advanced.py`); puzzles carry
`issue_type` (`community_learning_service.py`). Six distinct writers insert
into `puzzle_attempts`.

### The one genuine gap

**Nothing records the moment of teaching with a timestamp.**

`concept_mastery_tracker` can answer *"has he been clean for N games?"* It
cannot answer *"is he cleaner since we taught him?"*, because the only
record of having taught is an unbounded counter with no per-event time.

Two consequences:

- **No before/after cut.** There is no boundary to measure across.
- **No denominator at the teaching boundary.** A concept can look mastered
  because it stopped coming up. The denominator does exist — but it is
  `outcome`, not the `opportunity` flag. Measured 2026-09-21: `opportunity`
  is present on only **7,723 of 121,651 rows (6.3%)**, because it was added
  recently (`12c50da0`). `outcome` is on 100%: 72,643 `hit`, 48,948 `miss`,
  60 `unknown`. Every row is an occasion where the concept came up and the
  user either got it right or did not, which is the denominator we want. It
  simply cannot be split into before-we-taught-it and after.

### Why a new collection, and not an existing one

Tested, not assumed. `taught_events` and `concept_taught_events` have **0
references** in the backend. Positive control for the same probe:
`user_pattern_events` 29, `move_observations` 113,
`user_concept_understanding` 62 — the probe does find collections that exist.

`user_pattern_events` is the natural-looking host and is **disqualified by
its own dedupe rule**. `pattern_event_logger.deduplicate_events` keys on
`(user_id, game_id, move_number, concept_id)` and keeps exactly one row per
key, ranked `{unknown: 0, hit: 1, miss: 2}`. A "taught" row would collide
with the detector's `miss` row on the same move and one of the two would be
silently discarded — destroying either the detection or the teaching record.

### Decision

**EXTEND**, on two surfaces, plus one deletion:

1. Add an append-only taught-event log alongside the existing `shown_count`
   counter. The counter stays — it is load-bearing.
2. Read the taught timestamp in `concept_mastery_tracker` to produce a
   before/after rate instead of a bare streak.
3. Delete `mastery_gate_service.py`.

---

## 1. What it is

A coach remembers what he told you, and when. Today ChessGuru teaches the
right thing in the right position and then forgets it ever spoke. This adds
that memory: every time we teach a concept in a user's own game, we write
down which concept, which game, which move, and when.

With that one timestamp, questions we currently answer by feel become
queries — did he understand it, did the drill help, is he actually better at
it, has he earned the next topic, and what have we never taught him at all.

Nothing new appears on screen in V1. This is the join that turns the six
existing steps into a loop.

## 2. What the user sees

**V1: no UI change.** The user-facing effect is that the coach stops
repeating itself — the existing `shown_count >= 3` re-prompt becomes
accurate instead of unbounded, and a mastered concept stops being taught.

The first surface this unlocks (V2, explicitly out of scope below) would be:

```
  Piece safety — you've got this
  ─────────────────────────────────────────────
  We first talked about this on 12 Aug, in your
  game against Mahesh.

  Since then:   14 chances to hang a piece
                1 taken        (was 6 in 11)

  Next up: your rook endings.
  ─────────────────────────────────────────────
```

That card is NOT in V1. It is drawn here so the data model is designed
against a real destination instead of in the abstract.

## 3. In scope (V1)

- New append-only collection `concept_taught_events`, one row per teaching
  render: `{user_id, concept_id, game_id, move_number, fen_before, surface,
  cp_loss, caption_version, taught_at}`
- Written at the existing site, `game_decryption_v5_service.py:4701`,
  alongside — not replacing — the `shown_count` increment
- `surface` distinguishes `review` / `pwc` / `puzzle`, so a later question
  can ask which surface actually teaches
- Idempotent per `(user_id, concept_id, game_id, move_number)` — a re-render
  of a stored card must not double-count
- `concept_mastery_tracker` reads `first_taught_at` and additionally writes
  `opportunities_before` / `violations_before` / `opportunities_after` /
  `violations_after`, with the denominator taken as
  `user_pattern_events.outcome in {hit, miss}` — **not** the `opportunity`
  flag, which is only on 6.3% of rows
- Delete `services/mastery_gate_service.py` and its two comment references
- Backfill: `first_taught_at` cannot be reconstructed, because the counter
  has no history. Existing rows get `first_taught_at: null` and are excluded
  from before/after until they are taught again. **No invented timestamps.**

## 4. Explicitly out of scope (V1)

- The mastery card in §2 — data first, surface second
- Any change to reflections. Reading the player's stated cause is a real gap
  and a separate scope; this one must not depend on a form being filled in
- Unifying `weakness_type` / `skill_id` / `issue_type` into one spelling —
  real debt, separate scope, would touch six writers
- Any change to which concept gets picked (`primary_weakness_picker`)
- Consolidating the six `puzzle_attempts` writers
- Detector promotion. The reason only one detector is plan-grade is tracked
  in `docs/motif_profile_backlog.md`, not here
- Live PWC teaching events. V1 instruments the review path only; `surface`
  exists so PWC can be added later without a migration

## 5. Success criteria

V1 is data plumbing, so the criteria are data criteria — and all are
falsifiable on Mohit's own account, without a single new user:

1. Every concept rendered with `needs_acknowledgment` produces exactly one
   `concept_taught_events` row. Verified by re-rendering one game twice and
   asserting the row count does not change.
2. For a concept taught 10 or more games ago, the tracker returns a
   before/after rate over `user_pattern_events.outcome in {hit, miss}`, with
   at least 10 events on the **after** side (see Q3, now answered).
3. `mastery_gate_service.py` is gone and the deploy gate stays green.
4. Zero change to any rendered caption — diffed through the real render path
   (`generate_game_decryption_v5`), not by reading the code.

Explicitly NOT a success criterion: any engagement, retention or adoption
number. Not live.

## 6. Open questions

**Q1. Does a teaching render count when the user never scrolled to it?**

- *Why unresolved:* the write fires at render time on the server. A card
  that is built but never looked at would count as taught.
- *Unblocking step:* Mohit's call. The cheapest honest answer is to write it
  anyway and add a `viewed_at` later, since the alternative is a client
  round-trip.

**Q2. Should PWC teaching write the same row in V1?**

- *Why unresolved:* PWC teaches live and far more often. It could swamp the
  review signal, and the two probably deserve different mastery weights.
- *Unblocking step:* measure renders per game on each surface before
  deciding.

**Q3. What is the minimum event count before a before/after rate is shown
to anyone? — ANSWERED 2026-09-21, still needs Mohit's lock.**

Histogram over all 121,651 `user_pattern_events` rows, grouped by
(user_id, concept_id) — 371 pairs:

```
  min=1   p25=3   p50=11   p75=58   p90=425   max=13087

  pairs with >=  5 events:  245  (66.0%)
  pairs with >= 10 events:  192  (51.8%)
  pairs with >= 20 events:  150  (40.4%)
  pairs with >= 30 events:  135  (36.4%)
  pairs with >= 50 events:  107  (28.8%)
```

**Recommendation: 10, applied to the AFTER side only, not to the total.**
The median pair sits at 11, so 10 keeps about half the pairs while still
being enough events for a rate to mean anything. Applying it to the total
would be wrong: a pair with 40 events that was taught last week has ~2
events after the boundary, and a rate over 2 events is noise wearing a
percentage sign. The gate is "at least 10 events since we taught it."

Caveat on this distribution: the pair counts are heavily skewed (max
13,087), so the mid-percentiles are the honest part of it and the tail is
one or two users. Worth re-running once more accounts have analyzed games.

## 7. Pre-code requirements

- [ ] Mohit signs off on this document
- [x] Q3 histogram run (2026-09-21). Threshold **10 on the after side** proposed — needs Mohit's lock
- [ ] Q1 and Q2 answered
- [ ] Confirm no consumer treats `user_concept_understanding.shown_count` as
      a proxy for teaching events. `routes/coach.py:2180` sums it — check
      what that endpoint feeds before changing any semantics
- [ ] `/audit-pre-code` run against this scope

---

## Appendix — evidence

All verified on `origin/working-code` @ `83d2cc1b`, 2026-09-21.

| Claim | Evidence |
|---|---|
| `check_mastery_gate` has no live callers | grep: 2 hits, both comments |
| `shown_count` is the only teaching record | grep `shown_count`: exactly one `$inc`, at `game_decryption_v5_service.py:4701` |
| `shown_count` is load-bearing | `game_decryption_v5_service.py:3569`, `v5_learning_tracker.py:296` |
| `user_pattern_events` cannot host taught rows | `pattern_event_logger.py:203-211` — one outcome per `(user, game, move, concept)` |
| `taught_events` is not an existing concept | 0 refs, against 29 / 113 / 62 for the three real collections |
| `opportunity` is NOT a usable denominator | present on 7,723 of 121,651 rows (6.3%); added recently in `12c50da0` |
| `outcome` IS the usable denominator | on 100% of rows: 72,643 `hit` / 48,948 `miss` / 60 `unknown` |
| mastery runs per analyzed game | `analysis_worker.py` calls `update_user_mastery_for_game` |
