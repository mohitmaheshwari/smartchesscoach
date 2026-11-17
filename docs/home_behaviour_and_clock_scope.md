# Home: how you played as a person, and what to play

Status: SIGNED 2026-11-17 (Mohit: "let's build that too", after the dry run
and the time-control measurements of the same day).

Mohit, 2026-11-17: "home page should also evaluate your behavioural detectors
... chess also brings in your personality on how you react", and "if you find
more games I lose on time or lose with faster moves, you should recommend me
not playing bullet or blitz ... that's the sort of coaching I am looking for".

## 0. Existing surfaces audit

| What exists | Where | What it gives today | Decision |
|---|---|---|---|
| Coach-pages Home | `HomePageNew.jsx` coach-pages branch: CoachPlanCard, LastGameCard, BetweenGamesPanel | Plan, last game's deciding move, "Before your next game" (sitting note, last-game note, positions to play) | **EXTEND** BetweenGamesPanel |
| Player file | `services/player_coach_file.py`, written by the worker after each game | Everything the coach pages read | **EXTEND** with two fields |
| "The clock, not the board" badge | `LastGameCard.jsx` | That the clock decided the last game | Keep; it says what happened, not what to change |
| Clock finding ("lost N games you were winning, on the clock") | `FindingCard`, absorbed into `CoachMovements` | A count across all games | Not shown on the coach-pages Home; different claim (a count, not advice) |
| Time-management plan focus | `gap:time_management:clock_damage_exact` | Makes the clock a plan step for about seven players | Keep; the plan trains it, this line says which clock to play |
| `BehavioralInsightCard.jsx` | components/Home | Imported nowhere (checked 2026-11-17) | Not reused: built on older signals |
| Sitting guard | player file `sitting` | "Long sittings cost you" | Keep, same panel |

## 1. What it is

After each game, Home says one thing about how the player played as a person
in that game (not the chess): they were winning and did not win, or one
mistake brought another soon after. And when the evidence is plain, it says
which clock to stop playing and what to play instead.

## 2. What the player sees

In "Before your next game", under the last-game note:

```
YOU, IN THAT GAME
You were winning, and then one mistake brought another.
After a mistake, stop. Look at their best reply before your next move.

WHAT TO PLAY
Your 3+2 games go badly, mostly on the clock.
Your 5+3 games go better. Play 5+3 instead.
```

Each block shows only when it is true. No counts, no percentages.

Behaviour lines (one at most, from the newest analysed game):
- winning and lost on time: "You were winning this game when your clock ran
  out." / "When you are ahead, play simple moves and keep time on your clock."
- winning, then a mistake chain: "You were winning, and then one mistake
  brought another." / "After a mistake, stop. Look at their best reply before
  your next move."
- winning, not won: "You were winning this game and it slipped away." / "When
  you are ahead, check their replies before every move."
- a mistake chain: "One mistake brought another soon after." / same advice.

## 3. In scope (V1)

- `services/play_advice.py`: `behaviour_line` and `clock_advice`, pure.
- Player file schema 8: `behaviour` and `clock_advice`, built with the file
  (worker after every game, and on first visit).
- Clock advice reads analysed and unanalysed games (`games` PGN TimeControl,
  and `skipped_game_records` for bullet).
- BetweenGamesPanel renders both blocks.

## 4. Explicitly out of scope (V1)

- Speed after a blunder (no pattern in the dry run: as many faster as slower).
- "Use your time in rapid" (Mohit thinks as fast in 15+10 as in blitz):
  measured once, no gate yet.
- The behaviour line as a stable trait ("you always..."): only one player has a
  similar-rated comparison. V1 talks about the last game only.
- Players without the coach pages (BetweenGamesPanel is coach-pages only).

## 5. Success criteria

- Clock advice: the share of the player's games at the named clock falls in
  the weeks after it first shows (read from `games` and skipped records).
- Behaviour: winning positions converted, before and after, for players who
  were shown a "winning" line (the plan's conversion measure).

## 6. Measured decisions (2026-11-17, read-only over all 79 players)

- Clock advice gates swept: score gap 0.08 / 0.12 / 0.15 below the best clock
  (in both halves of the games at that clock) and on-time share 0.4 / 0.5 /
  0.6. Users flagged: 11 / 10 / 8, 8 / 7 / 5, 7 / 6 / 4.
  Locked: gap 0.12, share 0.5 (half the losses on time is what "mostly on the
  clock" says). 7 players: five "1+0", one "0+1", one "3+2" (Mohit, 3+2 at
  35% vs 5+3 at 54%, 28 of 52 losses on time, mistake rate 1.76 vs 1.87 per
  40 moves). Minimum 20 games per clock.
- Mohit's 2+1 (33%, 11 of 16 losses on time) is not named: his first twelve
  scored 17%, his last twelve 50%, so the both-halves gate holds it back.
- Behaviour on every player's last analysed game: no line 45, chain 19,
  winning and chain 10, winning and clock 3, winning 2. A line on 34 of 79
  last games: frequent enough to matter, not on every game.

## 7. Every player's Home (Mohit, 2026-11-17: "can you do it for all users home page?")

- The two lines now show on the normal Home too, under the last game, in a
  "Before your next game" panel (`HomeCoachLines`, `GET /api/home/coach-lines`).
  Coach-pages players keep reading them from the player file; nothing changes
  for them.
- One function makes both: `player_coach_file.coach_lines`. The player file
  calls it; so does `home_lines`, which reads only what the two lines need.
- Not the whole player file for everyone: building it also locks a plan week
  (`player_plan_weeks`) the player never sees, so a later plan would start
  with a week he was never shown.
- Kept in `home_coach_lines` per player and rebuilt only when his newest game,
  his analysed-game count or his skipped-game count changes.
- Dry run before deploy, read-only, all 79 players with games: clock advice 7,
  behaviour line 36 (chain 19, winning and chain 12, winning and clock 3,
  winning 2). The 8 players with a current player file got identical lines from
  both paths. First build per player: median 0.06 s, slowest 4 s; later loads
  read the stored answer.
- Not shown on the CurriculumHome branch (admins without the coach pages while
  PERSONAL_CURRICULUM_ENABLED is on).
