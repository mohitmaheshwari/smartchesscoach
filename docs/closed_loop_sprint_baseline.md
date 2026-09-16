# Closed Coaching Loop Sprint — Baseline (WS0)

**Recorded:** 2026-09-16
**Production was read-only for every measurement in this document.** No
production write, index change, backfill, dedup, scheduler change or deploy
was performed. The only mutations made anywhere were to a *local* dev
container, and those were reverted (see §6).

---

## 1. Build identity

| Thing | Value | How established |
|---|---|---|
| Sprint worktree | `origin/working-code` @ **`39d12f42`** | `git worktree add _cl_sprint origin/working-code` |
| Production deploy | **`0b32aaa5`** | `ssh root@72.60.204.176 'cd /root/repos/smartchesscoach && git log --oneline -1'` |
| Relationship | Prod is **one commit behind** the worktree, and that commit (`39d12f42`) touches only `docs/product_correctness_review_2026_09_11.md`. **Code is identical.** | `git show 39d12f42 --stat` |
| Prod working tree | clean (`git status --porcelain` empty) | ssh |
| Prod container built | 2026-09-16 14:31:40 UTC | `docker inspect chess-coach-backend --format '{{.Created}}'` |
| Prod `V5_COACHING_VERSION` | **165** | `docker exec chess-coach-backend grep -m1 '^V5_COACHING_VERSION' …` |
| Prod engine version stamp | `P2.4` on 15,352 analyses | `game_analyses.engine_version` |
| Prod analysis depth | 18 (uniform) | `game_analyses.analysis_depth` |

### Environments used

| Environment | What it is | Trustworthy for |
|---|---|---|
| `_cl_sprint` worktree | origin/working-code @ `39d12f42` | reading current source; all code edits |
| **Production** (`72.60.204.176`) | live site + live Mongo | **read-only** measurement, and the only place these numbers are real |
| `chess-coach-backend` (local Docker) | local container. **Image predates the 2026-08-07 `git_commit` field**, so it is older than prod. It connects to the **prod** DB over the `127.0.0.1:27018` SSH tunnel. | running read-only query scripts against prod data. **Not** valid for testing origin-HEAD code — see §6. |
| `cg-sprint-backend:ws0` | image built from the `_cl_sprint` worktree during WS0 | runtime verification of sprint code |

**Do not confuse these.** The local container uses prod *data* but old *code*.
A change that works there proves nothing about what a user receives.

---

## 2. Data model — the fields this sprint depends on

### `user_active_focus` (274 docs)
The spine. One row per named focus per user.

| Field | Meaning | Trap |
|---|---|---|
| `type` | `weakness` (227) / `strength` (39) / absent (8) | **Every query must filter `type`.** An unfiltered "active focus" count is 92; the weakness count is 45. This exact omission produced a wrong number in the pre-sprint audit — see §5. |
| `status` | `active` (45 weakness) or `superseded_vN` / `closed_unresolvable_metric` | `superseded_vN` means *an algorithm version replaced it*, not that the user resolved anything. |
| `topic_key` | e.g. `piece_safety` | |
| `started_at` | when the focus was named. `datetime` (35) **or** ISO `str` (10) | Mixed type. `_games_split_by_play_date` normalises via `.isoformat()`. |
| `locked_until` | when the outcome check may run | `null` on 39 rows — **all of them `type: "strength"`**, which the scheduler excludes by design. |
| `baseline_metric` | `{name, value, occurrence_count, n_games_at_baseline}` | Provenance only. `check_focus_outcome` re-derives both halves; it does **not** difference against this. |
| `current_metric` | the measured "after" value | **Null on all 274 docs. Never written, ever.** |
| `resolution` | `improved`/`regressed`/`stuck` are the real verdicts | **Zero rows have ever held one.** |

### `games` (16,207 docs)

| Field | Meaning | Trap |
|---|---|---|
| `date_played` | when the game was played | **Three incompatible shapes — see §3.** This is the field the outcome window splits on. |
| `date_played_iso` | a prior attempt at a clean field | Stale: the import path does not write it, so it re-freezes after each backfill (correctness review finding 6/17). **Do not build on it.** |
| `pgn` | full PGN including headers | Carries `[UTCDate]`/`[UTCTime]` — the recovery source for §3. |
| `is_analyzed` / `analysis_status` | `completed` (15,353), `failed` (733), `retrying` (2) | |
| `platform` | `chess.com`, `lichess`, `coach` | `coach` rows are Play-with-Coach games, not imports. |
| *(none)* | **there is no canonical external-game id field** | This is why imports are not idempotent (§3.3). |

### `game_analyses` (15,522 docs)
`stockfish_analysis.move_evaluations` holds per-move records. **0 of 96,056
sampled evaluations are opponent moves** — only the user's half of each game
is stored. Out of scope this sprint, but it bounds what any coaching can say.

### Supporting
`analysis_queue` (16,023 · `queued_at`/`started_at`/`completed_at`/`reanalysis`),
`notifications` (13,401), `digest_email_log` (43), `users.email_notifications`
(present on 1 of 117 external users).

---

## 3. Measured baseline

All figures re-derived 2026-09-16 against production, read-only.
"External" excludes 11 internal/test accounts matched on
`bhutra|lilimd|test|demo|dev_user|@example`.

### 3.1 Users and focuses

| Metric | Value |
|---|---|
| Users total / external / internal | 128 / **117** / 11 |
| `user_active_focus` docs | 274 (weakness 227, strength 39, untyped 8) |
| **Active weakness focuses** | **45** (42 external) |
| Active weakness focuses with `locked_until = null` | **0** |
| Active *strength* focuses with `locked_until = null` | 39 |
| Focus docs with `current_metric` set | **0 of 274** |
| Focus docs ever resolved improved/regressed/stuck | **0** |
| Stored resolutions | `None` 164 · `measurement_pending` 36 · `metric_gap` 18 · `no_data` 9 |
| Scheduler would select **right now** | **0** (all 45 locks are in the future; next unlock in 2 days, furthest in 15) |

**Topic concentration (active, external):** `piece_safety` 34 (81%),
`threat_awareness` 5, `missed_tactic` 1, `tactical_oversight` 1,
`punish_blunders` 1. 33 of the 34 were assigned on **2026-09-11** by
`migrate_destination_safety_focus.py`.

**What the outcome check returns today** (ran `check_focus_outcome` read-only
over all 42 external active focuses):

| Verdict | Count |
|---|---|
| `no_data` (<3 games since start) | 17 |
| `measurement_pending` | 11 |
| `regressed` | 6 |
| `stuck` | 4 |
| `improved` | 4 |

14 of 42 (33%) could already be told something true. **Nothing renders it.**

### 3.2 `date_played` integrity — the WS1a blocker

| Shape | Count | % | Example |
|---|---|---|---|
| ISO with offset | 15,469 | 95.4% | `2026-09-16T14:00:00+00:00` |
| **Dotted (chess.com)** | **477** | **2.9%** | `2026.04.15` |
| Missing | 261 | 1.6% | — (100% `platform: "coach"`) |

The outcome window compares `date_played` as a **string**
([`primary_weakness_picker.py:958-979`](../backend/services/primary_weakness_picker.py#L958-L979)).
ASCII `.` (0x2E) sorts above `-` (0x2D), so **every dotted value sorts after
every ISO timestamp regardless of its real date.**

| Consequence | Value |
|---|---|
| Active focuses whose "after" window is polluted | **15** |
| Games wrongly counted as post-focus | **407** |
| Worst cases | `user_ce4f53ccb…`: all 20 "after" games are from **April**, focus started **11 Sept**. Same pattern for 5 more users. |

**Recoverability (this corrects the brief's assumption).** The brief directed
that uncertain dates be flagged and excluded rather than guessed. Measured:

| Group | Exact UTC recoverable from PGN | Notes |
|---|---|---|
| Dotted (477) | **477 / 477 = 100%** | Headers are case-normalised on import: `[Utcdate "2026.03.01"]`, `[Utctime "05:45:33"]`, `[Timezone "UTC"]`. A case-insensitive read recovers an exact instant. |
| ISO (400 sampled) | 400 / 400 = 100% | control |
| Missing (261) | 0 / 261 — **no date header at all** | But all 261 are `platform: "coach"`, i.e. Play-with-Coach games, not imports. |

So **no import needs an "uncertain" exclusion**: every real game resolves to an
exact UTC instant. The open question is not confidence, it is **eligibility** —
see §4.

### 3.3 Duplicate imports

| Metric | Value |
|---|---|
| Extra copies (same user, byte-identical PGN) | **557** |
| Users affected (all / external) | 29 / **26** |
| Worst single user | 81 duplicates |
| Canonical external-game id field | **does not exist** |

### 3.4 Analysis health

| Metric | Value |
|---|---|
| Analyses stored | 15,522 |
| Games `analysis_status: failed` | **733** (4.5%) |
| External users with ≥1 failed analysis | **43 of 65 with games (66%)** |
| Queue pending right now | 2 |
| Engine time `started → completed` | median **1.3 min**, p90 2.4 min |
| Queue `queued → completed` (initial only, n=13,246) | median 1.9 min, p90 **204 min**, p99 **9.6 days** |
| Signup → 10 games imported | median **4.3 min** (77% within 1 h) |
| Signup → 10 games analysed | ~19 days median; **10%** within 1 h, **12%** within 24 h, **44%** ever |

Host: **4 vCPU / 15 GB, 13 GB used, load 2.7/4**, shared with three unrelated
product stacks. 2 analysis workers.

### 3.5 PWC message cleanliness (288 messages, last 45 days; 162 to external users)

| Category | Count | % |
|---|---|---|
| Raw centipawns shown | 145 | **50.3%** |
| `in 0.0s` claim (from an empty `time_taken`) | 104 | **36.1%** |
| Bare move announcement | 110 | 38.2% |
| Failure scoreboard ("your Nth … today") | 61 | **21.2%** |
| Detector id leaked | 41 | 14.2% |
| **Clean** | **33** | **11.5%** |

Denominator = all messages in `coach_messages`. Per the brief, WS2 reports both
this and a substantive-coaching-only figure; bare announcements are reported,
never excluded to flatter the score.

### 3.6 Digest and notifications

| Metric | Value |
|---|---|
| Digest sends, all time | 43 |
| Distinct recipients | **1** (the founder) |
| **External recipients** | **0** |
| External users with an `email_notifications` field | **1 of 117** |
| Default when the field is absent | all three categories **`True`** ([`settings.py`](../backend/routes/settings.py)) |
| Notifications | 13,401, of which `game_analyzed` 13,394 |
| Notifications read | **0** |
| Digest cron on prod | **none** (`crontab -l` has only a backup job and `run_assign_focuses.sh`) |

---

## 3.7 Coach games vs imported games — a measured bias, accepted by decision

Relevant because D1 below resolved to "coach games count, in one pooled rate."

The PIC path — which covers 34 of the 42 active external focuses — reads
`move_observations` filtered to `piece_safety_decision.version ==
piece_safety.d_live.v1`, `derivation_status == "ok"`, `eligible == true`
([`focus_bridge.get_d_live_evidence_summary`](../backend/services/focus_bridge.py#L168)).

| | Games contributing ≥1 PIC decision | Decisions per contributing game |
|---|---|---|
| Imported (2,000 sampled) | 1,923 (96.2%) | 5.0 |
| Coach (all 267) | 129 (48.3%) | 3.5 |

Coverage is thinner but the measurement is a **rate**, so thin coverage alone
does not bias it. The miss rate does. Restricted to the 3 users holding both
≥20 coach and ≥100 imported decisions, so the comparison is within-player:

| User | Coach miss rate | Imported miss rate | coach n | imported n |
|---|---|---|---|---|
| `user_88682a12…` | 2.0% | 22.9% | 199 | 2,201 |
| `user_8b599930…` | 3.9% | 10.0% | 103 | 2,880 |
| `user_d35b3745…` | 0.0% | 4.2% | 76 | 811 |
| **Pooled** | **2.12%** | **14.00%** | 378 | 5,892 |

**Coach games miss about 7× less often, and all three users point the same
way.** The mechanism is direct: the pre-move Guardian stops the mistake while
the game is being played.

**Consequence of the decision:** a user who plays Play with Coach after their
focus starts will tend to measure as *improved* partly because of live
coaching rather than a changed habit. This was put to the product owner
alongside these numbers on 2026-09-16 and the pooled-rate option was chosen
deliberately.

**Confidence:** direction and rough magnitude are solid (unanimous, large,
mechanistically explained). The precise multiplier is not — n=3 users. It
should be re-derived once more users have both kinds of game.

**Mitigation kept in place:** `played_at_source` is written on every row, so
the coach/imported mix of any window is queryable after the fact. Revisiting
this needs a query, not another backfill.

---

## 4. Decisions taken

Resolved by the product owner on 2026-09-16.

**D1 — Do Play-with-Coach games count in the before/after window? → YES, in a
single pooled rate.** Recommendation had been to exclude them, or to count
them but compare like-for-like. Both were declined in favour of one pooled
number, with the §3.7 measurement on the table at the time. Coach games are
dated from `imported_at` (present on all 267) and tagged
`played_at_source: "coach_imported_at"`.

**D2 — Backfill scope → ALL games, not only the 477 dotted rows.** One code
path produces every value, so the 15,466 ISO rows are verified against their
own PGN rather than trusted. Result: 0 disagreements, i.e. the stored ISO
values were already correct and the dotted ordering really was the only
defect.

**D3 — `date_played` is left untouched.** New fields only: `played_at_utc`
(BSON Date), `played_at_source`, `played_at_raw`. Rollback is `$unset` of
three fields.

**D4 — WS1b is re-scoped** from "fix the null lock" (which §5 shows is not
broken for weakness focuses) to "give the extend-loop a terminal state."

---

## 4b. WS1a dry-run result (production, read-only, 2026-09-16)

`python backend/scripts/backfill_played_at_utc.py` — dry run is the default;
`--apply` refuses to run unless `--confirm-plan` matches the printed
fingerprint.

```
games examined: 16210

-- derived provenance --
    15943  pgn_utc_headers
      267  coach_imported_at

-- stored shape -> derived provenance --
    15466  iso     -> pgn_utc_headers
      477  dotted  -> pgn_utc_headers
      261  missing -> coach_imported_at
        6  iso     -> coach_imported_at

-- write plan --
  would write played_at_utc : 16210
  already correct (no-op)   : 0
  no canonical value        : 0

-- stored value disagrees with PGN by >1d --
  count: 0

-- effect on active weakness focuses --
  active weakness focuses               : 45
  with a polluted after-window (before) : 15
  games wrongly in an after-window      : 407
  after repair, ordering is by BSON Date: pollution -> 0 by construction

plan fingerprint: 106641a34f8a5c07
```

**100% of games resolve to a canonical instant. Nothing is unrecoverable and
nothing needs an uncertainty flag.** No write was performed.

---

## 4c. WS0 health endpoint — runtime verified

Built `cg-sprint-backend:ws0` from this worktree and ran it against the
production database on port 8099 (read-only traffic: one GET):

```json
{
  "status": "healthy", "database": "connected",
  "git_commit": "39d12f42", "build_timestamp": "2026-09-16T23:30:00Z",
  "api_version": "1.0.0", "worker_version": "P2.4",
  "engine_version": "P2.4", "v5_caption_version": 165,
  "feature_flags": {
    "VERIFIED_CAPTIONS": "true",
    "DISTILLED_CAPTIONS_ENABLED": "1",
    "PERSONAL_IMPROVEMENT_CYCLE_ENABLED": "true"
  }
}
```

Only flags actually set in the environment are listed, and only their on/off
state — the reported set is a hard-coded allowlist, never an `os.environ`
dump, so a newly added secret cannot leak through this endpoint.

Container is stopped, not removed: `docker start cgws0` → `localhost:8099`.

---

## 5. Correction to the pre-sprint audit

The pre-sprint audit reported *"39 active focuses have `locked_until = null`,
37 of them external, stuck 76 days, permanently invisible to the outcome job."*
**That is wrong.** All 39 null-lock rows are `type: "strength"`, which
`focus_outcome_loop` excludes deliberately. **Zero weakness focuses are
invisible because of a null lock**, and re-running the scheduler's exact query
confirms it selects 0 type-eligible rows with a bad lock.

The error came from querying `{"status": "active"}` without filtering `type` —
the precise mistake the project's own notes warn about.

**This changes WS1b.** The loop does not fail because focuses are invisible. It
fails because of an **extend-loop**: when a lock does expire,
`check_focus_outcome` returns `no_data` or `measurement_pending`, the action is
`extend`, `locked_until` moves forward, and the cycle repeats forever. The
production cron log shows exactly this:

```
=== Step 1: 2 expired active focuses to check ===
  user …3798d8af93ed  topic=missed_tactic       → measurement_pending  action=extend
  user …d35b37459e10  topic=tactical_oversight  → no_data              action=extend
```

WS1b must therefore add a **terminal state** — a bound on extensions or focus
age, after which the user is honestly told "we could not gather enough
comparable games; here is what we are changing" — rather than fixing a
null-lock that is not broken.

Separately, the 39 strength focuses are never outcome-checked at all. Real, but
lower priority and out of this sprint's scope.

---

## 6. Local mutations made and reverted

To test the WS0 health change I copied the worktree's `server.py` and
`analysis_worker.py` into the **local** `chess-coach-backend` container. That
container's image predates those files' current form, so it failed to start
(`ImportError: cannot import name 'product_events' from 'routes'`) — a defect
of the test method, not of the change.

Both files were restored from the pristine image
(`docker create --name restoretmp smartchesscoach-backend` → `docker cp` →
`docker rm`) and the container is healthy again. Verified:
`{"status":"healthy","database":"connected"}`.

**Production was never touched.** Runtime verification of the health change is
done against a purpose-built image, `cg-sprint-backend:ws0`.

---

## 7. Reproducing this document

Every figure above comes from a read-only script run inside a container
connected to the production database. The scripts are parameterless and safe to
re-run:

```bash
# build identity
ssh root@72.60.204.176 'cd /root/repos/smartchesscoach && git log --oneline -1'
curl -s https://chessguru.ai/api/health

# the full baseline snapshot (§3.1, 3.3, 3.4, 3.6)
docker exec chess-coach-backend python /tmp/baseline.py

# date integrity and PGN recoverability (§3.2)
docker exec chess-coach-backend python /tmp/ws1a_probe2.py

# the null-lock correction (§5)
docker exec chess-coach-backend python /tmp/nullcheck.py

# what the outcome check would say today (§3.1)
docker exec chess-coach-backend python /tmp/focus_test.py
```

These are moved into `backend/scripts/` as versioned, `--dry-run`-capable
tools during WS1a.
