# One coach, five pages — scope

Mohit, 2026-11-12: *"we have to talk about home page, progress page, learnings page, you
know how a coach handles things, different pages, game reviews, super fast stuff, how??"*
and earlier the same day: *"what would this guy pay us even 1 dollar for... think what a
chess player really does"*, *"whatever we build should work for everybody and at every
level"*, *"we will buy better servers, so performance is not the issue"*.

Mission unchanged: **the academy head coach's assistant, and a coach for the player.**

Status: **DRAFT — awaiting Mohit's sign-off. No code until signed.**

---

## 0. What already exists (audit, done before anything else)

### Pages today

From `frontend/src/App.js` and `components/Layout.jsx` on `working-code` (2026-11-12).

**What a normal user's navigation shows** (`Layout.jsx:181-191`): Home → `/home`, Learn →
**`/lab`** (because `PERSONAL_CURRICULUM_ENABLED` is not set, so `/learn` is never reached),
Progress → `/progress`, then Play with Coach and Settings. `/home` renders `HomePageNew`
for everyone; its `CurriculumHome` branch reaches nobody (`HomePageNew.jsx:269`, `:452`).

There are **57 non-admin, non-marketing routes**. Thirteen have no inbound link at all
(`/reply-check`, `/weaknesses`, `/challenge`, `/calculation-test`, `/daily-fix/drill`,
`/opening-walkthrough`, `/replay/:gameId`, `/game-old/:gameId`, `/training/motif/:motif`,
`/training/geometry/:moduleId`, `/plateau-breaker/apply`, `/prototype/interactive-moment`,
`/today`). `/recover/:gameId` is linked only from dead code; `/plateau-breaker` only from
its own pages. A coach does not have 57 conversations.

### Earlier scopes this builds on (not replaces)

| Scope | What it settled | State |
|---|---|---|
| `home_as_a_coach_scope.md` (10-07) | Home = what I know about you → a board and a question → play me. Loop beats ASK, RETIRE, REMEMBER, NOTICE A REPEAT | built; **RESOLVE ("you have stopped doing this") not built** |
| `home_merge_scope.md` (10-06) | one home, not two | the flag-gated second home still exists and reaches nobody |
| `progress_then_and_now_scope.md`, `unified_progress_v2_scope.md` | Progress = evidence that teaching changed play | `/progress` live |
| `coach_assistant_plan_scope.md` (11-09) | cause-first, tap-only coach plan for academies | built (`coach_plan_service`), self-coach door not built |
| `reply_check_page_scope.md` | play your move, then the reply you expect | built for one user's frozen packet |

### Machinery to reuse

- **Per-game habit check:** `update_focus_lock_compliance` in `analysis_worker.py` scores
  every new game against the active lesson (`coach_states.focus_lock`: games done,
  compliance trend, deep-session trigger).
- **Resolution states:** `pattern_decay_service` (ACTIVE → DECLINING → FADING, recovery
  credit per clean game). This is the RESOLVE beat.
- **Repeat across games:** `user_pattern_events`.
- **Last-game card, cached by the worker:** `both_sides_review.warm_latest_game_sync`
  (`[HOME-CARD]` step, d71186e8).
- **Asking before telling:** board taps and the cause question (`reflection_sessions`, `home_today_answers`).
- **Sparring from a position:** Play with Coach accepts `starting_fen` (`routes/coach_play.py:415`).
  The Maia human-like opponent exists but is OFF in prod (`PWC_HUMAN_POLICY_OPPONENT_ENABLED=false`).
- **Openings:** `opening_curriculum.json` has `modern_defense` and `pirc_defense`, but
  neither mentions the early ...Bg4 or the Bxf7+ trap. `traps.json` (55 traps) has no
  Modern or Pirc entry.
- **Per-user caches already in use:** `coach_states`, `coaching_cache`,
  `home_conversation_state`, `both_sides_analysis`.

### Usage evidence

None usable. Over 14 days of nginx logs, `/api/home/session` was called from 9 distinct
addresses, including ours. Product analytics go to PostHog, which is not readable from the
server. ChessGuru is not live. **Keep, fold and retire decisions are product decisions,
not usage decisions**, and Mohit signs each one in section 3.

### Speed today (measured, newest 400 completed analysis jobs)

| Step | Median | 90th percentile |
|---|---|---|
| game start → imported | 17 min (about the game's own length) | 5.3 h |
| queued → started | 14 min | 45 h (backfill backlog) |
| started → completed | 6.5 min | 15.6 min |

From a game ending to its read being ready, a player waits **roughly half an hour or
more** today. The queue already has a `priority` field.

### What players need: measured on 53 players across every level

Each player has 20+ analysed games and a rating in the PGN; the newest 60 games per player.

- At every rating band, **86–91% of games contain one decisive own mistake** (150+ loss).
  The last-game read has something true to say from the first game, for everyone.
- Opening leaks (same position + same move, first 12 moves, played twice or more,
  average loss 60+) **exist at every level**, but only show up once enough games are
  analysed. With all 60 games analysed: 18/25 (<1000), 7/12, 7/9, 6/7 (1800+). With
  only the newest 20: 9/25, 3/12, 0/9, 4/7.
- The test player (Lichess ~1834, see the memory note for user_65360395020a) shows what
  one person's version looks like:
  - his Modern vs 1.e4 is worse by move 12;
  - an early ...Bg4 appears in 18 of 27 Black games;
  - he walked into a Bxf7+ trap three times;
  - his seventh-and-later game of a sitting scores 0.45 (0.70 for games 4–6);
  - he uses about 4½ of 10 minutes per game.

### Decision

**EXTEND and CONSOLIDATE.** Keep the data and engines; rebuild the navigation around five
pages that all read from one per-player file the worker keeps current. No backend source
of truth is replaced. Old routes redirect; no page code is deleted in V1.

---

## 1. What it is

ChessGuru becomes a coach with five rooms. **Home** is the conversation between games:
what happened in your last game, what to watch in the next one, and when to stop.
**Games** is where the coach walks through a game with you, starting at the moments that
decided it and asking before telling. **Learn** holds your homework and your files: your
opening file built from your own games, the habit you are training, and practice taken
from your own positions. **Progress** tells you, from your games and not from drills,
whether each habit is getting better, the same, or gone. **Play** is sparring from your
own positions. Every page reads one file about the player that is updated after every
game, so every page opens instantly and none of them disagree. An academy coach sees the
same five rooms for each student and can approve or change the plan.

---

## 2. What the user sees

The player-facing text below follows the standing rules: simple English, short
sentences, no numbers or percentages. Chess notation (e4, ...Bg4) is used for a player
who plays rated games; for the under-1000 band the wording drops notation where it can.
A clickable version built from the test player's real games goes on the canvas before
sign-off (pre-code requirement).

### Home: between games

```
Last game · lost with Black
It turned on one move. Your queen stood where White's pawn could
uncover a check on it. Same idea as earlier this week.     [See it]

Before your next game
Watch for: a piece lined up with your queen or king.

Your openings
Modern against e4: one leak, and a trap you keep walking into.  [Fix it]

You've played a long sitting today. Your later games go worse.
This is a good place to stop.

[ Play a position from your games ]
```

When the last game had no decisive mistake: *"Clean game. Nothing to fix. One good move
worth seeing."* With no games: the import invitation and Play, nothing else (as today).

### Games: one game, walked through

```
[ board from his game, the moment that decided it ]

Before your move ...Re8 — which White piece can win something?
Tap it on the board.                            → he taps

Right. The pawn moves forward with check from the queen behind it,
and hits your queen.                     (Stockfish line, verified)

Did you see it during the game?
( No, I didn't look )  ( I saw the pawn, not the check )  ( I thought I was safe )

This is the third time this idea cost you a game.        [Practise it]
─────────────
Moments in this game:  ● decided it   ○ you missed a chance   ○ good move
[ whole game, both sides ]
```

Opens on the deciding moment, never on move one. The list of games below it puts the
coach's pick first.

### Learn: homework and files

```
YOUR OPENING FILE                          built from your games
  As Black against e4 · Modern
    You reach this after e4 g6 d4 Bg7 Nf3 d6 Bc4.
    You play ...Bg4. It walks into Bxf7+.   Play ...Nf6 instead.   [Train it]
  As White · Queen's Gambit, Exchange Slav        working well
  A trap you can set in your own lines                              [See it]

THE HABIT YOU'RE TRAINING
  A piece left open to their reply
  Warning sign · Rule · Practice from your own positions      [Start]

LIBRARY
  Endgames · Openings · Board patterns
```

### Progress: is it working

```
A piece left open to their reply      Getting better
Fewer of your moves leave something open than when we started.

...Bg4 in your Modern                 Waiting for a game
Using your clock                      Same as before

KEPT    (habits that stopped showing up in your games)
WHERE YOU STARTED  →  WHERE YOU ARE
```

### Play

```
Spar from your own positions
  Your Modern, after Bc4 — you're Black          [Play it]
  The middlegame you lost on Tuesday             [Play it from here]
Or a full game with your coach watching.
```

### Academy: the same rooms, from the coach's side

The head coach opens a student and sees the student's Home, Games, Learn and Progress,
plus approve / edit on the plan (`coach_plan_service`, built) and a note on any game
moment. The class view lists students by what needs the coach's attention this week.

---

## 3. In scope (V1)

**The player file**
- One read document per player, written by the analysis worker after every analysed game
  and refreshed nightly. Contents:
  - the last-game read;
  - the active habit and its per-game check;
  - the opening file;
  - sitting stats;
  - the weekly check;
  - the Play positions.
- Every page reads only this document by player id. Nothing heavy runs when a page opens.
- It is a cache derived from the existing collections, never a new source of truth.

**Fast lane**
- A player's newest game, played in the last hour, jumps the queue (the existing `priority` field).
- The last-game read is written right after the Stockfish pass, before captions and profile work.

**The five pages**
- **Home:** last-game read (deciding moment + repeat link), one thing to watch, the
  opening line, the sitting guard, the Play invitation. It extends `HomePageNew` and
  keeps the 10-07 loop.
- **Games:** opens on the deciding moment, ask before telling (existing taps), repeat
  link, both sides; the coach's pick first in the list. It extends `/games` and `/game/:id`.
- **Learn:**
  - The opening file:
    - positions he reaches, and leaks (exact position AND habit level, see Q2);
    - traps against him and traps he can set;
    - what the next level plays (Maia), verified by Stockfish.
  - The habit he is training: warning sign, rule, and a reply-check set generated from
    his own positions, for every player.
  - The library below.
  - It extends `/learn`; the curriculum flag goes away.
- **Progress:** each habit's state from his games (`focus_lock` compliance +
  `pattern_decay_service`), the kept shelf, where you started → where you are. It
  extends `/progress`.
- **Play:** sparring from his own positions via `starting_fen`.

**Every level**
- The same definitions for every player; only the wording changes with level.
- Tested on at least two real players per rating band before Mohit's review.

**Academy**
- The same five rooms inside `/academy/student/:id`, plus plan approve/edit (built) and a
  per-moment coach note.

**Navigation and routes (Mohit signs each row)**

| Route | V1 |
|---|---|
| `/home`, `/games`, `/game/:gameId`, `/learn`, `/progress`, `/play-with-coach` | **the five pages** |
| `/settings`, `/academy*`, `/import`, `/onboarding`, `/welcome`, `/diagnostic`, `/review` (reviewers), public `/learn/openings*`, family token pages | **keep as they are** |
| `/lab/game/:gameId` | redirect → `/game/:gameId` |
| `/lab` | fold into Games (coach's pick) → redirect `/games` |
| `/training`, `/training/prescribed`, `/training/pattern/:p`, `/training/find/:m`, `/training/theme/:t`, `/training/safety`, `/training/skill/:id`, `/training/geometry*`, `/openings`, `/openings/:key`, `/openings-overview`, `/endgames/...`, `/reply-check`, `/opening-walkthrough` | **fold into Learn**: stay as deep links Learn opens, out of the nav |
| `/reflect`, `/replay/:gameId`, `/recover/:gameId` | **fold into Games** (reflection and guided moments live in the review) |
| `/coach/moments/:topic` | **keep** (email → page contract), restyled later |
| `/daily-fix/drill`, `/mission/:id` | fold into Home's short task, or retire: Mohit's call |
| `/weaknesses`, `/challenge`, `/training/motif/:m`, `/plateau-breaker*`, `/game-old/:id`, `/prototype/interactive-moment`, `/calculation-test` | **retire**: redirect to the nearest page; code stays for now |
| `/coach`, `/focus`, `/dashboard`, `/today`, `/journey`, `/training/quiz/:k` | already redirects; keep (`/focus` is used by notifications) |

**Rollout**
- Behind a per-user flag. The test player's account first; Mohit reviews it live through
  admin view-as and decides whether he would pay.
- Nobody else sees it until he says so.

**Rules carried**
- No numbers in player text; simple English.
- Every chess claim comes from Stockfish or a verified detector.
- The model writes English, never chess.
- No cross-player comparison in player text.
- Nothing links to an empty page.

---

## 4. Explicitly out of scope (V1)

- **Payments or a paywall.** Payments stay off. Which page is paid (the opening file is
  the candidate) is tested later with a price shown to existing users.
- **Turning the Maia opponent on in prod.** It is measured first (speed and play quality)
  and is Mohit's call.
- **Deleting any old page's code.** Retired routes redirect; deletion is a later cleanup.
- **New detectors.** V1 uses what is verified today; gaps are recorded, not papered over.
- **Model-written chess explanations,** including positional "why" sentences the why engine cannot prove.
- **Emails, push notifications, a mobile app,** and a browser extension for the sitting guard.
- **Buying servers.** That is decided separately; V1 must also run on the PC workers.
- **Redesigning Play with Coach itself,** beyond starting from a given position.

---

## 5. Success criteria

1. **Fast between games.** When a worker is up, a finished game's read is ready within a
   median of 2 minutes and a 90th percentile of 5 minutes, measured from the PGN end time
   to the player-file write. A repeat page load takes under 1 second; a first load under 2.
2. **It changes play.** For flagged players, the active habit shows up less often in their
   own games over three weeks than in their baseline weeks (per-game check from
   `focus_lock`). The size of drop that counts is locked from the baseline distribution
   before launch (`/lock-via-data`), not picked now.
3. **They come back between games.** The share of a player's games followed by a
   ChessGuru visit before their next game. Baseline in the first two weeks, then a
   locked target.
4. **True at every level.** On two or more real players per band, every block on every
   page renders true content or its honest empty state. A script checks this, with a
   negative control that must fail.
5. **Mohit's verdict.** He reviews the test player's account live and answers "would I
   pay for this". Nothing widens without a yes.

---

## 6. Open questions

1. **Where does the player file live?** Extend `coach_states` (already per-user, already
   written by the worker) or a new read-model collection? *Unresolved because:* both
   work; extending risks mixing state with cache. *Unblocking:* read every writer of
   `coach_states`, then decide with Mohit.
2. **Habit-level opening leaks.** Matching the same idea across positions (his ...Bg4 in 18
   games vs 3 exact repeats) should need far fewer games. *Unresolved:* not measured.
   *Unblocking:* run the definition on the same 53 players, all four bands, with
   precision checked by hand on a sample.
3. **What counts as a sitting, and when to say stop?** The research used a 45-minute gap.
   *Unblocking:* look at the distribution of gaps and of score by game number across all
   players, per band, then lock.
4. **"Same idea as before" — how far back, and by what match?** *Unblocking:* measure how
   often a game's deciding mistake matches one from the previous N games, using
   `user_pattern_events`, per band.
5. **Fold or retire:** `/daily-fix/drill`, `/mission/:id`, plateau-breaker (it holds the
   "one game, one mistake, one rule" idea). *Unblocking:* Mohit.
6. **Maia sparring opponent.** *Unblocking:* measure response time and move quality at
   several ratings in a throwaway container, then Mohit decides.
7. **How fast do new games arrive?** The median import is close to immediate, but the
   90th percentile is 5.3 h. *Unblocking:* read the auto-sync schedule and find what the
   slow cases have in common.
8. **Where does the academy coach's note live?** Next to `reflection_sessions`, or on the
   game? *Unblocking:* check the academy schema with the coach-plan code.

---

## 7. Pre-code requirements

- Mohit signs this document, including every row of the route table.
- A clickable mock of all five pages, plus the academy view, built from the test player's
  real games, is reviewed on the canvas.
- Questions 1–4 are answered with measurements, and their numbers are locked through `/lock-via-data`.
- The fast-lane latency is measured on the PC workers with the newest-game priority set
  by hand on one game.
- `/audit-pre-code` passes before the first file.
- Mongo (tunnel on 27018) is reachable for the measurements.
