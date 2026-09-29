# Explore: practice for a player we do not know yet

**Status:** DRAFT — awaiting Mohit's sign-off. No code has been written.
**Asked for:** 2026-09-28, "if user has not given us enough still, we still
want to give him an option to explore more".
**Evidence base:** `docs/cold_start_content_findings_2026_09_28.md`.

---

## 1. What it is

A place a player can keep solving when we do not yet know them — because they
have not imported games, or have played only one or two with us.

They pick nothing, configure nothing, and are told nothing about their
weaknesses until we have earned the right to say it. They solve, and the
profile builds itself underneath.

This is **not** the diagnostic. The diagnostic is bounded, decides an opening
ability band, and ends. Explore has no end, and exists for the player who
finished the diagnostic (or skipped it) and still has nothing else to do.

## 2. Why it is worth building

Measured, not assumed:

- `lichess_puzzles` holds **4,110,434** puzzles, theme **and** rating labelled.
  No user-facing route reads that collection. It is read by
  `admin_detector_review`, `build_diagnostic_pool` and the detector benches —
  it exists to test our detectors and has never been shown to a player.
- `community_training_positions` holds **45,828 approved** positions, tiered
  easy/medium/hard, tagged with 10 pattern types.
- `puzzle_attempts` holds 462 attempts from 20 users. People do solve here.

So the content exists and the appetite exists. What is missing is a door.

## 3. What the player sees

```text
KEEP YOUR EYE IN
[board, one position, no hint, no theme label]
[they move]

right:  a short confirmation, then the next position
wrong:  the move that worked, and one sentence on what it was
        [Try another]
```

No theme name before the attempt. Naming "discovered attack" above the board
tells them the answer; the whole value of a themed puzzle is that the player
has to see it unaided.

After roughly 8 attempts, and only then:

```text
[one line, in words, no counts]
"Forks keep catching you out. Want a few more of those?"
[Yes]  [Something else]
```

## 4. Where the puzzles come from

Both pools, for different reasons:

- **Lichess** for breadth and for `rating`. Its difficulty is crowd-derived
  from millions of attempts, which is far better evidence about a stranger
  than our `cp_loss` proxy.
- **Ours** (`community_training_positions`) because they are real mistakes
  real players at this level actually made, which the Lichess set is not
  selected for.

Sequencing rule: grade against the **puzzle's own rating**, exactly as
`diagnostic_service._grading_thresholds(puzzle_rating)` already does. Give a
theme 3-4 positions at ascending ratings, and:

- solves at 1200, fails at 1500 -> an ability ceiling, which is normal
- fails at 800 while solving 1200 elsewhere -> a genuine theme weakness

Without that separation a miss means nothing: the likeliest reason a 900 fails
a puzzle is that it was rated 1800.

## 5. In scope (V1)

- One route, one board, one position at a time, no configuration.
- Draws from both pools, sequenced by rating within a theme.
- Every attempt written to `puzzle_attempts` in the existing shape, so
  `pattern_decay_service` picks it up with no change.
- The "a habit is showing" line appears only after enough attempts at one
  theme to mean something, and says it in words with no numbers.
- Reachable from somewhere a new player actually stands. Where is the owner's
  call, not mine.

## 6. Explicitly out of scope (V1)

- No new detectors, no new engine calls, no caption work.
- No streaks, no XP, no daily goals, no leaderboards.
- No theme picker in V1. It is the obvious V2, and adding it first turns a
  coaching surface into a puzzle app.
- No change to the diagnostic. It stays bounded and keeps its own pool.
- No claim about a player's weakness before the evidence supports it.

## 7. Success criteria

- A player with zero imported games can solve continuously and, after one
  sitting, the coach can say one true thing about them that came from their
  own attempts.
- The weakness sentence is defensible: for every claim, the player failed that
  theme at a rating they cleared elsewhere. Testable per claim, offline.
- No claim fires before its evidence threshold. Measured by replaying real
  attempt sequences, not by inspection.
- Attempts land in `puzzle_attempts` and move the decay model. Verified by
  reading the model's output before and after, not by assuming.

## 8. Open questions

- **Where does it live?** Probably Lab (`docs/project_mastery_ia_lab_home`
  makes Lab the mastery home). Owner's call.
- **How many attempts before we say anything?** 8 is a guess and should not be
  locked from a guess. Per `feedback_threshold_before_distribution_is_sin`,
  pick it after looking at the distribution of attempts-per-theme in real
  sessions.
- **What happens when they then import games?** `diagnostic_supersedes_after`
  already handles diagnostic-to-games. The same question applies here and has
  no answer yet.

## 9. Ownership

Onboarding and `/home` composition belong to `-8f` and `-33` per
`docs/agents/BOARD.md`. Both sessions have ended. This scope is written so the
work survives the session that measured it; whoever picks it up should treat
section 8 as unanswered rather than inherited.
