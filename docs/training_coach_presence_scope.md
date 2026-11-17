# Training page: the coach is in the room

Status: DRAFT, awaiting Mohit's sign-off. 2026-11-17.

Mohit, 2026-11-16, on `/training/pattern/piece_safety`: "some kind of tracking
shows up, some kind of coach eyes, something that really looks like good stuff
... right now it's just board and nothing else".

## 0. Existing surfaces audit

| What exists | Where | What it gives today |
|---|---|---|
| Session progress dots | `PrescribedTraining.jsx` `Pips`, line 886 | Built, **hidden** since f211a06f (2026-08-31, "coaching language in place of report metrics"). Missed = red, a failure tally. |
| Weekly plan step + last-week words | `player_plan_weeks`, home coach file, `CoachPlanCard.jsx` | Home only. The training page does not know it is this week's step. For Mohit this week's step IS this drill (`habit:gap:piece_safety:destination_safety_exact`). |
| Game move, its timing | `move_evaluations[].move`, `time_spent_seconds` | Be7 at move 22 was played in 5 seconds. Never shown anywhere on this page. |
| Named game move + capture arrows | 7bbc6b7a (2026-11-16) | Live for the landing-square drill. |
| Landing-square grader | `grade_destination_safety_candidate` | Says whether a piece is safe on its new square. Used only to grade the final move. |
| Puzzle attempts | `puzzle_attempts` (122 rows for Mohit: correct, time_taken_ms) | Stored, never shown back. |
| Separate piece-safety lesson | `PICPieceSafetyLesson.jsx` | Another plain board + question; no checklist, no tracking. |

Decision: **EXTEND** `PrescribedTraining.jsx`. No new page, no new route.

Constraint carried in: no counts or tallies in player text
([never show a failure scoreboard]). Tracking is shown in words and shape.

## 1. What it is

The training page stops being a board with a question next to it. Three
things are added. A strip at the top says this is your step for the week and
how it is going in your real games. A "coach's eye" panel beside the board
watches you check the move, step by step, as you do it, and asks you one tap
question before it judges the move: can your piece be taken where it lands?
After each position, a short "what I saw" line compares how you handled it
today with how you handled it in the game.

## 2. What the player sees

Before moving (the landing-square drill, Mohit's move 22):

```
 YOUR STEP THIS WEEK
 Check the square where your piece lands.
 It still showed up in your games last week, so we stay on it.
 Today  ━━━━━━━━━━━━●○○○○○○      (filled = done, ring = now; no red)

 ┌──────── board ────────┐   COACH'S EYE
 │ red  h4→e7  your move │   From your game, move 22.
 │ blue c7→e7  the take  │   You played Be7 quickly, and the queen
 │                       │   on c7 could take your bishop on e7.
 │                       │
 │                       │   WHAT I'M WATCHING
 │                       │   ✓ You picked up your bishop on b3
 │                       │   ○ Where does it land?
 │                       │   ○ Can anything take it there?
 └───────────────────────┘
                              Show the solution  ·  Skip this one
```

After dropping a piece (the move is NOT judged yet):

```
 COACH'S EYE
 ✓ You picked up your bishop on b3
 ✓ It lands on c2
 ● Before I check it: can anything take your bishop on c2?
     [ Yes, it can be taken ]   [ No, it is safe there ]
```

After the tap, the engine judges the move as today, plus one line on the check:

```
 ✓ You were right, it is safe on c2.        (or)
 ✗ Look again: the knight on d4 can take it there.
 WHAT I SAW
 In the game you moved quickly here. Today you stopped and checked
 the square first.
```

Tracking stays in words: "getting steadier", "still slips when the move gives
check", never "7 of 10".

## 3. In scope (V1)

- Week strip on the training page when the drill's habit is this week's plan
  step, using the plan week's own words (same source as Home's card).
- Session path: filled for every position done (solved or not), ring for now.
  No red, no score.
- Coach's eye panel for the landing-square drill: live checklist driven by the
  board (piece picked up, landing square), then the one-tap safety question,
  graded by `grade_destination_safety_candidate` on the player's own move.
- The tap answer is stored with the attempt (new field on `puzzle_attempts`).
- "What I saw" line after each position: game think time vs today's, said in
  words ("quickly", "you took your time"), only when both times exist.
- Premium look: same board, serif question, quiet motion on each tick. Real
  pieces, no mascot.

## 4. Explicitly out of scope (V1)

- Coach's eye checklists for the other drill types (hanging piece, forks,
  mates). They get the week strip, session path and "what I saw" only; each
  needs its own honest checklist.
- A cross-week "your checking" trend line. Needs the new tap answers to pile
  up first; V1 only stores them.
- Sound, confetti, streak counters.
- Lichess-pool puzzles (not from your games): no game move or game timing to
  compare, so no "from your game" or "what I saw" lines.

## 5. Success criteria

- Behaviour in real games: the plan week's verdict for this step moves from
  "showed up again" to "kept" for players who do the drill (the measure that
  already runs every Sunday).
- Checking accuracy rises within a session: later positions answered correctly
  on the tap question more often than earlier ones (stored, not shown).
- Time per position goes up on the first try, not down (we want checking, not
  speed).

## 6. Open questions

- **Tap question on every try or only the first?** Unresolved: friction vs
  habit. Proposal: every first try; a retry skips it. Mohit to decide.
- **Should a wrong tap answer still let a good move count as solved?**
  Proposal: yes, the move is judged as now; the tap answer only changes the
  coach line. Mohit to decide.

## 7. Pre-code requirements

- Mohit signs off this document (or changes the two open questions).
- No open PR touches `PrescribedTraining.jsx` or `coaching_puzzle_service.py`
  (checked 2026-11-17: only PR #1, which touches neither).
