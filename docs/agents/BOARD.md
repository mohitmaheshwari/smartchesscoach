# Agent board — who is working on what

Six Claude sessions are working on ChessGuru in parallel. This board exists
so they stop overlapping and so a release can be assembled without guessing.

**Read this file before you start. Claim your files before you edit them.**

---

## How the board avoids becoming its own merge conflict

One file per session under `docs/agents/`. **You only ever edit your own
file.** Two sessions never touch the same path, so this board can never
conflict with itself. This index file changes rarely; if you must edit it,
say so in your session file first.

Session files: `docs/agents/<session-name>.md`.

---

## Live state (2026-09-23)

| what | value |
|---|---|
| deployed commit on 72.60.204.176 | `9a584b69` |
| deployed caption version | `V5_COACHING_VERSION = 175` |
| branch that matters | `working-code` (main is ~2250 behind, ignore it) |

### Sessions

| session | working on | branch | status | deployed |
|---|---|---|---|---|
| **-21** | thinking-habit scoring + lichess clock capture | `fix/habit-scores-and-clocks` | pushed | **no** |
| **-8f** | caption/detector correctness + diagnostic onboarding | `feat/band-aware-lesson-question` | pushed | yes |
| **-5b** | game-review board arrows | `fix/opponent-card-arrow` | merged | yes |
| **-70** | admin review tooling + caption quality | `research2` → working-code | pushed | yes |
| **-a0** | Play-with-Coach UX rework (frontend) | `codex/coaching-ux-polish-v1` | pushed | **partly** |
| **-33** | player profile / picker / positional | (this session) | scoping | n/a |

---

## Shared-file registry — check here before editing

These are the files two or more sessions touch. **If your change lands in
one of these, say so in your session file first and read the owner's file.**

| file | owner / heaviest editor | also touched by | note |
|---|---|---|---|
| `services/game_decryption_v5_service.py` | -5b | -8f, -33 | **version constant, see rule 1** |
| `services/caption_pipeline.py` | -5b | -21 (older, landed) | heaviest arrow edits |
| `services/caption_facts.py` | -8f | -21 (older, landed) | add facts, never edit another's |
| `services/primary_weakness_picker.py` | -8f | **-33 (scoping)** | see collision C1 |
| `services/pattern_decay_service.py` | -8f | — | was uncommitted in live container |
| `routes/admin_detector_review.py` | -70 | -8f | both editing |
| `routes/admin_positional_reasons.py` | -70 (appends at EOF) | -8f | both editing |
| `frontend/pages/AdminGeometryGaps.jsx` | -70 | -8f | both editing |
| `frontend/components/Layout.jsx` | -a0 (`fullBleed` prop) | anyone doing layout | shared |
| `analysis_worker.py` | -21 (PHASE 6 insert) | anything per-game | easy to clobber |
| `services/caption_why_heuristics.py` | -70 | — | NEW single source for why-heuristics; do not fork the regexes |
| `services/coaching_puzzle_service.py` | -70 (wants to edit) | — | flag before touching |

---

## Open collisions — these need resolving, not just recording

**C1 — the weakness picker.** -8f owns `primary_weakness_picker.py` and has
pushed changes to it. -33 has an open scope (`docs/picker_sources_scope.md`)
whose whole subject is that same file. Two sessions are about to rewrite one
picker. Resolve before either writes code.

**C2 — positional.** -8f has `positional_draft.py` (uncommitted, paused, may
be abandoned). -33 built and landed `positional_snapshot.py`. Both are
"measure positional play from the board". One of them should stop.

**C3 — the positional queue.** -8f is blocked on
`docs/positional_queue_assist_scope.md` (measured 13% coverage against a
projected 47%). -33's positional work feeds the same queue. Same decision.

---

## Rules

**1. `V5_COACHING_VERSION` — bump it LAST.**
It is one integer on one line in `game_decryption_v5_service.py`, and every
coaching change must bump it. Three sessions raced it today: -8f took it to
173, -5b hit the same number, resolved to 174, then 175. Whoever loses the
race silently ships a version that does not match their data, and stored
reviews never re-render.
> `git fetch origin && git rebase origin/working-code`, THEN bump, THEN push.
> Never bump early and carry it.

**2. Work in a worktree branched off `origin/working-code`. Never the main checkout.**
Measured today: `C:\Users\MIISCO\smartchesscoach` is **609 commits behind
origin**, carrying `V5_COACHING_VERSION = 137` against origin's 175. Anything
edited there is a month stale and will clobber live work on push.
> `git worktree add <dir> -b <branch> origin/working-code`

**3. `deploy.sh` check 8 fails on every deploy. It is not yours.**
Three sessions independently lost time to this. The fixture pins UCI `f5e5`
against a rotating community position, so it is illegal by the time it runs.
7/8 pass and the release genuinely goes live.
> Verify with the live `/api/health` commit, not the gate's exit code.
> **Fixing this fixture is pending Mohit's yes (-5b offered).**

**4. Run `deploy.sh` under `nohup`.**
-a0 lost a deploy to an SSH drop mid-build and could not tell whether it had
survived. Retrying blind races two docker builds on the live server.

**5. A deploy recreates the container and silently discards `docker cp`'d files.**
-8f measured a real fix as a no-op twice this way.
> After any deploy, re-copy anything you cp'd in before trusting a result.

**6. Stored data does not re-render on its own.**
`/admin/detector-review` serves STORED claim text — re-run
`scripts/build_detector_claims.py` or your caption change never reaches the
screen. V5 reviews re-render lazily on open, so an audit reading stored
`decryption_v5_data` is measuring old captions.

**7. Shared files are add-only.** Add your fact / endpoint / extractor.
Never repurpose someone else's.

---

## Waiting on Mohit

Nothing below is blocked on engineering. All of it is blocked on a decision.

| # | session | decision |
|---|---|---|
| 1 | -21 | Deploy `fix/habit-scores-and-clocks`? And backfill — all 16,512 stored thinking_scores came from broken code, and 56 lichess games need re-fetching for clocks. Both are writes; not run. |
| 2 | -8f | `docs/positional_queue_assist_scope.md` — signed off, then measurement came back 13% coverage vs the projected 47%. Stopped rather than build on a bad number. |
| 3 | -5b | Repair deploy-gate check 8 (see rule 3)? |
| 4 | -70 | `WEAKNESS_TO_PUZZLE_THEMES` names `removeTheDefender`, which matches 0 of 4.1M lichess puzzles — correct name is `capturingDefender`. ~10 min. |
| 5 | -a0 | New PWC renders are waiting for you to look. Not merging until you do. |
| 6 | -33 | `docs/picker_sources_scope.md` — path 1 (promote detectors by packet), 2 (narrow enforcement to captions), or 3 (accept one topic, build around the picker). |

---

## Assembling one release

Currently live is `9a584b69` / v175. Everything from -8f, -5b and -70 is
already in it.

**Not yet in:**
- -21's `fix/habit-scores-and-clocks` — needs decision 1
- -a0's 4 PWC layout commits — needs decision 5, and a rebase (branch is 4 behind)

So one clean release = decisions 1 and 5, then rebase both branches onto
`origin/working-code`, land them, bump the version ONCE (rule 1), deploy
under nohup (rule 4), verify via `/api/health` not the gate (rule 3).
