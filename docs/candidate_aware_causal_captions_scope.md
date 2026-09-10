# Candidate-Aware Causal Captions

## 0. Existing surfaces audit

ChessGuru already has most of the pieces needed for this experience, but they do not currently meet at one reliable player-facing boundary.

- **Game Review:** `GameDecryptionV5` already renders a caption beside the board, move highlights, arrows, principle cues, shape-pattern callouts, and a **Show me on the board** interaction when the backend supplies a legal line. In Mohit's stored reviews, the line payload is effectively absent, so the interaction rarely appears.
- **Central caption decision:** `caption_pipeline.build_move_teaching_decision` already produces the canonical `MoveTeachingDecision`, including `CaptionExplanation`, an optional typed cause, an optional `TeachingReasonBundle`, visual instructions, and optional replay moves. This remains the single source of player-facing chess explanation.
- **V5 game decryption:** `game_decryption_v5_service` already joins stored Stockfish facts, board geometry, openings, traps, endgames, shape detectors, player context and caption rules. It also performs a fresh depth-12 MultiPV search for many mistakes during regeneration, but most of the resulting candidate information does not reach the visible caption or replay experience.
- **Truth gates:** the existing legal-board, material, mate-direction, stored-line and rendered-claim verifiers correctly establish the architecture's safety boundary. They currently verify whether supported claims are true; they do not require an important learning moment to contain a useful reason, comparison and transferable lesson.
- **Human-policy runtime:** `human_policy_runtime` already defines governed Otter and Maia-2 evidence. Otter with legally verified game history is the preferred provider; Maia-2 is the no-history fallback. Human likelihood is explicitly not chess authority. Production currently has these features disabled and the configured model files are not mounted in the running backend.
- **Background enrichment:** `human_chess_analysis_enrichment` can attach human-policy and exact-endgame evidence during analysis without rerunning the original game evaluation. Its current all-candidate shape is disabled pending a measured memory and latency envelope.
- **Exact endings:** the Fathom/Syzygy contract already supplies exact result-preserving evidence for supported endings. It remains the highest authority for those positions.
- **Personalized lessons:** `PersonalizedLessonWorkspace` already shows a position from the player's games and can consume a typed reason bundle. The normal lesson still uses three generic reflection choices too often and can replace a richer verified explanation with a thin piece-safety message.
- **Play with Coach:** the central caption bridge, guarded opponent selector and optional human-policy ranking already exist. Human policy may rank only moves that the chess-safety boundary has accepted.
- **Hidden Opportunities:** verified setup, constraint and payoff proof families exist in Shadow or limited authorization states. They may contribute only when their exact proof family is allowed on the receiving surface.
- **Opening, trap, endgame and principle content:** canonical sources already exist. This work must reference them by stable identity; it must not copy their knowledge into a new caption-only catalog.

The overlap is substantial: captions, candidate moves, replay UI, human-policy evidence, player memory and chess knowledge all already exist. The genuine missing value is a single candidate-comparison product contract that turns those inputs into a short, verified, replayable coaching moment.

**Decision: EXTEND.** Upgrade the existing central caption pipeline and its current Game Review, lesson and Play-with-Coach consumers. Do not add a parallel Maia caption engine, a second chess-fact taxonomy, or a new review page. This path was approved by Mohit on 2026-09-10.

## 1. What it is

Candidate-Aware Causal Captions make ChessGuru review a game like a thoughtful human coach. For an important position, the coach considers the move the player made, the moves a similar human was likely to consider, and the strongest understandable alternatives. It verifies the chess with Stockfish, legal-board reasoning, approved detectors and exact endgame truth, then shows one memorable comparison: what the move changed, what could have happened instead, and what idea to recognize next time. The player never sees engine scores, model probabilities or a list of five computer moves.

## 2. What the user sees

The normal review remains quiet. A small number of important positions receive a richer coaching moment.

```text
MOVE 13

Trading queens helps White here

Qxg3 exchanges queens — it does not lose your queen for free.
But you are already behind, so the trade removes useful counterplay.
Qe4 keeps your queen active and attacks the knight on f3.

[ Compare the two ideas ▶ ]

REMEMBER
When you are behind, avoid trading queens unless the exchange
solves an immediate problem.
```

Pressing **Compare the two ideas** uses the existing board and shows one idea at a time:

```text
YOUR MOVE                  THE STRONGER TRY
Qxg3  hxg3                 Qe4
The queens come off.       Your queen stays active and attacks f3.

[ Replay ]   [ Back to the game ]
```

An opponent opportunity uses the same shape:

```text
MOVE 23

A pawn fork was hiding here

After Nxe4 Rxe4, d5 attacks the rook and bishop together.
The rook has to move, so the bishop cannot also be saved.

[ Show the idea on the board ▶ ]

REMEMBER
Before automatically recapturing, check whether a pawn push
can attack two pieces.
```

The coach may internally compare several human-plausible moves, but it shows only the comparison that teaches the clearest verified idea. A second good move may appear under **Another good choice** only when it is sound, meaningfully different, and teaches a different useful idea.

In a personalized lesson, the generic three-choice question becomes position-relative:

```text
What matters most before you choose?

[ Trading queens would help the player who is ahead. ]
[ My queen is attacked, so any queen move is equally safe. ]
[ I should create a threat even if the queens come off. ]

                         [ Let me play ]
```

After the move, the lesson gives a direct verdict and a short reason:

```text
Yes — Qe4 keeps the game complicated and attacks f3.
[ Show why ▶ ]
```

If the system can verify only that one move is stronger but cannot verify why, it may show a quiet comparison in the move list. It must not promote that move as a featured coaching moment or invent a lesson.

## 3. In scope (V1)

- Correct captured-value and exchange accounting so equal or favorable trades cannot be described as hanging a piece or losing it for free.
- Lock the reported `Qxg3` queen exchange and `Bxc3` exchange as exact regression positions, alongside existing actor, mate-direction, recapture, fork and line-horizon regressions.
- Recheck existing piece-safety lesson admissions produced through the affected proof path and mark invalid evidence unusable before any richer language is rendered.
- Extend the existing typed cause and explanation contracts to carry a verified comparison between the played move and one or more candidate moves without introducing another caption pipeline.
- Always include the played move and the stored Stockfish best move in the internal candidate set.
- Prefer Otter when the complete legal game history reaches the position; use Maia-2 only as the governed no-history fallback.
- Permit human-policy output to rank relevance and findability only. It cannot establish correctness, a weakness, intention, mastery or psychology.
- Evaluate the bounded candidate set through Stockfish or exact endgame truth, with legal continuations and stable evidence identities. New game analysis stores this evidence before the review is served.
- For already analyzed games, run an explicit, resumable enrichment job only for selected high-value positions and only for candidate branches not present in stored evidence. Preserve the original analysis unchanged.
- Remove or retire the current wasteful regeneration path that starts a fresh MultiPV search but does not deliver its candidate reasoning to the player.
- Derive separate typed facts for the played consequence and the missed opportunity. A centipawn difference by itself is never accepted as the cause.
- Support verified material and exchange decisions, mate attack and defense, forks, pins, skewers, discovered attacks, defender removal or overload, trapped pieces, restricted squares, opening purpose and move order, known trap opportunities, exact endgame decisions, and authorized positional transformations.
- Use canonical opening, trap, endgame, principle and detector sources by identity. Adding or correcting knowledge must not require editing a second caption-only copy.
- Select a small set of the game's most teachable moments rather than presenting every engine preference as a lesson.
- Require every featured moment to have a verified headline, position-specific explanation, legal replay line, visual focus and transferable memory cue.
- Generalize the existing `coach_line_moves` and **Show me on the board** interaction to user mistakes, opponent opportunities, exchanges, opening ideas, traps, exact endings and other authorized proof families.
- Make personalized-lesson questions and answers consume the same position-relative reason bundle as Game Review. Static choices remain only as an honest fallback when no specific alternatives can be proved.
- Let Play with Coach consume the same evidence contract asynchronously. Model or engine enrichment must not freeze the board or prevent a legal game from continuing.
- Keep generated text deterministic. No LLM is required to determine chess truth, choose the lesson, or produce the shipped explanation.
- Store model, engine, detector, knowledge-content and renderer versions plus an evidence fingerprint for every featured moment.
- Record whether the player opened the comparison, replayed it, answered the recognition question, and later encountered the same verified concept. Practice behavior remains separate from proof of transfer in an organic game.
- Provide a deliberate migration and regeneration report for historical reviews, including current, changed, newly enriched, unsupported, rejected and failed records.
- Validate both an existing historical review and a newly imported game through authenticated backend and frontend end-to-end tests before rollout.

## 4. Explicitly out of scope (V1)

- Running Maia, Otter, Stockfish or Fathom synchronously because a player opened or refreshed Game Review.
- Displaying centipawn scores, model probabilities, Elo stereotypes, provider names or technical detector language to the player.
- Showing five candidate moves merely because a human model returned five. The coach shows only useful, verified comparisons.
- Treating Maia or Otter as a source of chess correctness or as proof that the player intended, understood, rushed or guessed something.
- Claiming every valid chess idea in every position is explainable in V1. Unsupported positional residue stays unpromoted and is measured.
- Promoting Shadow detectors merely to increase caption coverage.
- Creating a second opening, trap, endgame, tactical-pattern, positional-principle or caption-template catalog.
- Re-running the complete original Stockfish game analysis for historical games. Historical enrichment is limited to missing candidate branches in selected positions.
- Changing puzzle answers, mastery, focus selection or improvement verdicts solely from human-policy likelihood.
- Automatically marking a concept learned because the player viewed or replayed a line.
- Broad production rollout before the blinded chess-quality review, runtime envelope, migration dry-run and authenticated player journey are green.
- Replacing the current Game Review, personalized lesson or Play-with-Coach pages.
- A permanent fixed top-five policy before candidate-count and probability-mass alternatives are measured.
- Community-authored explanations and reputation scoring. That remains a later, separately governed product.

## 5. Success criteria

- Every featured coaching moment contains all five player-facing parts: what happened, why it mattered, the stronger idea, a legal board replay, and one reusable memory cue.
- Every replay starts from the exact reviewed position, every move is legal in sequence, and the final board agrees with the explanation.
- The complete adversarial packet has zero critical actor, direction, mate, material, exchange, illegality and truncated-payoff failures.
- An equal or favorable capture-recapture sequence is never described as a hanging piece, free loss or uncompensated win.
- Human-policy evidence never introduces a move outside the separately verified candidate set and never changes a correctness or mastery verdict.
- Opening, trap, endgame and principle explanations reference their canonical content identity and current content version.
- A failed model, missing artifact, rejected provenance packet, incomplete line or unsupported detector produces a safe fallback without breaking the review.
- Opening a stored review performs no model inference and no engine analysis. Page latency is independent of how many human candidates were evaluated during enrichment.
- In a blinded coach-quality review, the candidate-aware version must beat the current caption on factual usefulness, clarity and memorability at the precommitted data-locked threshold, with no critical false claim.
- In player validation, users must more often identify the relevant idea after the board comparison than before it, at the precommitted data-locked threshold.
- The full existing-account journey and one freshly imported game both prove that candidate evidence reaches the visible caption, comparison control and board animation; a database-only field does not count as delivered.
- Migration reporting reconciles every targeted historical position. No selected row disappears into an unreported state.
- Existing users who are outside the pilot retain the current review contract unchanged until the new path clears rollout gates.

## 6. Open questions

- **Question:** How many human-policy candidates should be evaluated per selected position, and should the policy use a fixed count or cumulative probability mass? **Why unresolved:** Otter's measured top-five coverage is strong, but cost and marginal teaching value have not been compared for this caption use. **Unblocking step:** run a locked candidate-count bake-off over the existing anonymized evidence packet and report coverage, unique useful ideas, runtime and memory.
- **Question:** Which positions deserve candidate enrichment, and how many featured moments should one game contain? **Why unresolved:** enriching every non-best move would be expensive and would recreate the noisy every-move review. **Unblocking step:** compare current moment ranking, verified-event completeness and independent coach selections on complete games.
- **Question:** What makes a non-best move sound enough and understandable enough to teach? **Why unresolved:** a permanent centipawn band would be a product decision, and the current 25cp same-result proposal is not authorized for public teaching. **Unblocking step:** run a blinded review of candidate bands using stored or explicitly generated branch evidence, then lock the winning rule.
- **Question:** Which positional causes can enter V1 as verified facts? **Why unresolved:** material and forcing mechanisms have stronger proof than concepts such as counterplay, good-piece versus bad-piece and long-term weak squares. **Unblocking step:** create separate near-negative gold for each proposed positional family and authorize them independently.
- **Question:** What is the smallest readable caption and board sequence that still teaches the complete idea? **Why unresolved:** current captions range from hollow one-liners to paragraphs that are too dense for a 600–1500 player. **Unblocking step:** run a blinded three-shape mockup comparison using real verified positions and lock the preferred information order and reading budget.
- **Question:** Should live Play with Coach human-policy inference enter the first rollout? **Why unresolved:** the models are not mounted in the running container and the combined memory and latency envelope has not been observed. **Unblocking step:** benchmark a preloaded isolated inference worker and verify that normal play remains responsive under failure and concurrency.
- **Question:** How large should the historical enrichment cohort be before wider backfill? **Why unresolved:** the useful-position rate and per-position candidate-analysis cost are not yet measured on the current corpus. **Unblocking step:** dry-run a no-write cohort, report eligible positions, expected searches, duration, storage growth and abstention causes, then choose the first cohort.
- **Question:** What blinded preference and player-recognition thresholds constitute success? **Why unresolved:** choosing them now would be arbitrary and could let the result be graded after the fact. **Unblocking step:** use the repository's data-lock process to precommit the thresholds before implementation evaluation.

## 7. Pre-code requirements

- Mohit explicitly signs off this complete scope document.
- Run the repository's numeric data-lock process for candidate count, candidate selection, soundness, featured-moment count, reading shape, historical cohort and evaluation thresholds.
- Run the repository's pre-code audit after the data lock and before editing implementation files.
- Start implementation from a clean worktree at current `origin/working-code`; do not build on the stale, dirty primary checkout or copy whole files across divergent bases.
- Record the canonical owners before editing: `MoveTeachingDecision` for the decision, `ReviewTeachingCause` for the cause, `CaptionExplanation` for player-facing meaning, `TeachingReasonBundle` for position-relative questions, and existing canonical knowledge catalogs for chess content.
- Produce a source map proving no proposed cause, principle or name duplicates an existing canonical source. Where duplicate historical sources already exist, choose one owner and derive views rather than adding another copy.
- Freeze an adversarial regression packet containing the `Qxg3` and `Bxc3` exchange cases, mate-direction cases, paid-for-piece cases, recaptures, forks, quiet checks, x-rays, pinned recaptures, promotions and truncated stored lines.
- Verify the affected historical admission population read-only and define reversible reconciliation states before any update is allowed.
- Mount pinned Maia-2 and Otter artifacts only in an isolated development or staging runtime, verify their hashes and package versions, and observe inference latency and memory before enabling enrichment.
- Prove the candidate enrichment job can resume idempotently, never overwrite original Stockfish evidence, and produce the same fingerprint for the same inputs.
- Prove the new-game path reuses the existing analysis lifecycle and does not start a second full-game engine analysis.
- Define the no-model, no-engine, rejected-evidence and unsupported-cause fallbacks in tests before visible rollout.
- Prepare unit, adversarial, integration, authenticated API, frontend interaction and clean-base regression test lists, including an assertion that review reads start no engine or model process.
- Keep all production feature flags default-off until the migration dry-run, independent chess review and one-account end-to-end validation are complete.
