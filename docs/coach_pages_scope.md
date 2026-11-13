# One coach, five pages — scope

Mohit, 2026-11-12: *"we have to talk about home page, progress page, learnings page, you
know how a coach handles things, different pages, game reviews, super fast stuff, how??"*
and earlier the same day: *"what would this guy pay us even 1 dollar for... think what a
chess player really does"*, *"whatever we build should work for everybody and at every
level"*, *"we will buy better servers, so performance is not the issue"*.

Mission unchanged: **the academy head coach's assistant, and a coach for the player.**

Status: **Mohit, 2026-11-12: "go ahead", then "don't make mockups, work on the live site directly" and "build everything". Built behind the per-user flag; see "Build record" at the end. The mock requirement in section 7 is superseded by his instruction.**

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

- **Per-game habit check: in code, but never live.** `update_focus_lock_compliance` in
  `analysis_worker.py` scores every new game against the active lesson, but it reads
  `coach_states.focus_lock`, and **`coach_states` has 0 documents in prod** (counted
  2026-11-12). It has never run for anyone. V1 must give it real state, or replace it.
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

### Speed today (measured 2026-11-12, newest 284 jobs for just-finished games)

A fast lane already exists (`journey_service.py:1466-1505`):
- a game finished minutes ago is queued at priority 10, ahead of background work;
- a new user's first import gets 20–30.

| Step, for a just-finished game | Median | 90th percentile |
|---|---|---|
| game ends → our sync queues it | 3.5 min | 6.2 min |
| waits in the queue | 3.7 min | 119 min |
| analysis job (208 of 284 ran on the 1-CPU server workers) | 6.6 min | 16.4 min |
| **game ends → analysis done** | **11.5 min** | **105 min** |

End times come from the PGN `EndTime` tag, present on 232 of 284 games.

Players start their next game a median of **10–16 minutes** after the previous one
started (all bands, below), so the gap between games is only a few minutes. To be read
between games, the read must be ready in about 2 minutes, not 11.

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
- **Progress:** each habit's state from his games, the kept shelf, where you started →
  where you are. It extends `/progress`.
  - The per-game check comes from the `focus_lock` code, given real state for the first
    time (it has never run; see section 0), or replaced.
  - The resolve states come from `pattern_decay_service`.
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

Questions 1–4 were measured on 2026-11-12. Scripts are in the session scratchpad:
`q234.py`, `latency2.py`, `howmany.py`.

1. **Where does the player file live? → Recommendation: a new read-model collection.**
   - `coach_states` is empty in prod (0 documents). Its writers expect `focus_lock`
     semantics; it is state, not cache.
   - The player file is a cache rebuilt from canonical collections, so it gets its own
     collection, with one writer (the worker) and an index on the player id.
   - *Still open:* Mohit's OK on the name and on retiring the never-live `focus_lock` path,
     versus reviving it.

2. **Habit-level opening leaks → much faster, needs a precision rule.**
   - The habit is the same move idea (same piece to the same square) in the same opening
     family, in 3+ games and at least 2 different positions, with an average loss of 50+.

   | Players with a leak, newest 20 games | Exact position | Habit |
   |---|---|---|
   | under 1000 | 9/26 | 21/26 |
   | 1000–1399 | 3/11 | 8/11 |
   | 1400–1799 | 0/9 | 7/9 |
   | 1800+ | 4/7 | 7/7 |

   - Habits show up from about 10–20 games, at every band. The test player's own top two are
     ...Bg4 (17 games, 16 positions) and ...Re8 (6 games) in his Modern.
   - **Too loose as written:** at 60 games the median player has 10–20 "leaks".
   - Under 1000, the costly "habit" is often castling, Ng5 or Re1 with a large average loss.
     That is a piece left loose while making a normal move, which is a safety habit, not
     opening knowledge.
   - **V1 rule (to lock with `/lock-via-data`):**
     - show the top one to three by total cost;
     - check a hand-labelled sample;
     - send safety-shaped leaks to the safety habit instead of the opening file.
   - Average loss of habit keys seen in 3+ games:

     | Band | Median | 90th percentile |
     |---|---|---|
     | under 1000 | 31 | 140 |
     | 1800+ | 19 | 64 |

     So one cut for every band would be wrong; the cut is per band.

3. **Sittings → the stop signal must be personal, never a general rule.**
   - Across all 53 players, the score barely changes with the game's number in the sitting,
     for every gap definition from 20 to 90 minutes:
     - games 1–3: 0.50–0.54;
     - games 4–6: 0.51–0.56;
     - game 7 onwards: 0.47–0.52.
   - After a loss: 0.48–0.51, against 0.53–0.54 after a win.
   - The test player's drop (0.45 from game 7 onwards) is his own, not a law of chess.
   - **V1 rule:** say "good place to stop" only when the player's own history shows the drop
     with enough games behind it (the count to be locked). Otherwise say nothing.
   - *Caveat:* rating-based pairing pulls every score toward 0.5. Move quality by game
     number would be a sharper test and is the next measurement.

4. **"Same idea as before" → the obvious definition fails the control.**
   - A game's 100+ pattern miss (`user_pattern_events`, 23 pattern ids) is found in the
     player's own previous games no more often than in a random same-band player's:

     | Band | N=5, own | N=5, another player | N=10, own | N=10, another player |
     |---|---|---|---|---|
     | under 1000 | 0.86 | 0.87 | 0.94 | 0.95 |
     | 1800+ | 0.85 | 0.81 | 0.94 | 0.93 |

   - Pattern ids are so common that "same as before" would be true for anyone, so it says
     nothing about him. **It must not be shown on pattern ids.**
   - **V1:** "same as before" needs a narrower key that beats this control before it ships:
     - the habit key from Q2 (same idea, same opening family, same side); or
     - the same piece and square relation in the same phase.
   - *Check needed (inference):* the "earlier game" sentence already shipped on review cards
     (fd75da5b) is built on `user_pattern_events`. Its sentences are true, but by this
     measurement they may not be distinctive. That needs its own check against this control.
5. **Fold or retire:** `/daily-fix/drill`, `/mission/:id`, plateau-breaker (it holds the
   "one game, one mistake, one rule" idea). *Unblocking:* Mohit.
6. **Maia sparring opponent.** *Unblocking:* measure response time and move quality at
   several ratings in a throwaway container, then Mohit decides.
7. **Getting from 11.5 minutes to about 2.**
   - Measured: the sync notices a finished game in a median of 3.5 min; the job then takes
     6.6 min, mostly on the 1-CPU server workers.
   - Three levers, each to be measured, not assumed:
     - **notice faster:** poll active players more often, or use the platforms' game streams;
     - **run live games on the fast workers** (PC now, new servers later);
     - **write the read right after the Stockfish pass,** before captions and profile
       updates (about 100 s of each job, measured 2026-11-11).
   - *Unblocking:* time each lever on one live game.
8. **Where does the academy coach's note live?** Next to `reflection_sessions`, or on the
   game? *Unblocking:* check the academy schema with the coach-plan code.

---

## 7. Pre-code requirements

- Mohit signs this document, including every row of the route table.
- A clickable mock of all five pages, plus the academy view, built from the test player's
  real games, is reviewed on the canvas.
- Questions 1–4 were measured on 2026-11-12 (section 6). Before code, their numbers are
  locked through `/lock-via-data`:
  - the per-band leak cut and a hand-checked precision sample;
  - the personal stop rule's minimum games;
  - a "same as before" key that beats the other-player control.
- The three speed levers in question 7 are each timed on one live game.
- `/audit-pre-code` passes before the first file.
- Mongo (tunnel on 27018) is reachable for the measurements.

---

## Build record (2026-11-12)

Built on branch `claude/coach-pages`. Everything sits behind `BETWEEN_GAMES_USERS`, and is
also open to a super-admin viewing any player through view-as (`/auth/me` says
`coach_pages`), so every level can be reviewed live without anyone else seeing it.

**The player file, schema 2** (`services/player_coach_file.py`, `services/player_coach_habit.py`)
- **Openings count only real opening choices.** An instance is dropped when the better move
  was a capture or a check (a missed shot), or when the move left a piece hanging (a safety
  slip). Across 50 players these were 40% of instances under 1000 and 10-35% above. After the
  fix, 42 of 50 players still have a habit, against 50 before.
- **Traps.** A trap counts by position, so a transposition into the same setup is the same
  trap. The side a trap wins for is decided by Stockfish (depth 18, at the end of the trap
  line, 150+): `data/trap_roles_verified.json`.
  - The engine decides 30 non-plan traps out of 55.
  - The stored `trap_color` field is wrong on three of them.
  - Coverage is thin: 5 of 78 players have a trap to show, because the library rarely
    meets what they play (exact move order found 51 of 3,196 games). This is recorded as a
    gap, not padded.
- **"Same as before"** is said only when the deciding move matches one of his opening
  habits (same side, same opening, same move idea).
  - Against the other-player control, own vs other: 0.08 vs 0.01 (<1000), 0.05 vs 0.02,
    0.11 vs 0.14 (1400-1799, n=28, fails), 0.11 vs 0.00 (1800+).
  - The habit requirement (3+ games) is stricter than this key alone.
- **The habit he trains** comes from `coach_plan_service`, the academy plan's engine, using
  PLAN-trusted detectors only.
  - It is chosen from his newest 30 analysed games and kept for 14 days while it stays in
    his top three.
  - It has a per-game check against the baseline taken when it was chosen.
- **Progress** covers every trusted problem: his newest 20 games against the 40 before them.
  - The test is a one-sided binomial tail at 0.10, against his own earlier rate.
  - "Better" or "kept" also needs 3+ earlier games with the problem, and "worse" needs 3+
    recent ones.
- **Dry run** on 9 real players (two per band plus the test player), read-only, on the
  server:
  - every player has a habit, progress and positions to play;
  - 7 have an opening habit;
  - 7 had a deciding move in their last game;
  - no digit appears in any player sentence;
  - a build takes 11-21 s.

**Pages**
- **Home:** the sitting line, the last game's repeat line (only when it fires), "watch for"
  (the habit's sign and rule), the costliest opening habit, and two positions to play.
  The last game itself stays on `LastGameCard`.
- **Games:** the coach's pick leads the list; each row opens the review at the deciding move
  (`?move=`); a fresh pick opens at its turning-point chapter.
- **Learn** (`/learn` → `CoachLearn`): the opening file (habits, traps against him, traps he
  can set), the habit he trains (sign, rule, moments with "Play from here" and "See the
  game", and practice through `/training/pattern/:key`), positions to play, and the library.
- **Progress:** "Is it working?" with each habit's state and the kept shelf, shown even when
  the phase-8 journey is off.
- **Play:** any position starts Play with Coach in practice mode from that position.
- **Academy:** the student page shows the same file after consent: sittings, how each habit
  is changing, the opening file and traps. The habit stays with the coach plan above it.
- **Navigation** for coach-pages players: Home, Games, Learn, Progress, plus the Play button.

**Not built in this pass, and why**
- **What the next level plays (Maia):** the human-policy runtime is off in prod and needs its
  model mount; turning it on is Mohit's call (section 4).
- **A reply-check set generated from his positions:** no packet builder exists, since packets
  were hand-frozen. Practice is "play from here" plus the pattern drills.
- **Retiring and redirecting the old routes:** only the navigation changes, and only for
  coach-pages players. Redirects would reach everyone, so they wait for the decision to widen.
- **Speed levers (Q7)** and the per-moment academy coach note (Q8).
- **Ask before telling on Games:** it already exists (`PersonalizedReviewCoach` taps) where a
  game has a personalized plan; it is not extended here.

### Addendum 2026-11-13: the plan on Home, traps from the stored scan

- **The coach's plan** (`services/player_coach_plan.py`) is at the top of Home for
  coach-pages players: a read of how he plays plus up to three steps toward the next level.
  - Steps are ordered by games lost or drawn from level-or-better, across every kind of step:
    a trusted habit, the costliest opening habit, long sittings.
  - The habit being trained wins a tie. Habit-first was dropped after it put a 3-game habit
    ahead of an 8-game opening habit for the test player.
  - "Your last game: this week's step showed up again" is said only when it did. A game where
    it did not is not proof it was kept.
  - The older Home blocks are left out for coach-pages players only.
- **Maia as the "+200" ordering signal: measured, not used.** On 55 players a plan mistake is
  about 5% rarer 200 points up, by Maia. It beat both controls in 16/52 steps at 1000-1399,
  and Maia sees nothing under 1100 or at 1800+.
- **Our own rating:**
  - Move quality ranks players (rho about 0.8) but places them about 275-300 points off.
  - Maia places them about 225-260 off on Chess.com and about 130-180 off on Lichess (small
    groups).
  - Not shown as a number yet.
- **Trap school:**
  - `/learn/traps` covers 24 traps that Lichess players at 1000-1800 actually play to the end,
    with 93 real games, each replayed to confirm the line.
  - The player file's traps now come from `game_analyses.trap_fires` (one source) in four
    cases, judged with the engine's side and the whole line.
  - 36 of 78 players see their own traps, against 5 with the earlier rescanner.
