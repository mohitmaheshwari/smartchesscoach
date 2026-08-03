# player_profiles consolidation — scope

Status: RESOLVED 2026-07-25 (commit `ec6fbf9f`), verified live in production
2026-08-03. Option B was chosen: Writer 3 (`refresh_player_profile`) no longer
writes `total_blunders`/`total_mistakes`/`total_inaccuracies` — renamed to
`recent_20_total_blunders`/`recent_20_total_mistakes`/`recent_20_total_inaccuracies`
so the two writers' distinct field names never collide again. Writer 2
(`update_player_profile_sync`) remains the sole owner of the career-cumulative
`total_blunders`/`total_mistakes`, which is what `services/chess_understanding.py`
actually reads. `games_analyzed_count` (Writer 2, career) and `games_analyzed`
(Writer 3, last-20) were already distinctly named and both have live readers —
left as-is. Writer 1 (dead code, `player_profile_service.update_profile_after_analysis`)
untouched — zero live callers, not part of this fix. This section below is the
original pre-fix analysis, kept for context.

## Why this exists

Filed 2026-07-22 while auditing for the same "stale-derived-cache" bug shape
already fixed today in `user_pattern_decay`, `community_puzzles.issue_type`,
and `coach_memory` (weaknesses/performance/recurring_patterns). `player_profiles`
has the same disease, but worse — it's not one stale writer, it's **two live
writers with incompatible schemas writing to the same collection**, plus a
third writer that's dead code.

## Current state (verified against real prod data, `chess_coach` DB)

### Writer 1 — `player_profile_service.update_profile_after_analysis()` — DEAD CODE

Called only from `journey_service.py:854`, inside `auto_analyze_game()`
(an LLM/GPT-based legacy analysis path, separate from the Stockfish
`analysis_worker.py` pipeline). `auto_analyze_game` is called from
`coach_session_service.py`'s `analyze_priority_game()`, which fires from
`end_play_session()`, reachable only via `POST /coach/end-session`
(`routes/coach_advanced.py:621`). **Zero frontend callers of that route** —
confirmed via grep across `frontend/src`. Same "real bug, no live impact"
pattern as the ~25-bug dead-code cluster found earlier this session. Not
part of the consolidation — safe to ignore or delete separately.

### Writer 2 — `analysis_worker.py:585-715` (`update_player_profile_sync`) — LIVE

Fires on every newly analyzed game (`analysis_worker.py:1669`). Writes:
- `games_analyzed_count`, `total_blunders`, `total_mistakes`, `total_best_moves`
  — **pure incremental accumulators, only ever add**, no reset/rebuild path.
- `top_weaknesses` — derived from `cognitive_gap` via `cognitive_gap_to_weakness()`
  (line 617), same additive-only pattern. **Same staleness disease as the
  three collections already fixed today** — today's cognitive_gap backfill
  did not touch this field, and there's no rebuild script for it.
- `recent_performance` / `historical_performance` (last-10 / last-20 rolling windows).
- `motif_profile` merge (separately already has a mitigation script,
  `scripts/backfill_motif_profile_and_anticipation.py` — not this scope's problem).

### Writer 3 — `services/data_freshness.py:512-596` (`refresh_player_profile`) — LIVE

Fires immediately after Writer 2, same per-game flow
(`refresh_all_user_data()` at `analysis_worker.py:1971-1972`, plus the
manual `POST /api/data/refresh` route). Recomputes from only the **last 20**
analyzed games (a real aggregation, not additive) and writes a
**different set of field names**: `games_analyzed` (not `games_analyzed_count`),
`average_accuracy`, `errors_per_game`, `biggest_weakness`, `mistake_breakdown`,
and — critically — **also** `total_blunders` / `total_mistakes`, using
`$set` (not a full document replace).

### The concrete damage, verified on a real profile doc

```
games_analyzed_count: 648      <- Writer 2's cumulative count (itself possibly
games_analyzed: 20              <- Writer 3's last-20 count     over-counted —
                                     same duplicate-increment bug found today
                                     in coach_memory; not separately verified here)
biggest_weakness: "other"       <- ALWAYS "other", for every user
mistake_breakdown: {"other": 77}<- ALWAYS all-"other", for every user
```

`biggest_weakness`/`mistake_breakdown` are broken at the root: Writer 3
reads `move_eval.get("category", "other")` (`data_freshness.py:562`) —
**`category` does not exist on any real move_evaluations document**
(confirmed: 0/24 keys on a live sample; the real field is `cognitive_gap`).
Every mistake falls into the `"other"` bucket, so `biggest_weakness` is
always the string `"other"`. This is the same phantom-field bug pattern
fixed 14 times earlier this session — a 15th instance, in a function this
session's earlier sweep hadn't reached yet.

**However — zero blast radius.** Grepped both `backend/routes/*.py` and
`frontend/src` for `biggest_weakness` / `mistake_breakdown`: nothing reads
either field, anywhere. Writer 3's docstring claims it "powers: Biggest
weakness card, Progress stats, Blind spots" — that claim is stale; no such
consumer currently exists. Low priority to fix on its own merits (though
trivial — swap `category` for `cognitive_gap`), since fixing it changes
nothing a user sees today.

**Because Writer 3 always runs after Writer 2 in the same request**, every
single time a game is analyzed, `total_blunders`/`total_mistakes` end up
holding Writer 3's last-20-games sum, not Writer 2's cumulative count —
Writer 2's computation of those two specific fields is silently discarded
on every run. The field names ("total_") imply career-cumulative; the
stored value is actually a 20-game rolling window. Whether anything reads
`total_blunders`/`total_mistakes` from `player_profiles` live was not
exhaustively checked in this pass — flagged as the first thing to verify
before picking a consolidation direction.

## The actual decision Mohit needs to make

This isn't a bug with one obvious fix — it's two writers that were each
reasonable in isolation, built at different times, that never got
reconciled into one schema. Three real options:

**A. One writer, one schema.** Retire Writer 3 (`refresh_player_profile`)
entirely, keep Writer 2 as the single source, and give `top_weaknesses` a
proper decay/backfill mechanism (essentially importing the recency-weighted
approach `pattern_decay_service.py` / `user_pattern_decay` already has,
rather than Writer 2's flat "occurrence_count += 1 forever"). Lowest
long-term maintenance cost, but means auditing every reader of
`games_analyzed` / `average_accuracy` / `errors_per_game` (Writer 3's
unique fields) to make sure nothing breaks when they disappear.

**B. Merge into one call, one schema, keep both computations' intent.**
Have a single function compute both the cumulative view (career totals)
and the recent-window view (last-20 snapshot) under clearly distinct field
names (e.g. `career_total_blunders` vs `recent_20_avg_blunders`), so both
survive without colliding. More code, but no information is thrown away
and no product decision about "which number matters" has to be made
up front.

**C. Question whether `player_profiles` should exist at all** given
`user_pattern_decay` (recency-weighted, already correct, already backfilled
today) and `coach_memory.performance`/`.weaknesses` (also already rebuilt
today) cover overlapping ground. If nothing reads `player_profiles`
fields that aren't ALSO available more correctly from those two, the
right move might be to stop writing to it and point remaining readers
elsewhere — deletion, not consolidation.

## What this scope explicitly does NOT decide

- Whether `total_blunders`/`total_mistakes` should mean "career" or
  "recent" — that's Mohit's call, not an engineering default.
- Whether `player_profiles` survives at all (option C).
- Any code change to either writer. Nothing in this document has been
  implemented.

## Next step

~~Mohit picks A / B / C (or a fourth option), then this scope doc gets a
follow-up implementation section and only then does code change.~~

Resolved — see Status line at top. No further action needed unless a new
writer is introduced.
