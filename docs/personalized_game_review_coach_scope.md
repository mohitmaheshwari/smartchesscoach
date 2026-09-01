# Personalized Game Review Coach — Product Scope

**Status:** LOCKED — approved by Mohit on 2026-09-01  
**Date:** 2026-09-01  
**Decision:** Extend the existing Game Review. Consolidate its competing coaching paths rather than create another review page or another chess-content store.

## 0. Existing surfaces audit

**What already touches this need**

- The current Game Review page (`GameDecryptionV5`) already shows a board, per-move captions, principles, visual patterns, opening information, trap lines, Game Moments and a "Why did you play this?" interaction.
- The central caption pipeline already creates the shared per-move teaching decision used by Game Review and Play with Coach. It is the existing authority for move-level coaching.
- The post-game voice system separately chooses a truth line, player story, plan explanation and up to four moments. This overlaps with the central caption pipeline and can produce a second interpretation of the same game.
- The Reflect page already has a deterministic, predicate-backed quick-tag system. It stores intent, confidence, options shown, selected options and a derived awareness gap. Game Review also generates its own reflection options in the browser, so reflection is currently split across two systems.
- `opening_curriculum.json`, accessed through the opening unified source, is the declared canonical opening curriculum.
- `traps.json`, accessed through the trap library and trap scanner, is the canonical trap catalogue and recognizer input.
- Endgame teaching is split between `endgames.json` for Play with Coach and `coaching/endgame_theory_tree.json` for structured lessons and the personal curriculum.
- The concept-detector registry, shape-pattern services, caption facts and principle catalogue already recognize many tactical, geometrical, opening and endgame ideas, but their evidence grades and user-facing authority differ.
- Coach memory, the coach conductor, concept understanding, opening profiles, puzzle attempts and progress services already hold parts of the learner history. They do not yet present one answer to "what does this player know, and did they apply it?"
- Learning, Play with Coach, Today/Home and Progress are downstream coaching surfaces. They should consume the conclusions of Game Review rather than independently reinterpret the same game.

**What is genuinely new**

- Review the whole chess game as a connected lesson, not a list of evaluation losses.
- Recognize successful ideas, missed opportunities, opponent plans, geometry, positional relationships and transitions as well as mistakes.
- Ask the player what they believed through short, verified options before revealing the explanation.
- Combine board truth, player reflection and remembered learning history to distinguish a knowledge gap from rushing, forgetting, tunnel vision, miscalculation or deliberate risk.
- Turn the review into one personalized lesson and one measurable follow-up, then watch for transfer in later real games.

**Overlap decision: EXTEND existing**

The product remains the existing Game Review route and board experience. The central per-move teaching decision remains the move-level authority. A game-level coaching planner is added above it. The separate post-game selector, client-only thought-option generator, duplicate intent paths and split lesson lookups are migrated behind canonical interfaces and then retired after parity is proven. No parallel Game Review product will be created.

## 1. What it is

Personalized Game Review Coach feels like a strong private coach replaying one student's game. It understands what was happening on the board, what each player was trying to achieve, which ideas the student knew or missed, and why the important moves worked or failed. It asks a small number of easy, option-based reflection questions, teaches the most useful new chess knowledge from that game, connects the moments into one story, and creates practice that later proves whether the student can recognize and apply the idea without help.

## 2. What the user sees

The review opens with a human summary, not a scorecard:

```text
I watched how this game unfolded.

You understood the opening plan. The game changed when your opponent
challenged the centre and you continued your attack without answering it.
That same decision left your bishop without a real defender two moves later.

[ Review this game with me ]
```

The game is presented as a short sequence of coaching chapters:

```text
WHAT YOU UNDERSTOOD

6. Re1 was a good decision. You finished development and put the rook
behind the pawn you planned to advance. This is an opening idea you now
use naturally.

────────────────────────────────────────────────────────────

WHAT YOUR OPPONENT WAS TRYING

After ...c5, your opponent was attacking the centre before your king was
safe. If you answered the centre first, your kingside plan could continue.

          [ board with c5→d4 and defender arrows ]

────────────────────────────────────────────────────────────

BEFORE I EXPLAIN  12. Bg5

When you played Bg5, what did you believe about the bishop?

[ It was still protected ]
[ They had to answer my attack ]
[ I saw the risk but thought they could not take it ]
[ I moved without checking it ]
[ I wasn't sure ]
[ None of these ]
```

After the player selects one option, the coach reveals the comparison between belief and board truth:

```text
WHAT ACTUALLY HAPPENED

You were right that Bg5 created a threat. The problem was the defender:
your knight on f3 looked as though it protected the bishop, but the knight
was pinned to your king and could not recapture. The bishop was therefore
not truly safe.

This was not "you don't understand pins." You have solved ordinary pins
before. The new idea is a pinned defender: a piece can look protected even
when its defender cannot move.

[ Show the relationship ]   [ Let me find the safer move ]
```

The review can also teach unused opportunities and positional ideas:

```text
AN OPPORTUNITY YOU DIDN'T NOTICE

For one move, their king and rook stood on the same diagonal. Bd5 would
have attacked the king first and the rook behind it. Your pawn move closed
that diagonal, so the opportunity disappeared.

Remember the shape: king in front, valuable piece behind, one open line.
```

The review ends with one connected lesson and one next action:

```text
WHAT I WANT YOU TO TAKE FORWARD

Your attacking ideas were good. The recurring problem was continuing your
own plan before checking what your opponent's last move changed.

Today we will practise three positions where a defender only appears to be
protecting a piece. In your next games I will watch whether you verify the
defender before committing to an attack.

[ Practise this idea ]      [ Replay the game ]
```

There is no default textbox. Reflection uses short position-specific choices, including honest "not sure" and "none of these" choices. The board can be used when the player wants to demonstrate a calculated line, but typing is not required.

## 3. In scope (V1)

- Extend the existing Game Review route and visual language; no second review destination.
- Produce one game-level coaching plan from the complete ordered set of verified move-teaching decisions.
- Explain the game as opening and early plan, opponent intent, critical changes, tactical or positional moments, transition and finish when the evidence exists.
- Recognize and retain both positive and negative teachable events: created, noticed, used, prevented, allowed, ignored, missed, expired, corrected and repeated.
- Support verified tactical relationships including checks, captures, threats, forks, pins, skewers, discovered attacks, loose pieces, overloaded or pinned defenders, removing defenders, trapped pieces, back-rank patterns and mating geometry.
- Support verified board geometry including ranks, files, diagonals, rays, alignments, fork squares, escape squares, entry squares, promotion squares, rule-of-the-square boxes and relevant color complexes.
- Support verified positional teaching including piece activity, good and bad pieces, improving the worst piece, weak squares, outposts, open files, pawn weaknesses, pawn breaks, exchanges, space, restriction, counterplay and conversion when the recognizer can prove the claim.
- Connect canonical opening plans, deviations and move purposes to the player's actual game without treating every off-book move as an error.
- Detect a known trap being prepared, entered, avoided or punished when the stored line and board evidence establish it.
- Connect verified endgame events to canonical rules and lessons, including opposition, rule of the square, basic mates, rook-endgame positions and promotion races supported by current content.
- Generate reflection options on the backend from verified board facts and the teachable event; the browser must not invent chess explanations.
- Ask reflection before revealing the relevant explanation whenever doing so will produce useful information and will not interrupt the review excessively.
- Store the stable option IDs shown, the selected option, response timing and whether the answer preceded the reveal.
- Keep objective chess evidence and player self-report separate. A reflection answer can refine a diagnosis but cannot change what happened on the board.
- Distinguish, when evidence permits, unfamiliar knowledge, forgotten knowledge, attention lapse, rushing, tunnel vision, calculation stopping early, evaluation error, wrong plan and deliberate risk.
- Treat one answer as evidence about one position. Only repeated opportunities may become a remembered player tendency.
- Use the learner's prior games, demonstrated concepts, lesson attempts, puzzle help, real-game applications, current focus and opening experience to choose explanation depth and wording.
- Track each concept through encountered, introduced, recognized with help, solved independently, demonstrated in training, applied in a real game, retained and relapsed.
- Measure learning against relevant opportunities, not calendar time or raw game count alone.
- Create one clear follow-up from the review: practise this position, study its prerequisite, revisit a canonical lesson or watch for the idea in future games.
- Reuse the same per-move teaching authority in Game Review and Play with Coach, while allowing each surface to have different pacing.
- Keep Stockfish and tablebases as correctness authorities; use detectors to name verified chess reasons; permit human-likelihood models only as optional difficulty or findability evidence, never as correctness authorities.
- Use deterministic language from verified structured facts for chess claims. No deployed LLM is required to understand, classify or explain the game.
- Store all valid detected events for learning history while showing only the moments selected by the coaching planner.
- Provide provenance for every visible chess claim and remain silent or use a narrower explanation when the evidence is insufficient.
- Instrument review start, reflection choice, explanation reveal, board interaction, follow-up start, follow-up completion and later real-game application.

## 4. Explicitly out of scope (V1)

- A chat box that lets an LLM freely interpret the position or decide chess truth.
- Free-text reflection as the normal path. "Not sure" and "none of these" remain available without typing.
- Asking the player a question on every mistake or every move.
- Showing every detector fire, every engine line or every concept that happens to exist in the position.
- Claiming that the system knows why the player moved when the player did not answer and no behavioral evidence supports the inference.
- Promoting shadow-grade detectors directly into player-facing explanations without their required evidence review.
- Teaching opening memorization as a substitute for understanding the purpose, resulting structure and common plans.
- Treating a single correct move, puzzle solve or reflection answer as mastery.
- Replacing Stockfish with Maia, Otter or another human-move model for objective move correctness.
- A new opening, trap, endgame or principle database that duplicates an existing canonical source.
- A separate Game Review page, separate paid review product or permanent parallel caption engine.
- Final visual redesign of Learning, Progress, Home or Play with Coach. V1 supplies them with canonical learning events and next actions; their broader redesign remains separate.
- Inventing fixed planner weights, moment caps, mastery thresholds or rollout thresholds before the required corpus measurements and coach review.
- Regenerating every stored production review before the new pipeline passes shadow comparison and rollout gates.

## 5. Success criteria

- In a blinded reference review, a human coach can trace every visible chess claim to the position, stored engine evidence, a verified detector or canonical lesson content; unsupported claims never reach the player.
- The review explains a coherent cause-and-effect story of the game rather than presenting independent move corrections.
- Eligible reviews include useful chess beyond evaluation loss: at least one of opponent intent, a successful idea, a missed opportunity, a positional relationship, opening understanding or endgame understanding when such evidence exists.
- Two players with the same board event but different prior knowledge or different structured reflections receive meaningfully different diagnoses or teaching actions.
- Reflection choices are generated only from facts that are possible in that position, and the system records "not sure" or "none of these" without forcing a diagnosis.
- A selected review lesson produces a concrete follow-up and a future opportunity definition that can establish application, retention or relapse.
- The learner model changes only from attributable learning events and never from an unverified caption or an unanswered reflection.
- Game Review and Play with Coach agree on the move-level chess reason for the same evidence package.
- Adding or improving one opening, trap, endgame or concept requires editing its canonical source once; every consuming surface resolves it by stable ID.
- The pre-launch corpus bake-off establishes baseline rates for review completion, reflection completion, follow-up start, independent practice success and later opportunity success. Launch thresholds are locked from those distributions rather than selected from intuition.
- After rollout, the primary product outcome is a reduction in recurrence on comparable real-game opportunities among players who received and completed the lesson, measured against their own pre-lesson baseline and an honest untreated comparison where available.

## 6. Open questions

- **Question:** How many moments and reflection interruptions should one review contain for different game lengths and player levels?
  **Why unresolved:** More teaching increases coverage but can turn a review into homework and reduce completion.
  **Unblocking step:** Run a corpus distribution of eligible teachable events, prototype several review lengths and measure comprehension and completion with Mohit and the coach validation group.

- **Question:** Which current detector families are ready to make player-facing claims on day one?
  **Why unresolved:** The registry contains different evidence grades, and detector count is not the same as caption-grade reliability.
  **Unblocking step:** Produce a detector-to-concept coverage matrix with grade, reviewed fires, adversarial status, false-positive rate and current surface reach.

- **Question:** Which endgame source becomes canonical for both Play with Coach and structured lessons?
  **Why unresolved:** Two live sources currently serve overlapping endgame knowledge in different shapes.
  **Unblocking step:** Compare IDs and content coverage, select the richer canonical tree, and define adapters plus a no-duplicate guard test in the technical spec.

- **Question:** Which existing move-intent and reflection implementation becomes canonical?
  **Why unresolved:** Game Review, Reflect and Play with Coach currently use overlapping generators and storage paths.
  **Unblocking step:** Replay each implementation on the same verified sample, compare valid-option coverage and false suggestions, then select one backend contract.

- **Question:** What evidence is sufficient to call a concept introduced, independently understood, applied or retained?
  **Why unresolved:** The states are clear, but numeric opportunity and assistance thresholds must come from actual response and recurrence distributions.
  **Unblocking step:** Run the learning-state bake-off over existing puzzle attempts, lesson events and later game opportunities, then lock thresholds through the data-lock process.

- **Question:** When should the coach ask reflection before revealing the explanation, and when should it explain immediately?
  **Why unresolved:** Reflection is valuable only when the answer can change the diagnosis; unnecessary questions create friction.
  **Unblocking step:** Label a representative game sample by information gain and derive the first deterministic eligibility rules before UI implementation.

- **Question:** How should old stored Game Reviews be refreshed after the new system is enabled?
  **Why unresolved:** Immediate bulk regeneration has cost and migration risk, while lazy regeneration delays consistency.
  **Unblocking step:** Measure stored-review volume, generation cost and user revisit frequency, then choose lazy version refresh, bounded backfill or a combination.

## 7. Pre-code requirements

- Mohit explicitly signs off this complete scope document.
- A technical architecture spec is written separately and signed off; it must define the evidence, teachable-event, reflection, learner-state and game-teaching-plan contracts.
- The architecture spec names one canonical authority for move teaching, reflection options, opening content, traps, endgames, concept IDs and learning events, plus migrations for every retired path.
- A source-of-truth inventory records every current duplicate and its add-cost. No new domain data file or hardcoded concept table is introduced.
- A detector-to-concept coverage matrix identifies what can speak, what remains shadow-only and what content has no reliable recognizer yet.
- Before the Phase 3 planner leaves shadow, a representative, versioned reference corpus must cover wins, losses, quiet games, tactical games, opening deviations, known traps, endgames, missed opportunities, successful ideas and conflicting reflection answers.
- Independent coach annotation is the final internal rollout gate, before any player-visible release. Reviewers label game story, important moments, opponent intent, player-question value, lesson choice and unacceptable claims.
- Numeric choices—including moment limits, interruption budget, evidence gates, mastery transitions and rollout thresholds—are locked from corpus and user data rather than intuition.
- Before Phase 2 changes a live adapter, the current Game Review, Reflect and Play with Coach outputs are snapshotted so consolidation can prove no unintended loss of verified behavior.
- The technical spec defines a default-off feature flag, shadow comparison, A/B validation, staged rollout, rollback and deletion of legacy paths.
- Security and privacy review confirms that reflection data is treated as private learner evidence and is not exposed across users or community puzzles.
- The pre-code audit is completed after all preceding gates pass. No implementation begins before that audit.
