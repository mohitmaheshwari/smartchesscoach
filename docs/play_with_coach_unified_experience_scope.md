# Play with Coach — Unified Experience Scope

Status: APPROVED BY MOHIT — 2026-09-13
Audit base: `origin/working-code` at `c1e576c0`

## 0. Existing surfaces audit

The current Play with Coach product already contains substantial chess intelligence, but the player experience is the accumulated result of several overlapping product designs. The problem is not a missing feature. The problem is that setup, move handling, teaching, and postgame do not share one clear interaction contract.

This audit covered the current routed frontend and backend at the audit base above, the existing Play with Coach design documents, current production feature flags, and read-only aggregates from the player's recent production sessions. A live browser walkthrough was attempted, but the browser-control helper failed to start twice; no visual observations are claimed beyond the code, supplied screenshots, flags, and production aggregates.

Current entry surfaces:

- `/play-with-coach` is the canonical route, but it can be entered from Home, Activation Hub, Lab practice, Openings, Geometry practice, and direct links with `opening`, `focus`, `geometry_focus`, or `trap` context.
- Lab can also pass practice context through session storage. That creates another implicit entry contract the page must understand.
- Each entry can change the setup or initial coaching state, but the player is not shown one consistent explanation of what kind of session is about to begin.

Current setup surface:

- The player chooses a color.
- The player is shown three overlapping choices under “How close should I stay?”: Stay with me, Test this lesson, and Just play.
- A selected opening adds another choice between “Show me the ideas” and “Let me remember.”
- Opening suggestions are presented as “today’s first conversation.”
- A coach-memory card, curriculum strip, practice-position state, and a pre-game streak popup can also appear before the first move.
- Premium eligibility can be discovered only after the player presses Start, producing an upsell interruption after setup.

Current game shell:

- The board is the main surface, with a coaching sidebar on desktop and a bottom-sheet variation on smaller screens.
- Fixed overlays can independently appear for move prediction, self-rating, premium upsell, the active focus, enforcement confirmation, streak results, and session reflection.
- Board-adjacent elements can independently show a lesson overlay, teaching instruction, position-coaching panel, fundamentals checklist, or coach-turn recovery control.
- The sidebar can independently show the session goal, greeting, mission scoreboard, guardian warning, geometry moment, loading state, punishment puzzle, coach-move teaching, V5 feedback, trap result, fundamentals checklist, active teaching mode, move history, improvement proof, geometry summary, postgame reflection, or postgame lesson.
- A player-facing “Export Session (Debug)” action is still rendered when a game ends.

Current move interaction:

- An opening-guided move can be evaluated and rejected by opening enforcement.
- The same attempted move can then be evaluated by Guardian.
- The coach-flow controller can evaluate it again and place it into a critical hold.
- Depending on the path, the player may have to confirm a warning, satisfy a checkbox, retry a move, or tap the clock to commit it.
- Predictions, self-ratings, escape-square prompts, geometry moments, punishment puzzles, and coach feedback can then compete for the next interaction.
- The code contains explicit bypasses for Play mode because hidden hold or Guardian state previously blocked legal moves.

Current teaching surface:

- Traps and endgames can become a separate teaching mode with their own start, move, and exit lifecycle.
- Opening guidance, geometry training, escape-square quizzes, punishment puzzles, and move-prediction prompts each implement another style of teaching.
- These surfaces contain useful knowledge, but they do not consistently feel like the same coach. Some explain, some quiz, some block, some reveal arrows, and some move the player into a different lesson flow.

Current postgame surface:

- The end of a game can produce a lesson, reflection card, streak result, improvement proof, geometry summary, review link, and debug export.
- The session goal and active focus do not reliably resolve into one simple story: what the coach watched, what changed, and what the player should do next.

Current backend and memory:

- The route module exposes roughly fifty Play with Coach endpoints and touches more than twenty collections.
- Valuable reusable systems already exist: the coach conductor, verified central caption pipeline, active-focus context, player identity and memory, rating-aware feedback, teaching opponent, opening curriculum, trap and endgame knowledge, session persistence, postgame analysis, and improvement tracking.
- There are also overlapping decision owners: opening enforcement, Guardian, pending-move evaluation, coach-flow holds, interactive feedback, V5 feedback, quizzes, and teaching-mode state.

Production evidence confirms that this is player-visible, not merely code complexity. In five recent Coach-mode sessions there were 129 played plies and 105 stored coach messages, including 32 question messages. Forty-one messages were focus-coach messages and twenty-one were impulse warnings. In the same recent sample, Play-mode sessions still received a piece-safety nag, even though Play mode is supposed to be uninterrupted. Session goals were present, but the mission scoreboard recorded no matched moments in the sample.

Decision: **REPLACE the visible Play with Coach experience and its move-interaction controller, while REUSING and EXTENDING the proven chess intelligence, knowledge, memory, engine truth, session storage, and postgame analysis underneath.** This is not a backend rewrite and it is not a new parallel coaching product. Existing overlapping player-facing flows will be consolidated or retired as the unified experience takes ownership.

## 1. What it is

Play with Coach is one continuous, personalized chess session. The player freely plays a real game while one coach remembers the player's active work, watches the position, and chooses the single most useful moment to help. The coach can briefly prevent a repeated thinking error without taking over the game, can connect an opening, tactic, trap, positional idea, or endgame to the board when it is genuinely relevant, and ends by explaining what the game showed and what the player should do next. A separate Play a Game mode uses the same opponent and analysis pipeline but stays silent during the game.

## 2. What the user sees

### Entry and setup

The first screen is a decision, not a configuration form:

```text
Let's play one thoughtful game.

Today I'll watch how well you keep every piece protected.
That is the habit we are working on right now.

[ Play with Coach ]
I will step in only when the moment can teach you something useful.

[ Play a Game ]
No help during the game. We will review it afterward.

White · 15+10                         [ Change ]
Work on something else                [ Choose ]
```

The coach chooses a recommended color and time control. “Change” opens ordinary game settings. “Work on something else” opens no more than three choices that the player's current stage and available knowledge support. An opening or practice deep link replaces the introduction with the promised context but keeps the same two session modes.

Entitlement is resolved before this screen becomes actionable. A player is never allowed to complete setup and then discover a paywall only after pressing Start.

### Play with Coach mode

The board remains dominant. One coaching panel remains in the same place throughout the game. It contains:

```text
TODAY'S WORK
Keep every piece protected

COACH
I'm watching. Your turn.
```

When the player is about to repeat the active mistake, that same panel changes—no modal, quiz, or second card appears:

```text
PAUSE A SECOND
Moving this bishop leaves your knight on e5 undefended.
Before moving a defender, check what it leaves loose.

[ Try another move ]   [ Play it anyway ]
```

The coach states the board fact and gives control back to the player. It does not expose engine scores, demand a checkbox, hide the move behind a clock interaction, or ask the player to guess what the software already knows.

After a meaningful move, the panel can briefly teach:

```text
THAT WAS THE IDEA
Your knight made a threat, and your bishop still protects d5.
You improved a piece without leaving another one loose.
```

Most moves produce no new message. The persistent focus is enough to show that the coach is present. At most one coaching intervention is active at a time.

The player can request help without typing. “Ask coach” opens no more than three contextual actions, such as “What changed?”, “Explain their move”, and “Show the danger.” These actions use the same coaching panel and the same verified chess facts.

### Play a Game mode

The player sees the board, clocks, move history, resign/draw controls, and essential connection or recovery status. There are no live coaching messages, warnings, arrows, classifications, quizzes, nags, or focus enforcement. The game is still analyzed afterward so the coach can learn from it and present a review.

### Openings, traps, tactics, positional ideas, and endgames

Relevant knowledge appears as part of the current position and in the same coaching panel:

```text
THIS POSITION HAS A STORY
Black's bishop on g4 holds your knight against your queen, so the knight cannot safely move.
Before relying on a tied-down piece, check what it can really protect.

[ Save for after the game ]
```

The active game never teleports to a lesson board. The coach can name a known opening idea, trap, tactical opportunity, positional plan, or endgame technique only when the position and verified continuation support it. A longer lesson is offered after the game or entered explicitly before a game.

### Mobile

The board stays visible and playable. The single coaching panel sits below the board or in one stable sheet position. Opening the move list, settings, or “Ask coach” cannot stack another coaching surface over an unresolved intervention.

### Resume and recovery

Returning to an unfinished session restores the board, clocks, mode, focus, and any one visible coaching message. If evaluation or the coach response fails, the legal move is never silently trapped. The player sees a simple recovery state and can continue the game.

### Postgame

The game ends in one coaching summary:

```text
TODAY'S WORK
Piece safety

WHAT I SAW
You checked what became loose on 6 of 8 important moves.

THE TURNING POINT
After 18.Bg5, your knight on e5 no longer had a defender.
Before moving a defender, check which piece it leaves loose.

NEXT
Play one short position from this game, then test the habit in another game.

[ Review the moment ]   [ Play another ]
```

The summary can acknowledge an important issue outside the primary focus, but it does not turn the game into a dashboard of every detected weakness. Reflection, progress credit, saved lesson, and the next training step are composed into this one story.

## 3. In scope (V1)

- Replace the three current player-facing setup modes with exactly two: Play with Coach and Play a Game. “Checkpoint unassisted” becomes an internal evidence state, not a product mode the player must understand.
- Keep ordinary settings available behind one secondary action and choose sensible recommended defaults from the player's context.
- Preserve multiple active focuses in the player profile. Choose one primary focus for a session and, when evidence supports it, one secondary focus. Other issues may be acknowledged once and queued for later; they do not create simultaneous coaching programs inside one game.
- Make the primary focus visible in the introduction, live coaching decisions, postgame story, and next improvement action.
- Create one authoritative coaching-turn controller. Opening guidance, active-focus coaching, Guardian-style protection, tactical opportunities, geometry, and other detectors submit evidence to it; only the controller decides whether the coach speaks and which one message owns the surface.
- Replace the duplicate pre-move path with one evaluation and commitment contract. A legal move is either committed, or one verified warning offers Try another move and Play it anyway. There is no enforcement checkbox, hidden clock-to-commit step, or second evaluator asking the same question.
- Remove forced move prediction, forced self-rating, forced escape-square questions, and other blocking quizzes from the normal live game. Any future research prompt must be explicitly optional, cannot block a move, and must earn its place through measured learning value.
- Guarantee strict Play-mode isolation. The opponent and clocks remain active, but all live instructional surfaces and behavioral nags are disabled.
- Retain the teaching opponent. It may prefer sound, realistic moves that create useful opportunities around the active focus, but Stockfish remains the authority on chess truth and the opponent may not manufacture unsound lessons.
- Retain and route verified knowledge from the central caption system, opening curriculum, trap library, tactical and positional detectors, endgame teaching, player memory, rating band, and mastery evidence through the one coaching controller.
- Keep a relevant opening, trap, tactic, positional idea, or endgame inside the current board context. Offer a saved or longer lesson after the game; do not switch boards during an active V1 game.
- Add the low-typing “Ask coach” action with no more than three position-aware choices and no unrestricted option library.
- Consolidate all player-facing coaching into one stable panel on desktop and mobile. Prevent modal, card, sheet, and overlay stacking.
- Replace the current collection of postgame cards with one summary containing the session focus, observed behavior, one verified turning point, earned progress, and one recommended next action.
- Resolve access and entitlement before setup completion. Remove the surprise post-Start upsell path.
- Remove developer/debug actions from the player experience.
- Preserve session resume, legal-move recovery, engine failure recovery, game termination, postgame analysis, coach memory, and analytics.
- Instrument the complete journey: entry source, setup choice, first move, each proposed and delivered intervention, warning override, help request, interruption duration, abandonment point, game completion, postgame action, later unassisted opportunity, and evidence of transfer.
- Add automated mode-isolation, state-transition, resume, chess-truth, responsive-surface, and end-to-end tests before rollout.

## 4. Explicitly out of scope (V1)

- Building new chess detectors, adding opening families, adding traps, or expanding endgame content. V1 integrates and prioritizes the knowledge already present; quality work on individual detectors continues separately.
- Replacing Stockfish, retraining an opponent model, inventing a new player model, or making an LLM responsible for move truth or intervention decisions.
- Removing multiple active focuses from the overall improvement plan. The restriction is on how many focuses compete inside one session, not on what the coach remembers about the player.
- A general chat product, unlimited topic selection, or a large lesson library exposed inside the game.
- Voice or audio coaching.
- Social play, human multiplayer, tournaments, leaderboards, or community features.
- A new pricing model. The experience must respect the existing entitlement model, while revenue packaging is handled in a separate product scope.
- A full redesign of Home, Game Review, standalone Openings, standalone Endgames, or the broader Training product. Their entry and exit contracts with Play with Coach are included; their internal redesigns are not.
- Migrating every historical Play with Coach record into a new schema. Compatibility or a bounded migration is allowed only where required for resume, analytics, or coach memory.
- Switching the player to a separate lesson board during an active game.
- Choosing fixed cadence, severity, timing, or ranking thresholds from intuition. Those decisions are locked from production distributions before implementation.

## 5. Success criteria

The V1 is successful only if it changes player behavior and makes the coaching relationship clearer. Final numeric gates will be locked against a pre-release production baseline rather than invented in this document.

- A new player can choose between the two modes and make the first move without needing an explanation of product terminology.
- An existing player immediately recognizes what the coach remembers and what this game is working on.
- Setup-to-first-move conversion and completed coached-game rate improve over the locked baseline.
- Abandonment before move two and abandonment immediately following a coaching interruption both decrease from the locked baseline.
- Seven-day return to another coached game or the prescribed next action improves over the locked baseline.
- In a later unassisted opportunity, the player's handling of the primary focus improves over their own pre-session baseline. Puzzle completion alone is not accepted as proof of transfer.
- In Play a Game mode, automated and reviewed sessions contain zero live coaching messages, focus nags, teaching overlays, arrows, forced prompts, or hidden coaching holds.
- A player can never have more than one active intervention or coaching surface, including on mobile.
- Every player move has one understandable state transition. There are zero unrecoverable pending moves, hidden clock commits, or duplicate warnings for one attempted move.
- Every position-specific claim and shown line passes the existing deterministic chess verifier. Unverified claims abstain rather than reaching the player.
- For players with sufficient history, the introduction, live intervention, postgame summary, and next action all use the canonical active-focus context. For players with thin evidence, the coach says what it is observing today and does not invent a personal history.
- A human usability review can correctly identify the session focus, the one most important learning moment, and the next action without inspecting internal scores or analytics.
- Entitlement is known before the player commits to setup; zero sessions encounter an unexpected paywall after Start.
- The new experience can be disabled without corrupting an active game, coach memory, or postgame analysis.

## 6. Open questions

1. **How permissive should “Play it anyway” be after a verified warning?** Recommendation: always preserve player autonomy unless the move is illegal. It is unresolved because repeated overrides affect both learning and coach credibility. A state-transition prototype and a short observed playtest unblock the final rule.
2. **What color and time control should be recommended by default?** It is unresolved because the answer should reflect actual selections, early abandonment, and completion by player segment. A production distribution and the lock-via-data process unblock it.
3. **How should one primary and one possible secondary focus be selected when several focuses are active?** It is unresolved because recency, severity, readiness, opportunity frequency, and the player's explicit request may disagree. An audit of the canonical planner against recent games and later transfer evidence unblocks the ranking rule.
4. **How often should the coach intervene by rating band, history depth, and game phase?** It is unresolved because the current product is demonstrably noisy, but “quiet enough” must be learned from message density, interruption abandonment, helpfulness, and transfer—not chosen by taste. Baseline histograms and the lock-via-data process unblock the cadence policy.
5. **Which three “Ask coach” actions are most useful in each position state?** It is unresolved because a static global menu would become another option library. Scenario testing across opening, tactical, positional, and endgame positions, followed by the caption voice audit, unblocks the contextual mapping.
6. **Which production cohort receives the first rollout?** It is unresolved because existing players carry expectations from the current product while new players provide cleaner onboarding evidence. A rollout plan comparing a small returning-player cohort with a small new-player cohort unblocks the decision.

## 7. Pre-code requirements

- Mohit explicitly signs off this complete scope, including the REPLACE decision, the two-mode contract, one-intervention rule, player autonomy, strict Play-mode silence, and no in-game lesson-board switch.
- Capture a bounded production baseline for setup conversion, selected modes and settings, time to first move, message and question density, interruption duration, warning overrides, abandonment, completion, postgame actions, seven-day return, and later transfer opportunities.
- Apply the lock-via-data process to recommended defaults, focus ranking, intervention cadence, severity thresholds, and rollout gates.
- Complete a single-source-of-truth audit for session mode, active focus, move commitment, coaching-turn ownership, current intervention, and postgame outcome. Mark every existing owner as retain, adapt, or retire before creating a replacement.
- Write one explicit state-transition contract covering direct entry, opening/focus/trap/geometry deep links, setup, Coach mode, Play mode, proposed move, warning, override, retry, coach move, help request, reconnect, resume, evaluation failure, game over, and exit.
- Produce an endpoint and collection compatibility map so the visible replacement reuses trusted services without silently creating a second persistence model.
- Perform the deferred live visual audit on desktop and mobile when browser access is restored, and reconcile any player-visible state that the static audit could not see.
- Make a code-ownership plan for decomposing the large page, sidebar, and route module without moving old behavior into newly named parallel components.
- Define deterministic truth and abstention contracts for every live coaching source. Run the caption voice check on every new player-facing teaching pattern.
- Create test fixtures for a new player, a returning player with several active focuses, a thin-history player, opening and practice deep links, a warning override, Play-mode isolation, reconnection, engine timeout, mobile layout, and postgame transfer.
- Define a default-off feature flag, bounded cohort rollout, rollback behavior for active sessions, and an observability dashboard before enabling production traffic.
- Run the repository's audit-pre-code checklist immediately before the first implementation edit.
