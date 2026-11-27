# /progress: chances, not verdicts

Mohit, 2026-11-27: *"the progress UX sucks, check it out, we have talked a
lot of thing, please talk to coaching room agent on what to put in progress
page."*

I did both. The UX is the smaller half of the problem.

**Status: awaiting sign-off.**

---

## 0. Existing surfaces audit

Checked in the code at `bf412a39` and against production (read-only) on
2026-11-27.

### The page is not under-designed. It is empty.

`/progress` renders `UnifiedProgress.jsx`, whose only data source is
`GET /progress/complete-coaching` → `build_phase8_journey_projection`. That
is gated by `complete_coaching_access.get_complete_coaching_access`.

I ran that gate for **every user in production**:

| What the gate returns | Users |
|---|---|
| `enabled=False, paused=True, reason="paused"` | **49** |
| `enabled=False, paused=False, reason="composition_disabled"` | **90** |
| `enabled=True` — a working progress page | **0 of 139** |

Nobody has a working progress page. The locked target exists and 50 users
have baselines, so the data is not the blocker: `request.requested` is false
for everyone, and a user who has phase-8 state but is not requested falls to
`paused` (`complete_coaching_access.py:168-181`).

So what the 139 actually see, rendered at 390 and 1280:

- **49 of them**: an apology. Headline *"Nothing you learned has
  disappeared."* with *"Your coach is preparing the next step."* A progress
  page whose first sentence denies a loss the player had not considered.
- **90 of them**: `progress-unavailable`, *"Your progress will show here."*,
  58 words.
- **7 of those 90** (the `BETWEEN_GAMES_USERS` ids — I counted the env on the
  server: 7, not `*`) instead get `CoachProgressSection`, the habit list.

Neither dead end is a layout problem, and no amount of restyling fixes them.

### And the habit list, which the 7 do see, cannot report improvement

Verified independently, from the code's own constants, not from a memory
note. `player_coach_habit.change_state` compares the newest
`PROGRESS_NOW = 20` games against the previous 40 at one-sided
`CHANCE_P = 0.10`. "Kept" needs zero hits in 20 games to beat chance:

| habit appears in | clean recent games needed | possible at 20? |
|---|---|---|
| 20% of games | 11 | yes |
| 15% | 15 | yes |
| 12.5% | 18 | yes |
| **10%** | **22** | **no** |
| 5% | 45 | no |
| 2.5% | 91 | no |

**Any habit rarer than about 1 game in 9 can never be reported as improved**,
however much the player improved. And the test is asymmetric by construction:
`worse` needs only `EVIDENCE_GAMES = 3` recent occurrences, which 20 games
supplies easily, while `better` needs statistical *absence*, which 20 games
cannot supply.

Two coaching sessions were asked and both reached this independently.
`smartchesscoach-fb` counted it across the corpus: of 311 habit rows in 81
coach files, **"Same as before" 245 (79%), "Showing up more" 31, "Getting
better" 8 (2.6%)**. (That count is theirs; I verified the mechanism, not the
tally.)

### What the two coaching sessions said must NOT be on this page

Relayed from `smartchesscoach-fb` and `smartchesscoach-5d`, with who
verified what marked:

- **"Getting better" verdicts** — the test above. *Mechanism verified here.*
- **Mastery / "concepts mastered"** — not granted to anybody since
  2026-09-17. *Their claim, not re-verified here.*
- **Tilt, board region, rushing / "eyesight"** — all three measured dead:
  accuracy 62.7 after a loss vs 62.4 after a win; board region
  11.26/11.15/11.83% by file in the middlegame; a snap move is *protective*,
  0.71x. *Theirs. The board-region one I measured myself earlier today and it
  died the same way.*
- **Thinking Score, Area Grades, Tactical Eye** (`UnifiedProgress.jsx:598-601`)
  — none validated against anything; thinking score drew 9 requests from 3
  IPs in 14 days. *Theirs.*
- **cognitive_gap category shares** ("piece safety 63%") — classifier labels
  with no precision review, so 68% → 63% looks like news and is not evidence.
- **Accuracy and eval graphs** — commodity, and already ruled out as a
  differentiator.
- **Improvement credited to training.** Rating rose +337 for one user while
  mistake rates barely moved. Never "because of".

### Decision: **REPLACE the page's basis, EXTEND nothing**

The page's single data source is off for 100% of users and its one verdict
engine cannot say the thing a progress page exists to say. Restyling it would
produce a prettier apology. The page is rebuilt on `move_observations`, which
has a real denominator and 100% field coverage, and stops depending on the
phase-8 gate.

## 1. What it is

A page that tells a player what came up in their games and what they did with
it — counted out of the chances they actually had, not graded.

Today's page waits for a verdict engine to pronounce, and when it cannot, it
apologises. The new one has something true to say after a single game,
because "you had 36 chances to leave a piece where it could be taken, and
took none of them" is a fact about this week, not a claim about a trend.

Where nothing can honestly be said — and that is often — it says so in those
words, and that is a designed state, not an empty one.

## 2. What the user sees

```
  Progress

  THIS WEEK
  You played 11 games. 4 of them had a moment where the game
  turned on one move.

  CHANCES YOU TOOK                        last 10 games · all time
  ┌──────────────────────────────────────────────────────────┐
  │ Kept your pieces safe       36 of 36      1,247 of 1,360 │
  │ Answered their threat       18 of 24        2,212 / 3,545│
  │ Punished their mistake           --           983 / 1,630│
  └──────────────────────────────────────────────────────────┘
  Each row is out of the chances that actually came up. A row
  with no chances this week says so.

  "Punished their mistake" has no last-10 column on purpose:
  it offers about 0.7 chances a game, so ten games give about
  seven, and seven chances must not be drawn as a rate.

  WHEN IT GOES WRONG
  Of the pieces you left hanging this month, the commonest
  thing they had in common: you had just made another mistake
  (34%). Under a minute left: 18%.
  Half of them have nothing in common yet.

  YOUR OPENING STEP
  You reached your line 6 times and played the move 4 of them.

  THE FACTS
  Rapid 1,834 · 11 games this week · 6 wins
  (stated, with nothing claimed about why)
```

Three things about that mockup are deliberate:

- **"36 of 36", never "100%".** A rate out of chances is honest when it does
  not move; a percentage invites a trend line that the data cannot carry.
- **"Half of them have nothing in common yet"** is on the page, in that
  register. Nothing explains 50.3% of one-move piece blunders, and hiding
  that would make the 34% read like a diagnosis.
- **No verdict words at all** — no better, worse, improving, mastered.

## 3. In scope (V1)

- `/progress` stops depending on `complete_coaching_access`. It renders for
  any signed-in player with analysed games.
- **Three** chance axes as *n of m*, from `move_observations`:
  `destination_safety_exact` (kept pieces safe) and `responded_to_threat` /
  `ignored_opponent_threat` (answered their threat) with both a last-10 and
  an all-time column; `punished_opponent_blunder` /
  `missed_opponent_blunder` **all-time only**, because it offers ~0.7
  chances a game and ten games give about seven — too few to draw as a rate.
  Their player-to-player ranges are human and actionable: piece safety
  4-30%, threats 18-64%, punishing 18-68%.
- Counts come from **one server-side `$group` with `$cond` sums**, computed
  live per request. Never from `player_coach_files.behaviour_axes`: that
  roll-up is built only for the 7 `BETWEEN_GAMES_USERS` ids, so reading it
  would rebuild the exact gate problem section 0 is about.
- The behavioural cause mix from `services/player_behaviour_reading.py`, with
  **"no clear pattern yet" as a first-class row**, not an absence. The 50.3%
  that nothing explains is measured for **one-move piece blunders only**, so
  the page says it about those and does not generalise the figure to the
  other axes until somebody measures them.
- The opening step verdict (`player_plan_week.opening_verdict`), which has a
  real chance count.
- Facts with nothing claimed about cause: games, results, rating.
- Empty states designed, not fallen into: fewer than 10 analysed games; an
  axis with zero chances this week; a player with no opening line yet.
- Rendered check at 390 and 1280: zero overflow, zero controls under 44px,
  zero occluded, no JS errors.

## 4. Explicitly out of scope (V1)

- **Fixing `change_state`'s statistical test.** It is a real defect and it is
  a threshold decision (widen the window, or size it per habit), which
  belongs to the coaching sessions and to `/lock-via-data`, not to a UX pass.
  V1 simply does not depend on it.
- **Turning the phase-8 gate on.** Not mine to flip, and the new page does
  not need it.
- **Deleting Thinking Score / Area Grades / Tactical Eye.** V1 stops showing
  them on `/progress`; whether the components die is a separate call.
- **Any new detector, or any backend measurement.** V1 reads what is already
  stored.
- **Per-week history or charts.** Running totals and a last-10 column only.
- **"Found it when it mattered" as an n-of-m row.** See the resolved
  question below: the data is the best we have, the framing is unshippable.

## 5. Success criteria

1. **Every signed-in player with analysed games sees content**, where today
   0 of 139 do. Measurable: the page renders the chance table for a user with
   no phase-8 enrolment.
2. **Every number on the page has a denominator** that is countable from
   `move_observations`. No composite, no index, no score.
3. Nothing on the page says better, worse, improving or mastered.

Not success: that it looks better than the apology. That is a low bar and
not the point.

## 6. Open questions

- ~~**Question:** Is "found it when it mattered", at about 6%, too
  discouraging to show?~~ **Answered with a measurement, and it flipped.**
  `smartchesscoach-fb` tested whether the axis discriminates, over 53 users
  with 200+ critical moments and a rating: **r = +0.50 against rating**, the
  strongest single-axis correlation measured on this corpus. Under 1200
  find 6.1%; 1600+ find 8.6%; the whole human range is 1.7% to 13.1%.

  So the data is the most valuable of the four and the *absolute* framing is
  the unshippable part: every player alive sits under 14%, and "you found it
  7 times in 100" reads as "you are bad at chess" to all 139 of them while
  giving them nothing to do. V1 drops the row. It comes back either relative
  to level — the baseline now exists, so "in line with players around your
  rating" is honest and not crushing — or coach-side, where a coach reads it
  as a strength index rather than a scoreboard. That is a later decision
  with real evidence behind it, not a tone preference.

- **Question:** Does the page show the four axes to a player with 3 analysed
  games, or wait for 10?
  **Why unresolved:** Chances accumulate per move, not per game, so even 3
  games give a real denominator — unlike the habit test, which needs games.
  **Unblocking step:** V1 shows it from the first analysed game and says how
  many games it is based on. Revisit if it reads as noise.

## 7. Pre-code requirements

- [x] Section 0 audit done against code and production, including running
      the live access gate over all 139 users.
- [x] Both coaching sessions consulted (`smartchesscoach-fb`,
      `smartchesscoach-5d`) and their "do not show" lists recorded above.
- [x] The statistical defect verified from the code's own constants rather
      than inherited from a memory note.
- [x] **Cost settled, measured, no roll-up needed.** On the heaviest user
      (27,932 observations) over the ssh tunnel, so these are upper bounds
      and on-box will be lower: fetching all-time documents 9,324ms, but a
      single `$group` aggregate **243ms** — 38x faster. Aggregate
      server-side and return only counts; never transfer documents.
- [ ] **The last-10 window needs an aggregate too, or an index.**
      `move_observations` holds 765,780 documents and has **no
      `(user_id, game_id)` compound index**, which is why a windowed fetch
      of 244 documents took 2,212ms against 243ms for a full aggregate. Do
      the window inside the aggregate, or add the index first. Not yet
      decided which.
- [ ] **Mohit's sign-off on this document.**
