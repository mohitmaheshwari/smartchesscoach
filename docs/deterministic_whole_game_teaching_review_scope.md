# Deterministic Whole-Game Teaching Review

## 0. Existing surfaces audit

ChessGuru already contains most of the pieces needed for this experience, but the player receives them as separate fragments instead of one coherent review.

- **Game library (`/games`):** helps the player choose an analysed game and can recommend one worth reviewing. It does not explain the complete game.
- **Canonical game review (`/game/:gameId`):** `LabV2` and `GameDecryptionV5` already show the board, move-by-move captions, arrows, alternative moves and playable engine lines. They are the correct player-facing home for this work. The current experience is still primarily a sequence of move comments rather than a story of what the game was about.
- **Guided replay (`/replay/:gameId`):** already presents a few moments one at a time. It overlaps heavily with the proposed experience, but its board is view-only, its language is generic and its current design describes board reading as LLM-powered. It must not remain a second coaching brain.
- **Candidate-Aware Causal Captions:** the approved scope already requires position-specific explanations, verified candidate comparisons, legal replay lines, personalized questions and deterministic language. This remains the canonical explanation contract for each individual moment.
- **Caption facts and chess detectors:** the central caption pipeline already extracts legal-board, material, tactical, opening, positional and endgame facts. Detector authorization already prevents unproven concepts from influencing player-facing captions, plans and mastery.
- **Opening knowledge:** the opening recognizer, opening curriculum and stored opening-deviation record can identify the known opening, how long the player remained in known material and the first departure. Leaving the authored line is not automatically called a mistake; a stronger claim still requires verified chess consequences.
- **Phase analysis:** existing services divide a game into opening, middlegame and endgame and expose phase summaries. Those boundaries can organize the review, but phase labels alone do not prove a lesson.
- **Exact endings:** the exact-endgame path can identify result-preserving moves in supported tablebase positions. Named endgame principles remain subject to their own detector authorization.
- **Hidden Opportunities and good-move evidence:** existing work can supply verified missed possibilities and moves the player handled correctly. These must enter the same review plan rather than appear as an unrelated feature.
- **Learning and progress:** existing learning-session and mastery projections distinguish guided exposure, assisted success, recall and later real-game evidence. The review should emit evidence into these existing contracts rather than create another progress system.
- **Prior audits and scopes:** ChessGuru has already locked the central caption pipeline, one-source-of-truth knowledge, fail-closed detector promotion, no runtime LLM requirement and the difference between practice completion and real-game transfer. This scope preserves all of those decisions.

The overlap is substantial: game selection, phase detection, moment captions, candidate lines, replay controls, concept knowledge and mastery already exist. The genuinely new value is a deterministic whole-game teaching plan that connects those existing facts into one memorable story, followed by a complete-game coverage audit that improves the underlying shared intelligence rather than patching individual games.

**Decision: EXTEND.** Upgrade the canonical `/game/:gameId` review and central caption pipeline. Absorb or retire the overlapping guided-replay behavior; do not create another review page, caption engine, chess taxonomy, opening library, detector registry or mastery store. Mohit approved EXTEND on 2026-09-13.

## 1. What it is

Deterministic Whole-Game Teaching Review makes ChessGuru review a game like a careful personal coach. It explains what the game was really about, what the player understood, where the position changed, what either side could have done and what the player should recognize next time. The review connects the opening, middlegame and endgame instead of producing three reports or commenting on every move. Every chess statement comes from stored engine evidence, legal-board reasoning, exact endgame truth, canonical chess knowledge or an authorized detector; no LLM or live Codex call is needed when the player opens the page. Codex is used only offline to review complete games, discover missing teaching coverage and help turn repeated gaps into independently verified deterministic logic.

## 2. What the user sees

The game library explains why this game is worth the player's time:

```text
REVIEW WITH YOUR COACH

Won vs reyajaaa123

I chose this game because your opening was sound, but one central
pawn push changed the middlegame. You also found the same safety
idea we have been practising.

[ Review this game ]
```

The review begins with one connected story, not statistics:

```text
WHAT THIS GAME WAS ABOUT

Your Italian opening was not the problem. You developed naturally
and made your king safe. The game changed when the centre opened:
you recaptured automatically and missed a pawn fork. No real
endgame was reached.

[ Start with the opening ]
```

Each phase has an honest state. It may contain a lesson, acknowledge good play, say that no verified lesson was found or say that the phase was never reached.

```text
OPENING · ITALIAN GAME

You handled the setup well through move 7. Your bishop was active,
your king was safe and I found no verified opening problem before
the centre opened.

The position was now asking: how will Black challenge your e4 pawn?

[ Show the setup ]        [ Continue ]
```

The middlegame pauses before the important decision and lets the player think:

```text
THE POSITION CHANGED HERE

Before you see the old move, what is Black threatening after ...Nxe4?

[ Recapture the knight immediately ]
[ Check whether ...d5 can attack two pieces ]
[ Move the bishop before deciding ]
[ I am not sure ]

                         [ Let me play ]
```

After the answer or move, ChessGuru gives a direct verdict and a short causal explanation:

```text
The hidden move was ...d5

After Nxe4 Rxe4, ...d5 attacks your rook on e4 and bishop on c4.
One of them has to be left behind.

[ Play what happened ]   [ Try the safer choice ]

REMEMBER
Before recapturing, check whether a pawn push attacks two pieces.
```

The review also preserves genuine strengths:

```text
YOU UNDERSTOOD THIS ONE

Later, you moved your rook before taking the pawn. That kept every
piece protected—the exact habit we have been practising.

[ Replay my decision ]
```

The endgame section never manufactures a lesson:

```text
ENDGAME

This game ended before a real endgame began.
There is nothing useful to study here.
```

When exact evidence exists, it becomes interactive:

```text
ENDGAME · KING AND PAWN

This position was still winning. Kc4 kept the win; Kc3 allowed the
defending king to reach the drawing squares.

Can you find the winning route now?

[ Try it ]   [ Show the key squares ]
```

The review ends with one instruction and a clear learning status:

```text
TAKE THIS INTO YOUR NEXT GAME

When the centre can open, calculate the pawn push before recapturing.

You recognized it here. I will now look for the same decision in a
different position—and later in one of your real games.

[ Practise one new position ]   [ Finish review ]
```

## 3. In scope (V1)

- Extend the canonical `/game/:gameId` review; do not launch a parallel review product.
- Begin every eligible review with one plain-language explanation of what the game was about and why the game is worth reviewing.
- Organize the story into opening, middlegame and endgame while explicitly connecting how one phase produced the next.
- Give every phase one honest state: a verified lesson, verified good play, no verified lesson or phase not reached.
- Identify the opening by its canonical identity and explain the setup or first meaningful departure only when the evidence supports the wording.
- Never equate leaving authored opening material with making a chess mistake. Consequence language requires separate verified evidence.
- Select a bounded, data-locked number of the game's most teachable moments rather than commenting on every engine preference.
- Include verified good decisions, opponent opportunities and hidden alternatives—not only the player's mistakes.
- Reuse Candidate-Aware Causal Captions for every featured moment: what happened, why it mattered, the stronger idea, a legal replay and one reusable memory cue.
- Generate position-relative questions and answer choices from the same verified reason bundle. Generic questions are an explicit fallback, not the normal experience.
- Let the player make a move, request a hint, replay the played line, replay a missed line and retry from the original position.
- Use exact endgame truth when the position is covered and authorized named endgame principles when available.
- State plainly when a game did not reach a real endgame or when no verified phase lesson exists.
- End the review with one surviving instruction selected from the game's clearest verified lesson and the player's current learning context.
- Record review impression, phase opened, question answered, hint used, line replayed, retry result and review completion through existing analytics conventions.
- Feed eligible review and practice outcomes into the existing learning evidence contracts. Viewing, replaying or solving with help cannot by itself prove mastery.
- Keep all runtime chess claims and language deterministic. Opening a review starts no LLM, Codex, Maia, Otter, Stockfish or tablebase-network request.
- Preserve engine, detector, knowledge-content, renderer and evidence versions for every featured moment.
- Build a versioned, anonymized development packet of complete games using already stored evidence. It contains no email, user ID, external account name, game ID, credentials or unnecessary metadata.
- Have Codex independently review the complete games as a chess coach across opening, middlegame, endgame, good play, missed opportunities, opponent ideas, causality, clarity and memorability.
- Compare Codex's independent lesson inventory with ChessGuru's extracted facts, selected moments and visible explanations.
- Give every disagreement one explicit disposition: existing fact not wired, detector miss, incomplete fact contract, genuinely missing concept, unsupported residue or Codex interpretation rejected by chess evidence.
- Fix shared canonical logic for recurring gaps and add positive, hard-negative and adversarial evidence. Never patch prose or outcomes for one sampled game.
- Rerun the complete development packet after each accepted improvement and report coverage changes by phase and proof family.
- Freeze implementation before evaluating an unseen complete-game holdout. The holdout is not used to author detectors, templates, rankings or exceptions.
- Produce a final evidence report showing factual failures, useful-lesson coverage, abstentions, repeated wording, phase balance, interaction completeness and holdout generalization.
- Validate an existing stored game and a newly analysed game through authenticated API and visible frontend journeys before rollout.

## 4. Explicitly out of scope (V1)

- An LLM, Codex session or human reviewer generating or rewriting a player's review at runtime.
- Treating Codex's offline opinion as production truth without a deterministic predicate, canonical fact contract, verifier and required promotion evidence.
- Promising an explanation for every legal position or forcing one lesson into every phase.
- Calling an opening “perfect.” The strongest quiet claim is that no verified opening problem was found through a stated point.
- Calling every departure from opening material an inaccuracy or knowledge gap.
- Showing engine scores, model probabilities, detector IDs, proof terminology or rating stereotypes to the player.
- Inferring psychology such as panic, blindness, guessing, carelessness or intention solely from the move.
- Running a new full Stockfish analysis over the historical games. The original stored analysis remains immutable; separately approved bounded candidate enrichment follows the existing Candidate-Aware scope.
- Allowing Maia or Otter to establish chess correctness, weakness, mastery or the reason a move worked.
- Bypassing detector authorization to improve apparent coverage.
- Creating a second opening, trap, endgame, positional-principle, tactical-pattern or caption catalog.
- Creating a second mastery, progress, review-selection or coach-memory system.
- A separate replacement UI at `/replay/:gameId`; useful interaction is absorbed into the canonical review before the overlapping path is redirected or retired.
- Automatically marking a lesson learned after one correct answer, one replay or one guided puzzle.
- Community-authored explanations, reputation or human-coach marketplace features.
- Production backfill, rollout or deployment before the development audit, unseen holdout, migration report and authenticated journey pass.

## 5. Success criteria

- A player can describe the game's central lesson in their own words after the review more often than before it, at a threshold locked before evaluation.
- On a different position containing the same verified idea, players choose or play the relevant move more often after review, at a threshold locked before evaluation.
- Later unassisted games remain the only evidence that can establish real transfer or durable improvement.
- Every featured moment contains a verified position, a clear reason, a legal interactive line and one memorable instruction; incomplete moments abstain instead of becoming filler.
- Every displayed opening, tactical, positional and endgame claim is traceable to current authorized evidence, with zero critical false claims in the adversarial packet and unseen holdout.
- The whole-game story correctly states whether each phase contained a lesson, demonstrated good play, had no verified lesson or was not reached.
- Independent reviewers prefer the whole-game version over the current move-list experience for usefulness, clarity, chess truth and memorability at precommitted thresholds.
- The unseen holdout preserves the development corpus's improvement within the precommitted generalization tolerance; a large collapse blocks rollout.
- The audit accounts for every reviewed game and every proposed lesson. No disagreement or unsupported residue silently disappears.
- Accepted Codex findings change shared deterministic logic and improve more than the source position; exact sampled-game exceptions are zero.
- Review-page reads start no engine, model or external tablebase process and remain responsive when optional enrichment artifacts are absent.
- An authenticated non-admin player can open a recommended game, understand why it was selected, complete the phase story, interact with a featured line and generate the expected learning evidence.
- Users outside the pilot continue receiving the existing review until the new path clears the complete rollout gate.

## 6. Open questions

- **Question:** Should the first evidence run use 100 development games plus a separate holdout, or divide one fixed corpus into development and holdout sets? **Why unresolved:** using all 100 for both discovery and scoring would overfit, while the available complete-game population and phase coverage have not yet been measured. **Unblocking step:** run a read-only corpus census and lock the evidence design from the distribution.
- **Question:** How should complete games be stratified across rating, result, color, time control, game length, opening family and whether a real endgame occurred? **Why unresolved:** a convenient recent sample could contain almost no endgames or overrepresent one player and one opening. **Unblocking step:** measure the eligible corpus, compare candidate sampling plans and lock the plan that provides useful phase and source diversity without inventing quotas.
- **Question:** How many moments should a normal review feature, and can the number vary when a game has unusually rich or sparse evidence? **Why unresolved:** the present cap and the user's reading tolerance have not been compared against independent whole-game coach selections. **Unblocking step:** bake off a small set of candidate policies on complete games and review the literal resulting experiences.
- **Question:** Which deterministic rule identifies the game's central story when several individually correct moments compete? **Why unresolved:** highest engine loss, phase coverage, personal focus and teaching completeness can select different narratives. **Unblocking step:** compare candidate ranking policies against blinded independent coach selections and lock the winner from evidence.
- **Question:** What exact evidence permits “you handled the opening well” rather than the narrower “I found no verified opening problem”? **Why unresolved:** following known moves, playing soundly and understanding the plan are different claims. **Unblocking step:** define separate deterministic claims and review their positive and hard-negative examples before authorizing the stronger wording.
- **Question:** Which existing phase detector is canonical for review boundaries? **Why unresolved:** several legacy consumers use different phase representations or move-number fallbacks. **Unblocking step:** trace the central analysis path, select one owner and add a guard test preventing review-local phase inference.
- **Question:** Which positional and endgame concepts are ready to enter the first player-facing whole-game review? **Why unresolved:** implementation presence does not equal detector authorization, and several named concepts remain Shadow or Disabled. **Unblocking step:** produce an authorization inventory and include only concepts whose current grade permits the receiving surface.
- **Question:** What constitutes a successful independent Codex match: exact concept identity, equivalent causal explanation or merely the same better move? **Why unresolved:** move agreement alone does not measure teaching quality, while free-form prose comparison is not reproducible. **Unblocking step:** define a frozen structured adjudication rubric before Codex sees the development packet.
- **Question:** What evaluation thresholds govern factual precision, useful coverage, coach preference, delayed recognition and holdout generalization? **Why unresolved:** choosing thresholds after seeing results would make the audit non-falsifiable. **Unblocking step:** lock every threshold through the repository's data-driven decision process before implementation scoring.
- **Question:** Which historical games receive regenerated whole-game plans after the feature passes? **Why unresolved:** eligible volume, evidence freshness and reconciliation cost have not been measured. **Unblocking step:** run a no-write population report with current, partial, stale, unsupported, invalid and failed states before choosing a cohort.
- **Question:** Should `/replay/:gameId` redirect directly to the canonical review or remain temporarily as a compatibility entry point? **Why unresolved:** inbound links and current usage have not been measured. **Unblocking step:** inventory route references and recent route use, then lock redirect timing without maintaining a second implementation.

## 7. Pre-code requirements

- Mohit explicitly signs off this complete scope document.
- Run the repository's data-lock process for corpus design, stratification, moment count, story ranking, wording strength, audit rubric, evaluation thresholds, holdout tolerance and historical cohort.
- Run the repository's pre-code audit after the data locks and before editing implementation files.
- Start from a clean worktree at current `origin/working-code`; preserve all unrelated work in the dirty primary checkout.
- Record a canonical source map for game selection, phase boundaries, `MoveTeachingDecision`, typed teaching causes, reason bundles, opening identity, traps, endgames, principles, detector authorization, replay lines and mastery evidence.
- Prove that the whole-game composer is an orchestration layer over canonical facts and does not duplicate chess recognition, names, lesson text or truth.
- Freeze the current Game Review output on the chosen development and holdout corpus before changing ranking, composition or rendering.
- Freeze a structured Codex-review rubric before exposing development-game answer keys or current ChessGuru selections to the independent reviewer.
- Produce the anonymized complete-game packet with stable opaque signatures and stored evidence only; confirm that identities, credentials and unnecessary source metadata are absent.
- Keep development games and unseen holdout signatures disjoint and add an automated overlap check.
- Inventory current detector authorization by receiving surface. No Shadow, Disabled or unknown detector may influence a visible lesson, answer, game story or mastery event.
- Define tests for honest phase states, opening-deviation wording, good-move evidence, opponent opportunities, exact endings, no-endgame games, unsupported residue and conflicting candidate lessons.
- Define legal-replay and answer-hiding contract tests before building the new interaction.
- Define evidence events and eligibility using existing learning contracts; practice remains separate from organic-game transfer.
- Prepare unit, adversarial, clean-base regression, authenticated API, frontend interaction and end-to-end test lists, including a test proving page reads start no engine or model process.
- Define an idempotent, resumable and reversible historical plan-generation job with a no-write report before any record changes are allowed.
- Keep all production flags default-off until the complete-game audit, unseen holdout, migration dry-run and authenticated player journey are independently verified.
