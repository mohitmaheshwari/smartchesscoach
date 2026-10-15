# Import idempotency — scope

Status: SCOPE for sign-off. No code written. Measured 2026-10-15 against live
production (20,367 games). Follows
[integrity_investigation_2026_10_15.md](integrity_investigation_2026_10_15.md),
which confirmed the defect.

**Deletion and production migration are gated separately** (§7). This scope
covers making imports idempotent and reconciling identity. It does not delete
anything.

---

## 1. The defect, confirmed

`journey_service.py:1053` is a check-then-insert:

```python
existing = await db.games.find_one({"$or": [
    {"url": game_url, "user_id": user_id},
    {"pgn": pgn,      "user_id": user_id}]})
if existing: continue
await db.games.insert_one({**game_doc, "game_id": str(uuid.uuid4())})
```

Two concurrent fetches inside one sync run both pass the check, then both
insert with fresh UUIDs. Confirmed by three pairs sharing a lichess URL, a
move-sequence hash, and an `imported_at` **to the same second**, differing only
in PGN length (one carries `[%clk` annotations, the other does not).

Nothing in the database prevents it. `games` has **no unique index** —
`game_id_1` is not unique; only `coach_session_id_unique` is.

**Current scale, product-wide:** grouping on `(user_id, url)` where a url
exists, **1,245 keys hold more than one record, 1,397 extra records, and the
worst key holds 5 copies.** A unique index cannot simply be added; those 1,245
keys would violate it.

---

## 2. Canonical identity

### 2.1 The identity is the platform game ID, not the URL string

Parsing the URL rather than comparing it protects against variants. All
20,367 records resolve into three shapes with no unmatched remainder:

| Prefix | ID length | Records |
|---|---|---|
| `https://www.chess.com/game/live/` | 12 digits | 18,673 |
| `https://www.chess.com/game/daily/` | 8–10 digits | 266 |
| `https://lichess.org/` | 8 chars | 680 |

So the canonical identity is:

```
game_identity = (user_id, platform, game_kind, platform_game_id)
```

`game_kind` is load-bearing: chess.com **live** and **daily** IDs are both
plain integers and could collide, so the kind must be part of the key, not
discarded.

Normalisation rules, each one guarding a variant that would otherwise split an
identity:

- scheme and host case-folded; `http`/`https` and `www.`/bare treated alike
- trailing slash and any query string or fragment stripped
- lichess: the base 8-character game id only. Lichess also serves
  `lichess.org/<8-char>/white` and 12-character player-specific ids, so a
  longer id is truncated to its 8-character base
- chess.com: the numeric id plus its kind (`live` / `daily`)
- the identity is **derived and stored in a new field**, never by overwriting
  `game_id` — 28 collections reference `game_id` (§5) and it must not move

### 2.2 Missing platform IDs

**746 records (4%) have no url.** They split cleanly:

| Platform | Records | With url | Fallback |
|---|---|---|---|
| lichess | 680 | 680 (100%) | not needed |
| chess.com | 19,416 | 18,939 (98%) | content identity |
| coach | 271 | **0 (0%)** | `coach_session_id` |

- **Coach games have no platform at all**, correctly. They already carry
  `coach_session_id`, which is the one uniquely-indexed field in the
  collection. That is their identity; no new work.
- **The ~477 chess.com records with no url** fall back to a *content*
  identity: `(user_id, platform, sha1(normalised SAN sequence), played_at_utc
  truncated to the minute)`. Measured: a sample of 748 no-url records produced
  747 hashable PGNs, 719 keys and **28 extras (3.7%)** — so these duplicate
  too and the fallback is needed, not theoretical.
- **7 of 1,500 sampled PGNs produce no move hash at all** ("no moves in
  mainline"). Those get no content identity and must be left alone rather than
  collapsed — an un-identifiable record is not a duplicate.

### 2.3 What is explicitly not an identity

Not the PGN string (differs between copies of the same game — that is the
defect). Not `(platform, minute, result, colour)` — that nominates candidates
only, as the investigation established. Not `game_id` (a fresh UUID per
import).

---

## 3. Concurrent imports

Two changes, and the second is useless without the first.

**3.1 Database-enforced uniqueness.** A **partial unique index** on
`(user_id, game_identity)` where `game_identity` exists. Partial so that the
7-ish unidentifiable records and anything mid-backfill do not block writes.
This is what makes the race impossible rather than merely narrower.

**3.2 Replace check-then-insert with a conflict-tolerant write.** Either
`update_one(identity_filter, {"$setOnInsert": doc}, upsert=True)` or
`insert_one` wrapped to catch `DuplicateKeyError`. On conflict the importer
**must not silently `continue`** as it does today — it hands the incoming
record to the merge in §4, because the loser may be the copy carrying the
clock.

**3.3 Ordering constraint.** The index cannot be created while 1,245 keys
violate it. Sequence: derive and store `game_identity` on every record →
report conflicts → reconcile (§5, gated) → *then* create the index. Attempting
the index first fails, and attempting it with `unique` after a partial
reconciliation fails too.

---

## 4. Preserving the richer copy

This is the requirement that makes the work worth doing beyond tidiness. For
this player the clock survives on **10% of his moves** against ~82%
product-wide, and the duplicates are exactly where the clock lives: of three
confirmed pairs, PGN lengths were 735/2046, 1793/683 and 564/1234 — one copy of
each has clock annotations.

**Selection rule, in order:**

1. Prefer the PGN containing `[%clk` (or `[%emt`).
2. If both or neither do, prefer the one whose move count is complete and
   larger.
3. If still tied, prefer the longer PGN.
4. Tie-break on earliest `imported_at`, for determinism.

**Nothing is discarded.** The non-winning PGN is retained on the surviving
record (a `pgn_variants` list with its `game_id`, length and `imported_at`), so
the merge is reversible and auditable without the snapshot. A merge that loses
the clock copy is the one outcome this scope exists to prevent, so it is an
acceptance test (§6), not a comment.

**Field-level merge:** for every other field, prefer a non-null value over a
null one, and on a genuine disagreement keep the surviving record's value and
record the conflict in the corrections ledger rather than guessing.

---

## 5. Historical reconciliation

**De-duplicating only `games` leaves every derived statistic duplicated.** The
investigation measured 13 duplicate game_ids carrying 13 `game_analyses`, 332
`move_observations` and 13 `analysis_queue` rows.

Every collection that references a game, with current volume:

| Collection | Field | Rows |
|---|---|---|
| `move_observations` | `game_id` | 632,657 |
| `user_pattern_events` | `game_id` | 145,898 |
| `community_training_positions` | `source_game_id` | 53,982 |
| `community_puzzles` | `source_game_id` | 52,256 |
| `user_teaching_memory` | `game_id` | 29,974 |
| `thinking_scores` | `game_id` | 19,574 |
| `game_analyses` | `game_id` | 19,641 |
| `detector_claims` | `game_id`, `game` | 19,355 |
| `onboarding_puzzles` | `source_game_id` | 11,812 |
| `coaching_summaries` | `game_id` | 8,836 |
| `endgame_move_verdicts` | `game_id` | 4,800 |
| `move_enrichment` | `game_id` | 3,138 |
| `user_concept_understanding` | `last_evaluated_game_id` | 1,821 |
| `gold_captions`, `gold_deep_pv`, `gold_tester_captions` | `game_id` | 906 / 425 / 194 |
| `move_feedback` | `game_id` | 651 |
| `positional_reason_queue`, `_generated_candidates` | `game_id` | 240 / 238 |
| `module_injections` | `game_id` | 116 |
| `geometry_gap_rulings`, `pattern_feedback`, `reflection_sessions`, `user_thoughts`, `player_accepted_causes`, `game_review_prescriptions` | `game_id` | 23 / 26 / 9 / 6 / 2 / 3 |
| `analysis_queue` | `game_id` | — |

**Approach: one surviving `game_id` per identity, the others kept as aliases.**
A `game_id_aliases` record maps every superseded id to its survivor. Then:

- **Repoint, do not delete.** Downstream rows are `$set` to the surviving
  `game_id`. Where that creates a true duplicate row (two identical
  `move_observations` for the same move), the surplus is marked superseded, not
  removed — removal is §7.
- **Human-authored content is repointed, never collapsed.** `gold_captions`,
  `gold_tester_captions`, `geometry_gap_rulings`, `player_accepted_causes`,
  `user_thoughts` and `pattern_feedback` carry human judgements. Losing one is
  worse than carrying a duplicate.
- **Derived content can be regenerated instead of repointed** where that is
  cheaper and safer: `coaching_summaries`, `move_enrichment`,
  `detector_claims`.
- **`community_puzzles` / `community_training_positions` / `onboarding_puzzles`
  need care**: 118,050 rows carry `source_game_id`, and de-duplicating the
  source may expose duplicate *puzzles* in shared pools other users draw from.
  That is a second-order effect and needs its own check before anything moves.

**Prior art to read first:** `games_backup_dupcoach_20260824_043147` and
`game_analyses_backup_dupcoach_20260824_043147` (10 records each) show a
coach-game de-duplication was already run on 2026-08-24. Whoever writes this
should read that script and its backups before designing a second approach.

---

## 6. Acceptance tests

| # | Test | Pass condition |
|---|---|---|
| 1 | URL normalisation | all three variants plus case, scheme, `www.`, trailing-slash, query-string and lichess `/white` suffix forms resolve to the same identity; `live/123` and `daily/123` resolve to **different** identities |
| 2 | Identity coverage | every record gets an identity or is explicitly marked unidentifiable; the count of unidentifiable records is reported, not silently zero |
| 3 | **The clock copy survives** | for all 1,397 conflicts, the surviving record's PGN contains `[%clk` whenever *any* copy of that identity did. Zero regressions permitted |
| 4 | Nothing lost | every non-winning PGN is retrievable from `pgn_variants`; byte-compare against a pre-merge snapshot |
| 5 | Concurrency | 20 parallel imports of the same game produce exactly one record, with the index in place |
| 6 | Importer conflict path | a conflicting import triggers the merge, not a silent `continue`; asserted by a test that feeds the clock-bearing copy second |
| 7 | Downstream integrity | after repointing, no row references a superseded `game_id` except through `game_id_aliases`; counted per collection from the §5 table |
| 8 | Statistics move in the right direction only | the recomputed profile for the 7-plus affected users changes only by the removal of duplicate weight; spot-checked against §B of the integrity report |
| 9 | Clock coverage improves | this player's clock coverage is measured before and after. It is 10% today, and if the merge is working it should rise |
| 10 | Idempotent re-run | running the whole reconciliation twice changes nothing on the second pass |
| 11 | No artificial learning events | counts in `user_concept_understanding`, `puzzle_attempts`, `learning_sessions`, `user_active_focus`, `focus_history` identical before and after |
| 12 | Regression | `test_all_flows.py` green against a pre-change baseline |

---

## 7. Gates

Three phases, each separately gated, in order:

1. **Identity derivation (read-mostly).** Derive and store `game_identity`,
   report every conflict. Adds a field, changes no existing value, deletes
   nothing. Reversible by unsetting one field.
2. **Importer fix + index (forward-looking).** The conflict-tolerant write and
   the partial unique index. Stops new duplicates. Requires phase 1 complete
   and conflicts resolved, or the index creation fails.
3. **Historical reconciliation (gated separately, as instructed).** Merge,
   repoint, alias. Snapshot-and-verify first, per the procedure already proven
   on production (dump → restore to a throwaway namespace → byte-compare →
   drop). **No deletion in this phase either**; superseded rows are marked, not
   removed. Deletion, if ever, is a fourth phase with its own sign-off.

A read-path de-duplication is worth considering as an interim measure, since
every affected profile is inflated today and a read-time collapse is instantly
reversible — but it is a separate decision and not part of this scope.

---

## 8. Open questions

1. **Read-path de-duplication now, or wait for phase 3?** Seven-plus users'
   statistics are wrong today.
2. **`community_puzzles` and the shared pools** — de-duplicating
   `source_game_id` may surface duplicate puzzles that other users are served.
   Should phase 3 include the pools, or stop at per-user records?
3. **The ~477 chess.com records with no url** — backfill a url from the PGN
   where possible, or leave them on the content identity permanently?
4. **Does `game_id` itself want a unique index?** It is not unique today, which
   is a separate latent defect and may deserve its own small scope.
