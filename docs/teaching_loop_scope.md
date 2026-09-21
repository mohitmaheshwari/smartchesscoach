# Teaching Loop — Scope

Status: **DRAFT — awaiting Mohit signoff.** No code until signed off.
Author: Claude, 2026-09-21. Verified against `origin/working-code`.

**Revision note.** The first draft modelled "taught" as an impression — the
moment a coaching card rendered — and spent two open questions on whether a
card the user never scrolled to should count. Mohit rejected that outright:

> "No, taught doesn't mean scroll through. Taught means understood the
> concept. After the game review ends, we take a test of 5 puzzles that he
> wants us to test, and if he fails, he has not understood it yet.
> Otherwise we can take it to a monitor level in a real game."

The difference is not cosmetic. An impression is something we did.
Understanding is something **he** proved. Everything below is rebuilt on
that.

---

## 1. What it is

A coach does not tick a concept off because he said it out loud. He says it,
then he **tests you**, and only when you pass does he stop teaching it and
start quietly watching whether it holds up in a real game.

ChessGuru already teaches the right thing in the right position, and it
already watches real games. What it has never done is ask you to prove it.
This adds the proof step, and makes everything downstream depend on it.

### The state machine

```
   SHOWN          we taught it in his own game (review card)
     |
     |  he opts in — "test me on this"
     v
   TESTED         5 puzzles on that exact concept
     |
     +-- fail --> NOT UNDERSTOOD — teach it again, differently. No promotion.
     |
     +-- pass --> UNDERSTOOD
                     |
                     v
                  MONITORING     we stop teaching it, and watch real games
                     |
                     +-- violation --> back to SHOWN
                     |
                     +-- clean streak --> MASTERED — move to the next concept
```

The important property: **nothing is promoted on our say-so.** SHOWN →
UNDERSTOOD needs his proof. UNDERSTOOD → MASTERED needs his real games.

---

## 2. What the user sees

At the end of a game review, one card. Opt-in — he asks to be tested, we
never force it:

```
  ─────────────────────────────────────────────
  That's the third time this month you've moved
  a piece that was already doing a job.

        [ Test me on this — 5 positions ]
                                      [ Not now ]
  ─────────────────────────────────────────────
```

On finishing:

```
  ─────────────────────────────────────────────
  4 out of 5.

  You've got it. We'll stop bringing this up and
  just keep an eye on it in your next games.
  ─────────────────────────────────────────────
```

or:

```
  ─────────────────────────────────────────────
  2 out of 5.

  Not yet — and that's useful to know. Position 3
  is the one to look at again.

        [ Show me position 3 ]
  ─────────────────────────────────────────────
```

Failing is never a scoreboard and never a scold. It is information that
routes him back to teaching.

---

## 3. Existing surfaces audit

Every claim is a grep or a query, not an adoption number — ChessGuru is not
live, so usage counts are not evidence either way.

### What exists for each state

| State | Where it lives | Status |
|---|---|---|
| SHOWN | `game_decryption_v5_service.py:4701` — `$inc: {shown_count: 1}` on `user_concept_understanding` | **Exists** (a counter) |
| TESTED | nothing | **MISSING — this is V1** |
| UNDERSTOOD | `acknowledged` on `user_concept_understanding` | **Exists, set by the wrong things** |
| MONITORING | `concept_mastery_tracker.update_user_mastery_for_game`, from `analysis_worker.py` — `streak_clean`, `clean_games_total` | **Exists and works** |
| MASTERED | `mastered_at`, `mastery_stripped_at` on the same rows | **Exists and works** |

**Four of five states are built. Only the test is missing.**

### The ordering bug this exposes

`acknowledged` — the flag meaning "he understands this" — has two writers
today, and neither is proof:

1. `routes/coach.py:1787` — a self-report button,
   `/coach/decryption/acknowledge`. The tracker's own docstring says it
   "almost nobody uses."
2. `concept_mastery_tracker.py:407` — sets `acknowledged=True` off a
   **3-game clean streak alone**.

Writer 2 is the real problem for this design. In Mohit's model the clean
streak is the **MONITORING** phase, which only begins *after* he passes the
test. Today it runs first and promotes on its own. A concept can reach
`acknowledged` — and then `mastered_at` — **without the user ever
demonstrating anything**, simply by not coming up for three games.

That is the difference between "he learned it" and "it stopped being
relevant," and right now the system cannot tell them apart.

### The pool question — the thing that decides feasibility

His design needs 5 puzzles on a *specific* concept. First look said we
cannot do it:

```
  concepts users actually miss                 : 23
  community_puzzles.issue_type distinct values :  7
  community_training_positions.skill_id        :  1  (None, on all 44,985)

  concepts with >= 5 matching puzzles          :  0 / 23
```

That zero is a **vocabulary mismatch, not missing content** — the pools are
keyed on the coarse cognitive-gap vocabulary (`calculation_depth`,
`piece_safety`, `missed_tactic`, ...), while the detectors speak a
fine-grained one (`same_piece_better_square`, `knight_outpost`, ...).
`pattern_catalog.json` bridges 19 of 23, but only to a `human_name` and a
`family` — it carries no mapping to the puzzle vocabulary.

**The pool that does work was hiding in plain sight: `user_pattern_events`.**
It is the detector's own event log, and every `miss` row carries
`fen_before`, `concept_id`, `best_move_san`, the move he actually played,
and `cp_loss`. That is a puzzle, already labelled with the exact concept.

```
  concepts with >= 5 DISTINCT positions: 23 / 23

    same_piece_better_square    8,927        active_defense       1,476
    endgame_loose_pawn_attack   5,651        queen_fork           1,353
    knight_outpost              5,160        knight_on_rim          489
    pawn_kicks_piece            4,558        un_developing          241
    king_pawn_lifted            3,883        blocked_own_pawn       116
    ...                                      OP_SAME_PIECE_TWICE     18
```

**23 of 23.** Every concept a user actually misses has at least 5 real
positions to test on, and the thinnest has 18. No content authoring, no
re-tagging, no migration — the pool is a query.

### Decision

**EXTEND**, plus one reordering and one deletion:

1. **Build the test** — the only genuinely missing piece. Serve from
   `user_pattern_events`.
2. **Reorder the promotion.** `acknowledged` becomes test-driven. The clean
   streak is demoted to what it should be: the MONITORING evidence that runs
   *after* UNDERSTOOD, not a way to reach it.
3. **Delete `services/mastery_gate_service.py`** — a second, dead mastery
   system. Zero live call sites; the only two backend references are
   comments in `routes/coach_play.py:8230` and
   `services/mission_scoreboard.py:384`. `concept_mastery_tracker` does the
   same job, keyed on `concept_id` instead of a coarse `focus_area`, and
   actually runs.

---

## 4. In scope (V1)

- **Explicit state** on `user_concept_understanding`: `state` in
  `{shown, tested_failed, understood, monitoring, mastered}`, replacing the
  overloaded `acknowledged` boolean. `acknowledged` is kept in sync for the
  existing readers (`v5_learning_tracker.py:236,283`,
  `game_decryption_v5_service.py:3068`, `routes/coach.py:1836`) so nothing
  breaks on the way in.
- **`GET /api/coach/concept-test/{concept_id}`** — returns 5 positions for
  that concept from `user_pattern_events`, excluding positions from the
  user's own games he has already seen in review, and excluding anything he
  has already been tested on.
- **`POST /api/coach/concept-test/{concept_id}/submit`** — grades against
  `best_move_san`, writes one `concept_test_results` row
  (`{user_id, concept_id, positions[], answers[], score, passed, tested_at}`),
  and moves the state.
- **Grading reuses the existing grader.** `services/lesson_question_spec.py`
  owns the question text and grading family; the test must not introduce a
  second grader. Per the standing rule, the printed question and the grader
  must accept the same set of moves.
- **Opt-in card** at the end of the review. Declining is a first-class
  outcome, recorded, not treated as a failure.
- **`concept_mastery_tracker` stops promoting to `acknowledged`.** Its clean
  streak now advances `monitoring → mastered` only, and only for concepts
  already in `understood`/`monitoring`.
- **Backfill:** the 1,035 rows that already carry `mastered_at` were
  promoted without proof. They migrate to `monitoring`, **not** `mastered` —
  they keep their streak evidence but must pass a test to be called
  understood. No invented test results.

## 5. Explicitly out of scope (V1)

- Any change to how captions are written or which concept is picked
- Reading the player's stated cause out of `reflection_sessions` — a real
  gap, separate scope; this design deliberately does not depend on a form
- Unifying the `weakness_type` / `skill_id` / `issue_type` / `concept_id`
  vocabularies. V1 sidesteps it by serving from `user_pattern_events`, which
  already speaks the detector vocabulary. The debt stays, tracked elsewhere
- Lichess puzzles as a test source. 4,110,434 rows exist in
  `lichess_puzzles` and are better content, but they are themed tactically
  (`fork`, `pin`, `hangingPiece`) while most of these 23 concepts are
  positional, so that join is separate work
- PWC as a test surface. Measured: PWC is 683 of 121,748 pattern events
  (0.6%), and only 83 of 3,429 PWC moves carry a `concept_used` because
  `PWC_GAP_ENRICHMENT` is default off. It buys nothing in V1
- Spaced repetition / re-testing decay

## 6. Success criteria

All falsifiable on Mohit's own account, with no new users:

1. For all 23 concepts, the endpoint returns 5 distinct positions, none
   repeated across two tests for the same user.
2. A user who fails a test is **not** promoted — no `acknowledged`, no
   `mastered_at` — even if he then plays 3 clean games. This is the ordering
   bug, and it should ship with a regression test.
3. A user who passes enters `monitoring`, and a later violation in a real
   game returns him to `shown`.
4. The 1,035 pre-existing `mastered_at` rows land in `monitoring`, and the
   count of rows in `mastered` after migration is **0**.
5. Zero change to any rendered caption, diffed through the real render path
   (`generate_game_decryption_v5`).

Explicitly NOT a criterion: any engagement, retention or adoption number.
Not live.

## 7. Open questions

**Q1. What score counts as a pass?** 4/5 is the obvious guess, and a guess
is exactly what the standing rule forbids. `user_pattern_events` misses are
by definition positions people got *wrong*, so they may be far harder than a
fair test.
*Unblocking step:* histogram `solve_rate` on the overlapping
`community_training_positions` rows before locking. **This one genuinely
blocks the build.**

**Q2. Should the 5 positions include his own games, or only other people's?**
His own are more meaningful, but he has already seen the answer in review,
so it tests memory rather than understanding.
*Recommendation:* other people's positions for the test, his own for the
re-teach on failure. Wants a ruling.

**Q3. What happens on "Not now"?** Does the concept sit in `shown` forever,
re-ask after the next game, or fall back to today's streak-based promotion?
*Recommendation:* re-offer once after the next game that surfaces it, then
stop asking — never fall back to promoting without proof, because that
reintroduces the bug in §3.

## 8. Pre-code requirements

- [ ] Mohit signs off on this document
- [ ] Q1 locked via `/lock-via-data` — hard blocker
- [ ] Q2 and Q3 ruled on
- [ ] Confirm the four `acknowledged` readers behave correctly during the
      `state` transition (`v5_learning_tracker.py:236,283`,
      `game_decryption_v5_service.py:3068`, `routes/coach.py:1836`)
- [ ] Confirm `routes/coach.py:2180`, which sums `shown_count`, is not
      treated as a proxy for understanding anywhere downstream
- [ ] `/audit-pre-code` run against this scope

---

## Appendix — evidence

Verified 2026-09-21 against `origin/working-code` and the prod dataset.

| Claim | Evidence |
|---|---|
| only the test is missing | four of five states have live writers; `TESTED` has none |
| `acknowledged` is promoted without proof | `concept_mastery_tracker.py:407` sets it from a 3-game clean streak alone |
| the self-report button is not proof | `routes/coach.py:1787`; tracker docstring: "almost nobody uses" |
| puzzle pools cannot serve a concept test | `community_puzzles.issue_type` has 7 coarse values; `community_training_positions.skill_id` is `None` on all 44,985 |
| `pattern_catalog.json` does not bridge to puzzles | 21 entries, covers 19/23, carries only `human_name` and `family` |
| `user_pattern_events` CAN serve it | 23/23 concepts have ≥5 distinct `fen_before` with a `best_move_san`; thinnest is 18 |
| `mastery_gate_service` is dead | grep: 2 hits, both comments |
| PWC is not worth instrumenting in V1 | 683 of 121,748 pattern events (0.6%); 83 of 3,429 PWC moves carry `concept_used` |
| 1,035 rows already carry `mastered_at` | promoted under the old streak-only rule, hence the migration in §4 |
