# What this player can actually do — user_8b599930d7ef

Read-only, 2026-10-15, live production. Nothing written. Games evidence comes
from his **100 distinct analysed games** (2026-09-01 to 2026-10-15,
de-duplicated by platform game ID). Lesson evidence comes from **232 attempt
records** recovered from `learning_sessions.events[].attempt`, plus 37
diagnostic items, 4 calculation-test attempts and 118 puzzle attempts.

Labels are avoided throughout. Where a claim rests on inference rather than a
recorded fact, it says so.

**One correction to my own earlier reporting:** I said misconception-level
evidence did not exist because `user_misconceptions` holds 0 rows. Wrong —
**85 attempts carry a `misconception` field**, inside the lesson events. §4 is
built on it.

---

## 1. What he can actually do

### Tactics — demonstrated, with denominators

| Ability | Evidence |
|---|---|
| Take a free undefended piece worth 3+ | **182 of 215** chances (85%) |
| Deliver mate in one when it exists | **22 of 31** (71%) |
| Punish an opponent error | **108 of 171** (63%) |
| Answer a threat against him | **162 of 268** (60%) |

Prompted and untimed, he produced **the exact solution move in 32 of 37**
diagnostic items — and the grader accepted **no** alternatives (32 exact
matches, 0 different-move passes), so these are not near-misses scored
generously. Specific items he solved:

- `Rxe8#`, `Rxh7#` (mate, rated 895) and `Nc7#` (rated 1265)
- `Bd4+` as a discovered attack, twice — once at 894, once at **1275**
- `Bxc3+` as a fork (840)

So the concrete ability is: **he finds a one-move finish, a discovered attack
and a fork when the position is handed to him without a clock**, including at
the top of the range he was tested on.

### Calculation — one position tells us most of it

He is the only user who has used the calculation instrument. Four attempts, but
only **two distinct positions** (three attempts on the first) — so coverage is
thinner than the attempt count suggests.

Position `5N1k/1p4p1/7p/2p1P3/1pP5/4q3/6PP/5K2 b - - 0 37`, required depth 2:

| Attempt | Submitted | Found idea | Sound through | Judged the end |
|---|---|---|---|---|
| 01:41:19 | **`Kg8, Nd7, Qd3+`** | found | **3** | said winning, was winning ✓ |
| 01:41:22 | `Qxe5` | missed | 0 | — |
| 11:14:28 | `Qd3+` | found | 1 | — (`stopped_early: true`) |

So he **can** give a three-move line that stays sound for three ply, and he
judged the final position correctly in **both** attempts where he was asked
(2 of 2). That is a real, specific ability: he evaluates a resulting position
accurately.

### Openings

Repertoire derived from the moves, because `opening_name` is absent on all 87
of his lichess games: **1.e4 as White, 1…e5 against e4**, with d4 d5 and the
Scandinavian next. Over **996 opening moves: 41.9cp mean loss, 5% blunder
rate** — his cleanest phase. Of 13 non-artifact `opening` concept rows, 12
carry a mastery stamp, his best ratio (see §5 for why that stamp is weak
evidence).

### Endgames

**552 moves, 67.2cp, 7% blunders.** In near-pure pawn endgames: 81 moves, 5
blunders (6.2%). He converted 45 of 76 positions where he reached +3 (59%).

### Defence

Answers 162 of 268 threats (60%). Prompted, `threat_response` 5 of 7.

### Clock

Median **5 seconds** per move (p90 21s). Nothing further is supportable: a
clock reading survives on only **10% of his moves** against ~82%
product-wide.

### Learning behaviour

He reached `can_do_alone` twice, and twice solved an **unfamiliar** piece-safety
position (`distinct_position: true`) **unassisted, on his first answer** —
2026-09-10 and 2026-09-25. Those two records are the strongest independent
performance in his file.

---

## 2. Where each ability stops working

### By position difficulty — the clearest boundary

| Diagnostic tier | Understood |
|---|---|
| low (777–999) | **21 of 22 (95%)** |
| mid (1193–1300) | **11 of 15 (73%)** |

**All five of his misses, in full:**

| Concept | Tier | Rating | He played | Solution | cp lost |
|---|---|---|---|---|---|
| opening | mid | 1298 | `dxc3` | **`Bxc3`** | 509 |
| piece_safety | mid | 1300 | `Rxe2` | **`Bxd6+`** | 473 |
| pin | mid | 1261 | `Qxd8` | **`Ng5+`** | 442 |
| threat_response | mid | 1193 | `Kd6` | **`e7+`** | 1119 |
| threat_response | low | 838 | `Kh6` | **`c5`** | 408 |

Four of five are at 1193–1300. **And they share a shape:** in three he played
a **capture** when the answer was a different move, and in two he moved his
**king** when the answer was a pawn push. Both are the move that resolves the
tension immediately.

### By calculation depth

Required depth 2 → he found the idea on 2 of 3 attempts. Required depth 8
(`8/2p5/8/2P2k1p/1P3p2/3K1P2/8/8 b - - 1 44`) → missed the idea, sound through
0, **submitted a single move (`h4`)** — yet still judged the end position
correctly.

**Three of his four submissions were one move long** when the task asked for a
line. *Counterexample to my own reading:* that may be a misunderstanding of the
interface rather than a limit on his calculation — he gave a genuine three-move
line on his very first attempt, which argues he understood the task at least
once. Unresolved.

### By assistance

Graded lesson attempts: **assisted 18 of 40 correct (45%), unassisted 22 of 84
(26%).** First answers unassisted: 17 of 58 (29%).

### By familiarity

Only **35 of 232** attempts were on a position marked `distinct_position:
true`. On the three *transfer* attempts (unfamiliar, independent, unassisted)
he scored **2 of 3** — better than his recall rate on familiar positions. That
is the opposite of what a simple "struggles with new positions" story predicts.

### By phase

| Phase | Mean cp lost |
|---|---|
| opening | 41.9 |
| **middlegame** | **121.8** |
| endgame | 67.2 |

The middlegame costs him **2.9× the opening** per move.

### Counterexamples to my own interpretation

Three, stated because they weaken readings I have given:

1. **"He grabs the capture" does not generalise to his games.** It fits three
   of five diagnostic misses, but opportunity-adjusted, he plays a
   material-losing capture at **0.78×** the rate they are available — *less*
   often than chance. The tendency appears when a position is handed to him,
   not when he plays.
2. **"His recognition stops at his rating" is too strong.** He took **11 of 14**
   items at 1200+, including a discovered attack at 1275 and a mate at 1265.
3. **"Unfamiliar positions are harder for him" is contradicted** by the
   transfer results above (2 of 3 unassisted, on distinct positions).

---

## 3. What happened during assessments and lessons

**232 attempt records**, every one carrying its own assistance state.

| | Correct | Incorrect | Ungraded |
|---|---|---|---|
| unassisted | 22 | 62 | 96 |
| assisted | 18 | 22 | 12 |

**Untimed is not assisted**, and the data shows it: **184 of 232 attempts
record no assistance at all.** `assistance_measured: true` on 209 of 232, so
the distinction is tracked, not assumed.

Assistance actually used: `hint` 24, `guided_line` 10, `answer_revealed` 8,
`hint`+`answer_revealed` 6. Help requested: `show_on_board`, `ask_one_question`,
`let_me_try` — one item drew **15 `show_on_board` requests**.

Retries go deep: `retry_index` reaches **7**, distribution {0: 62, 1: 22,
2: 12, 3: 10, 4: 6, 5: 5, 6: 3, 7: 2}.

### The 2026-09-07 session, in full — a struggle, then an assisted success

Stage `retain`, lesson `piece_safety`, all on **unfamiliar** positions:

| Time | Move | His stated reason | Correct | Assistance |
|---|---|---|---|---|
| 16:31:47 | `e7d7` | keeps_piece_safe | ✗ | none (first answer) |
| 16:36:23 | `e7d7` | not_sure | ✗ | none |
| 16:36:48 | `e7f6` | looks_active | ✗ | none |
| 16:37:07 | `c5b7` | looks_active | ✗ | none |
| 17:04:37 | `a1c1` | keeps_piece_safe | ✗ | hint + 3 help |
| 17:05:08 | `c7e6` | looks_active | ✗ | hint + 11 help |
| 17:05:16 | `c5e6` | not_sure | ✗ | hint + 11 help |
| **17:24:35** | — | — | **✓** | hint + 12 help |

Seven unassisted failures, then a success only with a hint and twelve help
requests. Recorded correctly as `can_do_with_help`.

### Two product defects found in the teaching text, not player facts

- **The grader contradicted itself on the same move.** At 16:31 on `e7d7`:
  *"Your queen can be taken on d7."* At 16:36 on `e7d7`: *"Your queen is safe
  on d7, so the piece-safety part is right."* Five minutes apart, same move.
- **A placeholder shipped as a correction**, twice: *"This position is still
  being checked."*

Neither tells us anything about him, and both should be fixed before this
lesson is used as evidence of anything.

---

## 4. What his reasoning reveals

This is the one place he tells us *why*, by selecting a reason. **Explicitly
demonstrated**, not inferred — `reason_choice` recorded on 82 of 232 attempts:

| Reason he chose | Times |
|---|---|
| **`looks_active`** | **34** |
| `not_sure` | 20 |
| `keeps_piece_safe` | 18 |
| `uses_rule` | 6 |
| **`checked_landing_square`** | **4** |

`reasoning_consistent`: **false on 54**, true on 28.

Recorded misconceptions, on 85 attempts:

| Misconception | Times |
|---|---|
| **`piece_left_unsafe`** | **51** |
| `endgame_rule_not_applied` | 18 |
| `activity_before_safety` | 8 |
| `piece_safety_relationship_unclear` | 6 |
| `reason_does_not_match_move` | 2 |

**The finding:** his most-chosen reason is that a move *looks active*, and his
most-recorded misconception is that the piece was *left unsafe* — while
`checked_landing_square`, the reason that would describe the missing habit, is
his **least**-chosen at 4. He is not guessing: he selected "looks active" 34
times himself.

### What was never asked

**`prediction_correct` is null on all 232 attempts.** He has never been asked
in a lesson to predict the opponent's reply. The only place he produced a
continuation is the calculation test, three submissions, one of which was a
real line. So of Q4's four parts — threats identified, candidates considered,
replies predicted, positions evaluated — the product records the reason and the
move, records the evaluation only in the calculation test, and **records
candidate moves and predicted replies nowhere**.

---

## 5. What changed after teaching — `piece_safety`, the only idea with a chain

202 `piece_safety` records across seven origins: `external_game_observation` 95,
`in_lesson` 37, `personalized_lesson` 37, `verified_puzzle_attempt` 20,
`pwc_practice_assisted_observation` 10, `game_review_reflection` 2,
`pwc_just_play_observation` 1. **165 of them are `rollout_mode: shadow`.**

Teaching starts **2026-09-02T10:51** (stage `diagnose`, guided, correct).

| Date | Stage | Unfamiliar? | Unassisted? | First answer? | Result |
|---|---|---|---|---|---|
| 09-02 11:17 | transfer | **yes** | yes | — | ✗ |
| 09-07 16:31→17:24 | retain | yes | 7 no-help attempts | yes, then no | ✗ ×7, then ✓ with help |
| 09-10 02:42 | recall | no | yes | yes | ✓ |
| **09-10 18:02** | **transfer** | **yes** | **yes** | **yes** | **✓** |
| 09-13, 09-16 | guide | no | answer_revealed | no | ✗, ✗, ✓ |
| 09-17 03:14→15:35 | recall | no | mostly | mixed | ✗ ×6, ✓ ×2 (both with hint) |
| 09-24 08:15 | recall | no | yes | yes | ✗ |
| **09-25 15:08** | **transfer** | **yes** | **yes** | **yes** | **✓** |
| 09-28 15:56 | guide | no | yes | yes | ✗ |

**The before/after that survives scrutiny:** his first transfer attempt, on the
day teaching began, failed. Two later transfer attempts — **8 days** and
**23 days** after — were unassisted first answers on unfamiliar positions, and
both succeeded. That is three relevant opportunities, not a mastery stamp and
not a clean-game count.

**What it does not show.** Three transfer attempts is a small base, and
`recall` on familiar positions kept failing unassisted through 09-17, 09-24 and
09-28, after both transfer successes. So "he has learned piece safety" is not
supportable; "he twice applied it unaided to a new position, 8 and 23 days
after teaching, while still failing familiar drills" is.

**The in-game half of the chain is empty.** All **95** game observations carry
`correct: null` — they record exposure, not outcome. So the question "did it
show up in his games" has no graded answer in this data, and the mastery stamps
cannot stand in: every surviving stamp of his sits on a concept the product
never showed him.

Volume elsewhere is too thin to attempt this for a second idea:
`rook_endgames/lucena` 26 records, `king_and_pawn/key_squares` 2,
`rook_endgames/active_rook` 2.

---

## 6. What remains unknown

**Missing evidence — never tested, so no difficulty is demonstrated:**

- **Planning and positional understanding: nothing at all.** `pawn_structure`
  and `piece_activity` appear **zero times** in his 2,958 observation rows. All
  five of his `positional` concept rows were artifacts. No instrument in the
  product asks for a plan, and no collection stores an answer to one. This is
  the largest hole in the profile and it is a hole in the *product*, not in him.
- **Predicting the opponent's reply**: never asked (`prediction_correct` null
  ×232).
- **Candidate-move generation**: never asked anywhere.
- **Anything above 1300**: the hardest item ever put to him was 1300, while he
  plays at 1490.
- **His clock**: 10% coverage. The condition under which he actually decides is
  the one we cannot see.
- **His openings by name**: 52 `opening_knowledge` flags that cannot be tied to
  an opening, because the lichess importer records none.

**Demonstrated difficulty — tested, and he struggled:**

- Piece safety on familiar recall positions, unassisted: repeated failure
  across 09-17, 09-24, 09-28.
- `threat_response` at mid tier: 2 of his 5 diagnostic misses, his weakest
  prompted concept.
- A depth-8 endgame calculation: single-move answer, sound through 0.
- The middlegame generally: 121.8cp per move against 41.9 in the opening.

---

## 7. Here is what I would teach this player next, why, and what independent performance would show they learned it

**What: checking the landing square before committing a piece.** Not "piece
safety" as a topic — the specific habit of asking, for the square the piece is
moving *to*, what can take it there.

**Why, from his own records rather than my reading of them.** He chose
`looks_active` as his reason **34 times**, more than any other, and
`checked_landing_square` only **4 times** — the least of any reason. His most
recorded misconception is `piece_left_unsafe`, **51 times**, and the
corrections he was shown name the destination square again and again: *"Your
knight lands on e6, where the pawn on f7 can take it."* His stated reason and
his error are two halves of one habit, and the habit has a name he has barely
ever selected. It is also the only idea in his file with a full evidence chain
(§5), so progress on it can actually be measured. Two supporting facts: it is
his worst puzzle type with real volume (**9 of 24**), and his second-largest
in-game pattern (98 flags across 62 games).

**What independent performance would show he learned it** — all four, or it is
not established:

1. **Unassisted, unfamiliar, first answer.** `assistance: []`,
   `requested_help: []`, `distinct_position: true`, `retry_index: 0`, correct —
   on **three separate positions**, with at least a week between the first and
   last. One success is the 09-10 result he already has; the standard is
   repeating it.
2. **The reason has to match.** He selects `checked_landing_square` with
   `reasoning_consistent: true`. If he is right while still answering "looks
   active", he has guessed the move, not learned the habit.
3. **It appears in his games, opportunity-adjusted.** Over his next 20
   **distinct** games, his rate of leaving a piece worth 3+ attacked and
   undefended falls — measured against the positions that *offered* the mistake,
   not as a raw count, and de-duplicated by platform game ID.
4. **It survives a delay on an unfamiliar position.** One correct unassisted
   transfer attempt at least three weeks after the last lesson, which is the
   one condition his current record does not yet meet twice.

**What would falsify it:** success only on familiar drill positions, or success
with `looks_active` still selected, or a falling raw count with no change in
the opportunity-adjusted rate. Each of those is the shape of a result that
looks like learning and is not.
