# AI personal class — scope

**Status:** DRAFT — awaiting Mohit's sign-off. No code until signed.
**Author:** Claude, 2026-11-06, against `origin/working-code` at 7a185d0e.
**Mockup:** one class built from Mohit's real games, every position engine-checked —
see the artifact linked in the sign-off record at the end.

Mohit, 2026-11-06: *"how do we build classes, personalised classes for our
students with AI?"* and earlier the same day: *"how can we become so tech
enabled that we can make it purely AI with very less human"* and *"I want to
build it for all levels … what we have built should be used"*.

---

## 0. Existing surfaces audit

A great deal of the teaching machinery exists. What does not exist is a
**class**: one sitting with a beginning, a middle and an end, that strings the
existing pieces together and changes as the child answers.

| Existing owner | What it already does | Used by the class as |
|---|---|---|
| `focus_resolver.get_active_focus` + `user_active_focus` | Decides "what should this player work on now" from their games | **Which idea today** — the class never picks its own topic |
| `personal_curriculum.build_player_curriculum` (signed 2026-08-28) | The Learn page plan: one lesson in focus, what comes before and after it | The fallback idea when no habit is showing in the games |
| `personalized_lesson_adapter.resolve_personalized_lesson` / `grade_personalized_move` | The coached workspace at `/training?personalized=1` ("make your move first, then your coach asks what you saw") for openings, traps, endgames, tactics | **Today's idea** step for curriculum lessons |
| `lesson_question_spec.py` | Owns the printed question and its grading so they match | Every question the class asks |
| `personal_teaching_profile` | Adapts delivery (never chess truth) to the learner | How the idea is explained |
| `lesson_continuation.build_continuation` | Plays a lesson out after the correct move, coaching each move | After a correct answer in "Today's idea" |
| `/training/pattern/:pattern`, `/training/prescribed` | Positions from the player's own games for one habit | **Guided practice** pool |
| Board geometry lessons + memory check | Spaced "memory check due" for the four shapes | The pattern for the **warm-up** recall |
| Play with Coach, `CoachOpponent`, Maia (`human_policy_runtime`, flag `PWC_HUMAN_POLICY_OPPONENT_ENABLED=false` on prod) | A coached game; Maia predicts human moves at a rating | **Play it** — the opponent should be Maia at the child's level |
| `academy_service.read_move`, `safe_better_move`, `_hanging_after` | Board checks: a piece left to be taken, a piece left under attack, a piece saved | Picking and grading piece-safety positions (used for the mockup) |
| Academy Win it back homework, parent report, class topic | Homework from the child's own slip; weekly parent report; one topic per batch | **Wrap-up** homework and the parent line; group class topic |
| `concept_mastery_service`, `lesson_evidence_review`, `MASTERY_STRICT_EVIDENCE` (default off) | Whether an idea is learnt, from tests and real games | The only place "learnt" is decided — the class writes evidence, never a verdict |
| `home_session.build_session` | Home's "appreciate / improve / discover / challenge" choice | Home offers "Start today's class" as one of its choices |
| `docs/teaching_loop_scope.md` (draft) | Mohit's rule: "taught means understood… a test of 5 puzzles… then monitor in a real game" | The class's practice step is that test; the next class's warm-up is the monitor |
| `docs/learning_experience_system_scope.md` | "Do not create a separate Academy or another open lesson library" | Honoured: the class adds no lesson content and no library |

**Overlap.** Learn, Training and Play with Coach can each already deliver a
piece of a lesson. A player has to stitch them together alone, and nothing
adapts within a sitting.

**Genuine difference.** The class is a sequencer with a fixed shape, a
difficulty rule inside the sitting, a child voice, and a warm-up that checks
the last idea against the child's real games.

**Decision: EXTEND.** The class is a new *sequence* over existing owners. It
adds no new focus picker, lesson content, grader, mastery store or caption
path. Two known gaps limit what it can teach (see section 6):

- Only ideas we can reliably find on a board can be taught. All 36 positional
  principles on `/admin/detector-review` are still in shadow mode.
- "No puzzles for King Safety yet" (`/training?weakness=current`, seen
  2026-11-06 for Mohit) — the current focus can point at an idea with no
  positions. The class must then fall back, not show an empty step.

---

## 1. What it is

A short class, about fifteen minutes, that a child (or any player) takes on
their own. It has the same shape a good human class has: a warm-up from last
time, one idea, practice that gets harder or easier depending on the answers,
a short game where the idea comes up, and a wrap-up with homework. The idea
and the positions come from the child's own games, so every class is
different for every child. The engine decides the chess; the AI only puts it
into words the child understands.

## 2. What the user sees

The mockup shows Mohit's real class (piece safety, from his games of
5 November). In words, for a child:

```
┌────────────────────────────────────────────┐
│ 1  WARM-UP                        ★ ☆ ☆ ☆ ☆ │
│ Hi Mohit! Quick warm-up.                   │
│ Tap your piece that is in danger.          │
│ [ board from your game ]                   │
│ → Yes! The rook is looking at your queen.  │
├────────────────────────────────────────────┤
│ 2  TODAY'S IDEA                            │
│ This is from your game.                    │
│ Before you move, ask one question:         │
│   "Is anything of mine attacked?"          │
│ Tap the piece in danger. → the bishop.     │
│ The knight on d5 attacks it. You played    │
│ Bb5 and the bishop stayed in danger.       │
├────────────────────────────────────────────┤
│ 3  PRACTICE                 easy → harder  │
│ Your queen is attacked. Find a safe square.│
│ Right → a harder one. Wrong → a hint, then │
│ an easier one.                             │
│ Three ways to save a piece:                │
│   move it · take the attacker · guard it   │
├────────────────────────────────────────────┤
│ 4  PLAY IT                                 │
│ A short game against a player at your      │
│ level. "Stop! Something of yours is        │
│ attacked. Can you find it?"                │
├────────────────────────────────────────────┤
│ 5  WRAP-UP                         ★★★★★   │
│ Today you learnt: before every move, ask   │
│ "Is anything of mine attacked?"            │
│ Homework: Win it back                      │
│ For your parent: one line, no numbers.     │
└────────────────────────────────────────────┘
```

Adults get the same class with adult wording, no stars, and a longer game.

## 3. In scope (V1)

- A class sequencer: warm-up → idea → practice → play it → wrap-up, resumable
  if the child leaves mid-class.
- Idea selection read from `get_active_focus`; when that idea has fewer than
  the minimum practice positions, fall back to the next plannable item from
  `build_player_curriculum` (never an empty step).
- Practice positions from the child's own games first, then the shared pool,
  graded through `lesson_question_spec` so every move that answers the printed
  question is accepted. Three replies, decided by playing every legal move out
  with the engine:
  - **right**: no piece worth saving can be won, and the move is close to the
    engine's best;
  - **safe but costly**: the piece is safe but something else goes — named when
    the engine line shows it ("their queen takes your e4 pawn with check");
  - **still in danger**.

  The question says "save it **without giving anything else away**". Building
  the mockup showed why: "keep every piece safe" only checks knights, bishops,
  rooks and queens, so in one of Mohit's positions Bxe5 saves the bishop and
  still loses the e4 pawn with check two moves later. The printed question
  must match the grader.
- One difficulty rule inside the class: right → next position is harder;
  wrong → a hint, then an easier position. "Harder" and "easier" defined by a
  measured property (number of safe answers, depth of the threat), locked with
  `/lock-via-data` before code.
- The play-it game against Maia at the child's level, with the coach stopping
  at most twice, only when today's idea is on the board.
- Warm-up: one position on the previous class's idea, taken from the child's
  real games since that class when one exists.
- Child voice and adult voice through the central caption layer
  (`caption_pipeline.py`), chosen by a per-account audience setting (age group
  + level, set by the parent, academy or player).
- Wrap-up homework from the existing Win it back, and one parent line in the
  academy report.
- Tap-to-answer everywhere (tap a piece, tap a square, make a move). No typing.
- Ideas in V1: piece safety only (the three ways: move it, take the attacker,
  guard it). It is the one idea whose board checks are built and verified.

## 4. Explicitly out of scope (V1)

- **Voice in and out.** The coach speaking aloud and listening comes after the
  class shape is proved. Text and taps first.
- **A coach character with a name and a face.** A design decision for Mohit
  (section 6); V1 uses "Coach".
- **Ideas beyond piece safety.** Each new idea needs its board check passed on
  the detector-review page first.
- **Group classes taught live.** The batch topic exists; teaching a batch at
  once is V2.
- **Rules lessons for children who cannot play yet.**
- **Rewards beyond the stars in one class** (levels, streaks, badges).
- **Hindi and other languages.**
- **Any new mastery verdict.** The class writes evidence; the existing
  mastery owner decides.
- **Reading frustration from play** (fast moves after a loss, quitting). It is
  probably behavioural monitoring of a child under DPDP section 9(3) — not
  built until the lawyer answers.

## 5. Success criteria

1. **Children come back on their own.** Of the test children, the share who
   start a second class within 7 days with no reminder from anyone. This is
   the kill test for "purely AI": if children do not return without a human,
   the direction is wrong. The bar is set by Mohit before the test starts, not
   after.
2. **The idea reaches real games.** For children who finish three piece-safety
   classes, the weekly "piece left under attack" rate in their own games,
   compared with their weeks before the first class. Measured, not claimed;
   reported to the parent only through the existing trend cut (0.4 / 2.5).
3. **Every question is fair.** Zero practice positions where a move that
   answers the printed question is marked wrong (checked by replaying every
   served position against its answer set).

Not success: classes started, minutes spent, stars given.

## 6. Open questions

| Question | Why unresolved | Unblocking step |
|---|---|---|
| Who are the 5–10 test children? | Not ours to choose | Mohit names them (his network or one academy) |
| What return rate kills the idea? | It is a business bar, not a measurement | Mohit sets it before the test |
| Does reading a child's games count as behavioural monitoring under DPDP section 9(3), and does ChessGuru (or an academy using it) count as an educational institution? | Law-firm summaries only; not the Gazette text | The lawyer, with the consent text and the Terms |
| Coach character: name, look, voice | Product taste | Mohit chooses after seeing the mockup |
| Age groups for the audience setting (e.g. 5–7, 8–10, 11–14, adult) | No age field exists today (checked on all 132 users, 2026-11-05) | Mohit chooses; the parent or academy sets it |
| Turn on Maia for the play-it game? | `PWC_HUMAN_POLICY_OPPONENT_ENABLED=false` on prod; Maia measured at 400 ms a move on the shared box | Measure on the server we move to |
| What makes a position "harder"? | Not measured | `/lock-via-data` on the practice pool before code |
| How close to the best move is "right"? The mockup used 0.3 pawns at depth 14. At depth 12 one position's answers changed at the edge (Bg5 in and out). | Not measured | Lock the margin and depth with data on the practice pool |
| The current focus can be an idea with no positions (King safety for Mohit today) | Focus picker and position pool disagree | Fall back by rule (section 3); log every fallback so the gap is visible, never silent |

## 7. Pre-code requirements

- Mohit signs off this document.
- The "harder / easier" rule is locked with data.
- The practice pool for piece safety is counted per level: enough positions
  at each level that a class never repeats a position within a month.
- The audience setting (age group + level) is agreed, because the child voice
  hangs on it.
- The test children and the kill bar are named before the first class runs.

---

## Sign-off record

- 2026-11-06 — drafted. Awaiting Mohit.
- Mockup (playable, Mohit's games of 5 November): https://claude.ai/artifact/QLw7YqGTQ3kiNLQeacWXFp
