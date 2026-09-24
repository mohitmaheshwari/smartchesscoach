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

## C5 — state principles move to the measurement layer. RESOLVED: -8f does it.

-8f measured principle fires against stored `cp_loss` over 600 games:

```
TAC_CHANGED_AFTER_MOVE  2771 fires   0.0% at cp_loss<=20   median 210
TAC_HANGING_PIECE        937         0.0%                  median 188
TAC_DEFENDER_COUNT       599         0.0%                  median 222
---
MID_BAD_BISHOP            91        53.8%    state, not error
MID_KING_SAFETY         1650        47.0%    state, not error
OP_NOT_CASTLED           951        46.2%    state, not error
---
TAC_PIN_PATTERN          241        99.2%    fires on GOOD moves
```

> **CORRECTION 2026-09-24, after -8f challenged it.** The next sentence is
> WRONG and is left visible rather than quietly edited. All three cited
> principles carry `gate_policy: "endorsement_required + cp_loss_strict"`,
> and `caption_facts.py:6182` defines that as "engine's #1 must DIFFER from
> played" with a hard `cp_loss >= 30` floor. A detector that cannot fire
> below 30cp can never appear in the `cp_loss <= 20` bucket, so **the 0.0%
> is guaranteed by the gate, not discovered by the probe.** -8f said two of
> the three were tautological; checking the gate policies, it is all three.
>
> What survives: the STATE band principles are NOT cp_loss-gated, so their
> measured 44–71% and "they straddle the 56.4% base rate" still stand.
> What does not: any claim the probe was *shown* able to discriminate. A
> valid control needs a principle with no cp_loss gate landing near 0% —
> `OP_CLAIM_CENTER` (`endorsement_preferred`) and `TAC_BACK_RANK`
> (`endorsement_required`, no cp_loss floor) are candidates. Until one is
> shown, treat the band separation as measured but uncontrolled.

The 0.0% rows are the positive control: the probe can separate
error-principles. So the middle band is real — three principles fire about
half the time on moves the engine agreed with, because they describe the
POSITION, not the move. MID_BAD_BISHOP fired on the same bishop for 11
consecutive moves in one game, none of them mistakes. TAC_PIN_PATTERN is
the inverse pathology, firing almost only on good moves.

A state principle cannot be graded as a violation either way, so it is not
a shadow-vs-caption candidate at all. The three move out of -8f's grading
queue into `positional_snapshot.py` as tracked numbers over a player's games.

**-8f does the transfer; -33 stays out of the file until it lands.** Ruled
2026-09-23 by the two sessions, Mohit delegating ("you guys decide"). -8f is
already in that file with a refactor proven to move nothing across 24,738
positions and holds the measurements; -33 doing it would mean re-deriving
them.

Worth recording: -8f had read the bad-bishop result as Stockfish being
tactically short-sighted, and retracted that themselves when the numbers
disagreed.

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

**14. "Does it work" and "can a user reach it" are SEPARATE checks.**
-5b counted six things built today and reaching nobody: review arrows, the
PWC eval bar, the coaching timeline, the Explain button, "Practice Now", and
36 openings' worth of chapters. All wired, all working, none rendered or
reachable. Treating each as its own bug misses that it is one disease.
> After building, ask "what does a user click to see this" and answer it by
> loading the page, not by reading the code.

**15. The backend and the frontend deploy separately. Check BOTH.**
Measured 2026-09-24: `/api/health` reported `git_commit 11fe2569`, which IS
`origin/working-code` HEAD — backend fully deployed, zero commits behind.
The live bundle was `main.83455eb4.js` and did NOT contain that commit's
frontend work:

```
marker                 live bundle   trunk source
lesson-spine           PRESENT       present   <- positive control
coach-play-eval-bar    absent        present
lesson-next-chapter    absent        present
```

A green backend commit label says nothing about what the browser is running.
> Verify the frontend by fetching the live bundle and grepping for a
> `data-testid` the change introduced, with a known-present marker alongside
> it as the control.

**12. `/admin/detector-review` cannot tell "no index yet" from "all ruled".**
It renders the same reassuring "no claims left" for an empty index AND for a
504 — which is how a live scan blowing past nginx's 60s timeout read to Mohit
as "you're done". Anyone adding a detector to that queue will hit it.

---

## Ownership map — route tasks by AREA, not by file

**Rule 13: before starting anything new, check this map.** If the task is not
your area, say so and hand it to the owner — sessions can message each other
directly. Nothing auto-routes; Mohit types into whichever session he has
open, and it is on the receiving session to redirect.

Areas, not files, because Mohit thinks in areas and files change weekly.
Each session chose its own and named what it explicitly does NOT want.

| session | owns |
|---|---|
| **-21** | thinking habits & per-game scoring · game import & clock capture · time-management and rushing signals · game-review narrative truth · caption claim *verification* (is it TRUE, does it answer why) |
| **-8f** | review caption *correctness* · detector quality, grading & the review queue · onboarding diagnostic · chess-truth verification ("prove it on the board") · game-analysis data correctness ("this number looks wrong") |
| **-5b** | game-review board geometry (arrows, highlights) · caption pipeline · PWC caption presentation & eval bar · release verification, deploy gate, `/api/health` identity |
| **-70** | admin review tooling (`/admin/detector-review`, `/admin/geometry-gaps`) · caption why-quality & the missing-why queue · claim wording on review surfaces · detector coverage measurement |
| **-a0** | Play-with-Coach screen & layout · frontend theming and design tokens · board rendering / chessground · pre-move guardian *presentation* |
| **-33** | player profile & `/home` composition · focus picker sources and topic selection · positional measurement from the board |

### Seams — named by the sessions themselves

- **grading vs choosing.** -8f owns detector GRADING (evidence, queue,
  shadow→caption promotion). -33 owns which topic the picker CHOOSES from
  the graded set. The single PLAN-graded id is the seam: -8f makes the case
  for promoting more, -33 decides what the picker does with them.
- **words wrong vs detection wrong.** Anything phrased "the coach said the
  wrong thing" goes to **-5b** first; they hand off to -8f if the problem is
  detection rather than wording. They can usually tell in one query.
- **concept presence.** `positional_snapshot.py` (-33) is the ONE board
  measurement. Anyone needing "is this concept present on the board" calls
  it; new concepts are added there, add-only, not in a parallel module.
  Ruled 2026-09-23 on -8f's positional gold-set request.
- **theming crosses pages.** -a0 owns theming, which by nature touches pages
  others own. They flag before editing rather than treat the area as a
  licence.
- **`analysis_worker.py`** belongs to everyone. Route by what the task is
  about, not by the file.

### Nobody's area

**Product and visual design of customer surfaces** — the curriculum-vs-profile
question, what `/home` should say. -8f, -5b and -70 each explicitly declined
it for lack of design context. -33 holds it by default. Worth Mohit knowing
that four of six sessions consider this out of scope for them.

---

## Ownership map — route tasks by AREA, not by file

**Rule 13: before starting anything new, check this map.** If the task is not
your area, say so and hand it to the owner — sessions can message each other
directly. Nothing auto-routes: Mohit types into whichever session he has
open, and it is on the RECEIVING session to redirect.

Areas, not files, because Mohit thinks in areas and files change weekly.
Each session chose its own and named what it explicitly does not want.

| session | owns |
|---|---|
| **-21** | thinking habits & per-game scoring · game import & clock capture · time-management and rushing signals · game-review narrative truth · caption claim *verification* (is it TRUE, does it answer why) |
| **-8f** | review caption *correctness* · detector quality, grading & the review queue · onboarding diagnostic · chess-truth verification ("prove it on the board") · game-analysis data correctness ("this number looks wrong") |
| **-5b** | game-review board geometry (arrows, highlights) · caption pipeline · PWC caption presentation & eval bar · release verification, deploy gate, `/api/health` identity |
| **-70** | admin review tooling (`/admin/detector-review`, `/admin/geometry-gaps`) · caption why-quality & the missing-why queue · claim wording on review surfaces · detector coverage measurement |
| **-a0** | Play-with-Coach screen & layout · frontend theming and design tokens · board rendering / chessground · pre-move guardian *presentation* |
| **-33** | player profile & `/home` composition · focus picker sources and topic selection · positional measurement from the board |

### Seams — named by the sessions themselves

- **Grading vs choosing.** -8f owns detector GRADING (evidence, queue,
  shadow→caption promotion). -33 owns which topic the picker CHOOSES from
  the graded set. The single PLAN-graded id is the seam: -8f makes the case
  for promoting more, -33 decides what the picker does with them.
- **Words wrong vs detection wrong.** Anything phrased "the coach said the
  wrong thing" goes to **-5b** first; they hand to -8f if the fault is
  detection rather than wording. Usually one query to tell.
- **Concept presence.** `positional_snapshot.py` is the ONE board
  measurement. Anyone needing "is this concept present" calls it; new
  concepts are added there, add-only, never in a parallel module.
- **Measurement vs threshold.** Inside that file, measurement is
  threshold-free (how many pawns sit on the bishop's colour) and the
  verdict (how many is too many) belongs to whoever grades. Verdicts may
  differ; the numbers never do. This is the seam that would have prevented
  C4, and it came from -8f, not from the file's owner.
- **Theming crosses pages.** -a0 owns theming, which by nature touches pages
  others own. They flag before editing rather than treat the area as licence.
- **`analysis_worker.py`** belongs to everyone. Route by what the task is
  about, not by the file.

### Nobody's area

**Product and visual design of customer surfaces** — what `/home` should
say, curriculum vs profile. -8f, -5b and -70 each explicitly declined it for
lack of design context; -a0 declined the curriculum specifically. -33 holds
it by default. Four of six sessions consider it out of scope for them, which
is worth knowing before it is handed to any of them.

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
