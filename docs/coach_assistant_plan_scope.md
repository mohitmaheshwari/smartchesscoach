# Coach's assistant and self-coach plan — scope

**Status:** REVISED DRAFT 2026-11-09, **awaiting Mohit's sign-off.** The signed
version (puzzle-led plan, signed 2026-11-09 "so, go ahead") is superseded: Mohit
rejected its mock as "very basic … anybody who uses simply game analysis can know
this" and asked for a coach that teaches *what to look at* so the child sees the
problem next time. Sections 1–7 below are rewritten for that. Storage on the week
row (confirmed 2026-11-09) still stands. No feature code until this is signed.
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

### Added 2026-11-09 for the cause-first direction

Read in code and on prod (read-only) on 2026-11-09.

| Existing owner | What it does today | Live? |
|---|---|---|
| Reflect V1 (`routes/reflect.py` `/v1/quick-tags`, `/v1/submit`; `reflect_constants.py`; `Reflect.jsx` at `/reflect`) | Asks the player, per mistake, for an intent from a fixed list (Attack, Defend, Develop / Improve piece, Avoid a threat, Not sure … `reflect_constants.py:63-93`), a confidence (Very sure / Somewhat sure / Guessing), and quick tags from board predicates; computes an "awareness gap" type; a tap budget per rating band | Routed. **Used by almost nobody:** `reflection_sessions` 10 rows from 1 user ever, latest 2026-11-06; `reflections` 0 rows |
| `two_layer_diagnosis.py` (signed 2026-09-28, `docs/two_layer_coaching_scope.md`) | "You do not know this pattern yet" vs "you know it and are not looking", inferred from population statistics (knowledge rate; thinks-long tempo). Called from `routes/home.py`, `motif_drill_service.py`, `opportunity_gate.py` | Yes. Whether its output reaches a screen today: not checked |
| `grade_destination_safety_candidate` / `destination_safety_exact` (PLAN grade in `detector_quality.py`) | Says, from the board, whether a piece landed where it can be taken | Yes |

**Decision (proposed):** EXTEND Reflect V1 rather than build a new reflection.
Keep its storage (`reflection_sessions`) and its intent ids; replace the
generic text chips with board taps whose options the board computes; add two
answers it does not collect today: *found the taker when asked* (a tap test)
and *saw it in the game* (a self-report). Those two give
`two_layer_diagnosis` direct evidence per moment instead of only a population
inference. The tap flow is the child's screen; the coach reads the results.

---

## 1. What it is

Every week, ChessGuru finds the one problem that cost each student the most
results, not the one that happened most often. It then works out the cause
with the student: on two or three of their own moments, the student answers
by tapping the board what the move was for, which enemy piece could take it,
and whether they saw that piece in the game. From those answers the coach
sees whether the student does not know the pattern, knows it and did not look,
or saw it and misjudged the trade. The plan then teaches a warning sign — one
question to ask before moving — and sets one rule for real games. Puzzles and
replays practise that question; they are not the plan. Next week the rule is
checked against the student's new games. A head coach approves each student's
plan from one batch page; a player without a coach gets the same plan with no
approval step, only for problems the engine can prove on the board.

## 2. What the user sees

The child's screen is built as a clickable mock on three real moments from the
test child's games: https://claude.ai/artifact/78PJ9nfnTgWPSjKZ6Ha8Jr (version 3,
2026-11-09). The coach screens below are text sketches; their clickable mock
is a pre-code requirement (section 7). Names and counts below are illustrative.

### 2a. Coach — batch page, approve every student's plan

```
Saturday batch                                         This week (9–15 Nov)
┌────────┬────────────────────────────┬──────────────────────┬──────────────┐
│ Child  │ Costliest problem          │ Cause (from her taps)│ Needs you?   │
├────────┼────────────────────────────┼──────────────────────┼──────────────┤
│ Asha   │ Pieces left where they can │ Not looking: finds   │ Approve      │
│        │ be taken (lost 2 good      │ the taker when asked,│ [ Approve ]  │
│        │ positions)                 │ didn't see it in game│              │
│ Kabir  │ Not enough games yet       │ —                    │ —            │
│ Meera  │ Pieces left where they can │ Doesn't see knight   │ Approve      │
│        │ be taken                   │ jumps yet            │ [ Approve ]  │
└────────┴────────────────────────────┴──────────────────────┴──────────────┘
[ Approve all unchanged ]
```

### 2b. Coach — one student

```
Asha · 9–15 Nov                                          Draft, not sent
──────────────────────────────────────────────────────────────────────────
COSTLIEST PROBLEM
  Leaving a piece where it can be taken. Lost 2 positions that were level
  or better, in 6 games.                         [ See the moments ]

WHAT HER REFLECTIONS SAY (3 moments)
  Qf3  wanted: bring the queen out · taker: knight e5 (knight jump)
       found it when asked: yes · in the game: didn't see it
  Rc7  wanted: attack the knight on e7 · taker: bishop h2 (long diagonal)
       found it when asked: no · in the game: didn't see it
  ...
  Cause: mostly NOT LOOKING (she finds the piece when she looks).

WARNING SIGN
  General check: "Before any piece lands: pieces close by, knight jumps,
  long lines to the edge."     (No sign of her own beats her baseline yet.)

RULE FOR REAL GAMES THIS WEEK
  Do the three looks before every move that puts a piece on a new square.
                                                           [ Change ▾ ]

PRACTICE (practises the sign)
  Her 2 other moments in the tap flow · 6 positions: "can it be taken here?"

LAST WEEK'S CHECK
  The problem: 4 games of 6 → 2 games of 5.  Slower at those moments: yes.

  [ Approve and send ]   [ Skip this week ]
```

### 2c. Child — the reflection, then the rule

The tap flow in the mock: what was it for (tap the ringed pieces it attacks or
guards, or "Bring it into play" / "Not sure" / "Something else") → which of
his pieces can take it (tap them) → "in the game, did you see it?" (three
buttons) → what happened → your turn (tap a square, the board does the check
aloud) → "Your reflection" card and this week's rule. No typing anywhere.
Every reply comes from the board or the engine; none is written by an AI.

### 2d. Parent — one line in the existing weekly report

```
This week Asha looked back at three moments from her games and has one
thing to check before she moves. Her coach will see how it goes.
```

### 2e. Self-coach player — same flow, no approval

The same reflection flow and rule on Home, only for problems on the proven
list (section 3).

## 3. In scope (V1)

- **Rank problems by results lost, not frequency.** A moment counts when the
  position was level or better before it and the game was then lost or drawn.
  The exact cut is locked with data (section 7).
- **One proven problem in V1: a piece left where it can be taken**
  (`destination_safety_exact`, PLAN grade). It is the only problem with both a
  trusted detector and a tap test already mocked. *Proposed narrowing — the
  signed version also listed fork, pin, skewer and discovered attack; Mohit
  decides.*
- **The child's reflection flow (2c)** on two or three of the week's moments,
  chosen by results lost. Options on the board are computed from the board:
  pieces the move attacks, own pieces it guards that were under attack, and
  "bring it into play" checked against the piece's starting square.
- **Three recorded answers per moment:** what the move was for (Reflect V1
  intent ids), found the taker when asked (tap test), saw it in the game
  (self-report). Stored in `reflection_sessions`.
- **Cause per student**, from those answers, in three kinds: not looking,
  doesn't know the pattern yet (named by the taker's kind: knight jump, long
  line, piece close by), misjudged the trade. Fed to `two_layer_diagnosis` as
  direct evidence.
- **Warning sign:** the general three-look check by default. A sign specific
  to the child (for example "long diagonals") is shown only when it beats that
  child's own baseline by the bar locked in section 7; never shown as fact
  otherwise.
- **One rule for real games per week**, and **next week's check**: did the
  problem happen less in the new games, and did the child take longer on the
  moves where a piece could be taken. Think-time is read from
  `move_observations` (clock fields filled 2026-11-09).
- **Practice that drills the sign:** the child's other moments in the tap
  flow, and positions asking "can it be taken here?" from their own games.
  Lichess puzzles only where they train the same side of the habit (see the
  note on "hanging piece" below).
- **Coach screens (2a, 2b):** approve all unchanged, approve one, change the
  rule, skip. Every coach action recorded.
- **Parent line (2d)**, no numbers. **Self-coach door (2e)**, proven list only.
- **Background build** with the two-hourly week rebuild; no engine work on a
  page load; never scan `game_analyses` on a request.

## 4. Explicitly out of scope (V1)

- **Typing, free text and AI-written replies** to the child. Every answer is a
  tap; every reply comes from the board or the engine.
- **Problems beyond piece safety** in V1 (if Mohit accepts the narrowing):
  missed tactics, positional ideas (all 36 in shadow), king safety, endgames,
  openings. The coach still sees them named as runners-up.
- **Showing the cause or the check result to children or parents** as a
  verdict. The child sees their own reflection card only.
- **A new mastery verdict.** `concept_mastery_service` stays the owner of
  "learnt".
- **The 15-minute AI personal class**, automatic sending, payments, reminders,
  streaks, badges, opening traps from Lichess.
- **A new collection.** Reflections go in `reflection_sessions`, the week's
  plan on the week row.

## 5. Success criteria

1. **The problem happens less in real games.** For children who did two weekly
   rules on piece safety, the rate in their own games against their weeks
   before the first rule. Reported to coaches through the existing trend rule.
2. **They look longer where it matters.** Think-time on moves that land a
   piece where it can be taken, against the child's own baseline.
3. **Children finish the reflection.** Share of assigned moments reflected on
   within the week.
4. **Coaches trust it.** Share of plans approved with at most one change; the
   bar set by Mohit. **Coach time:** median minutes per batch.
5. **The self-coach door is earned:** offered only after (4) passes on enough
   plans; the count locked with data.

Not success: reflections started, pages viewed, puzzles served.

## 6. Open questions

| Question | Why unresolved | Unblocking step |
|---|---|---|
| V1 limited to piece safety? | Proposed narrowing of the signed scope | Mohit decides. |
| How "results lost" is cut (level-or-better before, lost or drawn after; which eval band) | Not measured for this use | `/lock-via-data` on the pilot children's games. |
| The bar a child-specific warning sign must clear | The diagonal sign the Game Review session tested scored 5/16 vs 1/21 (knight) and 3/59 (near piece), but the split was chosen after looking, across four comparisons (relayed, not re-run here) | `/lock-via-data`: fix the comparison before looking, then measure. |
| Is the "saw it in the game" self-report honest? | A child may tap "didn't see it" by default | Measure agreement with the tap test on the pilot weeks; if the two never disagree, the question adds nothing. |
| How many moments a week to reflect on | Taste and completion data | Start at 3; adjust from success measure 3. |
| Reflect V1's latest `reflection_sessions` row has none of the V1 intent fields | Its writer is not found yet | Find the writer before calling it a bug. |
| ~~Where does an approved plan live?~~ The improvement-cycle scope says "no rival program collection", but an approval and its edits must be stored somewhere. | **Answered 2026-11-09: the week row** (Mohit, "so, go ahead") | **Confirmed:** on the existing week row (`academy_student_weeks`, unique on student + week, `academy.py:74`), so no new collection. Store the draft as generated, the coach's changes, `opened_at`, `approved_by`, `approved_at` — measures 1 and 4 need them, and parent reports already keep who approved and when (`academy.py:579-581`). The week rebuild writes with `$set` (`academy.py:262-266`), so the plan must be carried over the way a good moment is (`academy.py:253-261`): the approval survives only when the focus is unchanged; a new focus starts a new, unapproved draft. Self-coach door: read from the focus, nothing stored in V1. |
| ~~Lichess puzzles for children: yes or no?~~ | **Answered: YES** — Mohit to the Game Review session, 2026-11-08 (relayed, not said in this session). | The October theme route (`topic_practice_themes.py`) is the rule for children; the 2026-04-21 note in `coaching_puzzle_service.py` no longer governs the plan. |
| ~~The rating used for the puzzle window.~~ **Traced 2026-11-09** (prod, read-only). | Mohit's 912 is the median of his last three chess.com games (`rating_source: chess.com`; chess.com rapid 920, 912, 904; last chess.com game 2026-09-24). He now plays on Lichess (blitz about 1340, rapid about 1436). `resolve_coaching_rating` keeps the named source even when it has gone quiet (`rating_resolver.py:157-174`). The test child has no named source, so it gets 1432 from Lichess (`sample_games: 3`, blitz and rapid mixed). | Children: correct. Adults with a quiet named source: the puzzle window would be wrong. Changing the resolver touches every rating-aware surface, so it is a separate decision for Mohit, not part of this build. |
| ~~Mohit's July strength row still `status: active`.~~ **Answered 2026-11-09:** intended. | Strength rows (`type: strength`) are one per player, overwritten in place (`primary_strength_picker.py:262-266`), and skipped by the weakness picker (`primary_weakness_picker.py:503-511`). They are written only by a manual script (`scripts/assign_strengths.py:7`), so the row stays from July. | None for this scope. |
| What approval share, on how many plans, makes an idea safe for the self-coach door? | Needs pilot data | `/lock-via-data` after the first weeks of coach approvals. |
| One theme or several? `topic_practice_themes` maps a broad weakness to several themes (missed tactic gives fork, pin, skewer and discovered attack). A coach would pick the one motif the student actually missed. **Direction, 2026-11-09 (Mohit to the Game Review session, relayed, not said in this session):** the assistant must track precisely what each child misses, his example "missing back rank mate", so the coach has that data. | Granularity not decided. **Checked 2026-11-09** in `detector_quality.py` on `origin/working-code` (last changed f3d2bd94): trusted to steer a plan are `missed_fork`, `missed_pin`, `missed_skewer`, `missed_mate` (:262, "says a mate was available, not how to find one", so the mate pattern is not named), `ignored_king_attack`, `destination_safety_exact` and three time-management ids. `back_rank_mate_exact` (:567) is built but SHADOW, and only names immediate mates. So today a coach would see "missed a mate", not "missed a back-rank mate". Not re-run, from saved notes of 2026-10-20: 62% of missed tactics fall in a generic bucket, and about 1.8% of that bucket can be named at the precision bar. | Proposal from the Game Review session, **not decided by Mohit:** record every miss under the most specific name that is proven. Keep an unnamed miss as "missed a forced mate, pattern not named", with its position, and never drop it. A coach's label on an unnamed miss becomes reviewed evidence for promoting a detector such as `back_rank_mate_exact`, so the coach's work improves the tracker. Measure first: on the pilot children's weeks, how many misses get a proven name, and how many stay unnamed. |
| Filter puzzles by the student's own openings ("forks from your Italian games")? | `opening_tags` is not indexed; a count on it ran over 10 minutes (Game Review session) | Decide if wanted; if yes, add the index after a deploy, then measure. |
| How many puzzles a week for a child? | Taste and completion data | Start at Mohit's number; adjust from success measure 2. |
| ~~Who is the first coach?~~ | **Answered: a real academy coach, not Mohit** — Mohit to the Game Review session, 2026-11-08 (relayed). | Mohit names the academy and the coach before the pilot week. |
| `docs/ai_personal_class_scope.md`: its status line says signed, its sign-off record says "Awaiting Mohit". | The document contradicts itself | Mohit says which is true. |

## 7. Pre-code requirements

- ~~Mohit signs off this document.~~ Done 2026-11-09.
- ~~Mohit confirms the recommended storage (the week row).~~ Done 2026-11-09.
  Lichess for children is answered (yes).
- ~~The rating used for the puzzle window is traced.~~ Done 2026-11-09. Correct
  for the test child (1432, Lichess). Mohit's 912 comes from a chess.com source
  that went quiet in September (section 6); fixing that is a separate decision.
- ~~The focus picker is run read-only on the academy test children.~~ Done
  2026-11-09 by calling `pick_next_focus`, which writes nothing, with the
  active-focus check stubbed out in memory. Results:
  - Child 1 (Lichess linked, 64 analysed games): the stored active focus is
    piece safety, and it stays until closed. A fresh pick today would choose
    time management (36 games lost on time), with king safety, missed tactic and
    piece safety as runners-up.
  - Child 2 (no online account, one class game): no focus, because the picker
    needs 10 analysed games. This is the "Not enough games yet" path, not an
    error.
  - The improvement-cycle query is off for role `student` (`pic_enabled:
    false`), so children are read with the older evidence query and admins with
    the newer one.
- ~~Puzzle supply is counted.~~ Done 2026-11-09 with the plan's own query
  (`topic_practice_themes.mongo_query`: theme, from 150 below to 250 above the
  rating). Smallest: pin near 700, 9,242. Hanging piece is 28,215–40,763 at
  every rating point measured (700 to 1900), and fork is 100,338 or more. A
  child will not repeat a puzzle within a month at any number per week under
  2,000.
- ~~A clickable mock of the puzzle-led screen 2b~~ (GjGUF5uDipvQ7nTZe2bZbV).
  Reviewed and **rejected** by Mohit as basic; superseded.
- **Mohit signs off this revised document.**
- **Child's tap flow mock** (2c): https://claude.ai/artifact/78PJ9nfnTgWPSjKZ6Ha8Jr.
  Mohit's review so far fixed two things (more than one pick; "bring it into
  play" and "did you see it in the game"). Every board fact in it was computed
  with python-chess and depth-16 Stockfish on prod; not yet clicked through
  end to end by anyone but Mohit.
- **Coach screens mock** (2a, 2b) from the test child's real reflections.
- **Find the writer** of the `reflection_sessions` row without V1 intent
  fields, and check what `Reflect.jsx` renders today, before extending it.
- **Check whether `two_layer_diagnosis` reaches any screen today**, so its new
  evidence lands somewhere.
- **Re-run the Game Review session's child think-time figures** after the
  2026-11-09 clock backfill: before it, worker-written `move_observations` had
  no clock fields.
- `/lock-via-data`: the results-lost cut, the warning-sign bar, the
  next-week check, and what Mohit sets (approval bar, coach-time target);
  then `/audit-pre-code` passes.

### Found while running the pre-code checks (2026-11-09), for the build

- **The academy's own count and the focus detector disagree** on the same week.
  The academy counted 5 of 19 games (examples Ne4 and Qd3). The focus detector
  (`destination_safety_exact`, the only subtype the quality gate authorises)
  counted 6 of 19 games, at seven moves that include neither example. The plan
  takes its moments from the focus detector, as section 3 says.
- **Lichess "hanging piece" puzzles train the other side of this habit**: they
  ask the child to take a loose piece, while the habit is leaving one's own
  piece loose. The mock says so to the coach. Puzzles from the child's own
  games train the habit itself.
- **One position can be both the study item and a puzzle** (the Rf7 moment vs
  AboutToBlunder is also own-game puzzle `fb48ae2c_m32`). The build removes the
  duplicate.
- **The existing review chooser writes when asked** (`get_recommendation`
  creates a prescription row). The plan must use the read-only candidate loader
  (`_load_candidates`), run it in the background, and never scan
  `game_analyses` on a page load.
- Seen, not checked: the existing `/training/prescribed` payload labels Lichess
  hanging-piece puzzles with `themes: ["calculation_depth"]`, while the puzzles
  themselves carry `hangingPiece`. Not checked whether any page shows that label.

---

## Sign-off record

- 2026-11-08 — Section 0 path EXTEND agreed by Mohit ("go ahead").
- 2026-11-08 — sections 1–7 drafted. Awaiting Mohit.
- 2026-11-08 — supply, usage, theme granularity, opening filter and traps folded
  in from the Game Review session's measurements; the counts quoted in Section 0
  were re-run and matched.
- 2026-11-08 — three answers from Mohit, given to the Game Review session and
  relayed here: Lichess puzzles for children YES; first coach is a real academy
  coach; storage "you recommend" (recommendation recorded, awaiting his
  confirmation). The document itself is NOT signed off.
- 2026-11-09 — Mohit, in this session, after being told the remaining items were
  his sign-off and a yes on week-row storage: "so, go ahead". Recorded as sign-off
  of the document and confirmation of the week-row storage. Still unanswered: the
  `ai_personal_class_scope.md` contradiction (not blocking this scope).
- 2026-11-09 — Mohit also said "go ahead" in the Game Review session (relayed
  by that session). It came after he described the product as two doors (an
  assistant to a head coach, and a coach for players who have none). He had been
  told the scope already has both doors, coach door first with the self-coach
  door earned from it (success measure 5), and that his sign-off and the
  week-row storage were the open items. This is the same reading as the entry
  above: sign-off plus storage. It does not decide the record-every-miss
  proposal, which stays discussed, not decided.
- 2026-11-09 — Section 7 run: rating traced, picker run read-only, supply
  counted, mock built. Waiting on Mohit's review of the mock and on his numbers.
- 2026-11-09 — Mohit's "track precisely what each child misses" direction,
  relayed by the Game Review session, added to the "one theme or several"
  question. Detector grades re-checked on origin and matched. The record-every-miss
  proposal is still waiting for Mohit.
- 2026-11-09 — Mohit rejected the puzzle-led mock (relayed by the Game Review
  session) and, per that session, approved its cause-first recommendation there
  ("go ahead, do what you recommend"). In this session he asked for a tap-only
  board ("i don't want typing, how can we make board interactable"), reviewed
  the tap mock twice, and answered "okay". Sections 1–7 rewritten for the
  cause-first direction; Section 0 gained Reflect V1 and two-layer diagnosis.
  **Not signed:** the rewrite itself awaits Mohit's explicit sign-off.
