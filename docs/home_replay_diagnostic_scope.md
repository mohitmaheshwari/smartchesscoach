# Home Replay Diagnostic — Product Scope

**Status:** LOCKED — approved by Mohit on 2026-09-02 (“now go for home”)  
**Date:** 2026-09-02  
**Decision:** Extend the existing Personal Curriculum Home experience. Replace its generic primary card with an answer-hidden board diagnostic; do not create another Home page, replay product, or learner model.

## 0. Existing surfaces audit

### What already touches this need

- The routed Home page is `HomePageNew`. When Personal Curriculum is enabled, it renders `CurriculumHome`, whose primary recommendation is rendered by `CurriculumPrimary`.
- `CurriculumPrimary` already shows the active focus, the coach's instruction, one primary action, and a “What I noticed in your games” disclosure. Its personal explanation currently comes from the teaching profile and can collapse to the generic sentence, “This is the one idea in your current coaching plan.”
- `PersonalizedLessonWorkspace` already provides an interactive board, answer submission, reason choices, help actions, evidence disclosure, and the Diagnose → Explain → Guide → Recall → Mix → Transfer → Apply → Retain learning stages.
- The personalized lesson endpoints already create an owned, idempotent learning session, grade a board move, record assistance, capture a reason choice, identify a supported misconception, and distinguish assisted from independent evidence.
- `review_reflection_service.py` already owns verified, options-only reflection prompts on the backend. It validates that the event is authorized, includes honest “not sure” and “none of these” choices, and stores one current answer per user, game, and event.
- Game Review already has the exact position before a mistake, the move played, verified board evidence, reflection prompts, and later follow-up actions.
- The stored move observations and verified training positions already contain the game, move number, FEN, played move, safe answer, detector identity, and provenance needed to reconstruct a moment without asking the player to remember the game.
- `LichessBoard` already supplies the board interaction, orientation, arrows, square highlighting, and variation playback needed for a replay.
- `/replay/:gameId` already presents several moments from one game, but it is a view-only narrative driven partly by LLM board reading. It does not test the player's present understanding and is not a safe authority for this feature.
- `CriticalMoments` and older parts of `GameDecryptionV5` contain useful interaction patterns, but some reflection state is local or some options are generated in the browser. Those paths must not become a second source of diagnosis truth.
- The signed Home conversation scope already requires one coach conversation, no exposed reports or percentages, and a relationship that feels more personal over time.
- The signed Personal Curriculum scope already requires Diagnose, gradual help, independent transfer, later real-game application, and honest learning states instead of instant mastery.

### Overlap

- Home already recommends one focus, Training already tests it on a board, Game Review already asks what the player believed, and Progress already watches recurrence.
- A separate “memory examples” card, new replay route, new reflection store, or new mastery model would duplicate those responsibilities and split the coaching relationship again.
- Showing the opponent name, move number, or a sentence about a lost rook repeats what Game Review can already report. It does not establish whether the player understands the position today.

### Genuine missing value

ChessGuru currently decides what to teach before it has directly tested whether the player lacks the knowledge, merely failed to use knowledge they already possess, recognizes only a remembered position, or needs a small trigger. The important evidence is hidden in separate pages. Home therefore reports a theory instead of letting the player experience the coach proving or correcting that theory.

### Decision: EXTEND existing

Extend the canonical Personal Curriculum flow. Replace the generic `CurriculumPrimary` Home interaction with an answer-hidden two-position replay diagnostic when verified evidence makes one available. Reuse the existing board, verified grader, personalized learning session, backend reflection authority, curriculum state, and later real-game monitoring. Keep the existing Home route and existing coaching-plan ownership. Do not use the old LLM replay as chess authority and do not create parallel diagnosis or mastery collections.

## 1. What it is

Home Replay Diagnostic lets the coach test a belief about the player before prescribing a lesson. Instead of telling a 1000-rated player to remember a previous game, ChessGuru quietly rebuilds the position, hides the answer and lesson label, and asks the player to move now. It then tests the same underlying decision in a different-looking position. The combination tells the coach whether the player understands the idea, recognizes it only in a familiar setting, can finish with a hint, or genuinely needs to learn it. Home changes immediately from “I noticed something” to “Now I understand what is happening,” gives one appropriate next action, and later watches real games to see whether the change holds.

## 2. What the user sees

### Home — before the coach has tested its theory

```text
Good evening, Mohit.

I think the same blind spot is hiding in different positions.
I do not want you to remember the games. I want to see what you notice now.

                    [ Test my coach's theory · about 1 minute ]

This will not change your plan until you show me what you understand.
```

The Home headline does not say “Piece safety,” expose a detector name, show a frequency, or claim that this is the player's main weakness.

### First position — rebuild the decision, not the memory

```text
ONE POSITION FROM YOUR GAMES

                 [ interactive board ]

It is your move. Play what you would choose now.

                    [ I want one small question ]
                    [ Show me what to look at ]
```

The original move, best move, detector label, lesson title, opponent name, and explanation remain hidden. The player moves first. Asking for help is always allowed and remembered honestly.

### Second position — test whether the idea transfers

```text
NOW A DIFFERENT POSITION

The pieces are arranged differently, but I am checking the same decision.

                 [ interactive board ]

It is your move. What would you play?
```

When a second matching moment from the player's games is unavailable, the coach uses a verified, answer-hidden position from the canonical or admitted community pool. It does not pretend that position came from the player's game.

### Reflection — only when it can change the diagnosis

```text
Before I explain, what were you checking?

[ Whether all my pieces stayed safe ]
[ Whether my move created a threat ]
[ Only the piece I moved ]
[ I moved quickly without checking ]
[ I wasn't sure ]
[ None of these ]
```

The choices come from verified backend facts. There is no default textbox, and the answer cannot alter objective chess truth.

### Home — after both positions

If the player solves both independently:

```text
Now I understand it better.

You already know how to keep the position safe. You found the idea even when
the board looked different. The work is using that knowledge before every move,
especially when you already like your attacking idea.

TODAY'S PRACTICE
One short coached game. I will stay quiet unless this decision appears.

                         [ Play with my coach ]
```

If the player solves the familiar position but misses the transfer position:

```text
You recognized the first position, but the idea disappeared when the board changed.

So I will not make you repeat the old answer. I will teach you the board signal
that tells you when this check is needed.

                         [ Learn the signal ]
```

If the player needs a hint:

```text
You could finish once I pointed your eyes in the right direction.

The knowledge is partly there. What is missing is a reliable question that
starts your check before you move.

                         [ Build my trigger ]
```

If the player misses both independently:

```text
This is not just a careless move. There is a relationship on the board that
you do not see reliably yet. I will teach that first, then let you solve a new one.

                         [ Teach me on the board ]
```

These conclusions remain appropriately hedged until the evidence supports them. One diagnostic never becomes mastery and never becomes a permanent personality label.

### A later Home visit — the relationship moves forward

```text
Last time, you showed me that you understand this idea when you stop to check.

In your newest game, the same decision appeared again. This time you handled it
without help. I am keeping the lesson in your plan until you do that reliably in
different positions.

                         [ See the moment ]
```

The diagnostic is not repeated on every visit. Home advances through a relationship: theory → direct test → teaching decision → real-game watch → demonstrated change. It reopens the question only when new evidence contradicts the current understanding or a materially different hypothesis needs testing.

## 3. In scope (V1)

- Replace the generic primary curriculum card on Home with a replay invitation whenever one verified, eligible coaching hypothesis exists.
- Keep the existing `/home` route, Personal Curriculum ownership, layout, and one-primary-action rule.
- Select one candidate hypothesis from verified player evidence without equating “the only Plan-authorized detector” with “the player's largest weakness.”
- Reconstruct an exact answer-hidden position from the player's stored game evidence; never ask the player to remember the game.
- Test the same underlying decision in one different-looking, independently graded position.
- Prefer a second eligible position from the player's games; otherwise use a verified canonical or admitted community position and label its source honestly.
- Require backend-verified position identity, legal move grading, answer redaction, detector provenance, content version, and admission state for every served position.
- Let the player move before revealing the topic, answer, original move, opponent, explanation, or coaching conclusion.
- Offer the existing three help modes and record their use; assisted success remains different from independent success.
- Ask a short backend-owned reflection only when its answer can distinguish plausible diagnoses or select different teaching.
- Include honest “not sure” and “none of these” options and never require a textbox.
- Produce a bounded diagnostic result from the two moves, help used, and reflection: demonstrated transfer, familiar-only recognition, prompted recognition, or current learning need.
- Treat solving both positions as controlled transfer evidence only. It does not prove that ChessGuru caused improvement, that the skill is retained, or that the player will apply it during a real game.
- Use diagnostic results to choose the next existing curriculum action: coached application, trigger practice, targeted lesson, or independent reassessment.
- Store events in the existing learning-session and coaching-evidence architecture with stable IDs and idempotent submissions.
- Preserve objective chess evidence separately from the player's explanation and from the coach's provisional interpretation.
- Change the Home conversation after completion so the user sees what the coach learned and what happens next.
- Avoid repeating a completed diagnostic unless later evidence is contradictory, stale under a data-locked rule, or testing a materially different hypothesis.
- Watch future verified real-game opportunities and update Home from “learning” toward “used in games” only when the existing evidence contract permits it.
- Keep the lifecycle explicit: theory → controlled test → teaching decision → watching for an organic opportunity → applied or missed → delayed retention → graduated or refreshed.
- When no relevant later opportunity occurs, preserve “not measured”; absence of a detector fire cannot be presented as improvement.
- Instrument invitation shown, diagnostic started, first move submitted, help requested, transfer move submitted, reflection selected, result reached, prescribed action started, prescribed action completed, and later real-game opportunity outcome.
- Ship behind a default-off feature flag and validate on Mohit's enrolled account before any broader cohort receives it.

## 4. Explicitly out of scope (V1)

- A new Home route, separate replay product, new curriculum engine, new mastery collection, or second learner profile.
- Replacing the full Game Review, Training, Progress, or Play with Coach interfaces.
- Using `/replay/:gameId` or an LLM-generated board narrative as chess truth or diagnosis authority.
- Asking the player to remember an opponent, result, move number, or previous mistake as proof that coaching is personal.
- Showing reports, percentages, centipawn loss, detector names, confidence scores, weakness rankings, or peer comparisons on Home.
- Declaring that one recurring detector fire is the player's primary weakness without comparative evidence across eligible skill families.
- Diagnosing rushing, blindness, knowledge failure, calculation failure, or a permanent behavior from one answer alone.
- Treating one correct replay, one reflection, or one later clean move as mastery.
- Asking reflection questions on every position or forcing an explanation before the first board attempt.
- Free-text reflection as the normal experience.
- Letting client-generated option text, caption prose, or the player's self-report change the objective grader.
- Serving shadow-grade, Disabled-grade, quarantined, conflicted, answer-leaking, or incompletely proven positions.
- Running Stockfish again over games that already contain sufficient stored engine truth.
- Introducing Maia, Otter, Fathom, or another model into the deployed correctness path. Human-move models may be researched separately for findability or difficulty only.
- Expanding V1 to every opening, trap, endgame, positional, and tactical detector before each family can provide verified paired positions and a valid teaching action.
- Rolling the feature out to all users before the candidate-selection and diagnostic-validity checks pass.

## 5. Success criteria

- In blinded usability review, a 600–1500 player can explain why the coach chose the next action without needing to remember the original game or interpret a statistic.
- Different observed behaviors produce different coaching actions: independent transfer leads to application practice, familiar-only recognition leads to transfer teaching, assisted success leads to trigger practice, and repeated misses lead to direct instruction.
- A player's first move cannot be influenced by leaked lesson labels, original moves, answers, highlighted solution squares, client payload fields, or pre-move explanatory copy.
- Every served position and every chess claim can be traced to stored engine truth, an authorized detector or canonical content, a versioned grader, and an honest source label.
- The diagnostic result remains reproducible from stored events and is unchanged by page refresh, retry, duplicate submission, or browser manipulation.
- Completion leads to a meaningful downstream behavior: the player starts the prescribed lesson or coached application, and ChessGuru later measures a relevant real-game opportunity rather than merely recording a click.
- Retrospective validation shows that the result categories separate players who subsequently handle comparable real-game opportunities differently from a baseline based only on raw mistake frequency.
- Manual testing on Mohit's account produces a coaching conclusion that a human coach agrees is supported by the two positions and the player's responses.
- The Home experience continues from the prior result on the next visit instead of showing the same generic observation again.
- No other user receives the experience until the agreed correctness, comprehension, completion, and downstream-action thresholds are locked from evidence and passed.

## 6. Open questions

- **Question:** What evidence makes a coaching hypothesis eligible for this diagnostic?
  - **Why unresolved:** The current production focus demonstrates recurrence but the primary-weakness ranking and stored score metadata are not yet comparable across exact skill families.
  - **Unblocking step:** Recompute candidate families from stored observations, compare recency, severity, opportunity rate, clean opportunities, and peer-relative prevalence, then run `/lock-via-data` on the eligibility rule.

- **Question:** How similar must two positions be to test the same underlying decision while still being genuinely different?
  - **Why unresolved:** Matching only a broad category creates false equivalence; matching an exact FEN tests memory rather than transfer.
  - **Unblocking step:** Build a candidate-pair corpus using verified detector facts and board relationships, have Codex and human coaches grade same-skill/different-surface validity, and data-lock the pairing predicate.

- **Question:** When should reflection be asked, and which answer choices are genuinely diagnostic?
  - **Why unresolved:** Asking every time creates friction, while generic options add no information and may prompt the answer.
  - **Unblocking step:** Map each provisional result branch to the minimum extra fact needed, then retain only backend options that can change the selected intervention.

- **Question:** When may the system say “you understand this” rather than “you solved these positions”?
  - **Why unresolved:** Two answers can establish current transfer evidence but cannot establish durable mastery.
  - **Unblocking step:** Keep V1 language narrow, then data-lock stronger language against delayed independent positions and later real-game opportunities.

- **Question:** What should happen when only one verified position exists for a candidate hypothesis?
  - **Why unresolved:** Fabricating a transfer test would damage trust, but silently suppressing every sparse skill may hide useful coaching.
  - **Unblocking step:** Measure eligible pair coverage by skill and user. Choose between a clearly labelled single-position “coach check” state and deferring the hypothesis until a valid pair exists.

- **Question:** What completion, comprehension, and downstream-action thresholds unlock wider rollout?
  - **Why unresolved:** Pre-launch behavior is not a valid engagement baseline, and historical PostHog data must not quietly become the threshold source.
  - **Unblocking step:** Collect the predeclared validation events and coach-session observations from the enrolled validation cohort, then lock thresholds before expansion.

## 7. Pre-code requirements

- Mohit explicitly signs off on this complete scope document.
- `/lock-via-data` selects the candidate-hypothesis eligibility rule, position-pairing rule, sparse-evidence behavior, reflection trigger, and rollout thresholds from versioned evidence.
- The active-focus selection audit separates recurrence, comparative weakness, detector authorization, and content availability; authorization alone cannot choose the player's “main weakness.”
- The stale or mixed focus metadata observed on Mohit's migrated record is repaired or excluded so broad-family scores cannot be presented as exact-skill evidence.
- A versioned offline candidate-pair sample is produced from stored Stockfish analysis without rerunning Stockfish on already analyzed games.
- Each sampled pair is independently reviewed for legal correctness, answer preservation, same underlying decision, genuine surface difference, no answer leakage, and an available downstream teaching action.
- The literal Home, first-position, transfer-position, reflection, result, and later-visit mockups are approved as the frontend contract.
- One canonical backend contract owns diagnostic state, position source, answer redaction, grading, assistance, reflection, result, and next action; the browser only renders and submits IDs/moves.
- The implementation plan identifies the exact existing services to extend and proves that no parallel replay, reflection, curriculum, or mastery authority is being added.
- The feature flag, Mohit-only enrollment, analytics events, kill switch, and rollback behavior are defined before the first player-facing change.
- `/audit-pre-code` passes, including the move-led headline, answer-hidden interaction, behavioral success metric, single-source-of-truth check, and explicit exclusion of deferred features.
- Development starts from the current deployed `working-code` state so the feature does not overwrite newer Home, curriculum, teaching-engine, or Game Review work.
