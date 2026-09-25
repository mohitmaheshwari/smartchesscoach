# Personalized Opening Coach — Scope

## 0. Existing surfaces audit

ChessGuru already has several opening experiences and several different records that try to describe what a player knows. This work extends the useful parts; it does not create another opening product.

### Existing player-facing surfaces

- `/openings` is the active repertoire page. It separates White and Black, groups played openings into broad knowledge bands, and recommends lessons from opening-phase performance.
- `/openings/:openingKey` is the active lesson page. It presents a coach-led thread, the player's engine-confirmed opening mistakes when available, traps, one alternative line, and board practice.
- Play with Coach recognizes openings during games, can select an unseen branch, changes guidance by mastery phase, and records opening performance after a coached game.
- Game review already recognizes opening context and can distinguish an engine-confirmed opening mistake from a sound departure from an authored line.
- `/openings-overview` is a secondary older surface. It displays useful repertoire-profile information, but it overlaps with the active `/openings` page and must not remain a competing destination.

### Existing learning records

- `user_opening_profiles` is a derived portrait of what the player actually plays, including common variations, recurring deviations, engine-confirmed recurring mistakes, and trap exposure.
- `user_opening_mastery` holds engine-aware accuracy, teaching phase, traps, recent accuracy, and a placeholder for branches seen.
- `user_opening_progress` holds broad exposure and application counts from imported games and older teaching flows.
- `opening_learning_progress` is read by the active repertoire service but has no production records.
- Engine 2 opening skills record exposure but currently do not provide applied-game proof.

Production evidence on 2026-09-16 confirmed the fragmentation: 6,952 `user_opening_progress` rows, 727 `user_opening_mastery` rows, 78 opening profiles, and zero `opening_learning_progress` rows. The two populated progress systems also disagree about how many openings are mastered.

### Overlap and genuine differentiation

The overlap is the repeated attempt to answer the same question: “What does this player understand about this opening?” The systems use different names, thresholds, evidence, and read paths.

The genuine differentiation worth keeping is:

- The repertoire profile describes what positions and opening families occur in the player's games.
- Mastery describes what the player can do independently.
- The curriculum contains verified chess knowledge and lesson material.
- Game analysis supplies new evidence.

These are separate responsibilities, but they must feed one player-opening truth rather than compete as separate truths.

### Decision

**EXTEND the existing `/openings` and `/openings/:openingKey` surfaces.** Play with Coach and game analysis will feed the same learning state. Useful material from `/openings-overview` will move into `/openings`, after which the duplicate route can be retired. No new player-facing opening page will be created.

Internally, the competing progress ownership will be replaced by one canonical mastery owner. `user_opening_mastery` is the starting owner because it already contains engine-aware game evidence, phases and trap state. `user_opening_profiles` remains a regenerable repertoire portrait rather than a competing mastery source. Existing curriculum and trap knowledge sources remain canonical for chess content; this work creates no duplicate opening theory.

## 1. What it is

The Personalized Opening Coach watches the opening positions a player reaches, understands which side and role the player had, identifies the exact opponent response or decision that is unreliable, and quietly chooses the smallest useful lesson. It distinguishes an opening-theory problem from a calculation, board-awareness, positional-understanding, or time-management problem, so an opening is never blamed merely because the mistake happened early. The player mostly plays chess; ChessGuru learns from moves, retries, hints and later games instead of asking for written explanations.

## 2. What the user sees

### Repertoire

```text
OPENINGS WITH YOUR COACH

As White
Italian Game                         RELIABLE
You handle the opening well. When these games go wrong,
the problem usually comes later.

As Black — what I would teach next
Keep your c-pawn free against the London setup
You have reached this setup three times. The same early decision
left you without the pawn break you needed in two of them.

[Practise this position]

I will watch for this setup in your next games.
```

The headline describes the chess idea, not a move code or database category. Move notation appears only as supporting evidence when it helps.

### Lesson

```text
TODAY'S SMALL FIX
Challenge the London bishop without blocking your counterplay

This comes from a position you reached as Black.
You do not need a full London course—only this response.

[Board showing the decision position]
Your move.
```

If the player chooses a sound alternative, ChessGuru accepts it and explains the different plan. If the move is unreliable, the coach gives one short cue and lets the player try again. It does not ask the player to type an explanation.

### Completion

```text
PRACTISED
You found the plan independently in the changed position.

That is evidence of understanding, not mastery yet.
I will look for it when this setup appears in a real game.

[Continue]
```

If assistance was used, the message says so honestly:

```text
PRACTISED WITH A HINT
The idea is becoming familiar. We will test it again later without help.
```

## 3. In scope (V1)

- Use one canonical player-opening mastery owner for reads and writes across repertoire, lessons, Play with Coach, practice and analyzed games.
- Migrate or project useful legacy evidence without treating an old status label as proof when its underlying evidence is missing.
- Represent the player's perspective: color, whether the player chose the opening or was answering the opponent's system, opening family, opponent-response branch, and decision position.
- Support both plans agreed with Mohit: deepen openings the player chooses and teach responses to openings the opponent chooses.
- Store branch-level evidence for encounters, independent correct decisions, assisted correct decisions, sound alternatives, engine-confirmed mistakes, trap outcomes, last encounter and recent outcomes.
- Keep opening context separate from root cause. When the move is primarily a calculation, board-awareness, positional or time-management error, route it to the corresponding existing coaching focus instead of prescribing generic opening theory.
- Replace the false “mastered this opening line” completion claim with evidence-accurate language.
- Persist server-graded practice evidence, including retries and hints, rather than trusting a browser declaration of mastery.
- Accept verified sound alternatives during practice; do not mark every non-authored move wrong.
- Prevent a coached game from being counted twice when immediate session evidence and later engine analysis describe the same game.
- Repair mastery progression so every promotion path is executable, evidence-backed and capable of becoming stale when later play deteriorates.
- Make the lesson composer choose one next lesson from the player's evidence: a recurring mistake, a common weak response, a common unseen response, a resulting plan, or a stale branch needing review.
- Use existing verified curriculum, trap and analysis sources; add no duplicate opening-theory table.
- Move the useful repertoire portrait—specific recurring mistakes, encountered variations and trap history—into the active `/openings` experience.
- Explain every recommendation in short player language using observable evidence from the player's games.
- Require no typing and no mandatory questionnaire. The normal inputs are chess moves, an optional hint, and a simple continue/later action.
- Record the relationship between a taught branch and later eligible real-game decisions so the coach can report retained improvement.
- Add non-user-visible instrumentation for recommendation shown, lesson started, independent attempt, assisted attempt, real-game re-encounter and verified application.
- Ship behind a default-off rollout flag, validate with internal accounts, then use a bounded production cohort before wider release.

## 4. Explicitly out of scope (V1)

- Building another opening catalogue, dashboard or player-facing route.
- Attempting to cover every theoretical opening line.
- Importing a complete masters database or automatically authoring new lessons.
- Replacing the existing verified opening curriculum or trap libraries.
- Rebuilding the complete calculation, tactical, positional or behavioral coaching systems. V1 connects opening context to those existing systems.
- Asking players to write why they chose a move.
- Adding a chat conversation after every move.
- Treating win rate alone as opening mastery.
- Promoting lesson completion, repeated memorization, or success with a hint directly to mastery.
- Locking new numeric mastery, staleness or recommendation thresholds before measuring the relevant production distributions.
- Changing pricing, subscriptions or revenue packaging.
- Broad visual redesign outside the repertoire and opening-lesson journey.

## 5. Success criteria

- No player-facing flow calls a line or opening mastered because a lesson or one practice session was completed.
- The active repertoire page and lesson page read the same canonical mastery state.
- Every recommendation shown to a player names a concrete idea, response or position and explains why it was selected from that player's evidence.
- A player who handles an opening reliably is not sent back to generic move memorization; the coach advances to an unseen response, a plan, or a different active need.
- A mistake made during an opening is prescribed as opening study only when opening knowledge or understanding is the supported root cause.
- Sound alternative moves are accepted in practice and never described as errors merely because they differ from the authored line.
- Independent success, assisted success and later real-game application remain distinct evidence states.
- A taught branch can be connected to a later real-game encounter, allowing improvement to be measured as changed independent decisions rather than page views or lesson completion.
- The primary rollout metric is improvement in independent decisions on re-encountered taught branches compared with the player's pre-lesson evidence. The release threshold will be locked from the instrumentation baseline, not guessed in this scope.
- There is no required typing and no forced reflection form in the opening journey.
- Adding a new opening lesson remains an edit to the existing canonical curriculum, not to a new personalization-specific knowledge file.

## 6. Open questions

- **Question:** What evidence thresholds promote a branch from learning to reliable and move it from reliable to stale?
  **Why unresolved:** The current systems use contradictory thresholds, one promotion path is unreachable, and mastered state never regresses.
  **Unblocking step:** Measure independent, assisted and real-game outcome distributions from existing mastery and practice evidence, then run the data-lock process before implementation of promotion rules.

- **Question:** What is the canonical transposition-safe branch identifier?
  **Why unresolved:** Current code mixes provider names, curriculum keys, SAN move paths and positions.
  **Unblocking step:** Compare curriculum branch coverage using normalized position keys and choose the identifier that preserves player color, role and transpositions without copying chess content.

- **Question:** How should contradictory legacy mastery labels be migrated?
  **Why unresolved:** Production contains 6,952 broad progress records and 727 engine-aware mastery records with conflicting mastered totals.
  **Unblocking step:** Run a read-only migration preview that classifies rows as evidence-backed, exposure-only, contradictory or unmappable; only evidence-backed facts enter canonical mastery.

- **Question:** How many later games and how much elapsed time constitute a fair retention check for an opening branch?
  **Why unresolved:** Opening branches recur at different frequencies; a calendar-only rule would punish rare openings and a game-only rule could wait indefinitely.
  **Unblocking step:** Measure per-player branch re-encounter intervals and lock a dual game/event-time policy from that distribution.

- **Question:** Which openings form the first rollout cohort?
  **Why unresolved:** V1 needs enough real-game recurrence and verified lesson coverage to measure learning.
  **Unblocking step:** Rank opening families by eligible users, branch recurrence, curriculum coverage and verified practice paths; choose the smallest cohort that produces a measurable follow-up window.

## 7. Pre-code requirements

- Mohit explicitly signs off on this full scope document.
- Run the numeric data-lock for promotion, staleness, recurrence and rollout thresholds; reuse already measured thresholds only where their evidence population matches this use.
- Complete a read-only legacy migration preview with counts for evidence-backed, exposure-only, contradictory and unmappable rows.
- Lock `user_opening_mastery` as the canonical owner and document which legacy writers become adapters, migrations or deletions.
- Lock a transposition-safe branch identity without introducing another opening knowledge source.
- Capture a test corpus covering: a player-chosen opening, an opponent-chosen system, a sound alternative, an assisted solve, a recurring theory mistake, a non-opening calculation error during the opening, and a later real-game re-encounter.
- Ensure the literal UI contract in Section 2 is accepted before schema work begins.
- Define default-off rollout and rollback behavior before any production data migration.
- Run the pre-code audit after the data locks and migration preview pass.

