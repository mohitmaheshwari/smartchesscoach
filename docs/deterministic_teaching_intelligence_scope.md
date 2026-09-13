# Deterministic Teaching Intelligence

## 0. Existing surfaces audit

ChessGuru already has the player journey and most of the interaction needed for a genuinely strong game review. The new work must improve the chess intelligence inside that journey, not create another competing experience.

- **Game Review library (`/games`, `AllGames.jsx`):** already presents one coach-selected game before the full archive. When evidence exists, the player sees “Your coach’s pick,” why the game was selected, a short list of chapters under “What we’ll uncover,” and a “Review this with me” action. When that evidence is unavailable, the page falls back to a generic invitation to choose a game. This is the correct place to answer “Why should I study this game?”
- **Canonical single-game review (`/game/:gameId`, `LabV2` and `GameDecryptionV5`):** already provides the board, move navigation, move captions, arrows, candidate comparison, legal line playback, reflection and reporting. It receives the stored teaching plan, whole-game review, teachable events and validation data. It is the correct place for the stronger coaching experience.
- **Whole-game coach (`PersonalizedReviewCoach.jsx`):** already opens with “What this game was about,” shows opening, middlegame and endgame cards, distinguishes a lesson from good play, no proven lesson and a phase not reached, and supports turning points, opponent plans, missed opportunities, recurring connections and reflection. This is the existing product shell to extend.
- **Legacy replay (`/replay/:gameId`):** overlaps with the canonical review. It is already being redirected toward the canonical review and must not become a second coaching brain.
- **Central caption pipeline (`caption_pipeline.py` and `caption_facts.py`):** already owns the facts and explanation decision for one move. It can reason from legal board geometry, stored engine continuations, material consequences, mate, hidden opportunities and canonical chess knowledge. It must remain the single owner of move-level chess truth and explanatory facts.
- **Review event and plan path (`game_review_event_adapter.py`, `game_review_contracts.py`, `game_review_planner.py` and `whole_game_review_composer.py`):** already turns an authorized move decision into a teachable event, selects a bounded review plan and composes the three-phase story. The composer intentionally presents verified facts rather than detecting chess again.
- **Game selection (`coach_selected_review_service.py`):** already selects a game from authorized teaching plans. New intelligence should improve the evidence it receives and the reason shown to the player, not introduce another recommendation store.
- **Opening, traps, positional concepts and endgames:** canonical recognizers, curricula, authored knowledge and exact-ending support already exist. Availability is uneven, and implementation presence does not mean a concept is authorized to make a player-facing claim.
- **Detector authorization (`detector_quality.py`):** already decides which evidence may influence a caption, plan or mastery statement. Shadow and Disabled evidence must stay invisible to the player.
- **Learning evidence, reflection and Progress:** existing services already distinguish exposure, assisted practice, independent recognition and later unassisted-game transfer. This phase must write through those contracts rather than invent another mastery system.
- **Existing deterministic whole-game scope:** already defines the intended connected game story and player interaction. Its first frozen holdout proved chess safety but failed the useful-lesson comparison: legacy captions covered 70 of 90 independently proved moments, while the new shared fact layer reached an upper bound of 72 of 90. The player-visible improvement was therefore not proved and release correctly remained blocked.

The overlap is large: ChessGuru already has the correct routes, pages, interaction controls, storage path, review composer, authorization gate and learning ledger. The genuine missing value is broader and deeper deterministic chess understanding: recognizing what the position was asking, which tempting human choices mattered, what either side could have tried, why an alternative works, and what the player should remember.

**Decision: EXTEND.** Preserve the existing Game Review experience and canonical reasoning path. Improve shared chess facts, proof families, candidate contrasts, selection and teaching language inside that path. Do not create another review page, caption service, detector registry, chess-knowledge catalog, recommendation system or progress tracker. Mohit approved EXTEND on 2026-09-13.

## 1. What it is

Deterministic Teaching Intelligence makes a ChessGuru review feel like sitting with a strong coach who has studied the whole game. The coach does not merely announce that one move was inaccurate or repeat an engine’s preferred move. It shows what the position was asking, what the player and opponent could have tried, why a tempting choice succeeds or fails, which good decisions deserve to be remembered, and how one moment connects to the opening, middlegame, endgame and the player’s current learning plan. Every statement shown to the player is reproducible from verified chess evidence. Codex contributes deep chess reasoning offline to discover missing ideas, challenge shallow explanations and create adversarial examples, but it never becomes an unverified runtime authority.

## 2. What the user sees

The library chooses a game for a concrete learning reason:

```text
YOUR COACH’S PICK

Lost vs Arjun

Study this one because your Italian opening was healthy, but the first
central pawn break created a tactic neither side used. Later, you solved
the same piece-safety problem correctly.

What we’ll uncover
  Opening       Your setup was sound; the centre was the real question.
  Middlegame    A pawn push could attack two pieces at once.
  Your progress You protected the rook in a similar position later.

[ Review this with me ]                       [ Choose another game ]
```

The review begins with one connected account of the game:

```text
WHAT THIS GAME WAS ABOUT

The opening did not lose this game. You developed normally and made your
king safe. The important moment came when the centre opened: both players
looked at the capture, but the stronger idea was the pawn push behind it.
The game ended before a real endgame began.

[ Start with the first lesson ]
```

The opening card teaches purpose rather than rewarding memorization:

```text
OPENING · ITALIAN GAME

You handled the setup well through move 7. Your bishop was active and your
king was safe. I found no verified opening problem there.

After ...d5, the position stopped being about development. It became a
question of what happens after the centre opens.

[ Show the setup ]   [ Show what changed ]
```

At a featured moment, the player sees the board before the answer and receives a position-relative question:

```text
THE POSITION CHANGED HERE

Your opponent played Re1. Before moving, what can your d-pawn do if the
rook captures on e4?

[ Push ...d5 and attack the rook and bishop ]
[ Exchange queens because equal trades are always safe ]
[ Move the knight because it is attacked ]
[ I cannot see it yet ]

[ Let me play on the board ]   [ Give me one clue ]
```

The answer is short first, with detail available through interaction:

```text
ATTACK TWO PIECES AT ONCE

After Nxe4 Rxe4, ...d5 attacks the rook on e4 and bishop on c4 together.
White can save only one.

[ Play the missed sequence ]   [ Try a safer defence ]

REMEMBER
Before recapturing, check whether a pawn push attacks two pieces.
```

The coach also explains the opponent’s opportunity when that is the most useful lesson:

```text
WHAT YOUR OPPONENT COULD HAVE TRIED

Your queen moved away from the defence of f2. Black did not use it, but
...Ng4 would have attacked f2 twice while your king had only one defender.

[ Play Black’s idea ]   [ Find your defence ]
```

Positional lessons must show a board consequence, not an abstract label:

```text
THE EXCHANGE YOU SHOULD PAUSE OVER

Trading queens here removes your only active piece while you are a pawn
down. Keeping the queens gives you checks against the exposed king—the
counterplay that keeps the game difficult for Black.

[ Compare the two positions ]
```

Good play is part of the review:

```text
YOU UNDERSTOOD THIS ONE

You moved the rook before taking on c6. That avoided the pawn fork and kept
both pieces safe—the same decision we have been practising.

[ Replay my decision ]
```

Endgame teaching is exact when exact evidence exists and honest when it does not:

```text
ENDGAME · KING AND PAWN

Kc4 keeps the win because your king reaches the three key squares in front
of the pawn. Kc3 lets the defending king take the opposition and draw.

[ Find the winning route ]   [ Show the key squares ]
```

or:

```text
ENDGAME

This game ended before a real endgame began. There is nothing useful to
study here.
```

The review ends with one instruction and an honest learning state:

```text
TAKE THIS INTO YOUR NEXT GAME

When the centre can open, calculate the pawn push before automatically
recapturing.

You recognized the idea here. That is practice—not proof that the habit has
changed. I will look for the same decision in a different position and then
in one of your later games.

[ Practise one new position ]   [ Finish review ]
```

## 3. In scope (V1)

- Extend the canonical `/games` recommendation and `/game/:gameId` review; no parallel player journey is created.
- Preserve one connected story across opening, middlegame and endgame, with an honest state for each phase: verified lesson, verified good play, no verified lesson or phase not reached.
- Make the explanation contract for every featured moment: **position demand → tempting human choice → best verified reply or opportunity → concrete consequence → better idea → memory cue**.
- Treat the best engine move as evidence, never as the lesson by itself.
- Explain opportunities that were not played by either side when their setup, legal continuation and payoff are verified and the lesson is more useful than merely describing the played moves.
- Support multiple candidate branches when they teach meaningfully different ideas; do not display several engine lines that say the same thing.
- Include opponent plans, missed defensive resources, positive decisions and quiet moves—not only the player’s mistakes and captures.
- Expand deterministic teaching coverage across the proof families that the fresh development audit identifies as the largest player-visible gaps. Eligible families include multi-move tactics, defensive resources, opening purpose, exchanges, pawn transformations, piece coordination, king safety, geometry and exact or authorized endgames.
- Distinguish a verified chess fact from its teaching interpretation. A position can prove an attack, trade, fork, forced result or square relationship without automatically proving what the player knew or intended.
- Generate every question and answer choice from the actual verified position bundle. Wrong options must be legal or recognizably tempting in that position and must never contradict the board.
- Give a direct right/wrong verdict, the causal idea and an interactive line after the player answers or moves.
- Keep the initial explanation brief enough for a 600–1500 player; reveal deeper lines progressively through replay, comparison, hint and “why?” controls.
- Use canonical opening knowledge to explain setup, purpose and first meaningful departure. Leaving known material is never called a mistake without separate consequence evidence.
- Use exact endgame truth where supported. Named principles may appear only when their own evidence is authorized for the receiving surface.
- Recognize and preserve good play using the same factual standard as mistakes. “You understood this” requires more than matching one best move by accident.
- Personalize game choice, example order, recalled history, question depth and the final memory cue from the player’s existing profile and evidence. Personalization may change delivery and priority, never chess truth.
- Use Maia or another human-move model offline only if a measured bake-off shows that it improves the choice of plausible candidates or distractors. Stored engine evidence, exact endgame truth and verified deterministic rules remain the correctness authority.
- Use Codex chess reasoning offline throughout development to review complete games, inventory instructive ideas from both sides, challenge the system’s explanations, find missing proof families and author difficult positive, negative and adversarial examples.
- Require every accepted Codex finding to become a reusable typed fact or proof, deterministic rule, independent verifier, test set and authorization packet before it can reach a player.
- Never add a sampled-game exception, FEN-specific prose patch or hidden answer keyed to the development corpus.
- Build a fresh anonymized development corpus of complete games using stored evidence. The previously opened 42-game holdout and its 90 positions remain frozen historical evidence and are not used for tuning.
- Freeze a second, untouched, player-stratified holdout before development answers or system selections are inspected.
- Compare the actual authorized player-visible old and new experiences, including text, interaction and selected moments. Internal fact coverage is reported separately and cannot stand in for product improvement.
- Score factual correctness, causal usefulness, missed teachable moments, abstentions, phase balance, repeated language, question quality, line legality, memory value and whole-game coherence.
- Account for every independent-review disagreement with one frozen disposition: exact match, causal equivalent, wrong reason, incomplete proof, fact not wired, detector miss, unsupported interpretation or genuinely missing concept.
- Improve shared canonical logic only when the gap repeats or represents an important adversarial failure. Rerun the development evaluation after every accepted family-level improvement.
- Keep the existing detector authorization gate fail-closed. Shadow evidence may be measured and reviewed, but it may not influence visible stories, answers, plans or mastery.
- Preserve proof family, evidence source, rule version, knowledge version and renderer version for every visible lesson.
- Record existing review, replay, hint, answer, retry, reflection and learning events through the current analytics and learning contracts.
- Keep assisted review success separate from independent recognition and later unassisted-game transfer.
- Validate one existing stored game and one newly analysed game through authenticated API and visible frontend journeys before any rollout recommendation.

## 4. Explicitly out of scope (V1)

- A new Game Review page, replay product, caption service, detector registry, chess taxonomy, content library, recommendation store, mastery system or progress page.
- Runtime LLM, Codex, Maia, Otter, Stockfish or network tablebase calls when a player opens or uses a stored review.
- Letting a language model or human-move model decide whether a move is correct or whether a chess claim is true.
- Re-running Stockfish across the historical analysed-game corpus. Any bounded offline enrichment beyond stored evidence requires a separate written data and cost decision.
- Claiming complete chess understanding or promising a lesson for every position.
- Padding sparse games or phases with generic chess advice.
- Showing raw centipawn values, engine depths, model probabilities, detector names, authorization grades or internal reports to players.
- Treating every engine preference, opening departure or uncommon human move as a mistake.
- Unsupported mental-state claims such as panic, blindness, laziness, guessing, carelessness or “you did not know this.”
- Rating stereotypes as explanations. Rating may control teaching depth or candidate relevance only when the behavior is measured.
- Promoting a detector because its prose sounds convincing, its internal coverage increased or Codex agrees with individual examples.
- Using the opened 42-game holdout, its 90 adjudicated moments or the failed baseline comparison to tune rules, rankings, templates or exceptions.
- Weakening chess-safety, authorization or evidence gates to meet a coverage target.
- Community-authored explanations, reputation, human-coach hiring or marketplace workflows. They remain a later product opportunity.
- Claiming mastery from one correct answer, one solved puzzle, one review completion or one coached game.
- Production migration, backfill, feature enablement or deployment during this scope’s research and implementation work. Claude retains push and production deployment responsibility after an independently verified handoff.

## 5. Success criteria

- On a fresh unseen holdout, the new **authorized player-visible** review beats the current player-visible review for useful causal teaching under a precommitted paired comparison whose confidence requirement is locked before results are opened.
- The comparison evaluates the complete rendered lesson and interaction, not merely whether an internal fact exists or whether both systems recommend the same move.
- Critical false chess claims are zero in development adversarial evidence and in the fresh holdout.
- Every featured line is legal from the displayed position, preserves actor and board orientation, and reaches the consequence described to the player.
- Independent chess adjudication confirms that each featured moment teaches the correct reason—not just the correct move—and that every stronger alternative shown is supported by its stated consequence.
- The new system finds materially more of the independent coach’s genuinely useful moments across opening, middlegame and endgame without filling the review with low-value engine differences. Exact thresholds are locked from data before scoring.
- The system improves whole-game coherence: independent reviewers can identify one central game story, understand why each chosen moment belongs, and see how the phases connect at precommitted thresholds.
- Position-relative questions pass factual, relevance and answer-hiding checks; static generic choices are used only in an explicitly measured fallback state.
- The experience remains readable for 600–1500 players: the first visible explanation is concise, the board carries the demonstration, and optional detail is progressive. Voice and comprehension thresholds are locked before evaluation.
- Verified good play and opponent opportunities appear when they are independently judged more instructive than another mistake caption; sparse games still abstain honestly.
- Every accepted Codex discovery improves a reusable proof family or canonical explanation contract and passes examples outside the game where it was discovered. Per-position production patches remain zero.
- Development, holdout and adversarial signatures are disjoint, versioned and reproducible. No player identity or credential enters an evidence packet.
- Page reads and interactions initiate zero runtime engine or model work and make zero unexpected database writes.
- The authenticated non-admin journey proves that a player can see why a game was chosen, understand the phase story, answer a relative question, replay a missed opportunity, retry it and produce the correct existing learning evidence.
- Assisted activity never changes an organic-game transfer verdict by itself, and users outside the approved pilot remain on the current experience.

## 6. Open questions

- **Question:** How large should the fresh development corpus and untouched holdout be? **Why unresolved:** the previous 100-game development set and 42-game holdout revealed the direction, but the eligible population, player diversity and phase distribution have changed. **Unblocking step:** run a read-only census and lock sizes that provide player-level independence and enough opening, middlegame and real-endgame evidence.
- **Question:** How should games be stratified across player, rating evidence, result, color, time control, opening family, game length and endgame presence? **Why unresolved:** a recent or random sample can overrepresent one player, one opening or short tactical losses. **Unblocking step:** compare candidate sampling plans against the current corpus distribution and lock one before exporting positions.
- **Question:** Which missing proof families should V1 implement first? **Why unresolved:** intuition favors tactics and material because they are easy to prove, while the largest player-visible teaching gap may be opening purpose, defence, positional transformation or good-play explanation. **Unblocking step:** have Codex independently inventory complete development games before seeing existing captions, then rank recurring uncovered lessons by frequency, importance and proof feasibility.
- **Question:** What exact structured contract represents a teaching idea without creating a second chess taxonomy? **Why unresolved:** the current typed facts cover many consequences but not every position demand, candidate contrast or reusable memory cue. **Unblocking step:** map proposed fields onto existing `MoveTeachingDecision`, reason bundles and `TeachableEvent`; extend the canonical owner only where a repeated gap cannot be represented.
- **Question:** Which human candidate source best identifies tempting alternatives for a player’s level? **Why unresolved:** legal moves, played moves, engine multi-PV and Maia can produce different candidate sets, and popularity is not proof of instructional value. **Unblocking step:** run an offline bake-off on frozen positions, compare candidate recall against independent human review and keep the simplest source that wins without becoming a truth authority.
- **Question:** How many featured moments and alternative branches create the best review? **Why unresolved:** the current bounded plan protects attention, but some games have one deep lesson while others have several connected opportunities. **Unblocking step:** render complete experiences under candidate policies and lock the rule from coach usefulness and player-comprehension evidence.
- **Question:** How is the central game story selected when engine swing, personal recurrence, opening lesson, hidden opportunity and demonstrated knowledge disagree? **Why unresolved:** no single existing score has proved that it chooses the most memorable teaching story. **Unblocking step:** bake off candidate ranking policies against blinded whole-game coach selections and freeze the winner before holdout.
- **Question:** What evidence permits “you understood this” rather than “you played the right move”? **Why unresolved:** a good move can be forced, obvious, accidental or supported by prior learning. **Unblocking step:** define positive-understanding claims with hard negatives and require independent recognition or comparable-decision evidence before stronger wording.
- **Question:** What evidence permits a strong opening claim such as “you understood the Italian setup”? **Why unresolved:** following known moves, achieving a sound position and demonstrating the opening’s purpose are different facts. **Unblocking step:** separate identity, known-line coverage, plan execution and consequence claims, then authorize their wording independently.
- **Question:** Which positional concepts can be proved reliably from stored evidence without turning labels into vague opinion? **Why unresolved:** geometry and pawn transformations can often be measured, while “bad bishop,” “space” or “counterplay” need explicit board consequences and hard negatives. **Unblocking step:** require each proposed concept to supply a legal observable, a counterexample and a payoff or constraint before it enters the proof-family bake-off.
- **Question:** What is the canonical phase owner for Game Review? **Why unresolved:** legacy paths have used move numbers, opening boundaries and material-based endgame guesses differently. **Unblocking step:** trace every current phase consumer, choose the existing source with the strongest evidence and add a guard against review-local reclassification.
- **Question:** What thresholds define useful improvement, reviewer preference, comprehension, factual precision, coverage, abstention and generalization? **Why unresolved:** setting them after viewing results would make the release gate meaningless. **Unblocking step:** use the repository’s data-lock process on baseline distributions and precommit every threshold before implementation scoring.
- **Question:** Which historical reviews would eventually be regenerated? **Why unresolved:** the number of current, partial, stale, unsupported and invalid records is unknown, and regeneration must not create a user-visible dark window. **Unblocking step:** produce a no-write reconciliation report and design an idempotent transition only after the fresh holdout passes.

## 7. Pre-code requirements

- Mohit explicitly signs off this complete scope document.
- Run the repository’s data-lock process before choosing corpus sizes, sampling strata, proof-family priorities, candidate source, moment count, story ranking, wording strength, evaluation rubric, success thresholds or rollout cohort.
- Run the repository’s pre-code audit after all required data locks and before changing an implementation file.
- Use a clean worktree based on current `origin/working-code`. Reconcile the isolated whole-game branch deliberately; do not copy entire stale files over newer upstream work.
- Record the opened 42-game holdout and all 90 adjudicated signatures as permanently unavailable for tuning. Automated checks must reject overlap with the new development and holdout sets.
- Freeze the current production-visible Game Review output for the new evidence corpus before altering facts, selection, composition or rendering.
- Define and freeze the independent Codex chess-review rubric before Codex sees existing captions, selected moments, detector labels or product answers for the development games.
- Make the Codex review inventory complete games and both players’ opportunities across opening, middlegame and endgame, including good decisions and honest no-lesson phases.
- Produce identity-free, versioned packets with stable opaque signatures and only the stored board and continuation evidence necessary for review. Prove the absence of user IDs, game IDs, emails, account names, credentials and source URLs.
- Inventory every canonical owner before adding a field or rule: game recommendation, phase boundary, opening identity, canonical chess knowledge, fact builder, move decision, teachable event, detector authorization, replay line, reflection and learning evidence.
- Demonstrate that each proposed proof family cannot be represented by an existing canonical fact before extending the shared contract.
- Freeze an authorization inventory for every candidate proof family and receiving surface. Unknown, Shadow and Disabled evidence must be excluded from player-visible baseline and candidate scores.
- Define hard-positive, hard-negative, equal-trade, recapture, quiet-resource, x-ray, zwischenzug, opponent-best-response, orientation, legal-replay and stored-horizon adversarial requirements before authoring new rules.
- Define one independent verifier for each new proof family. The production recognizer must not grade its own answer key.
- Define tests proving that question options are position-relative, legal or explicitly conceptual, mutually meaningful, answer-hidden and consistent with the replayed consequence.
- Define tests for opening-purpose language, non-mistake deviations, opponent opportunities, good play, positional claims, exact endings, no-endgame games, sparse games and conflicting possible stories.
- Define old-versus-new product projection so that it compares only what the player can actually see under current authorization. Internal fact upper bounds must be labeled and scored separately.
- Define unit, property, adversarial, clean-base regression, authenticated API, frontend interaction and end-to-end test lists, including zero runtime model/engine calls on review reads.
- Define the migration and rollback contract before any stored review is regenerated: dry-run categories, stable counts, idempotency, per-record atomicity, provenance compatibility and no dark window.
- Keep production flags default-off until the fresh untouched holdout, clean-base test comparison, reconciliation dry-run, authenticated non-admin journey and independent deployment review all pass.
