# Daily coach plan — scope

Status: SIGNED by Mohit 2026-11-18 ("go ahead"). Built in two stages:
- **Stage 1 (built 2026-11-18):** the day card on the coach-pages Home.
- **Stage 2 (waits on the band review in Section 7):** the coach pages for
  every player.

Defaults taken for the questions he left open, which he can overrule:
- Open question 4: academy children get the day card on their own Home; a
  coach view of it comes later.
- Open question 5: the old Home's daily board question is dropped.
- Open question 6, answered: no time zone is stored anywhere (`users` has
  only `country`, on 58 players). The browser sends its own time zone with
  each request, and the day starts at the player's midnight.

Mohit, 2026-11-17/18:
- A coach has a schedule and tasks for each day.
- He also brings new things: a game to review, new traps, openings,
  techniques, and tactics suited to the player's rating.

Decided in the discussion:
- Tasks, not a 2-hour timer.
- The player picks a daily size.
- A day is done when its tasks are done, in one sitting or several.
- Mohit's choices on 2026-11-18 (the two options I did not recommend, both
  taken):
  - This becomes **every player's Home**.
  - Something **new every day**.

## 0. Existing surfaces audit

Every line below was read in code or measured on prod on 2026-11-18, unless
marked unverified.

### What already exists

1. **The coach-pages weekly plan** (Home for players with the coach pages).
   - Renders "Your coach's plan": the read, up to three steps in order with the
     points at stake, and under step one "This week's work": Learn it / Find
     it in your own games (three moments) / Play it (three positions), each
     ticked when done, plus a target for his games
     (`frontend/src/components/Home/CoachPlanCard.jsx:47-112`,
     `backend/services/player_coach_plan.py:115-133`).
   - One step is locked per week, and a Sunday verdict is given from his games:
     kept / not yet / no chance (`backend/services/player_plan_week.py:1-38`).
   - Work done is recorded per week in `plan_activity`. On prod that is 3 rows
     from 1 player, all in the week of 2026-11-16.
   - Reach: the coach pages are behind `BETWEEN_GAMES_USERS`, which lists 7
     players on prod, plus a super-admin using view-as.
   - Teaches only from his own mistakes and openings. Nothing new.
2. **Learn page** (coach pages): his opening file, the habit he trains, play
   positions, and a library of links (`frontend/src/pages/CoachLearn.jsx:45-143`).
3. **The personal curriculum** (`CurriculumHome`, the Home for eligible players
   without the coach pages).
   - One main lesson per visit, plus at most one review. No task list, no daily
     size, no record of days.
   - The new topic comes from `engine2_skill_builder.pick_next_skill(memory,
     rating)` (`:467`), over `data/coaching/skill_tree.json`: 43 topics (24
     openings, 8 endgames, 3 trap sets, 3 concepts, 2 mate patterns, 2 traps,
     1 coached play), each with a rating range.
   - It does not use the openings he plays to choose a topic.
   - Live on prod: `PERSONAL_CURRICULUM_ENABLED=true`, roles `admin,super_admin`,
     plus a cohort through `complete_coaching_access`. The cohort's size is
     unverified; a 2026-10-14 doc said 48 players.
4. **Daily Fix** (`backend/routes/daily_fix.py`).
   - Freezes one assignment per day and keeps a day streak with one grace day
     (`users.practice_streak`).
   - No page shows it. Its scope is still a draft.
5. **`/api/today`** (`compose_today`: a fix plus a "learn next"). Its card
   `TodayHero.jsx` is not mounted anywhere.
6. **Missions** (`behavioral_missions`): a dated set of positions from his own
   games, graded on the server. Reached after a loss.
7. **Teaching content a task can open**:
   - Trap school `/learn/traps[/:slug]`: 24 traps, with his own traps first.
   - `traps.json`: 55 traps over 28 openings. Practised at
     `/play-with-coach?trap=<key>`.
   - Opening lessons `/openings/:key`: 79 openings.
   - Endgames `/endgames/:category/:lesson`: 20 lessons in 7 categories.
   - Lichess puzzles by theme `/training/theme/:topic`, at his rating −150 to
     +250. Only 4 topics today.
   - Not available: games by strong players to review, and puzzles chosen by
     opening.
8. **What was taught, and when**: `coach_memory.learning.skills[]` keeps per
   topic: seen, correct, wrong, first seen, last seen, learned at
   (`services/coach_memory.py:52-96`).
9. **Trap lessons from games** (`docs/trap_lesson_from_games_scope.md`, another
   session): draft awaiting Mohit's sign-off.

### Supply of new material, measured

- **Topic tree.** Topics whose rating range includes a player at:

  | Rating | Topics | Kinds |
  |--------|--------|-------|
  | 800 | 4 | 2 mate patterns, 1 trap, 1 coached play |
  | 1200 | 13 | 7 openings, 5 endgames, 1 trap |
  | 1600 | 20 | 13 openings, 3 trap sets, 3 endgames, 1 concept |
  | 2000 | 11 | 9 openings, 2 concepts |

  With something new every day, the tree alone runs out in under a week at
  800 and in under three weeks at 1600.
- **Lichess puzzle themes.** A sample of 30,000 of the 4,423,645 puzzles gives
  42 teachable themes with enough puzzles each. Their typical puzzle rating
  makes a ladder:
  - back-rank mate ~930, smothered mate ~940, mate in one ~940
  - mate in two ~1110, skewer ~1240, fork ~1300, rook endgame ~1350
  - hanging piece ~1390, discovered attack ~1400, deflection ~1480, pin ~1560
  - attraction ~1600, intermezzo ~1600, pawn endgame ~1610, double check ~1630
  - trapped piece ~1680, clearance ~1700, zugzwang ~1740, quiet move ~1840

  Lichess puzzle ratings are not game ratings. The ladder gives the order; the
  starting point per player needs locking (Section 6).
- **Traps:** 24 + 55, chosen by the openings he reaches.
- **Endgames:** 20. **Openings:** 79.

### Decision: EXTEND, and turn the coach-pages Home on for everyone

- Today's tasks are added to the coach-pages Home, made from this week's plan
  (fix) plus one new item a day (learn).
- The coach-pages Home then becomes every player's Home.
- CurriculumHome and the older Home stop being shown to players.
- No third "today" system. `TodayHero` and Daily Fix stay unshown.

## 1. What it is

Every day, Home gives the player a short list of chess work, like a coach
leaving a schedule.
- **Fix:** something from his own games, taken from this week's plan step.
- **New:** one new thing at his level each day. A tactic idea such as a fork or
  a pin, a trap in an opening he actually plays, an endgame technique, or an
  idea in one of his openings. Each comes with a short explanation and
  positions to solve.
- **Look back:** a quick check, a few days later, that an earlier new thing
  stuck.
- **Play:** games to play at the clock that suits him, or the lesson's position.

He picks how big his day is. The day is done when the tasks are done, whether
in one sitting or in pieces. Home shows which days this week he did his work,
and never counts what he missed. Later, his games show whether the new things
stuck: a trap he learned that he then sets, an opening move he now plays.

## 2. What the user sees

Home, for every player with games. Example: a 1600 player, Normal day.

```
Good evening, Mohit.                                      WEDNESDAY 18 NOVEMBER

┌ TODAY ────────────────────────────────────────────────────────────────────┐
│ Your day: Normal  ·  change                                               │
│                                                                           │
│ ✓ FIX     Find the better move in your game from Monday.            Open →│
│           Your piece was left where it could be taken.                    │
│                                                                           │
│ ○ NEW     The pin. A piece cannot move without exposing                   │
│           a more valuable piece behind it.                                │
│           Read the idea, then solve positions at your level.       Start →│
│                                                                           │
│ ○ LOOK    Last Saturday you learned the skewer.                           │
│   BACK    One position to show it stuck.                           Solve →│
│                                                                           │
│ ○ PLAY    Two games at 5+3. Your 5+3 games go better than 3+2.            │
│                                                                           │
│ This week   Mon ●   Tue ●   Wed ◐   Thu ·   Fri ·   Sat ·   Sun ·         │
└───────────────────────────────────────────────────────────────────────────┘

┌ YOUR COACH'S PLAN ── (existing card: the read, the steps, the stake) ─────┐
┌ YOUR LAST GAME ───── (existing) ──────────────────────────────────────────┐
┌ BEFORE YOUR NEXT GAME ── (existing: you in that game, sitting note) ──────┐
```

Short day: Fix + New. Normal: Fix + New + Look back (or Play). Long: all four,
with more positions.

When every task is ticked:

```
┌ TODAY ── Done for today. ─────────────────────────────────────────────────┐
│ ✓ FIX  ✓ NEW  ✓ LOOK BACK  ✓ PLAY                                         │
│ Tomorrow: something new, and the next step from your games.               │
│ This week   Mon ●   Tue ●   Wed ●   Thu ·  ...                            │
└───────────────────────────────────────────────────────────────────────────┘
```

A day with nothing done stays a plain dot. There is no red, and no "you
missed" text.

A new trap, for a player who reaches the Italian as Black:

```
│ ○ NEW     A trap in the Italian, which you play as Black.                 │
│           White can lose a piece on move six if he grabs the pawn.        │
│           See it, then play it against your coach.                 Start →│
```

The pages these open already exist: theme puzzles, trap school, opening
lessons, endgame lessons, game review at the move, and Play with Coach.

## 3. In scope (V1)

**Home for everyone**
- The coach pages are turned on for every player (`BETWEEN_GAMES_USERS="*"`).
  Home alone is not enough: the plan's links open Learn, Games and Progress,
  which are coach-pages pages.
- Players without games keep the current first-session Home.
- A player file is built for every player with games. It is rebuilt after each
  game, as today.

**The day card**
- The day's tasks are fixed when the day starts, so they do not change
  mid-day.
- The day starts in the player's own time zone where it is known, and in India
  time otherwise.
- Daily size: Short / Normal / Long. Remembered per player, changeable on the
  card. Normal by default.
- Task kinds:
  - **Fix:** from this week's plan step: a moment to find, or a position to
    play. Once the week's work is done, it comes from the next step. When
    there is no plan (12 of the 79 players with games today), it is "review
    your last game at its deciding move".
  - **New:** one new item every day, never repeated. Where it comes from:
    - tactic themes along the Lichess ladder from his level
    - traps in openings he reaches
    - endgame lessons in his range
    - ideas in openings he plays, from the topic tree and opening lessons

    The kinds rotate, so no kind comes two days running when another is
    available. Each item has a short plain-English explanation and positions
    at his level.
  - **Look back:** one position on an item taught a few days earlier.
  - **Play:** the clock advice when there is one, otherwise "play the
    position from today's new item against your coach".
- A task is ticked when he does it. Each kind has its own proof of "done":
  - a puzzle set: solved
  - a game moment: opened
  - a position: played
  - games at a clock: played and imported

  Being done in pieces works, because ticks are saved as they happen.
- A week row with a dot per day: done, part done, nothing. Never a count of
  missed days.

**Teaching record and check**
- Every new item and its outcome go to `coach_memory.learning.skills` (topic,
  date taught, solved or not), so nothing repeats.
- Look back answers are recorded there too.
- In-game checks for V1, where we can already prove them:
  - a trap taught → whether he later sets it, springs it or falls for it
    (`trap_fires`)
  - an opening idea taught → whether he later plays the lesson move when he
    reaches the position (the weekly plan's opening check)

**Content**
- The tactic-theme ladder: about 30 themes picked from the 42 measured, each
  with a two-sentence explanation in very easy English, checked against the
  puzzles it serves.
- A theme puzzle page for any of those themes. Today it exists for only 4
  topics.

**Old Homes**
- CurriculumHome and the older Home blocks are no longer rendered for players.
  The code stays until a later clean-up.

## 4. Explicitly out of scope (V1)

- **Timers or minutes tracked.** Done means the tasks are done.
- **Reviewing games by strong players.** We have no source yet; the free
  Lichess game database is a later step.
- **Puzzles chosen by opening.** No such route exists yet.
- **Academy coach editing a child's day, or a parent's weekly note.** Option 3
  from the discussion: later, with the first paying academy.
- **Reminders by email, WhatsApp or push.**
- **Rewards, badges, points, leaderboards.**
- **In-game checks for tactic themes and endgames.** V1 checks them with Look
  back positions only. In-game checks exist for traps and openings only.
- **Deleting CurriculumHome, TodayHero, Daily Fix and the old Home blocks.**
  Hidden in V1; deleted later.
- **Lessons written by the model.** The model may smooth words, never the chess
  (standing rule).
- **The trap-lessons-from-games build** (another session's scope). The daily
  New task will offer its "Learn this trap" pages once that ships.

## 5. Success criteria

Measured over the first four weeks. The numbers are proposals, to be locked
after the first week shows the baseline:
- **Adherence:** at least half the players who open Home in a week finish the
  whole day on two or more days of that week. Today there is no daily work to
  finish, and `plan_activity` has 3 rows from 1 player.
- **It sticks:** Look back positions on taught items are solved at least 60% of
  the time. A chosen theme or position that stays far lower gets fixed or
  removed.
- **It reaches the games:**
  - Of traps taught, the share set or sprung in a later game is higher than
    before teaching (from `trap_fires`).
  - Of opening ideas taught, the share of later games that reach the position
    and play the lesson move is higher than before.
- **The plan still works:** the weekly verdict "kept" is at least as frequent
  as in the four weeks before launch, so the daily card has not pulled work
  away from the plan.

## 6. Open questions

1. **Daily size:** how many tasks and positions make Short, Normal and Long?
   - Why unresolved: there is no data on how long each task takes.
   - Unblocking: measure the time on each kind of task on the coach-pages
     players before the wide release, then lock.
2. **Where each player starts on the theme ladder.**
   - Why unresolved: Lichess puzzle ratings are not game ratings.
   - Unblocking: compare the solve rates of players at each band on each
     theme's puzzles (lock-via-data), then lock the start per band.
3. **Look back spacing:** how many days after teaching.
   - Why unresolved: no data of ours.
   - Unblocking: start with a common spacing (3 days, then 10) and read the
     solve rates after two weeks.
4. **Academy children:** does a child get the same day card on their Home, and
   does the coach see it in the academy view?
   - Why unresolved: not discussed.
   - Unblocking: Mohit's input.
5. **The old Home's daily board question** (`CoachMovements`, which reaches
   non-coach-pages players today): drop it, or turn it into a New task?
   - Unblocking: Mohit's input.
6. **Time zone:** is a player's time zone stored anywhere?
   - Why unresolved: not checked.
   - Unblocking: look in `users` and the import data before the build.

## 7. Pre-code requirements

- Mohit signs this document.
- **Every band reviewed before everyone gets the coach pages.** Rebuild the
  player file for all 79 players with games (today 53 files are on schema 5,
  9 on schema 7, 17 on schema 8). Mohit reviews the plan on two players per
  band through view-as. Today 67 of the 79 have a plan; the 12 without are all
  in 1000-1399.
- **Server room.** Building and refreshing a player file for every player adds
  work to a shared box. That box showed about 70% CPU steal on 2026-11-17.
  Measure the per-game refresh cost first.
- Theme ladder start (open question 2) locked with data.
- About 30 theme explanations written and checked.
- Open questions 1, 4, 5 and 6 answered.
- `/audit-pre-code` passes.


## 8. Build record, Stage 1 (2026-11-18)

Built:
- `services/daily_plan.py` and `GET /api/daily-plan`, `POST
  /api/daily-plan/tick`, `POST /api/daily-plan/size`, behind the coach-pages
  gate. View-as shows the day without writing it.
- `DayCard` on the coach-pages Home, above the plan.
- Themed puzzles for any of the 32 ideas in `data/daily_themes.json`, through
  the existing puzzle page: `/training/theme/theme-<idea>`.

Where the build differs from the draft:
- **Size is the number of tasks:** Short 2, Normal 3, Long 4. A New idea is
  always a set of 6 puzzles. Both are provisional until open question 1 is
  measured.
- **What was taught is read from the day documents** (`daily_plans`), not from
  `coach_memory.learning.skills`. Opening and endgame lessons still record
  themselves there when opened, as before.
- **An idea counts as done once it has been done.** One that was offered but
  not done comes back on a later day of its kind.
- **Where a player starts on the ladder.** An idea is offered when:
  - Lichess has at least 200 of its puzzles in the player's own puzzle window
    (counted over all 4,423,645 puzzles, `data/daily_theme_supply.json`); and
  - its typical puzzle is no more than 400 below his rating.

  Both are provisional (open question 2). Ideas available at 700, 900 and
  1200: all 32. At 1500: 26. At 1800: 19. At 2100: 4.
- **Bug fixed in the existing theme drill:** below 600 its window was empty.
  Those players now get the easiest band, 600 to 850.

Dry run on prod before deploy, read-only, all 79 player files:
- Fix 72, New 77, Play 79.
- New on day one: 74 ideas and 3 traps. Two players under 600 had no New, which
  is the bug above.
