# WS1a rollout plan — `played_at_utc` backfill + shadow outcome loop

**Status: awaiting approval. Nothing here has been applied.**
Production has been read-only throughout: no write, index, dedup, scheduler
change or deploy.

---

## 1. What this changes, and why it is not cosmetic

The focus outcome window splits a user's games with a **string** comparison on
`date_played`. That field holds three shapes, and ASCII `.` (0x2E) sorts above
`-` (0x2D), so every chess.com `2026.04.15` compares as later than any ISO
timestamp regardless of the date it names.

Measured on production, comparing the current window against the window a
canonical timestamp produces:

| | |
|---|---|
| Active weakness focuses | 45 |
| Focuses whose "after" window changes | **15** |
| Game memberships corrected | **409** |
| **Focuses that cross the `MIN_GAMES_FOR_OUTCOME` (3) threshold** | **8** |

The last row is the one that matters. Eight users currently *look* like they
have 18–31 games since their focus began. They actually have **0 or 1**:

| user | after-window today | after-window once fixed | wrongly counted |
|---|---|---|---|
| `user_ce4f53ccb…` | 20 | **0** | 20 |
| `user_58dc26172…` | 30 | **0** | 30 |
| `user_9659e4516…` | 30 | **0** | 30 |
| `user_63fe50a05…` | 28 | **0** | 28 |
| `user_82fa02e58…` | 27 | **0** | 27 |
| `user_4a671526e…` | 18 | **0** | 18 |
| `user_186ab42ab…` | 31 | **1** | 30 |
| `user_666b2f164…` | 24 | **1** | 23 |

Turn rendering on today and those eight receive a confident
improved/regressed/stuck verdict computed entirely from games they played
*before* the coaching started. After the backfill they correctly become
`no_data` — "we have not seen enough of your games yet."

**So the backfill is not a tidy-up ahead of the real work. It is the
difference between the loop's first-ever user-visible statement being true or
being fabricated.**

## 2. What gets written

Three new fields on `games`. Nothing existing is modified.

| Field | Type | Meaning |
|---|---|---|
| `played_at_utc` | BSON Date | the canonical instant; the only field measurement reads |
| `played_at_source` | string | `pgn_utc_headers` · `pgn_local_headers` · `stored_iso_fallback` · `coach_imported_at` |
| `played_at_raw` | as stored | verbatim copy of `date_played` |

`date_played` is untouched, so **rollback is `$unset` of three fields** and
every existing reader keeps working.

Dry run over all 16,224 games:

```
  15957  pgn_utc_headers     (incl. 100% of the 477 dotted rows)
    267  coach_imported_at
would write : 16224
unrecoverable : 0
stored value disagrees with PGN by >1d : 0
plan fingerprint: ea0de5ffc910f857
```

Zero disagreements means the ISO rows were already correct — dotted ordering
really was the only defect.

## 3. Code that ships with it

| File | Change |
|---|---|
| `backend/scripts/backfill_played_at_utc.py` | new. Dry-run default, `--apply --confirm-plan`, `--rollback`, batched bulk writes, idempotent. |
| `backend/services/primary_weakness_picker.py` | window splits on `played_at_utc`; transitional legacy branch keeps un-migrated rows in the window and logs a warning naming the fix. |
| `backend/server.py` | `focus_outcome_render_enabled()` (default **off**); shadow mode measures every active weakness focus and records to `focus_outcome_shadow`; `_lock_is_due` normalises naive BSON dates. |
| `backend/analysis_worker.py` | `engine_version` becomes a shared constant. |
| tests | `test_played_at_utc_backfill.py` (20), `test_focus_outcome_shadow_mode.py` (19), 3 added ordering cases in `test_focus_outcome_is_measured_fairly.py`. |

**Deploy order matters and is safe in both directions.** The reader ships with
a legacy fallback, so deploying before the backfill does not drop un-migrated
rows out of the window — it splits them the old way and logs. Verified by
A/B against production:

| | no_data | pending | regressed | improved | stuck |
|---|---|---|---|---|---|
| pristine `origin/working-code` | 19 | 11 | 7 | 3 | 5 |
| with these changes, pre-backfill | 19 | 11 | **8** | 3 | **4** |

Identical window sizes; one focus moves `stuck → regressed`, which is the
dotted-date correction reaching a verdict.

## 4. Why the loop runs before anyone sees it

`FOCUS_OUTCOME_RENDER_ENABLED` defaults off. In that mode the loop measures
every active weakness focus each pass and writes what it *would* have said to
`focus_outcome_shadow`; `close_focus` is never called and no focus document
changes.

Two reasons:

1. **There is no history to choose a terminal-state rule from.** No focus has
   ever completed a cycle. The open question — how many extensions, or how
   many days, before a user is told "we could not gather enough comparable
   games" — should come from the distribution of daily verdicts, not a guess.
2. **The modal honest verdict today is not one to lead with.** Of the 45
   active focuses: 19 `no_data`, 11 `measurement_pending`, 8 `regressed`, 4
   `stuck`, 3 `improved`. Before the diagnosis itself is personal (41 of 41
   users currently receive the identical sentence), "you got worse" is a
   churn message, not a proof message.

Shadow mode deliberately ignores `locked_until`. The due-only selector would
have recorded **0 rows** on today's pass — every active lock is still in the
future, the nearest two days out.

## 5. Ordered rollout

Each step names its own rollback.

| # | Step | Verify | Rollback |
|---|---|---|---|
| 1 | `mongodump` the `games` and `user_active_focus` collections | dump size non-zero, restore tested into a scratch DB | — |
| 2 | Deploy code (render flag **absent**, i.e. off) | `/api/health` returns the new commit + `v5_caption_version` | redeploy previous image |
| 3 | Re-run the dry run on the deployed box | fingerprint still `ea0de5ffc910f857` | — |
| 4 | `--apply --confirm-plan ea0de5ffc910f857` | script reports `games still without played_at_utc: 0` | `--rollback --apply` |
| 5 | Re-run the A/B verdict count | 8 focuses move to `no_data`; totals match §1 | `--rollback --apply` |
| 6 | Confirm the loop is shadowing | log line `SHADOW measured N focuses`; `focus_outcome_shadow` gains ~53 rows/day; **no** `user_active_focus` doc has a new `current_metric` | unset nothing — shadow writes are additive; drop the collection |
| 7 | Watch for 14 days | daily verdict distribution stabilises; use it to set the terminal-state rule | — |
| 8 | *(separate approval)* enable rendering | — | unset `FOCUS_OUTCOME_RENDER_ENABLED` |

The fingerprint covers the plan's **shape** — which provenance categories
exist, whether anything is unrecoverable, whether any stored value disagrees
with its PGN — not row counts, which drift every time a game imports. Normal
drift will not invalidate an approved plan; a material change will.

## 6. Risks

| Risk | Severity | Handling |
|---|---|---|
| Backfill writes a wrong instant | High | 0 disagreements across 16,224 games; both date and clock must parse or the row is not claimed as exact (a malformed `[Utctime]` previously became midnight while still tagged exact — caught by test, fixed). |
| Deploying the reader before the backfill | Medium | Legacy fallback keeps un-migrated rows in the window and logs. A/B shows parity. |
| Shadow rows accumulate unbounded | Low | One upserted row per focus per day; ~53/day. |
| Coach games bias the pooled rate | **Accepted by decision** | Measured ~7× lower miss rate (2.12% vs 14.00%). Recorded in the baseline §3.7 and on `OUTCOME_ELIGIBLE_SOURCES`. `played_at_source` keeps the mix queryable. |
| 8 users lose an apparent verdict | Intended | They never had one. They had a verdict computed from pre-focus games. |

## 7. What this does not do

Does not dedup the 557 duplicate games, add indexes, change the scheduler's
cadence, send any email, or render anything to a user. Those are separate
approvals.

---

# EXECUTED — 2026-09-17

Steps 1–6 ran against production with approval. Step 8 (enable rendering)
remains **not done** and needs separate approval.

## Results per step

| # | Step | Result |
|---|---|---|
| 1 | Backup + restore proof | `games` 16,250 docs and `user_active_focus` 275 docs dumped to `/root/ws1a_evidence/` (15 MB + 49 KB, gzipped). Restored into `ws1a_restoretest` and reconciled: **16,250 = 16,250**, **275 = 275**. Scratch DB dropped afterwards. |
| 2 | Deploy, render flag off | Live at `a3b20180`. `/api/health` confirms `git_commit`, `v5_caption_version: 166`, and **`FOCUS_OUTCOME_RENDER_ENABLED` absent from the flag list**. |
| 3 | Dry run on the deployed box | 16,251 games, 0 unrecoverable, 0 disagreements, fingerprint **`ea0de5ffc910f857`** — the approved value, unchanged despite row counts moving from 16,224. The shape-based fingerprint did its job. |
| 4 | Apply | `matched=16251 modified=16251`; **games still without `played_at_utc`: 0**. |
| 5 | Re-measure | See below. |
| 6 | Confirm shadowing | `focus_outcome_loop: SHADOW measured 54 focuses (nothing rendered)`. 54 rows in `focus_outcome_shadow`. **`current_metric` written: 0. Focuses resolved improved/regressed/stuck: 0.** |

## Step 5 — what the repair actually changed

Verdicts over the 46 active weakness focuses, same code, before and after the
backfill:

| | improved | regressed | stuck | measurement_pending | **no_data** | after-window <3 games |
|---|---|---|---|---|---|---|
| **Before** | 3 | 7 | 5 | 12 | **19** | 19 |
| **After** | 1 | 4 | 3 | 11 | **27** | 27 |

**Eight focuses moved into `no_data`.** Those eight users were one flag-flip
away from a confident improved/regressed/stuck verdict computed from games
they played *before* their focus began — for six of them, every single game in
the "after" window predated the focus by months. They now correctly report
that we have not seen enough of their games yet.

Total verdicts fell from 15 to 8. That is the repair working: fewer claims,
all of them defensible.

## Pre-apply safety check that fired

The first approved apply attempt **refused to write**: the deployed script
still returned `APPLY not implemented` and exit 3, because the commit that was
meant to add the write path had been applied with an unverified
`str.replace()` that silently did not match. The gate held, no data was
touched, and the real path was implemented, tested against a 3,000-game
scratch database (refusal / apply / idempotent re-run / rollback all verified)
and redeployed before the apply succeeded.

## Open items from this rollout

- **`build_timestamp` reports `"unknown"`.** `Dockerfile.backend` declares
  `GIT_COMMIT` as a build ARG but not `BUILD_TIMESTAMP`, so the exported value
  never reaches the image. Cosmetic — `git_commit` already proves which code a
  user received — and fixable on the next build.
- **The production repo holds a local merge commit that is not on origin**
  (`a3b20180`). Its `origin` remote is HTTPS with no credentials, so
  `git push` fails from the box. Every commit *inside* that merge is already
  on `origin/working-code`, so nothing is at risk of being lost, but the box
  cannot publish and its HEAD will keep diverging until the remote is switched
  to SSH.
- **Rendering is still off.** The shadow series starts accumulating today at
  ~54 rows/day. The terminal-state rule should be chosen from that
  distribution, not guessed.
