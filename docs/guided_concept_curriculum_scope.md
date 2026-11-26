# Guided Concept Curriculum — scope

Drafted 2026-11-26. **Awaiting Mohit's signoff. No code until then.**

Trigger: Mohit, 2026-11-26 — *"pick up content and actually teach user in his
own style… user should feel like guided, not like Aimchess and Chessiro that
you can do whatever you want."* Reference content: a YouTube short teaching
endgame concepts to under-1400s, whose transcript Mohit supplied.

---

## 0. Existing surfaces audit

**Everything in this section was read from prod (`chess_coach`) and this repo
on 2026-11-26. Counts are verified.**

### What already exists for this exact user need

| Surface | What it already provides | Size |
|---|---|---|
| `user_concept_understanding` | Per-user, per-concept mastery machine: `state` (shown/monitoring), `mastered_at`, `streak_clean`, `clean_games_total`, `shown_count`, `source_position`, and `concept_text` — the sentence we would say | **4,224 rows, 76 real users**, 1,037 with mastery set |
| The concept vocabulary | **36 named concepts** in a phase taxonomy: 12 `OP_`, 10 `TAC_`, 5 `END_`, 5 `MID_`, 3 `DEF_`, 1 `PAWN_`. Plus 225 lower-case ids, most of them auto-numbered `golden_*_NN` artefacts rather than concepts | 261 distinct ids |
| `onboarding_puzzles` | A question bank that already has the exact shape this feature needs: `question`, `answer_san`, `explanation`, `difficulty`, `family`, and `source_game_id`/`source_ply` so the position came from a real game | **11,812 rows** |
| `diagnostic_pool` | Curated Lichess puzzles tagged by `concept` and `tier`, with `puzzle_rating` and **frozen `step_grades` + `grade_fingerprint` (`diagnostic_frozen_grades.v1`)** so grading cannot drift between versions | 388 rows |
| `/diagnostic` route → `DiagnosticPuzzles.jsx` | A live, shipped page that runs a diagnostic puzzle session | `diagnostic_sessions`: 49 |
| `calculation_test_attempts` | The deeper-probe schema already designed: `found_the_idea`, `judged_the_end`, `sound_through`, `required_depth`, `stopped_early`, `submitted` | **4 rows ever** |
| `chess_understanding` | A knowledge profile across 8 dimensions, each with level / score / confidence / evidence_count / trend | 63 rows, stale since April |
| `user_teaching_memory` | Per-move teaching moments from real games, tagged with a `principle_id` (`TAC_PIN_PATTERN`, `OP_FINISH_DEVELOPMENT`) | **28,333 rows** |
| `user_misconceptions` | The belief-model collection, with a working vocabulary (`stops_calculating_too_early`) | **1 row** |
| `concept_tests`, `concept_test_results` | — | **0 rows. Scaffolded, never filled.** |
| `GET /api/coach/concepts/*` | `acknowledged`, `evidence/{id}`, `demote/{id}`, `mastery-detail`, `learning-progress` | live |
| `GET /api/coach/human-coach/curriculum` | A weekly training plan generated from weaknesses | live |
| `GET /api/coach/personal-curriculum` | "The one default-off curriculum decision shared by Home/Learn" | live, default-off |
| `/learn`, `/learn/traps`, `/learn/openings`, `/endgames/:cat/:lesson` | Existing teaching pages | live |

### Where the overlap is, honestly

The overlap is **large**. A mastery state machine, a concept list, two question
banks, a diagnostic page, and two curriculum endpoints already exist. Building
a parallel "concept curriculum" would be the third curriculum surface and the
third question bank.

### Where the genuine differentiation is

Three things do not exist anywhere in the above, and they are the whole point:

1. **Ordering.** I checked every concept record for any prerequisite, rank,
   level, tier, stage or difficulty field: **there is none.** Nothing decides
   that opposition comes before the rule of the square, or that a student is
   not ready for a concept. This is the "don't jump to an advanced concept"
   requirement and it has no implementation at all.
2. **A question that branches.** Every existing surface either shows a puzzle
   and marks it right/wrong, or explains. None asks, then asks a *second,
   related* question when the answer is right, and explains only when it is
   wrong. `calculation_test_attempts` has the schema for the deeper probe and
   4 rows of use.
3. **Proof-grade content.** Nothing currently distinguishes a lesson whose
   answer is *computed exhaustively* from one whose answer is an engine
   opinion. That distinction is what makes this feature safe (see §1).

### Known defect that blocks this feature

`concept_text` is the sentence we would speak to the student. **1,297 concept
ids carry more than one different text**, and the conflicts are nonsense — the
same queen-and-king mating sentence appears on `blocked_bishop`,
`premature_pawn` and `knight_on_rim`. `END_OPPOSITION` has **empty** text.

This is not a nice-to-have cleanup. It is the layer that talks to the student,
and it is wrong today.

### Decision: **EXTEND**

Extend `user_concept_understanding`, `diagnostic_pool` and the `/diagnostic`
page. Do **not** create a new curriculum surface, a new concept collection, or
a new question bank. `concept_tests` / `concept_test_results` already exist and
are empty — use them rather than inventing new names.

---

## 1. What it is

A guided course that the coach runs, concept by concept, in an order that
makes sense. Instead of handing the player a pile of puzzles and letting them
wander, the coach decides what today is about, teaches one idea, and checks
whether it landed by asking — not by telling. If the player answers correctly,
the coach asks a second, related question where the answer is different, so a
lucky guess is caught. If the player gets it wrong, that is when the coach
explains, and walks through the position the way a person would: here is the
move you want to play, here is why it fails, here is what they try, here is
your answer to each try.

The whole course starts in the endgame and in forced tactics, for one reason:
in those positions the right answer can be **proved by exhaustive search**
rather than estimated by an engine. A lesson built on a proof cannot be wrong.
That is deliberately the opposite of where our coaching text has been weakest.

---

## 2. What the user sees

### Screen 1 — the coach says what today is

```
  ────────────────────────────────────────────────────────
   TODAY · Endgames · 1 of 5
   The rule of the square
  ────────────────────────────────────────────────────────

   When a pawn runs for promotion, you do not have to
   calculate. You count.

   Count how many moves the pawn needs. Count how many
   moves the king needs. If the king needs more, the pawn
   gets through.

                                        [ Show me ]
  ────────────────────────────────────────────────────────
```

### Screen 2 — his own game, as the question

```
  ────────────────────────────────────────────────────────
   Your game, 14 November. Move 49. You are Black.
  ────────────────────────────────────────────────────────

        [ board: 8/p7/8/1K6/8/6k1/8/8  black to move ]

   Your pawn on a7. Their king on b5. Your move.

   Does your pawn get through?

            [ Yes, it queens ]    [ No, the king catches it ]
  ────────────────────────────────────────────────────────
```

Answer: **the king catches it.** Proved by exhaustive search, not evaluated.

### Screen 3a — he got it right, so the coach probes instead of praising

```
  ────────────────────────────────────────────────────────
   Right. Now a different one.
  ────────────────────────────────────────────────────────

        [ board: 2k5/8/8/8/2K5/8/5p2/8  white to move ]

   Their pawn on f2. Your king on c4. Your move.

   Can you catch it?

                      [ Yes ]    [ No ]
  ────────────────────────────────────────────────────────
```

Answer: **no, it queens.** The answer flips, so a player who said "the king
catches it" both times is caught here, and a player who counted gets both.
Two correct answers with opposite outcomes is the bar for "he knows this".

### Screen 3b — he got it wrong, so the coach explains

```
  ────────────────────────────────────────────────────────
   Not quite. Let us count it.
  ────────────────────────────────────────────────────────

        [ board, with the pawn's path and the king's
          path both drawn on it ]

   The pawn needs 5 moves to reach a1.
   Their king needs 4 moves to reach the a-file.

   4 is fewer than 5, so the king arrives first.
   The pawn does not get through.

   Try the same count on this one:        [ next position ]
  ────────────────────────────────────────────────────────
```

### Screen 4 — the concept made load-bearing

The final position of each concept is one where the idea decides a real game.
For the rule of the square, that is the position from Mohit's reference video:

```
  ────────────────────────────────────────────────────────
   Last one. You are Black, and you are winning.
  ────────────────────────────────────────────────────────

        [ board: 8/p1n3k1/8/6PP/5K2/8/8/8  black to move ]

   You have a passed pawn on a7. Before you push it —
   count.

   Their king reaches the a-file in time. So pushing
   the pawn is not the answer.

   There is exactly one move here that wins.

                              [ make your move ]
  ────────────────────────────────────────────────────────
```

Verified: `Ne6+` wins (engine, depth 40). **Every other legal move evaluates
to 0.00** — including the natural `a5`.

### The walk-through, when the coach explains a multi-move idea

Delivered in the structure of a human coach, which is the structure of a search
tree:

```
   You want to push the pawn. Count first — their king
   is in time, so that only draws.

   Ne6+ wins, and it is the only move that does.

   If they take the knight →  you queen the pawn.
   If they chase your pawn →  you take on g5 first.
   If they hold the pawns  →  you have both of them.
```

Each branch, and the verdict on each, comes from search. The words are
written from that tree; nothing in the chess is chosen by a language model.

---

## 3. In scope (V1)

- **The 15 computable concepts only**: 5 `END_` + 10 `TAC_`. Each one's
  correctness is established by exhaustive solve (endgames) or forced search
  (tactics).
- **A prerequisite order over those 15.** A concept cannot be offered until
  its prerequisites are mastered. Authored once, stored on the concept.
- **Rewritten `concept_text` for all 15**, replacing the broken and empty
  values. One sentence per concept, in the voice of the mockups above.
- **A generated position ladder per endgame concept.** For king-and-pawn
  concepts the full position space is enumerated and solved exhaustively; the
  ladder is selected from the solved set by difficulty.
- **The ask → right → related question → wrong → explain loop**, persisted in
  `concept_tests` and `concept_test_results` (both exist and are empty).
- **A Maia-conditioned script for every taught position.** Mohit, 2026-11-26:
  the coach must have a line ready for *every candidate move a player at this
  rating would actually consider*, not only the right one. Maia-2 supplies the
  human move distribution at the student's Elo; search supplies the verdict on
  each candidate; the coach answers each in order of how likely he is to play
  it. Verified working today: Maia-2 `0.11.0:rapid` on the reference position
  returns, at Elo 1200, `Ne6+` 70.8% (wins), `a5` 12.0%, `Nd5+` 9.8%,
  `Ne8` 4.3%, all drawn.
- **Maia as the difficulty filter for position selection.** A position where
  most of the student's rating band already finds the move is a weak lesson.
  Positions enter a concept's ladder only if the band's success rate falls in
  a chosen window. This replaces guessing at difficulty.
- **Personal hooks where they exist**: the user's own position mined from his
  games, used as the opening question of a concept when one is found.
- **A fallback when no personal hook exists** — the lesson opens on a
  generated position instead. This is the common case and must work on day one.
- **Mastery written back** to `user_concept_understanding` using the existing
  state machine, not a new one.
- **Surface**: extend `/diagnostic` (`DiagnosticPuzzles.jsx`), the page that
  already runs a question session.

## 4. Explicitly out of scope (V1)

- **The 20 positional concepts** (`OP_`, `MID_`, `DEF_`, `PAWN_`). Their
  answers are not computable, which is precisely where our existing coaching
  text is unreliable. They wait until the format is proven.
- **The front-versus-side principle** from the reference video. I verified the
  rule of the square exactly; I did **not** isolate this claim. It is not
  taught until it is proved.
- **Knight-routing / "count backwards to c8 in three"**, the third idea in the
  video. Computable (graph search) but a separate concept, deferred.
- **Rook endgames via Syzygy tablebases.** Correct approach, needs tablebase
  files on the box. Deferred to V2.
- **"Cool games to review together."** `teaching_games` holds 1 row; this is a
  content type from zero.
- Any LLM-written chess. The model writes English from a computed tree only.
- Parent or academy reporting on curriculum progress.
- Replacing `human-coach/curriculum` or `personal-curriculum`. They stay.
- Repairing `concept_text` for the other 1,282 ids. V1 fixes the 15 it uses.

## 5. Success criteria

V1 worked if, within 3 weeks of launch:

1. **Completion**: ≥ 60% of users who start a concept finish all its questions
   in the same session. Below that, the sequencing is wrong or it is boring.
2. **The probe earns its place**: ≥ 15% of users who answer the first question
   correctly get the *related* question wrong. If nearly everyone passes both,
   the second question is too easy and is not testing understanding. If nearly
   everyone fails it, the ladder is mis-ordered.
3. **It survives contact with play**: for users who master a concept, the rate
   at which they violate that concept in their subsequent games falls, measured
   on `games.date_played` with the detector version held constant.
4. **Zero wrong answers.** Any graded answer that is later shown to be wrong is
   a V1 failure, not a bug to triage. This is the claim the whole feature rests
   on.

## 6. Open questions

- **Question:** Does the reference video's "never attack a passed pawn from the
  side, only from the front" hold as a general rule, or only with specific
  king placements?
  **Why unresolved:** my test used positions with no defending-side king, so
  the side approach never arose.
  **Unblocking step:** enumerate K+P vs K positions where the defending king
  is adjacent to the pawn's file and compare outcomes by approach square.

- **Question:** What is the real yield of only-move positions from our users'
  own games?
  **Why unresolved:** the mining job was still running when this was written.
  Earlier, 11 pure king-and-pawn races turned up in 1,200 games (<1%);
  only-move positions are a subset of that.
  **Unblocking step:** the running job reports it.

- **Question:** What is the prerequisite order over the 15 concepts?
  **Why unresolved:** nobody has authored it, and it is a coaching judgement,
  not an engineering one.
  **Unblocking step:** Mohit, or a coach, orders 15 index cards. One sitting.

- **Question:** Does the existing `/diagnostic` page's session model fit this
  loop, or does extending it distort it?
  **Why unresolved:** I read its route and its collections, not its component.
  **Unblocking step:** read `DiagnosticPuzzles.jsx` before the first commit.

- **Question:** Do we gate V1 to a few users, as `BETWEEN_GAMES_USERS` and
  `PERSONAL_CURRICULUM_ROLES` already do, or ship it to everyone?
  **Why unresolved:** Mohit's call.

- **Question:** What success-rate window makes a position a good lesson? A
  position 71% of the band already solves is weak; one 5% solve is
  demoralising. Where are the edges?
  **Why unresolved:** no distribution has been measured. Picking the window
  before seeing it is the mistake `/lock-via-data` exists to prevent.
  **Unblocking step:** run Maia over a few hundred candidate positions per
  concept and plot the band success rate before choosing cut-offs.

- **Question:** How far can Maia's output be trusted for ordering positions by
  difficulty?
  **What is known:** on the reference position it is smooth and monotonic
  across 1100-1500 in both directions — `Ne6+` 70.6 / 70.8 / 69.5 / 67.0 /
  64.1, and `a5` 10.8 / 12.0 / 14.4 / 17.9 / 21.5. That is reassuring. The
  only kink was at Elo 1000.
  **Why still unresolved:** one position proves nothing, and our own prior
  notes record Maia being unreliable at fine ordering.
  **Unblocking step:** check the same across a sample of positions with a
  known difficulty ordering before any ladder depends on it. Until then Maia
  is used for coarse band difficulty, never for a number shown to a student.

- **Question:** Should position selection weight "the error that grows with
  rating" above raw difficulty?
  **Why it matters:** on the reference position every wrong move shrinks as
  rating rises except `a5`, which doubles from 10.8% at 1100 to 21.5% at 1500.
  A growing error is the signature of a half-learned principle — the student
  has absorbed "passed pawns are strong" and it now overrides his counting.
  That is more valuable to teach than a position that is merely hard.
  **Why unresolved:** measured on one position only.
  **Unblocking step:** compute the rating-slope of each wrong move across a
  few hundred candidate positions and see whether growing-error positions are
  common enough to select on.

## 7. Pre-code requirements

Each is a hard gate.

1. **Mohit signs off on this document.** Explicit: "locked" / "ship it" / "go
   code". Not "sounds good".
2. The prerequisite order over the 15 concepts is authored and written down.
3. The 15 rewritten `concept_text` sentences are written and read by Mohit.
4. The generated-and-solved position set exists for at least one endgame
   concept, with every answer produced by exhaustive search.
5. `DiagnosticPuzzles.jsx` has been read, and the extend-versus-fork decision
   for that page is made.
6. The mining job's yield number is in hand, so the personal-hook rate is
   known rather than assumed.
7. `/lock-via-data` has been run on the numeric thresholds in §5 — the 60%,
   the 15%, and the difficulty bands of the ladder.
8. Maia-2 runs where the curriculum will run. Verified on this workstation
   today (`maia2_models/rapid_model.pt`, `0.11.0:rapid`); **not** verified in
   the prod container or on the server, and the model file is 280 MB.
9. The Maia band question is settled: `human_policy_runtime.py` refuses any
   player Elo outside 600-1500 by default. The curriculum must either stay
   inside that band in V1 or set the band explicitly. Note that this file
   currently carries a 47-line **uncommitted** change widening the band by
   environment variable; uncommitted work in this tree is at risk of being
   reverted by the parallel sync, so it must be committed or dropped before
   anything depends on it.

---

## Notes on evidence

Verified today, cited where used: the collection counts and field shapes above;
36 named concepts and the absence of any ordering field; 1,297 concept ids with
conflicting `concept_text`; `Ne6+` as the unique winning move in the reference
position at depth 40 with all alternatives at 0.00; the bare a-pawn race being
a draw; the exact solve of king moves in the a5/Ke4 race; and 11 pure
king-and-pawn races found in 1,200 analysed games.

Carried from memory and **not re-verified**: the 38%-wrong caption figure, and
the `BETWEEN_GAMES_USERS` / `PERSONAL_CURRICULUM_ROLES` gating.
