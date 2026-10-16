# Integrity investigation — read-only

Run 2026-10-15 against live production. **Nothing written, nothing deleted, no
flag changed.** Three questions, as commissioned: confirmed duplicate games and
their import path; which writers produced the artifact concept records and
whether they still do; and the profile recomputed over distinct games with
artifact records excluded by provenance.

Verdict up front: **the duplicates are real and confirmed by platform ID, the
artifact counters are not an active loop, and recorded mastery is a weaker
signal than I presented — weaker, in fact, than your correction assumed.**

---

## 1. Duplicate games — confirmed, with a root cause

### 1.1 Identity confirmed, not inferred

The candidate key `(platform, minute, result, colour)` only nominates. Identity
was confirmed independently: **all 12 candidate groups in his window share an
identical platform game ID** (`games.url`, e.g.
`https://lichess.org/caUavCYZ`), and in every case the normalised move-sequence
hash and move count match too.

| Verdict | Groups |
|---|---|
| CONFIRMED (identical url) | **12** |
| CONFIRMED (same moves + players) | 0 |
| DIFFERENT GAMES (moves differ) | 0 |
| UNDECIDABLE (unparseable PGN) | 0 |

**13 extra records across 12 groups → the window holds 87 distinct games, not
100.** Your caution about the provisional key was right to insist on, and the
key survived it.

### 1.2 The root cause is a race, not a PGN mismatch

I first blamed exact-PGN comparison. The evidence says otherwise. Three
confirmed pairs:

| url | PGN chars | `imported_at` |
|---|---|---|
| `lichess.org/vy4pU6Z2` | 735 / 2046 | both `2026-10-05T13:42:53` |
| `lichess.org/s7FWwI5c` | 1793 / 683 | both `2026-10-05T13:25:43` |
| `lichess.org/caUavCYZ` | 564 / 1234 | both `2026-10-05T13:14:18` |

Both copies carry `auto_synced: True`, both carry the url, and both were
imported **in the same second**. The guard at `journey_service.py:1053` is a
check-then-insert:

```python
existing = await db.games.find_one({"$or": [
    {"url": game_url, "user_id": user_id},
    {"pgn": pgn,      "user_id": user_id}]})
if existing: continue
...
await db.games.insert_one(game_doc)   # game_id = str(uuid.uuid4())
```

The `url` clause *should* catch a re-import. It does not here because both
inserts happen before either can see the other — and **nothing in the database
prevents it.** Index inventory on `games`:

| Index | Unique |
|---|---|
| `user_id_1`, `user_id_1_platform_1`, `user_id_1_is_analyzed_1` | no |
| `game_id_1` | **no** — not even the primary key is unique |
| `coach_session_id_unique` | yes |

So the differing PGN lengths are a symptom of two concurrent fetches
(one with clock annotations, one without), not the cause of the duplication.
The cause is a check-then-insert with no uniqueness constraint.

### 1.3 It propagates to every derived record

Each duplicate was analysed independently:

| For the 13 duplicate `game_id`s | Count |
|---|---|
| `game_analyses` | 13 |
| `move_observations` | **332** |
| `analysis_queue` rows | 13 |

So duplication reaches every derived statistic, which is exactly why §3
recomputes rather than assumes.

### 1.4 Scope beyond this player

A 1,500-game sample, confirmed by `(user_id, move-hash)`. **Corrected: the
original table invited 1,500 − 1,416 = 84 and that conflates two different
things.** Full accounting:

| | |
|---|---|
| records sampled | 1,500 |
| PGNs that produced a move hash | 1,493 |
| PGNs that did not ("no moves in mainline") | **7** |
| distinct `(user_id, move-hash)` keys | 1,416 |
| extra records beyond one per key | **77** |

Both identities reconcile: 1,493 = 1,416 + 77, and 1,500 = 1,493 + 7. So the
duplicate rate is **77 of 1,493 hashable records (5.2%)**, and the 7 remaining
records never entered the keyspace at all — they are unidentifiable, not
duplicates. 84 was never a count of anything. **7 users affected.**

A better product-wide figure came from the identity survey for the
idempotency scope: grouping on `(user_id, url)` where a url exists,
**1,245 keys hold more than one record, 1,397 extra records, worst key holds
5.** That is 6.9% of 20,367 games, and it supersedes the sample estimate.

---

## 2. The artifact concept records — writers traced

### 2.1 You were right: no active loop

Three distinct writers, and none of them is a runaway:

| Field | Writer | Nature |
|---|---|---|
| `shown_count` | `game_decryption_v5_service.py:4929`, `$inc` by 1 | **per render** — so a caption regen over hundreds of games increments it hundreds of times |
| `mastered_at` | a 2026-06-04 one-shot backfill, which stamped 749 of 763 | historical bulk write |
| `mastery_stripped_at` / `_reason` | `backend/scripts/cleanup_artifact_mastery.py` | one-off script, not live |

`concept_mastery_tracker.py` already documents the counter in its own header —
"99.7% with `acknowledged=False`, `shown_count` climbing without bound" — so
10,593 is historical replay, as you suspected, not a loop.

Rows **are** still being touched (`updated_at`: 25 on 2026-10-14, 20 on
2026-10-13, 4 on 2026-10-15), which is consistent with the per-render `$inc`
and not with anything pathological.

### 2.2 The stripping, and what it actually means

All 42 of his stripped rows carry `mastery_stripped_at` on **2026-06-06** — a
single cleanup run, two days after the backfill. The cleanup's own scope says
the 2026-06-04 backfill "stamped `mastered_at` against the streak math at
backfill time — permissive for users with long game histories… many on concepts
the user hadn't genuinely mastered", and that its thresholds are "gut numbers
(NOT data-locked)".

So the sequence is: a bulk backfill stamped mastery too freely, a cleanup
removed the stamps that failed a stricter but admittedly un-calibrated rule.
**Neither "forgot" nor "never mastered" is the right word. The stamp was never
trustworthy.**

Product-wide `mastered_at` by day confirms the bulk pattern: 2026-06-04 → 201,
2026-06-06 → 145, 2026-07-14 → 94, 2026-08-28 → 39.

For him, 10 of the 33 surviving stamps are dated 2026-06-04 — i.e. backfill
stamps that passed the gut-number rule — and the other 23 are spread across
June to September and look organic.

### 2.3 The finding that goes further than your correction

You cautioned that 5 of 43 endgame masteries cannot establish his weakest
skill, "especially with some concepts never shown." It is worse than that.
Splitting his 76 clean (non-artifact) rows by whether the product ever showed
him the concept:

| | Rows | Mastered |
|---|---|---|
| **shown at least once** | 40 — endgame 38, tactical 2 | **0** |
| **never shown** (`shown_count: 0`) | 36 | **33** |

**Every surviving mastery stamp sits on a concept the product never showed
him.** The 5 "mastered" endgame rows are 5 of the never-shown rows; of the 38
endgame concepts he was actually shown, **none** is marked mastered.

That inverts the signal. `mastered_at` is derived from game-play streak math,
not from any teaching event, so it cannot be read as "we taught this and it
landed" — and the endgame reading in the profile (§7, "the taught endgame
material has not stuck") **is withdrawn: the material was largely never
delivered.** `missed_pattern: endgame_technique` (38 occurrences) remains valid
on its own terms; the mastery column should not be used as evidence about
teaching at all.

---

## 3. The profile recomputed over distinct games

One function, one pass, de-duplicated by confirmed identity. **You were right
that duplicates reweight rates, not only counts** — and the shifts are small
but real, and in one case directionally interesting.

| | With duplicates | Distinct only |
|---|---|---|
| games | 100 | **87** |
| his moves | 3,021 | **2,689** |
| won | 49/100 (49%) | 43/87 (49%) |
| lost | 51/100 (51%) | 44/87 (51%) |
| mate in 1 taken | 21/30 (70%) | **19/28 (68%)** |
| free 3+ piece taken | 179/213 (84%) | **164/195 (84%)** |
| reached +3 and won | 46/78 (59%) | **40/67 (60%)** |
| capture preference | 4.22× | 4.19× |
| check preference | 2.87× | 2.87× |
| punished opponent errors | 113/176 (64%) | **101/160 (63%)** |
| answered a threat | 158/276 (57%) | **147/249 (59%)** |

Accuracy by phase:

| Phase | With duplicates | Distinct only |
|---|---|---|
| opening | 997 mv, 41.3cp, 5% | 869 mv, **42.3cp**, 5% |
| middlegame | 1,433 mv, 112.5cp, 13% | 1,285 mv, **116.2cp, 14%** |
| endgame | 591 mv, 51.6cp, 8% | 535 mv, **50.6cp**, 7% |

Nothing reverses, but note threat response moves from 57% to **59%** — the
duplicated games were slightly worse than his average on that measure, so the
duplicates were making his most-corroborated weakness look marginally worse
than it is. That is precisely the reweighting you flagged.

**Corrected: that column is 87 distinct games out of 100 records, not the
last 100 distinct games.** Walking further back (113 records, 13 duplicates
dropped) gives a true 100-distinct-game window, 2026-09-01 to 2026-10-15, and
these are the canonical figures:

| | 100 distinct games |
|---|---|
| his moves | **2,996** |
| won / lost / drew | 48 / 52 / 0 |
| mate in 1 taken | **22 of 31 (71%)** |
| free 3+ piece taken | **182 of 215 (85%)** — 33 of those in check |
| reached +3 and won | **45 of 76 (59%)** |
| capture preference | **4.14×** |
| check preference | **2.84×** |
| punished opponent errors | **108 of 171 (63%)** |
| answered a threat | **162 of 268 (60%)** |

| Phase | Moves | Mean cp lost | Blunder rate |
|---|---|---|---|
| opening | 996 | 41.9 | 5% |
| **middlegame** | 1,448 | **121.8** | 13% |
| endgame | 552 | 67.2 | 7% |

Two readings move materially against the 87-game column: the middlegame is
worse (121.8cp against 116.2) and the endgame is worse (67.2cp against 50.6),
because the extra 13 games reach back to 2026-09-01. Threat response settles
at **60%**.

**These are the canonical numbers for this player.** Every earlier figure
(2,986 moves / mate 20 of 29 / free 179 of 211, and the 87-game column above)
is superseded.

### 3.1 The 211 / 213 reconciliation

Resolved. One pass, one definition:

| | |
|---|---|
| free 3+ opportunities (with duplicates) | **213** |
| of which he was in check | 33 |
| of which not in check | 180 |
| sum | 213 ✓ |
| free 3+ opportunities (distinct only) | **195** |

The earlier 211 came from a different pass with a different guard; 180 + 33 =
213 was right and 211 was the wrong number. My error was reporting totals from
two runs as if they were one.

---

## 4. What I recommend, given no cleanup is authorised

Stated as recommendations only; nothing here has been done.

1. **A unique index on `(user_id, url)` for games with a url** is the fix that
   makes the race impossible, rather than narrowing the window. It needs the
   existing duplicates resolved first, so it is sequenced after, not before.
   Note `game_id_1` is not unique either, which is worth a separate look.
2. **Do not delete duplicates yet.** They have `game_analyses`,
   `move_observations` and `analysis_queue` rows attached; removing a game
   without those is how orphans are made. A de-dup needs its own scoped plan
   with the same snapshot-and-verify discipline as the other migrations.
3. **De-duplicate in the read path meanwhile.** Every count in every profile is
   currently inflated for the 7-plus affected users. A `(user_id, url)`
   collapse at read time is reversible and changes no stored data.
4. **Stop reading `mastered_at` as evidence about teaching**, on the strength of
   §2.3. It describes game-play streaks on concepts that were never shown.
5. **Treat `shown_count` as a render counter, not an exposure count.** It
   increments on regens, so it cannot answer "how often has this player seen
   this".

---

## 5. The assessment, with your two changes

Both adopted.

**The prompt is now a two-part question**, so the first step tests detection
rather than assuming a threat exists: **"Is there a threat that needs a
response? If so, what?"** Then, as before: what do you play, and what do you
expect after that. The no-threat control positions are now load-bearing rather
than decorative — they are the only way to tell detection from assent.

**Outcomes are described as performance on that trial**, not as a diagnosis.
The previous table said "points at the clock" for an all-correct result; that
was wrong, and it is replaced:

| Step 1 | Step 2 | Step 3 | What the trial showed |
|---|---|---|---|
| wrong | — | — | on this trial he did not identify the threat |
| right | wrong | — | identified it, did not find a response on this trial |
| right | right | wrong | responded without predicting the continuation on this trial |
| right | right | right | performed the whole task correctly on this trial, untimed |

All four are statements about the trial. **Getting everything right untimed
does not isolate the clock as a cause** — it says he can do the task under
those conditions, and nothing more. Any clock claim stays out of reach while
his clock survives on 10% of his moves.

---

## 6. Standing position

The nine-area profile remains **provisional**, now with its canonical numbers
recomputed over 87 distinct games (§3) and its recorded-mastery column struck
as evidence about teaching (§2.3). Data integrity is the priority. No deletion,
no production cleanup, no new scoring system, and no further profile
conclusions until the duplicates are resolved.

---

## 7. Follow-on scope

The import fix is scoped separately in
[import_idempotency_scope.md](import_idempotency_scope.md), covering canonical
identity (including missing IDs and URL variants), database-enforced
uniqueness and conflict handling, preservation of the clock-bearing copy, and
reconciliation across the 28 collections that reference a game — with
historical deletion and production migration gated separately.
