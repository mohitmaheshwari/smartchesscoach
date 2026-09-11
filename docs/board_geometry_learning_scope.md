# Scope: Board Geometry Learning

**Status:** LOCKED v1 — Mohit signed off · 2026-09-11
**Product decision:** EXTEND the canonical `/training` learning system, then integrate the completed layer into Play with Coach through the existing instruction, mastery, and board-annotation paths. This scope supersedes the earlier always-on direction in `coach_geometry_arrows_scope.md`.

## 0. Existing surfaces audit

ChessGuru already has most of the raw chess geometry and several partial delivery mechanisms. The missing product is one coherent journey that teaches a player to see the relationship, checks that they can find it without help, and then tests the same habit during Play with Coach.

| Existing surface or authority | What it already provides | Overlap and decision |
|---|---|---|
| `docs/pattern_learning_system_scope.md` | A signed knight-fork lesson: understand, see the attack map, identify both targets, reject fake forks, create or avoid the fork, solve mixed unseen positions, revisit a personal position, and complete delayed recall. | **Extend.** It remains authoritative for knight-fork content. Board Geometry generalises its teaching method to pawn and sliding-piece geometry; it does not create another fork lesson. |
| `docs/learning_experience_system_scope.md` and `docs/learning_experience_system_architecture.md` | `/training` as the host, `services.teaching_engine` as the lesson lifecycle, reviewed content, resumable sessions, immutable evidence, and the learner-facing states Learning / Remembered / Proven in games. | **Extend.** These remain the shared learning authorities. No separate Academy, lesson engine, mastery service, or progress model is created. |
| `PrescribedTraining.jsx`, `SkillDrill.jsx`, `MotifDrill.jsx`, and `EndgameLesson.jsx` | Personal puzzle delivery, detector-graded attempts, motif positions, and a reusable interactive board with introduction, attempt, feedback, retry, arrows, and completion. | **Consolidate.** The Board Geometry branch lives in `/training` and reuses the shared lesson shell. Migrated motif routes resolve to the same lesson state instead of maintaining a second experience. |
| Canonical caption facts in `caption_facts.py` | Piece-agnostic `multi_target_attack_evidence`, fork naming rules, and `aligned_pieces_evidence` with attacker, front piece, rear piece, squares, values, and line type. | **Canonical chess truth.** Board Geometry reads these facts or extracts their shared primitive; it does not create lesson-local fork, pin, or skewer truth. |
| `shape_patterns.py`, `shape_detectors.py`, and `shape_layer.py` | A 23-pattern catalog and deterministic detection of current or next-move knight, pawn, bishop, and rook forks, plus pin, skewer, x-ray, and related shapes. Current shape detections are blocked from product influence when the detector-quality gate is enforced because they lack reviewed promotion packets. | **Reuse only through the canonical evidence boundary.** Valuable future-square logic may be extracted into the shared truth path after a duplication audit and quality review. The lesson cannot directly bypass the quality gate. |
| `geometry_plans.py`, `/coach/play/geometry`, and `CoachPlay.jsx` arrows | A separate detector returns pins, active forks, loose targets, open files, and latent lines as arrows. The endpoint is default-off, and normal Play mode currently clears and suppresses the arrows. | **Replace the product direction.** Convert any reusable rendering adapter to consume canonical geometry facts. Retire the independent detector rather than maintain two definitions of a fork or pin. The new live experience is learner-controlled and evidence-gated, not a permanent map of every plan. |
| One Surviving Instruction, `pwc_skill_gate.py`, active focus, and the Play with Coach mission scoreboard | A stable instruction can be carried into a game, coaching can be gated by skill state, and the postgame flow can report session-owned evidence. These paths are default-off or limited by their existing rollout contracts. | **Extend.** A completed geometry lesson may contribute one plain instruction and verified application opportunities. Board Geometry does not create another PWC focus, mission, or mastery mechanism. |
| Existing PWC captions and teaching cards | Deterministic teaching captions, board arrows, interactive teaching modes, and the recent quiet-move suppression and atomic teaching-card behavior. | **Preserve.** Geometry prompts use the same completed response payload and central coaching surface. They never introduce a second late-arriving caption or a “Coach thinking” placeholder. |

The genuine new value is the learner-facing relationship layer: selecting two targets, finding their shared attacking square or line, identifying the usable piece, rejecting geometry that does not produce a sound tactic, and carrying that exact scan into a game.

**Decision: EXTEND AND CONSOLIDATE.** Build the complete layer in `/training`. When its truth, learning, and retention gates pass, connect it to Play with Coach through the existing instruction and application-evidence paths. Do not ship a parallel pattern product or revive the always-on arrow overlay as an independent coaching engine.

## 1. What it is

Board Geometry teaches 600–1500 players to see relationships between pieces before calculating moves. The player learns four visual families: knight shared-attack squares, pawn-fork spacing, diagonal lines for bishops and queens, and rank/file lines for rooks and queens. Each lesson moves from seeing the piece's attack map to finding a candidate square, distinguishing a real tactic from a visual coincidence, and recognizing the same relationship in an unfamiliar or personal position. Once the full layer is proven, Play with Coach carries one learned scan into a game and measures only opportunities the board can verify.

## 2. What the user sees

The lesson remains inside the existing Training experience. One instruction, one board, and one action appear at a time. Notation is secondary.

Every module opens with a **Geometry Flash**: a nearly empty board, one colored shape, and one short memory line. It appears as one complete visual state. There is no paragraph, evaluation bar, notation lesson, or delayed explanation.

```text
BISHOP / QUEEN                         ROOK / QUEEN

  o                                   o---o---o
    o
      o                               Same line. Check what stands behind.

Same colour. Trace the diagonal.


KNIGHT                                PAWN

T1       T2                           T1   .   T2
   L   L                                  \ /
     X                                     P

Two L-jumps. Find their meeting square.   One gap. Pawn attacks both.
```

The real board uses highlights rather than letters: the relevant light or dark squares receive one color, the line or L-shapes animate once, and unrelated pieces stay muted. The same Geometry Flash returns after a personal-game answer so the learner connects the clean shape to the crowded position.

**Knight shared-square lesson**

```text
SEE THE SHARED SQUARE

Their king and rook can both be attacked by one knight.
Tap the square where your knight would attack both.

                    [ interactive board ]

Hint                         Skip for now
```

After a correct answer, the board draws the two L-shaped attacks at once:

```text
Yes — a knight on c7 attacks the king on e8 and the rook on a8.
The shared square is what makes the fork possible.

                                      Continue
```

**Pawn geometry lesson**

```text
FIND THE PAWN FORK

These two pieces are on the same rank with one file between them.
Where must your pawn stand to attack both?

                    [ interactive board ]
```

The explanation names direction when it matters:

```text
A white pawn on d5 attacks c6 and e6.
The shape works only in the pawn's forward direction.
```

**Line geometry lesson**

```text
THREE PIECES, ONE LINE

Your bishop, their knight, and their king share a diagonal.
Tap the piece that is shielding the king.

                    [ interactive board ]
```

Then the player identifies what the order means:

```text
The knight on c6 is shielding the king on e8.
That is why the knight cannot leave the diagonal safely.
```

A matched counterexample uses the same visible alignment but changes a blocker, piece order, legal move, or tactical reply:

```text
The pieces share a diagonal, but this is not a working pin.
After the bishop moves, they can take it without losing either target.
```

Help fades in a fixed order: a plain-language hint, the relevant piece, one part of the line or attack map, and finally the complete animation. Revealed answers teach but do not count as independent recognition.

When the complete layer is eligible for Play with Coach, the setup explains the selected habit without adding another panel:

```text
ONE THING THIS GAME

Before moving your queen or rook, scan every square their knight can jump to.
```

At a verified application moment, the current coach card remains stable until the whole geometry interaction is ready. The board and prompt appear together:

```text
GEOMETRY MOMENT

Something changed. Which two pieces now share a knight's attack square?

                    [ tap two pieces ]

Show the geometry                 Continue playing
```

After the game, the result reports only measured opportunities:

```text
YOUR GEOMETRY CHECK

You found the shared square on move 18 without help.
On move 27, the same pattern was available and you missed it.

Next game: keep the same scan.
```

If no eligible opportunity occurred, the card says: `This pattern was not measured in this game.`

Personal positions are framed as one of three board-verifiable moments:

- **You allowed it:** the player's move created geometry that the opponent could use immediately.
- **You missed it:** the verified best move created useful geometry, while the played move did not.
- **You found it:** the player's move created useful geometry and the engine-supported continuation confirms that it worked.

Each card first asks the learner to find the shape on the board. The explanation then names the squares and reconnects the crowded position to the module's clean Geometry Flash. A moment is omitted when its attribution or tactical value is uncertain.

## 3. In scope (V1)

- Four complete geometry modules: knight shared-attack squares; pawn-fork spacing and direction; bishop/queen diagonal alignment; rook/queen rank-and-file alignment.
- Every module begins with one reusable Geometry Flash consisting of a minimal board, one highlighted relationship, one brief animation, and one short memory line.
- The clean flash and the later personal-game explanation use the same color, line, target, and shared-square visual grammar so the relationship is recognizable without rereading theory.
- Personal application positions are classified as `allowed`, `missed`, or `found` only when the move attribution and tactical value are deterministic; uncertain positions stay out of the lesson and live coach.
- Sliding-piece modules teach direct attacks, double attacks, pins, skewers, and latent x-rays by changing the blocker and piece order while keeping the visual relationship clear.
- Every module follows the proven journey: understand, map attacks, identify targets, find the shared square or line, reject real-versus-fake examples, create or avoid the pattern, solve mixed unseen positions, apply it to an eligible personal position, and complete delayed recall.
- Square selection, target selection, line drawing, candidate-square selection, and legal piece movement use one shared board interaction shell inside `/training`.
- Every answer is graded from deterministic board facts. Engine/PV evidence is required before a lesson says the geometry wins material, forces a move, or is the correct tactical choice.
- Every assessment, counterexample, and personal application position is reviewed and versioned under the existing learning-content contract. A changed position or accepted answer invalidates pending evidence for that content revision.
- Fork truth remains piece-agnostic. Knight and pawn lessons filter the canonical multi-target evidence by attacker type; they do not define their own forks.
- Pin, skewer, and x-ray lessons consume one canonical aligned-piece representation containing attacker, front piece, rear piece, line type, blockers, and whether the rear piece is the king.
- `concept_mastery_service` remains the only learner-facing progress projection. The user sees Learning, Remembered, or Proven in games, plus Refresh needed when supported.
- The full Board Geometry learning layer is completed and passes its content, truth, baseline/post, delayed-recall, accessibility, and resume tests before live PWC geometry intervention is enabled.
- PWC integration reuses one surviving instruction, the existing active-focus bridge, skill gate, coach card, board arrows/highlights, and mission scoreboard.
- A learner becomes eligible for a geometry application instruction after passing the module's mixed unseen stage without answer reveal. Delayed recall and in-game application remain separate evidence.
- PWC supports one geometry focus at a time, one learner-controlled reveal, a skip/continue action, and an honest postgame application report.
- Geometry prompts and their board marks arrive atomically from one completed response. Existing content remains visible while that response is prepared; no temporary generic sentence or “Coach thinking” state replaces it.
- The live detector records opportunities as well as errors. A clean game with no relevant geometry opportunity does not count as successful application.
- Rollout remains default-off through an admin walking skeleton, reviewed internal games, a calibrated cohort, a frozen evaluation, and measured expansion under the repository's one-active-experiment policy.
- Existing routes that point to a migrated fork/pin/skewer drill resolve to the same Board Geometry lesson state and progress projection.

## 4. Explicitly out of scope (V1)

- An always-on overlay that fills every normal PWC position with arrows, zones, or strategic plans.
- Weak-square, outpost, pawn-break, general piece-coordination, and long-horizon positional-plan instruction. These may later use the same visual grammar after the core geometry families prove learning transfer.
- RAG, semantic search, or LLM-generated chess truth. An LLM may be evaluated later for wording only after receiving locked facts; it cannot decide geometry, grading, or soundness.
- Claiming that completing these modules makes a player “see everything like a grandmaster.” The product teaches a measurable part of strong board vision: attack maps, lines, shared squares, blockers, and target relationships.
- Prompts on routine moves, repeated prompts for the same unchanged relationship, or simultaneous geometry and caption cards competing for attention.
- PWC intervention for a geometry family whose detector lacks an approved quality packet or whose lesson has not passed its learning gate.
- A new top-level Academy, Geometry page, mastery collection, lesson dispatcher, PWC mission store, caption pipeline, detector catalog, or analytics service.
- Automatic public rollout merely because the UI and detector compile.

## 5. Success criteria

- **Truth:** Reviewed evaluation positions produce zero false claims about a shared attack square, line, blocker, pin, skewer, fork, or forced result. A geometric possibility is never worded as a winning tactic without engine/PV support.
- **Independent learning:** On frozen, difficulty-matched unseen forms, learners improve from their unguided baseline to the post-test without seeing the same position twice.
- **Retention:** Delayed, unannounced recall remains stronger than baseline. Hint-assisted or revealed answers remain excluded from independent recognition.
- **Transfer:** Eligible learners recognize or respect the taught relationship more often in verified PWC opportunities after completing the lesson. Opportunities, correct applications, misses, skips, and unavailable measurements remain separate.
- **Accessibility:** A 600–900 player can complete the core interactions using the board and plain language without needing SAN notation or terms such as `x-ray` before the geometry is shown.
- **Visual recall:** After seeing a Geometry Flash, the learner can identify the same relationship in a crowded unseen position without the lesson name, explanatory paragraph, or pre-drawn answer.
- **Experience:** No geometry interaction introduces caption flicker, a disappearing placeholder, a “Coach thinking” message, or board marks arriving after their explanation. The prompt, explanation, and marks render as coherent states.
- **Focus:** PWC presents at most one active learning objective and never shows a geometry interruption on a routine position. The final prompt quota and cooldown must be locked from replay data and pilot behavior before release.
- **Honesty:** When no qualifying opportunity occurs, the product says it was not measured. Lesson completion alone never produces Proven in games.
- **Continuity:** A learner can exit, resume on the next unanswered interaction, complete delayed recall later, and see one consistent state and next action on Training, Home/Lab, and PWC.
- **Architecture:** Adding a new geometry family requires one canonical truth addition and one lesson adapter. No product surface stores a competing definition of that geometry.

## 6. Locked decisions and remaining rollout question

- Replay data locks one learner-facing geometry prompt per PWC game. Later verified moments are recorded silently. An eight-player-move cooldown is retained for a future quota increase.
- Each module contains one flash and seven fixed activities, for eight distinct content items per family. Personal positions remain a separate application stage.
- `caption_facts.py` owns canonical move facts, multi-target evidence, aligned-piece evidence, and shared attack squares. `motif_profile_service.py` exposes the shared pin/skewer classifier. `geometry_plans.py` is retired from the product path.
- The measurements, candidate comparisons, and ownership table are recorded in `docs/board_geometry_data_lock.md`.
- **Remaining question:** When may the real-user geometry experiment run relative to the currently active product-learning experiment?
  **Required decision:** Keep implementation and internal validation default-off; before assigning a real-user cohort, close the active experiment or record an explicit orthogonality ruling.

## 7. Pre-code requirements

- Mohit explicitly signs off on this entire scope, including the four-module boundary and the rule that Training completes before live PWC intervention is enabled.
- The scope becomes the active Board Geometry product authority, and `coach_geometry_arrows_scope.md` is marked superseded rather than left as a competing live direction.
- `/lock-via-data` measures per-family content coverage, rating distribution, verified opportunity frequency, prompt quota candidates, cooldown candidates, and PWC interruption risk. No numeric runtime threshold is selected from judgment.
- A single-source ownership map names the canonical schema and function for multi-target attacks, shared attack squares, aligned pieces, blockers, and pin/skewer/x-ray labels. `geometry_plans.py` is either converted to a projection or retired.
- Each geometry detector that may affect a lesson grade, instruction, mastery state, or PWC prompt has an independently reviewed promotion packet and passes the repository's detector-quality gate for that surface.
- Reviewed content exists for every required role in all four modules, with stable source references, versioned accepted answers, counterexamples, and orientation coverage.
- The literal Training and PWC mockups in this scope are accepted as the UI contract; responsive behavior and the atomic no-flicker state transition are included in frontend acceptance tests.
- The learning evidence path can record baseline, hint level, reveal, retry, post-test, delayed recall, application opportunity, application result, skip, and not-measured outcomes without adding a competing mastery or analytics store.
- A test plan covers deterministic geometry truth, engine-supported tactical claims, legal moves, blockers, color/orientation, real-versus-fake examples, resume/idempotency, accessibility, PWC timing, prompt collision, and postgame evidence.
- Implementation starts in an isolated branch/worktree from the intended base because the current working tree contains substantial unrelated PWC, caption, opening, and admin changes that must not be overwritten or silently included.
- The active-experiment decision is recorded before any real-user rollout. Until then, every new runtime path remains default-off and limited to internal validation.
