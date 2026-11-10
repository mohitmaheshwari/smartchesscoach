# First look — the coach's read of your first game

Status: **DRAFT, awaiting Mohit's sign-off. No code until signed.**
Written 2026-11-10.

Mohit, 2026-11-10: *"i need our chessguru to start building real analysis after
user playing one game itself … think like a human coach … if I hire a coach,
what would the coach's actions be for me?"*

## The fact that shapes everything

Measured earlier on 48 players with 15+ analysed games (`docs/play_first_scope.md`
on branch `codex/first-coaching-session-v1`, commit c7bf0587): the top weakness
found from **one game matches the player's whole history 34.4%** of the time;
3 games 46%, 5 games 49.8%, 20 games 71.3%.

So after one game a coach (human or ours) can only form **guesses**. A good human
coach knows this. They ask questions at the moments that mattered, form one or
two impressions, give one thing to try, and check over the next games. That is
the product. Calling a one-game guess "your weakness" would be wrong two times in
three.

## 0. Existing surfaces audit

| Surface | What it already does (render level) | Overlap |
|---|---|---|
| `/journey/first-aha` → `/game/:id` (`routes/journey.py:190`, `Onboarding.jsx:208`) | After sign-up, queues the newest loss and opens the normal game review | The entry point. Today it lands on a move-by-move review, not a coach's read |
| Game story (`services/game_story.py:333`, `GameStoryPanel.jsx`, `LastGameCard.jsx`) | Good and bad moments of one game, shown at the top of the review and on home | Moment picking, including **good** moments |
| Review tap reflection (`services/review_tap_reflection.py`, `PersonalizedReviewCoach.jsx:351` → `ReflectFlow`) | "Before I explain": taps, then "find the move", then a cause-specific reply. Only on landing and missed-tactic moments, only behind the personalized-review rollout flag | The question-before-answer step |
| Coach plan (`services/coach_plan_service.py`: `rank_problems`, `choose_moments`, `cause_from`, `RULES`; `ClassReflect.jsx`) | Weekly plan for academy students: three moments, cause from "seen in game" × "found when asked", one rule, week check | Cause logic, rules, confirmation loop. Academy-only and coach-approved |
| First coaching session (branch `codex/first-coaching-session-v1`, not merged) | Coaching through a diagnostic puzzle before any game is analysed | Same goal (first contact), different input (puzzle, not the player's game) |

Missing everywhere: a **mixed set** of moments for one game (turning point, missed
chance, good decision); the **clock** as an input to the cause; **impressions as
guesses** that are later confirmed or dropped; any of this for a player who is
not in an academy.

**Decision: EXTEND.** The first look is a layer on the existing game review for
the player's first analysed game, built from the parts above. No new detectors
and no new page.

## 1. What it is

When a player's first game is analysed, the coach goes through it like a human
coach would. It picks up to three moments that mattered. At each one it asks
what the player was thinking and whether they can find a better move, before
showing the answer. From the answers, the board and the clock it says why each
moment went the way it did. Then it gives one or two first impressions, clearly
marked as guesses, and one thing to try in the next game. Over the next few
games it tells the player whether each impression held up or was dropped. A
confirmed impression becomes the start of their training plan.

## 2. What the user sees

**Opening card** (top of the review, first analysed game only):

```
┌─ First look ──────────────────────────────────────────────┐
│ I went through your game against rook_lover.               │
│ Three moments decided it. Before I tell you what the       │
│ engine thinks, show me what you saw.                       │
│                                                             │
│   The turning point  ·  A chance you had  ·  A good call    │
│                                          [ Start → ]        │
└────────────────────────────────────────────────────────────┘
```

**Moment: the turning point** (board before the player's move; the move is not shown yet):

```
You played Qh5 here. What were you going for?
 [ Attack ]  [ Defend ]  [ Bring a piece out ]  [ Get out of danger ]  [ Not sure ]

→ "Okay. Look again. Is there a better move?"   (board is clickable)

  found it:  "You found it straight away, so you know this idea.
              In the game you moved quickly and didn't look for it."
  missed it: "This one is new to you. Here's the idea: your knight
              on c3 is the piece that can take on d5."
```

**Moment: a good call:**

```
You took the pawn on e5 and kept your queen safe.
That's exactly what a strong player does here.
```

**Summary** (after the moments):

```
What I noticed — a first look
One game isn't enough to be sure, so treat these as my guesses.

 • I think you sometimes move before checking what your opponent
   can take. When I asked, you found the better move, so this is
   about looking, not about knowing.
 • I'll also watch your quick moves in the middle of the game.

Try this in your next game
Before every move, check which of your pieces can be taken.

I'll tell you after your next games whether I was right.
```

**Games two to five** (a card at the top of each review):

```
Update on what I noticed
 • Moving before checking what can be taken: it happened again
   in this game. [ Show me ]  Still watching.
 • Rushing in the middle game: not seen in your last games.
   I've dropped this one.
```

**Two starting points.**

- *Username given (Lichess or Chess.com)* — the main path. Pull the last five
  games in the player's main time control (wins and losses), give them a quick
  first-pass analysis so the first look is ready in minutes, and keep pulling and
  fully analysing older games in the background. The newest game gets the full
  conversation ("what were you going for?" + "find a better move"); older games
  get "find a better move" only, because nobody remembers what they were thinking
  a week ago. Impressions are then confirmed or dropped **against the history as
  it arrives**, usually within a day, without waiting for new games. The update
  reads *"I checked this against your earlier games: you do this often."* or
  *"Your earlier games don't show this, so I've dropped it."*
- *No username* (plays on the site, or a child in a class) — one game, and
  confirmation comes from the next games they play, as in the mock above.

Why five games: one game names the right top weakness 34.4% of the time, five
games 49.8%, twenty 71.3%. Five is still a guess, so the wording stays the same;
the history makes the guess checkable fast.

Live throughput, 2026-11-10 (prod `analysis_queue`): 221 games analysed in 24 h,
median 11.1 min per game (p90 20.8), two at a time, 900 pending. Five full
analyses at the front of the queue take about half an hour; behind the backlog,
days. Hence the quick first pass and the queue priority below.

Text rules: simple English, no numbers, no engine scores, mature tone (like
Chess.com or Lichess, not childish). The LLM may only rephrase English. Every
chess claim comes from the board, the engine or a graded detector.

## 3. In scope (V1)

- First-look layer on `/game/:id` for the player's first analysed game.
- Moment picker for one game: at most one each of turning point, missed chance
  and good decision. Never padded; a game with only one good moment shows one.
- Reflection on every moment through the existing `ReflectFlow`. Good decisions
  get the taps and a short confirmation, with no test.
- Cause per moment from three inputs: taps, "found when asked", and the clock
  (time spent compared with the player's own pace in this game).
- One or two impressions, each tied to a cause and to a graded (PLAN) problem
  id, worded as guesses.
- One "try this" line per impression, from the existing coach-plan `RULES`.
- An impression record per player: open → confirmed or dropped, updated on each
  new analysed game, games two to five.
- The update card on reviews of games two to five.
- Username path: pull the last five games in the main time control, put them at
  the front of the analysis queue, give them a quick first pass, and keep pulling
  and analysing the history in the background.
- Confirm or drop impressions against the history as it is analysed.
- For academy students: a confirmed impression is offered to the coach as the
  first weekly-plan problem (still coach-approved).
- Events: moment answered, impression shown, impression confirmed or dropped,
  next game played.

## 4. Explicitly out of scope (V1)

- New detectors or new problem labels. Impressions only use problems already
  graded PLAN in `detector_quality.py`.
- A weekly plan for non-academy players (the self-serve plan is its own scope).
- Parent-report lines from the first look. That comes after impressions are
  shown to be accurate.
- Changing the personalized-review rollout flag for other surfaces.
- The unmerged diagnostic-puzzle first session.
- Live coaching during the game (Play with Coach already exists).
- Any number or score in the text.

## 5. Success criteria

- **Impression accuracy:** of the impressions shown after game one, the share
  confirmed by game five. It must beat the 34.4% one-game baseline, because
  that is the point of asking questions and reading the clock. Target to be
  locked after the first month of data (open question 4).
- **Comes back:** share of first-look players who play and analyse a second
  game within seven days, compared with first-game players before launch
  (matched on sign-up source, never the whole population).
- **The habit moves:** for "try this" lines with a measurable habit (for example
  checking hanging pieces), the rate in games two to five against the player's
  own game one.

Not success: the number of people who open the card.

## 6. Open questions

1. **Clock cut-offs for "you moved quickly".** Unresolved: no measured cut-off for
   one game. Unblock: `/lock-via-data` on the stored misses (11% were under half
   the player's median; 38% were after long thinks).
2. **Confirm and drop rule.** For example "seen again in two of the next four
   games". Unresolved: needs the per-problem repeat rate. Unblock: measure, per
   PLAN problem, how often a problem seen in game one recurs in games two to five.
3. **Is a quick first pass good enough?** Does a shallow analysis find the same
   moments (turning point, missed chance) as the full one? Unresolved: not
   measured. Unblock: run both depths on a few hundred stored games and compare
   the picked moments.
3b. **Does the five-game import jump the 900-game backlog today?** The fresh-game
   priority (`claude/fresh-game-first`) covers a just-finished synced game; not
   verified for a first import. Unblock: read `journey_service.py` queue priority.
4. **The accuracy target number.** Unblock: one month of first looks.
5. **The personalized-review flag.** Should the first look show to everyone, or
   only behind the same flag at first? Unblock: Mohit's call.

## 7. Pre-code requirements

- Mohit signs off this document.
- Open questions 1 and 2 locked from data (`/lock-via-data`), with the
  measurement cited here.
- The mock above is reviewed by Mohit as the contract (wording included).
- `/audit-pre-code` passes.
