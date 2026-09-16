# Play with Coach V2 — Product Scope

**Status:** APPROVED BY MOHIT — 2026-09-16
**Date:** 2026-09-16
**Product promise:** A quiet, observant chess coach who understands this player, intervenes only when useful, explains the position truthfully, and checks whether the lesson transfers to later games.

## 0. Existing surfaces audit

### What already exists

The repository does not lack Play with Coach features. It has too many partially overlapping ones:

- The routed frontend is frontend/src/pages/CoachPlay.jsx: 4,075 lines, 77 local state variables, 27 effects, and 42 fetch calls. It owns setup, game state, move commitment, teaching lessons, warnings, opening guidance, quizzes, feedback, postgame, and two experience variants.
- frontend/src/components/coach/CoachPlaySidebar.jsx is a second 1,996-line interaction surface. It can render V5 captions, Guardian interventions, geometry moments, behavioral coaching, traps, opening teaching, escape-square quizzes, chat, timelines, checklists, and postgame content.
- frontend/src/components/coach/UnifiedCoachPlaySetup.jsx and UnifiedCoachPanel.jsx implement the newer two-mode setup and one-panel presentation, but they are mounted inside the same legacy controller. Most old behavior is suppressed conditionally rather than removed.
- backend/routes/coach_play.py is a 10,984-line route module with 65 endpoints. Several generations of move evaluation, coaching, lesson, Guardian, feedback, help, and end-game behavior coexist.
- backend/services/unified_pwc_coaching.py supplies one verified caption path, a quiet/advisory/critical decision, two help actions, and one postgame story. It is a useful bridge, not yet a complete human-coaching system.
- Existing reusable truth and knowledge include the central caption pipeline, Stockfish evaluation, tactical and positional detectors, opening curriculum, trap library, endgame teaching, personalized opening state, active focus, coach memory, rating bands, mastery evidence, session persistence, and postgame analysis.
- The approved play_with_coach_unified_experience_scope.md already chose two modes, one visible intervention, strict Play-mode silence, contextual help, and one postgame story. Its isolated staging QA passed, but production deployment remained on HOLD because remote smoke testing and human UAT were incomplete.
- Deployment configuration still defaults PWC_UNIFIED_EXPERIENCE_V1_ENABLED to false and limits eligible roles to admin and super_admin. Ordinary users therefore continue to receive legacy unless production configuration or a per-user flag says otherwise.

### What the current product already does well

- It can play legal chess at adjustable strength and persist sessions.
- It can verify some live teaching text through the central caption pipeline.
- It preserves player autonomy with Try another move and Play it anyway on a verified critical warning.
- It can carry an active-focus label from setup to live play and postgame.
- Play mode can be made silent when the unified path is actually active.
- It has a safe default-off rollout mechanism and meaningful automated coverage.

### Where it still fails the product promise

- **The focus is mostly decorative.** The current unified selector first chooses whether to speak from move quality and cadence, then calculates focusMatch. The player's focus does not choose which candidate lesson wins the turn.
- **It is mistake-reactive, not coach-observant.** Excellent and good moves are silent, so the coach cannot recognize an improved habit, explain an opponent's plan, prepare the player for an important choice, or reinforce correct thinking.
- **It does not arbitrate the full chess knowledge base.** Opening, trap, tactic, positional, endgame, threat, active-focus, and behavioral sources do not submit comparable candidates to one conductor.
- **The help model is too narrow.** Only “Explain their move” and “Remind me what to check” exist. There is no progressive help that preserves the player's calculation.
- **Changing focus is opening-biased.** The setup offers opening suggestions rather than the best stage-appropriate choices across tactics, calculation, positional play, time use, and endgames.
- **Legacy behavior still leaks.** Unified games can still receive a legacy V5 move-classification badge on the board, and the shared board can show old recovery prompts.
- **The controller is structurally fragile.** The newer experience is a conditional layer inside the old state machine. A small change can revive an old overlay, duplicate a request, or leave a move pending.
- **The evidence of learning is weak.** The postgame can count verified messages, but the system does not yet prove that a player later handled the same kind of decision without help.
- **Most players may not see the new experience at all.** The production contract defaults to legacy and the QA gate never authorized a live rollout.

### Competitive benchmark

Chess.com currently provides a polished baseline: strength and color selection, automatic move feedback, critical tips, progressive hints, suggestion and threat arrows, evaluation and move-feedback settings, undo, save/resume, coach personas, and voice. ChessGuru should not claim to be better merely by matching these controls.

Benchmark sources checked on 2026-09-16: [Chess.com Play Coach](https://support.chess.com/en/articles/10877257-how-do-i-play-against-the-coach), [Coach settings](https://support.chess.com/en/articles/10812255-how-do-i-manage-the-coach), and [Game Review](https://support.chess.com/en/articles/8584089-how-does-game-review-work).

The defensible advantage is a deeper coaching loop:

| Need | Chess.com public experience | ChessGuru V2 must prove |
|---|---|---|
| Know me | Skill-level adaptation | Persistent evidence from my games, active plans, prior help, and later transfer |
| Choose a lesson | Current-position feedback | One lesson selected from all verified candidates because it matters to me now |
| Help me think | Hint, then best move | A staged hint ladder that protects calculation before revealing a move |
| Notice growth | Move classifications and review | Specific recognition that I used a previously taught habit independently |
| Close the loop | Saved game and review | Focus → live opportunity → explanation → rehearsal → later unassisted proof |
| Feel human | Coach persona and voice | Restraint, continuity, memory, earned praise, and honest uncertainty |

### Overlap, differentiation, and decision

The proposed experience overlaps almost completely with the visible purpose of both legacy PWC and Unified V1. A parallel feature would create a third coach and make the architecture worse.

**Decision: REPLACE.** Play with Coach V2 replaces the visible experience and the move-interaction runtime. It reuses and adapts verified chess services and stored player evidence. During rollout, legacy and Unified V1 exist only as controlled fallbacks; after two clean weeks at 100%, they are deleted rather than maintained.

## 1. What it is

Play with Coach V2 is a complete coached chess game, not an analysis board with messages attached. The coach begins with one appropriate purpose, watches the player's decisions, lets most moves pass quietly, and steps in before or after a move only when doing so has high teaching value. It can draw from openings, traps, tactics, calculation, positional play, time management, king safety, piece safety, and endgames, but presents only the one lesson that matters now. It remembers what happened, gives the player low-effort ways to ask for help, and uses later unassisted play—not puzzle completion alone—to decide whether the lesson was learned.

## 2. What the user sees

### Returning player: setup

    PLAY WITH COACH

    Today I want to watch one habit:
    Before moving a defender, check what it leaves loose.

    I chose this because it appeared in 3 recent games.

    [ Play with Coach ]
    I will step in only at important moments.

    [ Play a Game ]
    No help during the game. We will review it afterward.

    White · 15+10                         [ Change ]
    Want different work today?            [ Show 3 choices ]

The player answers no questionnaire. “Show 3 choices” offers only stage-appropriate, evidence-backed options: for example “Handle the London setup,” “Keep pieces protected,” and “Calculate forcing replies.” It is not a library.

### New or thin-history player: setup

    LET'S PLAY AND LEARN

    I do not know your habits yet. I will watch how you make decisions
    and step in only when I can explain something clearly.

    [ Play with Coach ]       [ Play a Game ]

The coach does not invent a weakness. It starts with safe fundamentals appropriate to the rating and learns from actual choices.

### Normal live state

    TODAY'S CHECK
    Before moving a piece, ask: what can take it there?

    Your move. I am watching; I will not comment on every move.

    [ Ask coach ▾ ]

The board is dominant. One stable panel contains the focus, the current coaching state, and help. There are no floating quizzes, overlapping modals, duplicate move labels, debug controls, or surprise lesson boards.

### Before a clearly harmful move

    PAUSE A SECOND
    Moving the bishop leaves your knight on e5 with no defender.

    Before moving a defender, check which piece it leaves loose.

    [ Try another move ]      [ Play it anyway ]
    [ Show me what attacks it ]

The warning names the piece and square, explains why the move fails, and preserves autonomy. If truth cannot be verified, the move is committed without a claim.

### After an important learning moment

    THAT WAS THE HABIT
    You moved the bishop and kept the knight on e5 protected.
    That is the same check we have been practising.

Praise is earned from position evidence and prior coaching history. It is not generic encouragement after every good move.

### Progressive “Ask coach” help

The three visible actions depend on the position. Typical first-level choices are:

- “What changed after their move?”
- “What should I compare?”
- “Remind me of today's check.”

If the player asks for more help, the ladder reveals only the next useful layer:

1. Name the goal or opponent threat.
2. Highlight relevant pieces and squares.
3. Offer two sensible candidate moves or a calculation question.
4. Reveal the best move and a verified line only on explicit request.

Every layer records assistance, so later progress is not falsely called independent mastery.

### Openings and traps in the game

    THIS IS YOUR LONDON PROBLEM
    Black has built the pawn triangle you struggled against last week.
    Challenge the centre before it becomes fixed; do not chase the bishop.

    [ Show the plan ]         [ Save for after the game ]

The coach recognizes the actual position and transpositions, not only the opening name. A trap is mentioned only when its conditions and punishment are verified. Unknown or unsound “traps” abstain.

### Positional and endgame coaching

    TWO PLANS ARE POSSIBLE
    Your rook can use the open file now; the pawn break can wait.
    Improve the least active piece before changing the pawn structure.

The coach explains plans through concrete pieces, squares, threats, and tradeoffs. It does not use an evaluation number as an explanation.

### Play a Game mode

The player sees the board, clocks, move list, connection state, and normal game controls. No coach message, arrow, classification, hint, focus nag, or hidden hold can appear. Analysis starts only after the game.

### Postgame

    TODAY'S WORK
    Keep pieces protected

    WHAT I SAW
    You used the check independently twice. I helped once.

    TURNING POINT
    After 18.Bg5, the knight on e5 lost its defender.
    Replay the position and choose a move that keeps both pieces safe.

    NEXT
    One short rehearsal now, then test the habit in another game.

    [ Rehearse the moment ]   [ Play another ]

The summary distinguishes independent success from assisted success, includes one verified turning point, and recommends one next action. It never turns into a dump of every detector that fired.

## 3. In scope (V2)

- Make V2 a genuinely separate runtime behind the existing route entry, not another conditional branch inside CoachPlay.jsx.
- Keep exactly two modes: Play with Coach and Play a Game.
- Support new, thin-history, and returning-player introductions without requiring typed answers.
- Read one canonical primary focus and at most one quality-authorized supporting focus; never rank weaknesses independently inside PWC.
- Let opening, trap, tactic, calculation, positional, endgame, time, opponent-threat, active-focus, and positive-transfer sources submit verified candidates to one conductor.
- Select at most one visible coaching action per turn using urgency, truth, focus relevance, novelty, assistance history, game phase, rating, and interruption cost.
- Support pre-move warnings, after-move teaching, opponent-move explanation, proactive position preparation, and earned positive reinforcement.
- Add a contextual, progressive help ladder with no typing and no more than three choices at one time.
- Track assisted versus independent decisions so progress claims remain honest.
- Use a sound, rating-appropriate opponent that may prefer realistic positions relevant to the focus but never plays an unsound move merely to stage a lesson.
- Use one board, one panel, one current intervention, one move-commitment authority, and one postgame story on desktop and mobile.
- Enforce strict Play-mode silence in backend decisions, API responses, frontend rendering, and stored player-facing messages.
- Preserve resume, reconnect, time controls, color choice, resign, game termination, postgame analysis, coach memory, entitlement, and accessibility.
- Record an append-only coaching event trail with idempotent turn identifiers so retries cannot duplicate moves or messages.
- Reuse one engine result for commitment, coaching, opponent selection where valid, and postgame evidence; never ask the browser to echo trusted evaluation facts.
- Fail open for play and fail closed for claims: a legal move continues if coaching fails, while unsupported text remains silent.
- Instrument setup, interventions, help depth, assistance, overrides, latency, abandonments, completion, postgame action, later opportunities, and transfer.
- Delete legacy and Unified V1 player-facing runtimes after the controlled migration is proven clean.

## 4. Explicitly out of scope (V2)

- Voice, celebrity coaches, avatars, animation-heavy personalities, and social features. Chess.com already has scale here; they do not prove learning.
- A free-text general chess chatbot during play. Help remains contextual and bounded.
- New detector invention or bulk opening/trap/endgame authoring as part of the runtime rewrite. Bad or thin knowledge sources are improved through their own quality gates.
- Letting an LLM decide chess truth, select interventions, or invent player history. An LLM may later polish already verified facts without changing meaning.
- Exposing an opening or lesson catalogue inside the game.
- Arbitrary takebacks that erase evidence. “Try another” resolves an uncommitted warning; rehearsal happens after the game.
- Blitz or bullet as the initial coached default. Existing production evidence supports 15+10; faster modes need separate evidence and UX.
- A new subscription or pricing model. V2 must expose entitlement before Start and emit packaging evidence, but pricing is a separate decision.
- Claiming mastery from a solved assisted puzzle, a single game, or a clean game with no relevant opportunity.
- Simultaneously redesigning Game Review, Training, Home, Progress, Openings, and Endgames. Their handoff contracts are in scope; their internal redesign is not.

## 5. Success criteria

- **8.5/10 quality gate:** V2 is not called complete unless a blind human review averages at least 8.5/10 across chess truth, personalized relevance, teaching clarity, intervention timing/restraint, help quality, human-coach continuity, reliability, mobile usability, postgame usefulness, and evidence of later transfer. No core dimension—truth, personalization, teaching, or reliability—may score below 8/10.
- The matched comparison must show a clear advantage over Chess.com Play Coach in the areas ChessGuru is choosing to win: remembered context, relevance to the individual, explanation of why, continuity into the next action, and proof of improvement. Matching Chess.com controls alone is not success.
- In a later unassisted opportunity, players handle the primary focus better than their own pre-V2 baseline. Assisted moves are excluded from independent mastery.
- Returning players can identify what the coach remembers, why today's focus was chosen, and what improved without reading an analytics dashboard.
- New players reach the first move without a questionnaire and never receive a fabricated “you usually…” claim.
- Coach-mode completion, seven-day return, and completion of the prescribed next action improve over the measured legacy baseline.
- Abandonment before move two and immediately after an intervention decline relative to the legacy baseline.
- Human chess review finds zero false board claims in the release sample; automated verification finds zero illegal lines, wrong-side claims, or unverified player-facing continuations.
- Play mode has zero live coaching leakage across API, UI, persistence, resume, and postgame boundaries.
- Each attempted move has one idempotent state transition, with zero duplicate commits, duplicate opponent moves, unrecoverable pending states, or hidden holds.
- At most one coaching surface owns a turn on desktop and mobile.
- P95 turn latency and engine-timeout rates meet thresholds locked from a production shadow run; no threshold is invented in this scope.
- A coached session leaves one auditable chain: chosen focus → opportunities → assistance → turning point → next action → later transfer evidence.
- The player-facing runtime becomes materially smaller and has one named owner for session state, current intervention, and move commitment.

## 6. Open questions

1. **Question:** Which conductor ranking wins: lexicographic safety/focus priority, a weighted expected-learning-value score, or phase-specific rules?
   **Why unresolved:** Current production data measures noise, not which suppressed candidate would have taught best.
   **Unblocking step:** Run all three in shadow on the same stratified session corpus, review disagreements with a strong human player, and lock the winner with data.

2. **Question:** Which returning and new-player cohorts enter the first live A/B?
   **Why unresolved:** Returning players demonstrate memory value; new players give the cleanest onboarding signal.
   **Unblocking step:** Recommend two small cohorts measured separately; final sizes depend on eligible traffic and power analysis.

3. **Question:** Which three help actions should appear for each position state?
   **Why unresolved:** A static menu would become another library, while the existing two actions are insufficient.
   **Unblocking step:** Test contextual menus on opening, tactical, positional, defensive, and endgame fixtures; keep only actions players understand without explanation.

4. **Question:** Should a player be able to rehearse a committed mistake immediately or only after the game?
   **Why unresolved:** Immediate rehearsal can teach faster but interrupts the game and changes the opponent context.
   **Unblocking step:** Prototype both with event history preserved; observe comprehension, flow disruption, and completion before locking.

5. **Question:** What latency, completion, transfer, and abandonment thresholds authorize each rollout step?
   **Why unresolved:** The repository has a noise baseline but not V2 shadow and cohort distributions.
   **Unblocking step:** Instrument legacy and shadow V2 first, publish distributions, then use lock-via-data for the gates.

## 7. Pre-code requirements

- Mohit explicitly signed off this REPLACE decision, the product contract, and the out-of-scope boundaries on 2026-09-16.
- Confirm whether production currently serves legacy or Unified V1 to Mohit's account and record the exact deployment flags; do not infer deployment from source code.
- Complete a human UAT of the existing Unified V1 on desktop and mobile so useful behavior is retained and regressions are named.
- Produce a single-source-of-truth ownership map for session state, move commitment, engine evaluation, coaching decision, active focus, assistance, and postgame evidence; mark every old owner retain, adapt, or retire.
- Run the conductor candidates in read-only shadow against a stratified corpus covering rating bands, game phases, focuses, quiet moves, tactics, openings, traps, endgames, and hard negatives.
- Lock conductor choice, rollout cohorts, latency guardrails, and release thresholds from the resulting distributions. Preserve the already documented 15+10, White, two-per-six advisory, and three-warning values only as inherited V1 controls until V2 evidence replaces them.
- Write the state-transition and API idempotency contract before editing the frontend runtime.
- Establish golden chess fixtures and human-reviewed expected coaching outcomes for every candidate source and help level.
- Run the repository audit-pre-code checklist immediately before implementation.
- Ship no production code until the scope and the companion architecture spec are signed off.
