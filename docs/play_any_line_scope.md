# Play any line on the board — scope

Status: SIGNED by Mohit 2026-11-18 ("go ahead" on the plan as written).
Sharing question (section 6) not answered: the safer default is used, the
player and reviewers only; a coach once coach access exists (section 8).

Mohit, 2026-11-18: "i need to be able to play any line on the board, so coach
can also show, for example if student had asked sir what is the problem with
Qf3, coach could show up, with stockfish telling why Qf3 was a blunder there
... a board that interacts and tells for students to easily understand."

Agreed shape (same day, "go ahead"): extend the game-review board first, then
the coach pages.

## 0. Existing surfaces audit

Checked on `origin/working-code` a0de90bd.

| Surface | What it already does | Overlap |
|---|---|---|
| Game review board (`GameDecryptionV5.jsx`, `/game/:gameId`) | Steps through the game. Plays the better line by itself with arrows (`playBestLine`, line 1110). The board is `viewOnly` except in plan mode (line 1463). | Same board and same place. It cannot take a move from the student. |
| "Show my plan on the board" (plan mode in `GameDecryptionV5.jsx`, lines 821–905 and 3183+; `POST /analyze-plan` → `services/plan_analysis_service.py`) | After a saved "what were you thinking?" note, the player plays their intended line, submits it, and gets back where it fails, a gap label and a lesson. | **The closest thing that exists.** It is from 2026-03/04. Its lessons are fixed sentences per gap type (`_build_lesson`) and its tactic names come from pattern matching (`_identify_tactic`), which our later rules reject (principle bank is filler; reason from the board). The student plays the whole line before hearing anything, and the opponent's replies are the student's guesses, not the engine's. Not verified whether the note prompt that opens it is still reached since the tap reflection (67329306). |
| The why button (`GET /coach/why/{game_id}/{move_number}`, `coach.py:1452`) | Explains a game move: what the reply wins, the threat line, the opportunity line, mate. | The words engine to reuse. The engine itself (`why_differential.explain(fen, san, …)`) takes any position and move. Only the endpoint is tied to stored game moves. |
| Trap school, Study game, Reply check, drills | Boards that take moves, each graded against one stored answer. | They grade one answer. None answers a free move. |
| Coach pages (`/academy/student/:studentId`, `CoachFileBlocks.jsx`) | The academy coach's view of a student. Boards show stored moments. | The place a coach would show a line. No free board there. |
| Removed 10-28: "what if I played X? See on board" button | A button that replayed the better move. Mohit: "anybody can see that directly without you having that button". | This feature adds no button of that kind. The board itself takes moves. |

What the current why engine says about the Qf3 example, run 2026-11-18 on
branch `claude/trap-lessons` (c9fa15ba) in a throwaway container:

    After Qf3, Bxb5 simply takes your bishop on b5, and nothing can take back.

True, but it does not answer the student's real question ("but Qf3 attacks the
rook"). The answer to that is the next step, 5.Qxa8 Bc6, which only a board the
student can keep playing on reaches.

**Decision: EXTEND the review board, and REPLACE plan mode.** The new board
does what plan mode tried to do, move by move, with the engine's real replies
and proved words. Plan mode's button and `/analyze-plan` go once this ships.

## 1. What it is

On the game-review board, a student can move any piece to try their own idea
from any position in the game. The coach answers each move at once: it plays
the other side's best reply on the board, and says in one plain sentence what
the student's move does and what the reply does. The student keeps going ("but
what if I take the rook?") and every step gets an answer, until they understand
why a move failed or why another one works. A coach in an academy uses the
same board to show a student a line. When the engine can show a move but we
cannot explain it honestly, the board still plays it with an arrow, and says
nothing it cannot prove.

## 2. What the user sees

Words follow the caption rules: plain English, no engine numbers, "your" and
"their" by whose move it is. Under 1000 (`notation: false`) the words point at
the arrows instead of naming squares.

**Under the review board, always:**

    Move any piece to try your own idea.

**The Qf3 example.** The student is on 4.Qf3 in their game. The card says:

    After Qf3, Bxb5 takes your bishop on b5, and nothing can take back.

The student thinks "but my queen attacks the rook". They step to the position
after 4...Bxb5 and play 5.Qxa8. The board answers 5...Bc6 with arrows from c6
to a8 and from c6 to g2:

    YOUR LINE   4.Qf3 Bxb5 5.Qxa8 Bc6

    Qxa8 takes the rook.
    Bc6 attacks your queen. With your queen gone from f3, it also hits g2,
    and your rook on h1 behind it.

The student plays 6.Qxa7. The board answers 6...Bxg2:

    YOUR LINE   4.Qf3 Bxb5 5.Qxa8 Bc6 6.Qxa7 Bxg2

    Qxa7 saves the queen.
    Bxg2 takes the pawn, and your rook on h1 falls next.
    Count it up: you won a rook and a pawn, they win a bishop, a pawn and a
    rook. You end a piece down.

    [ Back one ]   [ Best move here ]   [ Back to the game ]

**A good idea the student tries instead.** Back at move 4, the student plays
4.Bxa6. The board answers 4...Nxa6:

    Bxa6 is the best move here: it trades off the bishop that was attacking
    yours.
    Nxa6 takes back.

**A move we cannot explain.** The board still plays the reply with its arrow:

    Ne2 is fine.
    The engine answers d5.

**Coach pages.** On `/academy/student/:studentId`, any game or moment the coach
opens has the same board, so the coach can play a line for the student and
the student sees the same answers.

## 3. In scope (V1)

- The review board takes a move from the student on any position of the game,
  for either side. The move starts "your line" from that position.
- After each student move, the board plays the engine's best reply for the
  other side, with an arrow, within the time budget set in section 6.
- One sentence on the student's move:
  - a mistake by the player's rating bar → the why engine's answer for that
    position and move (the same engine as the why button, extended to take
    any position, not just stored game moves);
  - the engine's best move → "X is the best move here", plus the why engine's
    reason when it has one;
  - otherwise → a plain verdict ("X is fine", "X is a little slower than Y").
- One sentence on the reply, from board facts proved by the line: what it
  takes, what it attacks, check, mate, and a running count of what changed
  hands once the material swings.
- When no sentence can be proved: the move and arrow only, never an invented
  reason (coverage stays first class: the board never goes blank).
- Controls: Back one, Best move here (plays the engine's best for the side to
  move), Back to the game. The game line is never overwritten.
- The same board in the academy coach view.
- Every tried line recorded (game, starting position, moves, which sentences
  were shown), for the success figures in section 5.
- Plan mode ("Show my plan on the board") and its `/analyze-plan` call removed
  once this ships.
- A per-user limit on engine requests, so free play cannot starve the shared
  server.

## 4. Explicitly out of scope (V1)

- A blank board or position editor (set up any position from scratch, paste a
  position). V1 starts from positions in real games. Can follow once V1 is used.
- Replies chosen by how players at the student's level play (Maia). V1 answers
  with the engine's best, because the question is "why is this a mistake",
  which the best reply answers. Maia replies are a later mode.
- Showing the coach which lines a student tried. Recorded in V1, shown later.
- The board on Play with Coach, puzzles, drills and the trap school. They
  grade one stored answer on purpose.
- Engine numbers on screen (standing rule: published text carries no numbers).
- Spoken or chat-style questions ("sir, what is the problem with Qf3?" typed
  in). The student asks by moving a piece.

## 5. Success criteria

- **Words are true (gate before release):** 30 sentences from the board on
  moves tried off the game line, across players and kinds (mistake, best move,
  reply), graded on a board by someone other than the author: at least 27
  true. Below that, those sentences stay off (move and arrow only).
- **Coverage:** the share of student moves that get a sentence, reported per
  kind. Measured, not gated, in V1.
- **Used:** of players who open a mistake card, at least 20% play a move of
  their own on the board within two weeks of release.
- **Understood:** players who played out a line on a mistake repeat that
  mistake's pattern less often over their next 20 games than players who only
  read the card. Reported once enough games exist.

## 6. Open questions

- Question: how fast must the reply come, and at what engine depth?
  Why unresolved: the why button's budget is seconds (one game measured 93.5 s
  before a guard), far too slow for a board. Unblocking step: time the reply
  move and the sentence separately on 50 positions; the reply can show first
  and the sentence follow.
- Question: how often will the why engine find words for moves off the game
  line? Why unresolved: measured only on game moves. Unblocking step: a dry
  run on 200 tried moves from real positions, counted per kind.
- Question: can anyone reviewing a shared game play lines, or only the owner
  and their coach? Why unresolved: product choice. Unblocking step: Mohit.
- Question: what per-user engine limit? Why unresolved: depends on the timing
  above and the shared box. Unblocking step: the timing run, then set from the
  numbers.

## 7. Pre-code requirements

- Mohit signs this document.
- The Qf3 example and two more positions are played through the new words on
  a board and read before the endpoint is built (the 5...Bc6 sentence must come
  from board facts, not from this mockup).
- The timing run (section 6) gives the depth and the time budget.
- Checked whether plan mode is still reached on live review pages, so its
  removal is reported correctly.
- No open PR or branch touches `GameDecryptionV5.jsx` or `coach.py` at the
  time the code starts (checked again then).

## 8. Results before release (2026-11-18)

**Plan mode use.** 0 calls to `POST /api/analyze-plan` in all 15 nginx access
logs on the server (about two weeks). Removed with this release.

**Coach pages.** The academy pages (`Academy.jsx`) never open a student's game
review, and game reads are scoped to the owner or a reviewer
(`services/access_scope.py`). So the coach half needs an access rule first
(an academy coach may read their students' games). Built next, as its own step;
this release is the player's review board.

**Timing run** (55 positions from 30 random stored games: 26 game mistakes, 29
other moves tried from the same positions; server, throwaway container, one
CPU at the lowest priority, so live times should be shorter):

| Depth | Median | 90% within | Same verdict class as depth 22 | Same reply |
|---|---|---|---|---|
| 12 | 0.3 s | 1.2 s | 37 / 55 | 38 / 55 |
| 14 | 0.4 s | 1.9 s | 40 / 55 | 38 / 55 |
| **16** | **1.3 s** | **4.4 s** | **43 / 55** | **45 / 55** |
| 18 | 3.0 s | 8.7 s | 46 / 55 | 41 / 55 |
| 22 | 16.2 s | 38.0 s | — | — |

Chosen: depth 16 (`LINE_BOARD_DEPTH`). The verdict class differs from a deep
search on about one move in five, so the verdict words were rewritten to stay
true across a class line (below).

**Why sentence coverage.** The why engine found a sentence for 35 of 38 moves
the board called a mistake (14 of 14 moves tried off the game line). Time:
median 19 s, longest 47.5 s, which is why it is a second call.

**Words gate (section 5).** 30 sentences from the board on about 40 players'
real positions (11 move facts, 12 reply facts, 4 verdicts, 3 counts), graded
on a board with Stockfish at depth 22–27 by an independent grader agent that
did not see this code: **27 of 30 true**. Every board fact was true. The three
failures were all verdict words near a class line:

- "Re2 is the best move here": Kg5 was 52 points better deeper.
- "Qd6 is a little slower than Qxb2": the loss was about a pawn.
- "dxe6 is a mistake: Rad1 was better": the loss was about half a pawn.

Fix: "the best move" only when the next move is at least 30 points worse,
otherwise "a good move"; one comparison for the middle of the table ("Qxb2
was better than Qd6"), true on either side of the line; "a mistake" only for
the rating table's big losses. Also: a target with a piece behind it is
named last, and "It" is not used after a verdict about another move.

## 9. Coach pages (built 2026-11-18, after the player's board went live)

- Access rule (`routes/academy_games.py`, `staff_may_read_game`): the academy's
  owner, its coaches and site admins may read a child's games, only while the
  parent's consent is given and the child is not deleted. The same rule as
  every other academy read (`routes.academy._student_for`).
- `/academy/student/:studentId` lists the child's 20 most recent games. Each
  opens `/academy/student/:studentId/game/:gameId`: the game replays move by
  move, and the coach can move any piece; the board answers through the same
  `/coach/line/*` calls, which now accept the access rule. "Your" in the words
  is the student.
- No review captions on the coach board: the coach page is the board and the
  line. The full review page stays owner-only.

## 10. The engine in the browser (Mohit 2026-11-18: "lichess explorer works damn fast for best moves and arrows")

The board answered each move from the server engine: 1.3 s typical at light
load, 20–30 s on the loaded box. Lichess is fast because the engine runs in the
browser. So does ours now:

- Stockfish 17.1, lite single-threaded build (npm `stockfish@17.1.0`, ~7 MB,
  served from `/stockfish17/`, cached after the first visit). Single-threaded,
  so the site needs no COOP/COEP headers. Play with Coach keeps its own Stockfish
  10 build; this is for the line board only.
- The browser searches the position on the board while the player looks at it
  (0.8 s, two best moves), and the position after their move when they move.
  The reply is played on the board as soon as it is found; the server then
  writes the words from the browser's numbers (`client_eval` on
  `POST /coach/line/move`, no server engine). If the browser cannot run the
  engine, or its numbers do not fit the board, the server engine answers as
  before.
- "Show the engine's best move" puts a green arrow on the board for the side
  to move, growing with the search. Off by default, so the board does not
  hand the student the answer.
- The why sentence stays on the server (deep search, arrives later).

**Measured before building** (46 real positions; reference: server Stockfish at
depth 22; the browser build run in Node on a desktop):

| Engine | Same verdict word | Same reply | Typical depth |
|---|---|---|---|
| Server, depth 16 (live) | 35 / 46 | 34 / 46 | 16 |
| Browser lite, 0.4 s | 33 / 46 | 31 / 46 | 18 |
| Browser lite, 0.8 s | 33 / 46 | 32 / 46 | 19 |
| Browser lite, 1.5 s | 33 / 46 | 29 / 46 | 21 |

Chosen: 0.8 s. A phone searches less deeply in the same time; not measured.

**Words gate on the browser engine** (30 sentences from the browser build's
answers, weighted to verdicts: 12 verdicts, 9 move facts, 9 reply facts; same
independent grader, Stockfish depth 24–30): **27 of 30 true**. Misses:

- "h4 is a mistake: Kf2 was better" when both moves are mated in about twenty.
  Fixed: when every move loses to a forced mate the board says so and calls no
  move a mistake ("still leads to mate" for the winning side).
- "Rxd2 ... also attacks your rook on d1" when the rook on d2 can simply be
  taken back. Fixed: an attacker that hangs makes no threat and is not named.
- "Ne4 is a mistake" for a loss of about 1.5 pawns, just under the mistake
  line: engine noise at a class line, the same kind as the server engine's.
