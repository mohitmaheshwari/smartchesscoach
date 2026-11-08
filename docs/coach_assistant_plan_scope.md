# Coach's assistant and self-coach plan — scope

**Status:** DRAFT — awaiting Mohit's sign-off. No code until signed.
Section 0 path (EXTEND) agreed by Mohit 2026-11-08: "go ahead".
**Author:** Claude, 2026-11-08, against `origin/working-code` at f3fae891.

Mohit, 2026-11-08: *"A head coach assistant, very very smart, a coach like me who
understands chess can use this tool, each student he selects and it generates a
plan, it reviews games, see issues, you know 90% automation with only coach
approval"* and *"A student can himself use it … backend automation is still
same, 100% automation."*

---

## 0. Existing surfaces audit

Read in code on 2026-11-08 unless marked *inference*. Live flags read from
`https://chessguru.ai/api/health` the same day.

### What already exists

| Existing owner | What it does today | Live? |
|---|---|---|
| `user_active_focus` + `focus_resolver` / `focus_bridge`, written by `primary_weakness_picker.py` | The one current weakness per player: topic, evidence, baseline, instruction | Yes |
| Personal Improvement Cycle (`docs/personal_improvement_cycle_scope.md`, APPROVED v1.3) | The student's loop: diagnosis from their games → one instruction → practice → checkpoint / Focus Game → honest verdict → next focus. Says: do not add a rival program collection | `PERSONAL_IMPROVEMENT_CYCLE_ENABLED=true` |
| `/training/prescribed/{weakness}` → `coaching_puzzle_service.get_prescribed_training` (`coaching_puzzle_service.py:360-489`) | Puzzles for the focus: own games first, then community positions, then Lichess puzzles | Yes |
| `topic_practice_themes.py` | Four weaknesses → Lichess puzzle themes around the player's rating, with a question that matches the theme | Yes |
| `personal_curriculum.build_player_curriculum` (`/learn`) | Lesson in focus, what comes before and after | `PERSONAL_CURRICULUM_ENABLED=true` |
| `coach_selected_review_service` + `/lab-coach-pick` | Picks which game to review, preferring one that shows the focus | `PERSONALIZED_GAME_REVIEW_COACH_ENABLED=true` |
| `focus_game_service.py` | The player commits their next imported game as a Focus Game | Under the cycle flag |
| `primary_weakness_picker.check_focus_outcome` | "Did the focus get better?" — runs in shadow (`focus_outcome_shadow`); a code note says no focus has ever closed because the player fixed it | Shadow only |
| Academy (`routes/academy.py`, `services/academy_service.py`, `Academy.jsx`) | Per child per week: games, one habit (piece left takeable / attacked, 2+ games), trend, Win it back homework, class progress. Batch page suggests a class topic | Yes |
| `approve_report` (`academy.py:562-586`) | The only coach-approves-before-family-sees step. The coach can add a note; the content cannot be edited | Yes |
| `docs/ai_personal_class_scope.md` | A 15-minute personal class (warm-up → idea → practice → play → homework), piece safety only | Not built. Status line says signed; its own sign-off record still says "Awaiting Mohit" |
| `GET /training/weekly-plan` (`training.py:1139`) | A Monday–Sunday list from `top_weaknesses` | Dead: no caller |
| `user_coaching_prescriptions` / `training_plans` + "Start This Plan" cards | Accept-a-plan flow with tracking | Backend live; the cards are imported nowhere |

### Puzzle supply and use (measured on prod 2026-11-08, read-only)

- `lichess_puzzles`: 4,110,434 rows. Rated 600–1400: fork 338,729, pin 92,270,
  hanging piece 72,657, skewer 60,286. Supply for the proven ideas is large.
- `puzzle_attempts`: 693 attempts on 412 puzzles by 21 players, ever. The
  supply exists and is barely reaching anyone. A plan is the delivery missing.
- Each of those counts took 7–17 seconds on the live database, so plans must be
  built in the background, never while a page loads.
- 857,292 puzzles also carry an opening tag (figure from the Game Review
  session, not re-counted here). `opening_tags` has **no index** (checked), so
  nothing may filter on it yet.

### Overlap

**Mode 2 (student on their own) mostly exists already.** The Personal
Improvement Cycle is live on prod and is the 100%-automated loop Mohit describes:
it finds the issue, gives practice, picks a game to review, asks for a Focus
Game and checks the result. Building a second student plan would duplicate it.

**Mode 1 pieces exist, but not for a coach.** Every ingredient a coach's plan
needs is already produced for adult players (focus, puzzles, Lichess themes,
review pick, Focus Game). None of it reaches the academy coach.

### Genuinely missing

1. **A coach's view of one student's plan.** The academy page shows a habit and a
   homework slip; it never says "this week: these puzzles, this position, play
   this, review this".
2. **Coach approve / edit.** Today a coach can only add a note to a parent report.
3. **One diagnosis for both doors.** Academy children get their habit from
   `academy_service`'s own count, not from `user_active_focus`. Two places decide
   "what is this child's problem" — the single-source rule says one.
4. **A visible "did the plan work" verdict.** The focus outcome is shadow-only and
   has never fired a real "fixed".
5. **The approval log as a measurement.** Nothing records what a coach changed,
   so nothing can say when an idea is safe to run without a coach.

### Section 0 decision (proposed, needs Mohit)

**EXTEND.** One plan engine on the existing spine:

`user_active_focus → prescribed puzzles (own games, community, Lichess themes) →
coach-selected review → Focus Game / Win it back → focus outcome`

- **Mode 2** = the live Personal Improvement Cycle, unchanged in shape. It reads
  the same plan the coach would see, with approval skipped.
- **Mode 1** = the academy coach page gains a plan for each child, built from
  that spine, with approve / edit before the child and parent see it.
- Academy children move onto `user_active_focus` so both doors read one diagnosis.

Not PARALLEL: a separate "coach plan" product would sit beside the cycle and
diverge from it.

---

## 1. What it is

Every week, ChessGuru reads each student's games, finds the one thing that is
costing them most, and writes that student a short plan: puzzles to solve, one
position from their own game to study, a game to play, and a game to look at
again, each with a one-line reason. A coach opens the student, reads the plan,
changes anything they disagree with, and approves it; only then does the
student (and, for a child, the parent) see it. A player without a coach gets
the same plan from the same engine, sent straight to them, but only for
problems the engine can prove on the board. Next week the plan is checked
against the student's new games, and every change a coach makes is recorded,
so we learn which kinds of plan are good enough to run without a coach.

## 2. What the user sees

All names, games and counts below are illustrative. Before code, screen 2b is
rebuilt as a clickable mock from real games (section 7).

### 2a. Coach — the batch page gains a plan column

```
Saturday batch                                       This week (9–15 Nov)
┌──────────┬──────────────────────────────┬───────────────┬──────────────┐
│ Child    │ What we saw                  │ Plan          │ Needs you?   │
├──────────┼──────────────────────────────┼───────────────┼──────────────┤
│ Asha     │ Leaves pieces where they can │ Ready to      │ Approve plan │
│          │ be taken                     │ approve       │              │
│ Kabir    │ Not enough games yet         │ Lessons only  │ —            │
│ Meera    │ Misses forks                 │ Approved      │ —            │
└──────────┴──────────────────────────────┴───────────────┴──────────────┘
```

### 2b. Coach — one student's plan (the core screen)

```
Asha · plan for 9–15 Nov                                   Draft, not sent
────────────────────────────────────────────────────────────────────────────
WHAT WE SAW (6 games since last Saturday)
  She leaves a piece where it can be taken — in 4 of the 6 games.
  [ See the 3 clearest moments ]

LAST WEEK'S PLAN
  Done: 7 of 10 puzzles, Win it back.  Not done: review.
  The habit: 4 games of 6 this week, 5 of 6 the week before — about the same.

THIS WEEK'S PLAN
  1  PUZZLES   10 positions: "Something here is loose. Find the move."
               6 from her own games, 4 from Lichess (hanging piece, near her
               level).                                   [ Change ] [ Remove ]
  2  STUDY     Her game vs Rohan, move 14. Her bishop on b5 was attacked by
               the knight and she moved the other bishop.   [ Pick another ]
  3  PLAY      Win it back: vs Rohan from move 18, she was winning.
                                                         [ Pick another ]
  4  REVIEW    Her loss vs Dev (24 moves): the clearest example this week.
                                                         [ Pick another ]

  Why this plan: the same slip in 4 games; nothing else came close.
  Change the focus: [ Piece safety ▾ ]   (also seen: misses forks, 2 games)

  Note to Asha (optional): [ __________________________________ ]

  [ Approve and send ]      [ Skip this week ]
```

Every "Pick another" offers two or three alternatives the engine already
checked. The coach chooses; they do not type chess.

### 2c. Student / child — the plan they receive

On the child's class page (academy) or the player's Home (self-coach):

```
This week with your coach
  ○ Puzzles: find the loose piece          ●●●●○○○○○○
  ○ Look at one moment from your game      [ Open ]
  ○ Win it back vs Rohan                   [ Play ]
  ○ Look again at your game vs Dev         [ Open ]
  Coach says: "Ask: is anything of mine attacked?"
```

No numbers about the child's play and no score: only what to do and how far
through it they are.

### 2d. Parent — one extra line in the existing weekly report

```
This week Asha's coach set her four short tasks on keeping her pieces safe.
She finished most of them.
```

### 2e. Self-coach player — same plan, no approval step

The same block as 2c on Home, titled "Your plan this week". Offered only when
the player's focus is on the proven list (section 3). Otherwise Home stays as
it is today.

## 3. In scope (V1)

- **One diagnosis for both doors.** Academy children are read by the same focus
  picker as every other player (`user_active_focus`), not by the academy's own
  count. A child with too few games gets "Not enough games yet" and a
  lessons-only plan.
- **A weekly plan with four kinds of item**, each with a one-line reason built
  from board facts (never written by the AI):
  - puzzles: the student's own verified positions first, then Lichess puzzles
    by theme (`topic_practice_themes`) near their rating, never one already
    solved;
  - one study position: the clearest moment from their week's games;
  - one game to play: Win it back (existing) or a class game (existing);
  - one game to review: the existing coach-selected review pick.
- **Proven ideas only** in V1: piece safety and the tactic themes already mapped
  (hanging piece, fork, pin, skewer, discovered attack). Any other focus shows
  the coach the diagnosis but no puzzle block, with "No checked puzzles for
  this yet".
- **Coach screen (2b):** approve, skip, remove an item, pick another from
  engine-checked alternatives, change the focus to a runner-up, add a note.
- **Every coach action is recorded** per item and per idea: approved unchanged,
  swapped, removed, focus changed, skipped.
- **Student view (2c)** on the class page. Each item opens the existing puzzle,
  review or Win it back page, and is ticked when done.
- **Last week's plan** shown to the coach: what was done, and the habit this
  week against the week before, using the existing academy trend rule.
- **Parent line (2d)** in the existing weekly report, no numbers.
- **Self-coach door (2e):** the same plan on Home with no approval, only when
  the focus is on the proven list.
- **Plans build in the background** with the existing two-hourly week rebuild;
  opening a page never runs the engine on a request.
- **No plan line is read from game-review captions.** "What we saw" comes from
  the focus record; the study position's reason is built from the board. A
  caption the verifier emptied must never leave a plan item without a reason.

## 4. Explicitly out of scope (V1)

- **Coaches writing their own puzzles or typing chess content.** They choose
  among engine-checked options only.
- **Ideas beyond the proven list:** positional ideas (all 36 are still in
  shadow on `/admin/detector-review`), king safety, endgames, openings.
- **The 15-minute AI personal class** (`docs/ai_personal_class_scope.md`). It
  can later become an item in the plan; it is not built here.
- **A plan for a whole batch at once.** The existing "suggested class topic"
  stays as it is.
- **Sending automatically.** WhatsApp stays the coach's own tap, as today.
- **Showing the "did it work" verdict to children or parents.** Coach only in V1.
- **A new mastery verdict.** The plan writes evidence; `concept_mastery_service`
  stays the only owner of "learnt".
- **Payments and plan pricing.**
- **Redesigning the adult Home** beyond adding the plan block.
- **Reminders, streaks, badges.**
- **Opening traps from Lichess.** Lichess themes are tactics, not traps; traps
  stay in our own 18-trap library.

## 5. Success criteria

1. **Coaches trust it.** Share of plans approved with at most one change, per
   idea. The bar is set by Mohit before the pilot starts. This is the "90%
   automation" claim, measured instead of assumed.
2. **Students do it.** Share of approved plan items finished within the week.
3. **It reaches real games.** For children who finish three weekly plans on one
   idea, the habit's rate in their own games compared with their weeks before
   the first plan. Reported to coaches only through the existing trend rule.
4. **Coach time.** Minutes from opening a student's plan to approving it,
   median per coach. The target is set by Mohit.
5. **The self-coach door is earned, not assumed.** An idea is offered there
   only after its coach-approval share passes the bar in (1) on enough plans;
   that count is locked with data, not chosen now.

Not success: plans generated, pages viewed, puzzles served.

## 6. Open questions

| Question | Why unresolved | Unblocking step |
|---|---|---|
| Where does an approved plan live? The improvement-cycle scope says "no rival program collection", but an approval and its edits must be stored somewhere. | Architecture choice that touches a signed rule | Proposal: store it on the existing academy week row; the self-coach door reads it from the focus without storing. Mohit decides. |
| Lichess puzzles for children: yes or no? `coaching_puzzle_service.py` says Lichess was removed on 2026-04-21 so every drill comes from real games; `topic_practice_themes.py` brought themes back in October where our own positions cannot be proven. | Two written rules disagree | Mohit decides. |
| The rating used for the puzzle window. Mohit's live focus says `rating_used: 912`, band "beginner". Not checked why. | Not investigated | Trace `resolve_coaching_rating` for his account before puzzles are picked by rating. |
| Mohit also has a focus row from 2026-07-02 marked `status: active` ("Low blunder rate", type strength) beside the November king-safety one. Not checked whether that is intended. | Not investigated | Read `primary_weakness_picker` for how strength rows are kept. |
| What approval share, on how many plans, makes an idea safe for the self-coach door? | Needs pilot data | `/lock-via-data` after the first weeks of coach approvals. |
| One theme or several? `topic_practice_themes` maps a broad weakness to several themes (missed tactic gives fork, pin, skewer and discovered attack). A coach would pick the one motif the student actually missed. | Granularity not decided | Decide whether the plan narrows to the single missed motif when the focus evidence names one. |
| Filter puzzles by the student's own openings ("forks from your Italian games")? | `opening_tags` is not indexed; a count on it ran over 10 minutes (Game Review session) | Decide if wanted; if yes, add the index after a deploy, then measure. |
| How many puzzles a week for a child? | Taste and completion data | Start at Mohit's number; adjust from success measure 2. |
| Who is the first coach: Mohit himself, or a real academy coach? | Not ours to choose | Mohit names them. |
| `docs/ai_personal_class_scope.md`: its status line says signed, its sign-off record says "Awaiting Mohit". | The document contradicts itself | Mohit says which is true. |

## 7. Pre-code requirements

- Mohit signs off this document.
- The first two open questions (where the plan lives, Lichess for children) are
  answered.
- The rating used for the puzzle window is traced and correct for at least
  Mohit's account and the test child.
- The focus picker is run read-only on the academy test children and returns a
  sensible result or "not enough games", never an error.
- Puzzle supply is counted for each proven idea at each rating band: enough
  unsolved puzzles that a child does not repeat one within a month.
- A clickable mock of screen 2b, built from real games, is reviewed by Mohit
  before the first file (card is the product).
- `/audit-pre-code` passes.

---

## Sign-off record

- 2026-11-08 — Section 0 path EXTEND agreed by Mohit ("go ahead").
- 2026-11-08 — sections 1–7 drafted. Awaiting Mohit.
- 2026-11-08 — supply, usage, theme granularity, opening filter and traps folded
  in from the Game Review session's measurements; the counts quoted in Section 0
  were re-run and matched.
