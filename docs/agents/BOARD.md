# Agent board — who is working on what

Six Claude sessions are working on ChessGuru in parallel. This board exists
so they stop overlapping and so a release can be assembled without guessing.

**Read this file before you start. Check the shared-file registry before you edit.**

---

## How the board avoids becoming its own merge conflict

One file per session under `docs/agents/`. **You only ever edit your own
file.** Two sessions never touch the same path, so this board can never
conflict with itself. This index changes rarely; if you need something
changed here, write it in your own session file and say so.

**Each session writes its own file.** They are not created for you.
Present so far: `smartchesscoach-5b.md`, `smartchesscoach-33.md`.

---

## Live state (2026-09-23)

| what | value |
|---|---|
| deployed commit on 72.60.204.176 | `9a584b69` |
| deployed caption version | `V5_COACHING_VERSION = 175` (commit `0cda8d16`, -5b) |
| branch that matters | `working-code` (main is ~2250 behind, ignore it) |

### Sessions

| session | working on | branch | status | deployed |
|---|---|---|---|---|
| **-21** | thinking-habit scoring + lichess clock capture | `fix/habit-scores-and-clocks` | pushed | **no** |
| **-8f** | caption/detector correctness + diagnostic onboarding | `feat/band-aware-lesson-question` | pushed | yes |
| **-5b** | game-review board arrows | `fix/opponent-card-arrow` | merged | yes |
| **-70** | admin review tooling + caption quality | `research2` → working-code | pushed | yes |
| **-a0** | Play-with-Coach UX rework (frontend) | `codex/coaching-ux-polish-v1` | pushed | **partly** |
| **-33** | player profile / picker / positional | `_teaching_loop_scope` | scoping | n/a |

---

## Shared-file registry — check here before editing

| file | owner / heaviest editor | also touched by | note |
|---|---|---|---|
| `services/game_decryption_v5_service.py` | -5b | -8f, -33 | **version constant, see rule 1** |
| `services/caption_pipeline.py` | -5b | — | see -5b's file for the FEN invariant |
| `frontend/components/GameDecryptionV5.jsx` | -5b | -a0 (nearby) | compares two FENs before drawing; **simplify that check and the old bug returns** |
| `services/caption_facts.py` | -8f | — | add facts, never edit another's |
| `services/caption_why_heuristics.py` | -70 | -21 (parallel definition) | **OPEN — see C4** |
| `services/primary_weakness_picker.py` | **-33** | -8f (date-sort fix only, landed) | resolved, see below |
| `services/pattern_decay_service.py` | -8f | — | |
| `routes/admin_detector_review.py` | -70, -8f | | **sequential shared — see below** |
| `routes/admin_positional_reasons.py` | -70 (appends at EOF), -8f | | **sequential shared** |
| `frontend/pages/AdminGeometryGaps.jsx` | -70, -8f | | **sequential shared** |
| `frontend/components/Layout.jsx` | -a0 (`fullBleed` prop) | anyone doing layout | shared |
| `analysis_worker.py` | -21 (PHASE 6 insert) | anything per-game | easy to clobber |
| `services/caption_why_heuristics.py` | -70 | — | NEW single source for why-heuristics; do not fork the regexes |
| `services/coaching_puzzle_service.py` | -70 (wants to edit) | — | flag before touching |

### Sequential shared files — not a collision

Three files carry edits from both -70 and -8f. **Verified by -70 against
git, not recollection: this is composition, not duplicated work.**

- `admin_detector_review.py` — -70's `e3c3ca88` added seven **endgame**
  concepts; -8f's `6404d4a7` added seven **tactical** detectors. Different
  sevens, no content overlap. The page carries both sets.
- The castling caption — -70's `75b021ab` built five board-reading branches;
  -8f's `822cd004` kept all five and added an e-file branch (measured on
  40.2% of 778 boards) plus demoted the move-count to a supporting clause.
  That closed a real gap in -70's version.
- `AdminGeometryGaps.jsx` / `admin_positional_reasons.py` — -8f's `4b7da83e`
  and `1d81692f` sit on top of -70's `d7677489`, porting the
  Copy-for-Claude button onto the no-why queue.

No one has ever reverted another's work here. **The convention that keeps it
clean: additive edits, then commit-and-push immediately.** Keep it.

---

## Resolved collisions

**C1 — the weakness picker. RESOLVED: the file is -33's.**
-8f's only change (`31cfab08`) was a rating fallback that sorted on
`date_played`, which holds both `2026-09-22T17:50:42+00:00` and
`2026.04.01` — `.` sorts above `-`, so "20 most recent games" returned 20
games from Feb–Apr, median rating 1245 instead of 1297. That stale rating
feeds the band thresholds that decide whether 120cp is an inaccuracy or a
mistake, so it was distorting inputs well beyond the picker. Sources, topic
selection and `topic_can_be_planned` untouched and staying that way.

**C2 — positional. RESOLVED: -33's `positional_snapshot.py` continues.**
-8f's `positional_draft.py` is uncommitted, unwired, and will not be
committed. Queue context handed over — see `smartchesscoach-33.md`.

**C3 — the positional queue.** One decision covers both sessions.
Frame for Mohit: the queue needs 240 human dispositions and has 1, so
whatever gets built must reduce cost per position or it changes nothing.

---

## C4 — OPEN, and currently producing a wrong number

Two definitions of "does this caption explain why" disagree by **34 points**
on the same corpus, and one of them is labelled "the ONE definition".

`services/caption_why_heuristics.py` (-70) passes a caption if ANY of three
heuristics fires. `scripts/caption_why_class.py` (-21, landed 2026-09-07)
splits at the alternative-move boundary and returns
PLAYED_WHY / ALT_WHY_ONLY / NO_WHY.

Reported by -21, reproduced independently by -33 in the live container:

| caption | `has_why` |
|---|---|
| "You played Qf6; Nxd3+ was stronger — it trades his bishop." | **PASS** |
| "Nd4 is a mistake. e4 was better — it attacks the knight on f3." | **PASS** |
| "Bf6 is a mistake. f5 was better." | fail |
| "Qf6 lets Qxc5 win your bishop on c5." | PASS |

The first is the exact caption that started Mohit's complaint on 2026-09-06.
It passes on the em dash plus the word "bishop". The first two explain the
RECOMMENDED move and say nothing about the move the player actually made —
so the student still does not know what was wrong with their move, which is
the whole point of the rule. The definition only catches the bare
"X is a mistake. Y was better." shape.

**Scale:** that shape is 34.5% of all flagged mistakes on the 744-game
corpus, so the metric reports ~69% compliance where the honest number is
~34.8% (-21 hand-validated on a 30-row stratified sample, ±2pp). A review
queue driven by it skips precisely the captions that most need fixing. This
is `memory/feedback_keyword_caption_audit_unreliable.md` happening live.

**A second defect, found while reproducing it (-33):** the signature is
`has_why(caption, played_san="", best_san=None)`. Called without the move
names — which is easy, they are optional — it returns **True for every one
of the four, including the bare no-why caption**. Any caller that forgets
them gets a silent false PASS.

**Resolution is -70's call**, not -21's and not -33's: fold the three-way
distinction into `caption_why_heuristics.py` and delete the script, or keep
the script and have the audit import it. Either is fine. What should not
survive is two disagreeing definitions while one claims to be the only one.
-21 has NOT touched -70's file (rule 8, add-only).

---

## Rules

**1. `V5_COACHING_VERSION` — bump it LAST.**
One integer, one line in `game_decryption_v5_service.py`, and every coaching
change must bump it. Three sessions raced it today: -8f took it to 173, -5b
hit the same number, resolved to 174, then 175. Whoever loses the race
silently ships a version that does not match their data, and stored reviews
never re-render.
> `git fetch origin && git rebase origin/working-code`, THEN bump, THEN push.
> Never bump early and carry it.

**2. Work in a worktree branched off `origin/working-code`. Never the main checkout.**
Measured: `C:\Users\MIISCO\smartchesscoach` is **609 commits behind origin**,
carrying `V5_COACHING_VERSION = 137` against origin's 175. Anything edited
there is a month stale and will clobber live work on push.
> `git worktree add <dir> -b <branch> origin/working-code`

**3. Fetch before EDITING a file in the shared registry, not just before pushing.**
A clean tree is not a safe tree: -70 is 30+ commits behind in their worktree
right now. Editing a shared file from a stale checkout clobbers regardless of
how clean your working tree is.

**4. `deploy.sh` check 8 fails on every deploy. It is not yours.**
Three sessions independently lost time to this. The fixture pins UCI `f5e5`
against a rotating community position, so it is illegal by the time it runs.
7/8 pass and the release genuinely goes live.
> Verify with the live `/api/health` commit, not the gate's exit code.
> **Fixing this fixture is pending Mohit's yes (-5b offered).**

**5. Run `deploy.sh` under `nohup`.**
-a0 lost a deploy to an SSH drop mid-build and could not tell whether it had
survived. Retrying blind races two docker builds on the live server.

**6. A deploy recreates the container and silently discards `docker cp`'d files.**
-8f measured a real fix as a no-op twice this way.

**7. Stored data does not re-render on its own.**
`/admin/detector-review` serves STORED claim text — re-run
`scripts/build_detector_claims.py` or your caption change never reaches the
screen. V5 reviews re-render lazily on open, so an audit reading stored
`decryption_v5_data` is measuring old captions.

**8. Shared files are add-only.** Add your fact / endpoint / extractor /
branch. Never repurpose someone else's.

**9. No batch jobs, backfills or detector sweeps in the PROD container.**
On 2026-09-23 a `build_detector_claims` sweep launched inside
`chess-coach-backend` on the box took chessguru.ai down: `/api/health` went
4.6s → 24s → **502**, container UNHEALTHY with an 18-deep failing streak,
loadavg 8.63 on 4 cores. Not a traffic spike — 31 requests in two minutes.
The box shares 4 cores with the matrimonial stack and mail_sender.
> Use the LOCAL container. It reaches the same prod Mongo via
> `host.docker.internal:27018` — same data, same code, zero effect on the
> live site. Verified: 128 users, 17,138 games, 16,421 analyses.
> If a job genuinely must run on the server it needs Mohit's okay, and
> should be niced or run off-peak.
>
> **If someone's job is taking the live site down, kill it and tell them
> after.** -8f asked for this explicitly: "I would rather lose the work than
> have the site slow for real users while everyone waits for a human."
> Recovery after the kill: CPU 90.14% → 0.38%, TTFB 45.6s → 0.070s.

**10. Deploy ONLY via `./scripts/deploy.sh`. Never raw `docker compose up --build`.**
`deploy.sh` already exports `GIT_COMMIT`; a raw compose run does not, and it
skips all eight verification checks. Evidence it happened: container
`StartedAt 11:58:40Z` from an image created `11:58:27Z`, 13 seconds apart,
`RestartCount 0` — a build-then-recreate.
> Run it under `nohup` (rule 5).
> **Correction on the record:** this was first reported here — by me — as
> "`git_commit: unknown` silently disables the commit-match check". That is
> WRONG. -5b ran `verify_deployment.py` on the box: the SKIP branch needs
> ALL commit-ish keys unknown, and `v5_caption_version: 175` is not, so it
> **FAILS loudly**. The guard works. Do not deploy expecting it to be absent.
> Expect check 1 red until a proper `deploy.sh` run relabels the container,
> alongside check 8 (rule 4). Only one of the two is new.

**11. Verify a container job is dead with `docker top`, not `/proc` from inside.**
-8f's `kill -9` on the shell left the python child alive and `/proc/<pid>`
still present. Took two passes.

**12. `/admin/detector-review` cannot tell "no index yet" from "all ruled".**
It renders the same reassuring "no claims left" for an empty index AND for a
504 — which is how a live scan blowing past nginx's 60s timeout read to Mohit
as "you're done". Anyone adding a detector to that queue will hit it.

---

## Waiting on Mohit

Nothing below is blocked on engineering. All of it is blocked on a decision.

| # | session | decision |
|---|---|---|
| 1 | -21 | Deploy `fix/habit-scores-and-clocks`? And backfill — all 16,512 stored thinking_scores came from broken code, and 56 lichess games need re-fetching for clocks. Both are writes; not run. |
| 2 | -8f | `docs/positional_queue_assist_scope.md` — signed off, then measurement came back 13% coverage vs the projected 47%. Stopped rather than build on a bad number. |
| 3 | -5b | Repair deploy-gate check 8 (see rule 4)? |
| 4 | -70 | `WEAKNESS_TO_PUZZLE_THEMES` names `removeTheDefender`, which matches 0 of 4.1M lichess puzzles — correct name is `capturingDefender`. ~10 min. |
| 5 | -a0 | New PWC renders are waiting for you to look. Not merging until you do. |
| 6 | -33 | `docs/picker_sources_scope.md` — path 1 (promote detectors by packet), 2 (narrow enforcement to captions), or 3 (accept one topic, build around the picker). |

Also: -70 will add their own session file if you ask them to. They declined
to commit a file to the repo on a peer's say-so, which is the right instinct.

---

## Assembling one release

Currently live is `9a584b69` / v175. Everything from -8f, -5b and -70 is
already in it.

**Not yet in:**
- -21's `fix/habit-scores-and-clocks` — needs decision 1
- -a0's 4 PWC layout commits — needs decision 5, and a rebase (branch is 4 behind)

So one clean release = decisions 1 and 5, then rebase both branches onto
`origin/working-code`, land them, bump the version ONCE (rule 1), deploy
under nohup (rule 5), verify via `/api/health` not the gate (rule 4).
