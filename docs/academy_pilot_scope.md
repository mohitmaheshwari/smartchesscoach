# Academy pilot: parent report, coach class view, Win it back homework

Scope for Phase 0 and Phase 1 of the product vision
(https://claude.ai/artifact/UuSevMkGUi2PgDK9voYnzL), with a sample of the two
screens at https://claude.ai/artifact/RhJwgmp5ZdPjRcdL4331mY.

**Sign-off.** Mohit, 2026-11-05: "cool, let's build all this", then in answer to
four questions: build everything as far as it gets in one night, deploy and
switch on, close port 8002, deliver the parent report by WhatsApp. Recorded as
the explicit sign-off for this document.

---

## 0. Existing surfaces audit

Checked in the code at `426c807a` and on prod (read-only) on 2026-11-05.

| Need | What exists | Overlap |
|---|---|---|
| Accounts for an academy, a batch, a coach, a child, a parent | Nothing. A search of the backend for `academy_id`, `class_id`, `student_id`, `parent_email`, `classroom` finds no model. `users.role` is `user` / `admin` / `super_admin`. | None |
| A weekly report | `backend/weekly_summary_service.py`, on request only (`routes/coach_advanced.py:710-734`). Written for the player, counts blunders and mistakes as numbers, reads `game_analyses`. | Same rhythm, different reader. Not reused: it shows numbers and scans `game_analyses`. |
| The habit we saw | `services/thinking_habits_card.py` speaks for two of five habits; for Mohit it says nothing this week. Review cards say "this keeps coming back". `move_observations` holds every move with `fen_before`, `move_uci`, `execution_quality`, white-relative `eval_before` / `eval_after`. | The report reads `move_observations` and checks each claim on the board, the same way the sample was built. |
| Homework from a thrown-away position | Win it back prototype on one laptop (scratchpad `wib/`). Play with Coach has an engine opponent, `coach_play/coach_opponent.py`, `CoachOpponent(user_rating).get_move(fen)`. | Homework reuses `CoachOpponent` at the real opponent's rating. |
| Game import for a child | `journey_service.run_background_sync` imports for every user with a Lichess or Chess.com username. | A child is a `users` doc. The username is written only after the parent consents, so nothing imports before. |
| Email to a child | Digest, reminder and weekly jobs skip users without an `email` (`digest_email_service.py:145`, `daily_fix_reminder.py:87`, `weekly_summary_service.py:209`). | A child account has no email, so no job writes to a child. |

**Decision: PARALLEL** for the academy surfaces (nothing exists), **EXTEND** for
analysis (child games go through the existing import and worker unchanged).

## 1. What it is

An academy signs up, makes a batch, and adds its children with a parent's phone
number. The parent gets a WhatsApp message with a link, agrees, and from then
on the child's online games are read like any other player's. Each week the
coach sees one table for the batch: each child's habit, whether it is happening
less or more, and whether homework was done. The coach adds a line and sends
the parent a one-page report on WhatsApp. The child gets one homework position:
a game they threw away, to play again against an opponent of the same strength.

## 2. What the user sees

The sample page is the contract for the parent report and the coach view. The
words below are what the code renders.

```
PARENT  /r/<token>                         COACH  /academy/batch/<id>
-----------------------------------        -------------------------------------------
Weekly chess report · Saturday batch       Saturday batch
Rohan's week                               Three children need you this week.
Rohan played most days this week.          SUGGESTED CLASS TOPIC
He won about as often as he lost.          Check the new square before you move.
THE HABIT WE SAW THIS WEEK                 Child | Habit | Compared with last week |
He moves a piece to a square where           Homework | Needs you?
it can be taken.                           Rohan | Moves a piece where it can be
[board: red arrow, green arrow]              taken | About the same | Not yet |
His knight jumped forward. Their rook        Yes. Homework not started
could take it for free.
A GOOD MOMENT ...                          CHILD  /academy/student/<id>
THIS WEEK'S HOMEWORK  Win it back          the same report, a note box,
ONE QUESTION TO ASK AT HOME                [Send on WhatsApp] [Copy link]
FROM COACH PRIYA  <coach's note>
This report shows habits we can see in
his games. It is not a score or a test.

CONSENT  /consent/<token>                  HOMEWORK  /homework/<token>
Sunrise Chess Academy wants to add Rohan   You were winning here. Win it back.
to ChessGuru ... [I agree]                 [board, you play, engine replies]
```

## 3. In scope (V1)

- Port 8002 bound to 127.0.0.1 only; nginx still reaches it.
- Academy, staff (owner, coach), batch, student; a child is a `users` doc with
  no email and no password, created by the academy.
- Parent consent page: what we collect, why, how to stop. Import starts only
  after consent. "Stop and delete" removes the child's games, analyses and
  reports.
- Weekly snapshot per child, built in the background from `move_observations`
  and `games`; never from `game_analyses` on a request.
- Two board-checked habits: *moves a piece where it can be taken* and *misses
  what their last move attacked*. Each claim is re-checked with python-chess
  before it is shown.
- A good moment: a piece was under attack with no guard, and the child's move
  saved it and was graded good or better.
- Win it back homework: the biggest one-move slip from winning in a lost or
  drawn game this week, played against `CoachOpponent` at the real opponent's
  rating, judged by the engine when it ends.
- Coach class view, child page, coach note, approve and send. "Send on
  WhatsApp" opens WhatsApp with the parent's number and the link filled in.
- Words only. No digits reach a parent or a child; a test locks it.
- Switched on for everyone (no flag), per the sign-off.

## 4. Explicitly out of scope (V1)

- Automatic WhatsApp sending through the Business API. Needs a ChessGuru
  WhatsApp Business number and approved templates; Smart Matrimony's number is
  not ours to use.
- A new server and an off-box backup. Not approved for tonight.
- Coach-approved proof inside the report ("he has stopped doing this"). The
  report describes; it does not claim improvement (vision, rules).
- Class games on the site, academy billing, direct-to-parent sign-up.
- A child login. Children reach homework by link only.

## 5. Success criteria

From the vision, measured during the pilot, not tonight:

- One academy pays for a pilot after about five conversations.
- Parents open the report in most pilot weeks (opens are recorded per report).
- The coach approves and sends reports in most pilot weeks.
- Homework started and finished per child per week.

Tonight's bar is engineering: every route tested, the strict deploy gate 8/8,
and one complete pass on prod by an admin account: create academy, add a child
with a real Lichess username, consent, snapshot, approve, open the report, play
the homework.

## 6. Open questions

- **Less / same / more. LOCKED 2026-11-05 from data.**

  ```
  DECISION LOCKED: when the coach's table says "Less often" / "More often"
  VALUE: both weeks >= 5 analysed games; less when rate <= 0.4 x last week,
         more when rate >= 2.5 x last week; otherwise "About the same"
  EVIDENCE:
    - 12 weeks of prod games (7,344 analysed, 33,151 mistake moves), the
      board check from services/academy_service.read_move
    - 151 consecutive-week pairs with >= 5 games each: ratio p10 0.31,
      p25 0.64, median 1.00, p75 1.37, p90 1.94 -- mostly noise
    - at 0.4 / 2.5: less 13%, more 3% of pairs
  REJECTED:
    - 0.5 / 1.5 (first guess): calls 19% less and 19% more -- a change
      every other week for a typical player, so the label means nothing
    - 0.5 / 2.0: less 19%, more 9%
    - >= 3 games: adds only 21 pairs and widens p10 to 0.24
  MEASUREMENT: scratchpad trend_measure.py over a read-only prod export
  ```

  Also measured: of 255 player-weeks with three or more games, 185 name a
  habit (73%). The two habits fire about equally (1,861 / 1,891 moves).
- **Numbers for parents.** The rule bans numbers for players; whether it covers
  parents is Mohit's call. V1 uses words.
- **Legal read on consent** for children under eighteen in India. V1 records
  who agreed, when, and to which text version.

## 7. Pre-code requirements

- Scope signed off: yes (above).
- No open PR touches these files: `gh pr list` shows only PR #1 (stale since
  2026-03-29).
- Server clean at `426c807a` before the first deploy.
