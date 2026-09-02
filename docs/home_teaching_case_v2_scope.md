# Home Teaching Case V2 — Product Scope

## 0. Existing surfaces audit

### What already touches this user need

- The routed Home page is `HomePageNew`. For a player enrolled in Personal Curriculum, it delegates the whole page to `CurriculumHome` rather than rendering a second dashboard.
- `CurriculumHome` already promises one clear coaching step and keeps the rest of the curriculum behind “See the rest of my plan.”
- `CurriculumPrimary` already replaces its normal recommendation with `HomeReplayDiagnostic` when an eligible Home diagnostic exists.
- `HomeReplayDiagnostic` already owns the answer-hidden board, first move, second transfer position, three help actions, pause/resume, reason selection, result state and next action.
- `PersonalizedLessonWorkspace` already owns guided teaching after the diagnosis. It presents a board, reason choices, help, correction, retry and completion without creating a separate lesson product.
- Personal Curriculum already owns the current learning decision and the lifecycle from diagnosis through teaching, independent practice, application and retention.
- `learning_sessions` already owns lesson and diagnostic interactions, including move submissions, help, assistance, reason choices and idempotent event history.
- `LessonResult` already distinguishes explanation, guided work, independent work, review and organic application. It also preserves position identity, assistance, reasoning consistency, detector identity, grader version and evidence provenance.
- Game Review already owns the complete explanation of a past game. It has the original position, played move, engine truth, verified continuation and reflection surfaces.
- Progress already presents the current focus, other tracked patterns and habits that have begun to hold in real games.
- The central caption pipeline already produces the canonical teaching decision for Game Review and Play with Coach. It owns deterministic board facts, typed causes, verified continuations, visual annotations and coaching metadata.
- The deployed destination-safety detector already grades whether a newly submitted move leaves a knight, bishop, rook or queen legally safe on its destination using two independent exchange calculations.
- The existing detector-quality gate already controls whether evidence may influence diagnostics, captions, plans and mastery.
- The current Home reason choices do not consume that canonical intelligence. Every concept position receives the same generic alternatives and one literal expected-reason ID.

### Existing value that must not be duplicated

- Home owns today’s one coaching action.
- Learn owns the full curriculum and exploration.
- Game Review owns the explanation of the original game.
- Training owns the guided and independent lesson workspace.
- Progress owns longitudinal real-game change.
- Personal Curriculum owns selection and state transitions.
- Existing evidence owners retain their meanings; the feature must not create another mastery score, learner profile, reflection store, lesson engine or replay route.

### Genuine missing value

- Home cannot currently explain the actual chess relationships behind the move the player just made.
- The reflection asks one generic question instead of separating threat recognition, move purpose and calculation.
- A move with several valid reasons is reduced to one expected string.
- The result cannot say which part of the chess idea the player demonstrated and which part still needs teaching.
- The user cannot see the complete honest lifecycle: understand the connection, prove it in a different position, then apply it naturally in a real game.
- The approved Home visual hierarchy is not yet the deployed hierarchy.

### Decision: EXTEND existing

Home Teaching Case V2 extends `CurriculumHome`, `CurriculumPrimary`, `HomeReplayDiagnostic`, the canonical per-move teaching decision and the existing learning evidence ledger. It does not create a new page or parallel chess brain. V1 upgrades the current destination-safety diagnostic as one complete vertical slice. Other chess-reason families follow only after separate evidence promotion.

## 1. What it is

Home Teaching Case V2 makes today’s Home lesson feel like a real coach has rebuilt one useful chess decision for the player. The player first chooses a move without being shown the lesson. ChessGuru then checks the actual relationships they understood: what the opponent threatened, what their move accomplished and why the destination was safe. The coach records those parts separately, teaches only the missing connection, tests the same idea in a different-looking position and later watches for a real-game opportunity before calling the lesson learned.

## 2. What the user sees

### Home — before the position

```text
Good evening, Mohit.

TODAY’S COACHING MOVE

Learn to hit back without hanging the piece.

You already notice when one of your pieces is attacked.
The next step is choosing a square that is both protected and useful.

WHY I CHOSE THIS FOR YOU
I rebuilt one moment from your games to check the chess idea—
not whether you remember the old game.

[ Try the position → ]

HOW THIS BECOMES YOURS

1. Understand the connection
   See the threat, the safe square and the recapture as one idea.

2. Prove it somewhere new
   Solve the same idea in a position that looks different.

3. Use it in your games
   Your coach watches for the next real opportunity before calling it learned.
```

No detector name, score, percentage, centipawn value, opponent name or original move is shown.

### Position — the player moves first

```text
A POSITION REBUILT FROM YOUR PLAY

Forget the old game. What would you play now?

[ interactive board ]

Choose your move first.
I’m checking what relationships you see—not whether you remember an answer.

Help, if needed:
[ Show me where to look ] [ Ask me one question ] [ Let me think ]
```

The board is answer-hidden. Lesson name, expected move, original move and explanation remain private until the player submits a move.

### Understanding check — part one

For the approved `R3d2` example:

```text
You played Rd2.

First: what danger were you answering?

What did the queen on c2 threaten?

( ) Both of my rooks—one on d3 and one on d1.
( ) Checkmate against my king.
( ) I did not notice a specific threat.
```

The alternatives are generated from verified facts about this position. They are not reused generic lesson copy.

### Understanding check — part two

```text
Now calculate one move further.

Why is your rook safe on d2?

( ) If the queen plays Qxd2, my rook on d1 recaptures it.
( ) The queen cannot move from c2 to d2.
( ) I attacked the queen, but I did not calculate Qxd2.
```

If the player found another legal, sound and supported move, the questions must match that submitted move. ChessGuru may not grade a different move using the reasons for `Rd2`.

If the submitted move is sound but its causal reason is not supported by a promoted proof family, ChessGuru says it cannot measure the explanation fairly. It does not force the player into the expected answer.

### Coach response

```text
CONNECTION UNDERSTOOD

Exactly. You saw the whole idea.

1. The queen on c2 attacks both rooks.
   You recognized the immediate problem.

2. Rd2 attacks the queen.
   You did not only run away—you made Black respond.

3. After Qxd2, Rxd2 wins the queen.
   The rook on d1 is what makes d2 a safe destination.

Demonstrated here:
✓ Threat recognized
✓ Protected destination understood
✓ One-recapture calculation understood

[ Try a different-looking position → ]
```

If one component is missed, the coach names only that missing connection and routes to the corresponding guided step. It does not label the player careless, blind, rushed or lacking knowledge from one response.

### After the transfer position

```text
YOU CARRIED THE IDEA ACROSS

You found the same relationship on a different board without coaching.
That proves you can recognize it here—not that it has changed your games yet.

Next, I’ll watch for the same decision when it appears naturally.

[ Play while I watch → ]
```

### A later Home visit

When a verified real-game opportunity has occurred:

```text
I saw the decision again.

You noticed the attack and chose a protected square in your game.
That is the evidence I was waiting for.

One later check will tell us whether the habit is beginning to hold.
```

When no relevant opportunity has occurred:

```text
I’m still watching for this decision in a real game.
Nothing new has been measured yet, so your plan stays where it is.
```

## 3. In scope (V1)

- Preserve the existing `/home` route, Personal Curriculum decision, one-primary-action rule and `HomeReplayDiagnostic` lifecycle.
- Apply the approved modern Home hierarchy, color, motion, spacing and progressive-disclosure treatment to the curriculum-enabled Home experience.
- Keep the existing answer-hidden first move and independently graded transfer position.
- Limit the first vertical slice to the promoted `destination_safety_exact` proof family.
- Produce a canonical, typed reason bundle for every supported submitted move. The bundle separates soundness, situation, move purpose, supporting relationships and verified continuation.
- Derive position-specific question text and choices from the canonical reason bundle. The browser renders server-owned choices and does not infer chess relationships.
- Separate at least these destination-safety understanding components when the position supports them: incoming threat recognition, safe-destination recognition, counterattack recognition and one-recapture calculation.
- Allow several verified supporting reasons for one move. Do not reduce a chess move to one literal expected-reason string.
- Grade each component from its own proof rather than treating the whole reflection as one correct/incorrect answer.
- Preserve “I did not notice,” “I did not calculate” and an honest unmeasured result where appropriate.
- Recompute deterministic board geometry for a newly submitted legal move and use the existing new-move soundness check. Do not rerun Stockfish over already analyzed historical games that contain sufficient stored engine truth.
- Handle a sound alternative move only when the system can produce a verified reason bundle for that exact move. Otherwise keep the explanation unmeasured without marking the chess move wrong.
- Keep objective chess truth, player-selected explanation and coach interpretation as separate fields.
- Store proof authority, proof version, semantic version and a stable fingerprint with every reason bundle used for a player-facing result.
- Extend the existing `LessonResult`/learning-session evidence so demonstrated components, missed components, assistance and transfer remain auditable and idempotent.
- Preserve the distinction between guided success, independent success, controlled transfer, organic real-game application and delayed retention.
- Route the result into the existing curriculum action: targeted explanation, guided practice, independent transfer, coached application, watch mode or later review.
- Change the next Home visit from the stored result and later eligible game evidence rather than replaying the same generic card.
- Reuse the same canonical reason bundle contract inside the central teaching pipeline so later Game Review and Play with Coach adoption will not require another chess-reason implementation. V1 player-facing rollout remains Home only.
- Instrument Home invitation, move submitted, help used, each component response, result reached, transfer started, transfer completed, prescribed action started and later organic opportunity outcome.
- Keep the existing default-off feature flag, Mohit-only enrollment, kill switch and rollback path for the first production validation.
- Add backend contract, fact-provider, reason-resolution, grading, persistence, authorization and route tests.
- Add frontend state, answer-hiding, alternative-move, help, result, accessibility and analytics tests.
- Run a deployed API end-to-end check and a manual browser pass on `bhutramohit@gmail.com` before any cohort expansion.

## 4. Explicitly out of scope (V1)

- A new Home route, separate replay page, second curriculum engine, second mastery system or new learner-profile collection.
- Replacing the complete Learn, Progress, Game Review, Training or Play with Coach interfaces.
- Player-facing reason families beyond verified destination safety in the first slice, including forks, pins, skewers, deflection, overload, opening plans, traps, positional plans and endgame principles.
- Calling one result the player’s largest or most important weakness without comparative eligible evidence.
- Treating two correct positions as real-game improvement, retention, reliability or rating gain.
- Diagnosing a permanent mental cause such as blindness, rushing, guessing, tilt or lack of knowledge from one move or one selected option.
- Free-text reflection as the normal interaction.
- Client-authored questions, distractors, chess labels, accepted answers or grading logic.
- Parsing caption prose to reconstruct chess truth.
- Letting a generic lesson label stand in for a verified causal explanation.
- Exposing engine evaluations, detector IDs, confidence scores, weakness rankings, percentages or internal mastery states on Home.
- Using an LLM, Maia, Otter or Fathom as runtime chess authority. Human-policy models remain optional offline evidence for future difficulty and distractor research.
- Rerunning Stockfish on historical moves that already have sufficient stored analysis.
- Automatically promoting newly discovered reason families without corpus replay and independent review.
- Building the community explanation/reputation system in this release.
- Automatically generating every possible chess explanation. Unsupported ideas remain honestly unmeasured and enter an offline coverage backlog.
- All-user rollout before the data-locked gates and Mohit-only validation pass.

## 5. Success criteria

- A 600–1500 player can state why ChessGuru chose today’s position without remembering the original game or interpreting a statistic.
- The first board move cannot be influenced by an exposed lesson name, expected move, answer, original move, opponent identity, highlighted solution square or explanatory sentence.
- The options shown after a move name the actual pieces, squares and legal continuation in that submitted position.
- A sound supported alternative move receives reasons for that move; it is never judged against reasons belonging to another move.
- Each player-facing factual claim is reproducible from stored engine evidence, deterministic board facts and a promoted proof family.
- Threat recognition, destination safety and recapture calculation can produce different stored outcomes and different next teaching actions.
- Assistance changes the evidence classification. A correct answer after help cannot be stored as independent understanding.
- The same submitted events produce the same result after refresh, retry or duplicate network submission.
- Completing the first position does not end the lesson. The product visibly continues to transfer, application and retention.
- A game without a relevant verified opportunity leaves application as “not measured.” It cannot silently improve or worsen the player’s state.
- Home changes meaningfully after the diagnostic and again after later eligible game evidence.
- The destination-safety reason family passes the data-locked factual-precision, supported-position coverage, ambiguity, answer-leakage and cross-surface-parity gates before player-facing rollout.
- The approved flow works on desktop and mobile without losing the board, primary action, explanation chain or honest next step.
- The current Home, Learn, Progress, Game Review and Play with Coach contract suites show no behavior regression outside the enrolled V2 path.
- Manual review on Mohit’s account finds that the result matches what a strong human coach can prove from the board and does not overstate what the responses demonstrate.
- Wider rollout remains blocked until the evidence-derived completion, comprehension, next-action and later-opportunity gates are locked and passed.

## 6. Open questions

- **Question:** What exact evidence fields are required for a destination-safety reason bundle to be considered complete?
  **Why unresolved:** The current detector proves destination safety but does not yet expose every causal relationship needed for teaching.
  **Unblocking step:** Replay the promoted corpus and identify the smallest fact set that explains each independently reviewed true positive without inventing a reason.

- **Question:** Which supporting reasons should be accepted when several statements about one move are true?
  **Why unresolved:** Primary reason, supporting benefit and sufficient calculation are different meanings; collapsing them would recreate the current problem.
  **Unblocking step:** Build a reviewed multi-label gold set and compare candidate grading policies against it.

- **Question:** How are wrong choices made plausible without becoming ambiguous or teaching false chess?
  **Why unresolved:** Generic distractors are unhelpful, while a second defensible answer makes the diagnostic invalid.
  **Unblocking step:** Generate candidate alternatives from falsifiable board relations, then independently review ambiguity and answer leakage before locking the policy.

- **Question:** What happens when the player submits a sound move whose purpose is outside the promoted reason vocabulary?
  **Why unresolved:** Calling it wrong is dishonest, but accepting it without understanding evidence does not measure the lesson.
  **Unblocking step:** Run the submitted-move coverage audit and lock the unmeasured response plus retry/alternate-position policy.

- **Question:** How different must the transfer position look while testing the same decision components?
  **Why unresolved:** Superficial similarity rewards memory; excessive difference may test a second skill.
  **Unblocking step:** Independently review candidate pairs and lock a pairing rule from evidence rather than visual intuition.

- **Question:** Which component outcomes change the next curriculum action?
  **Why unresolved:** The current result categories operate at lesson level, while V2 introduces component-level evidence.
  **Unblocking step:** Map each reviewed outcome combination to one existing action and reject mappings a coach cannot justify.

- **Question:** What numerical quality and rollout thresholds must the first reason family pass?
  **Why unresolved:** No current measurement establishes safe values for causal-reason coverage, ambiguity or comprehension.
  **Unblocking step:** Run `/lock-via-data` on the versioned corpus and usability results; do not choose thresholds from judgment alone.

## 7. Pre-code requirements

- Mohit explicitly signs off on this complete scope document.
- Development starts from a clean worktree created from the current deployed `working-code` state. The dirty main tree is not used as an implementation base.
- `/single-source-of-truth` confirms that the canonical caption facts, typed causes, destination-safety detector, Personal Curriculum, learning sessions and mastery projection retain one owner each.
- A schema-first contract defines the reason bundle, reason components, proof references, supported move, accepted evidence and public redaction before the UI or question renderer is edited.
- The contract extends the canonical per-move teaching decision rather than introducing a parallel Home-only chess inference service.
- The browser contract proves that expected reasons, accepted components, engine answers and proof internals are never included in the pre-answer payload.
- `/lock-via-data` locks the complete-proof rule, multi-label grading rule, alternative-move behavior, transfer-pairing rule, distractor rule and rollout gates from versioned evidence.
- A versioned corpus replay measures current destination-safety reason coverage without rerunning Stockfish over already analyzed historical games.
- An independent gold set covers successful moves, failing moves, sound alternatives, unsupported alternatives, proof disagreement, ambiguous reasons, help use and duplicate submissions.
- The existing detector-quality authorization is extended or reused explicitly for player-facing reason claims; no Shadow or unknown proof family may silently become teaching truth.
- `LessonResult` and the existing mastery projection are reviewed for component evidence. Any schema change remains backward compatible and preserves old events.
- Literal desktop and mobile states are derived from the approved mockup and checked against the exact copy in Section 2.
- The feature flag is declared in every required runtime configuration, defaults off, supports Mohit-only enrollment and has a tested one-step rollback.
- Relevant backend and frontend baseline suites are run on the clean deployed base before implementation so pre-existing failures cannot be attributed to V2.
- `/audit-pre-code` passes after the data locks, including schema-before-mockup, move-led interaction, instrumentation, forecasted bottlenecks and deferred-scope checks.
