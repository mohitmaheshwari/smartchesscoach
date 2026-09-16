# Play with Coach V2 — Architecture and Implementation Spec

**Status:** APPROVED v1 — Mohit sign-off 2026-09-16.
**Version:** v1 (2026-09-16).
**Scope:** largest of the PWC migrations; estimated 6–8 implementation weeks for one senior full-stack engineer with part-time chess QA, followed by two clean weeks before legacy deletion.
**Companion product contract:** docs/play_with_coach_v2_scope.md

---

## 1. The problem

The product has accumulated capable subsystems without one authoritative game runtime. The active page has 4,075 lines, 77 local states, 27 effects, and 42 fetch calls; the main sidebar has 1,996 lines; the route module has 10,984 lines and 65 endpoints. Unified V1 improves presentation but remains a branch inside that machinery.
Four correctness problems follow:

1. A player can receive behavior from more than one coaching generation. Unified rendering suppresses many legacy props, yet the board still derives a V5 move badge independently.
2. Move truth, move commitment, opponent response, and teaching are coordinated by the browser across multiple calls. Network retries and stale state can duplicate or strand a turn.
3. Personalization does not drive selection. The current policy selects from move severity and cadence, then decorates the result with focusMatch.
4. The system cannot compare all valid lessons. Opening, trap, tactic, active-focus, opponent-plan, positional, endgame, positive-transfer, and behavioral signals do not share one candidate contract.

The delivery problem is separate but equally important: Unified V1 passed isolated staging, never passed remote smoke or human UAT, and remains default-off for ordinary users. Source presence is not proof that the product reached a player.

The competitive baseline is also higher than “show a caption.” Chess.com publicly offers automatic feedback, progressive hints, arrows, settings, undo, save/resume, coach personas, and voice. V2 wins only if it proves a deeper learner loop and stays simpler during a game.
## 2. The shape — six outcomes

### Authoritative turn flow

    Board attempt
         |
         v
    server validates session revision + legal move
         |
         v
    one engine/search evidence packet
         |
         v
    verified candidate adapters
      opening | trap | tactic | focus | positional | endgame
      threat  | positive transfer | time (only with valid clocks)
         |
         v
    Coaching Conductor: choose zero or one action
         |
         +--> COMMIT_SILENT       commit and continue
         +--> COMMIT_ADVISORY     commit; show one non-blocking lesson
         +--> HOLD_WARNING        do not commit; Try another / Play anyway
         +--> PREPARE_NEXT_TURN   after opponent move, set one thinking cue
         +--> ANSWER_HELP         requested progressive help; never unsolicited
         +--> ABSTAIN             continue chess; make no unsupported claim

### Frontend state machine

    SETUP -> STARTING -> PLAYER_TURN -> SUBMITTING
                                  SUBMITTING -> WARNING -> PLAYER_TURN
                                  SUBMITTING -> OPPONENT_TURN
                                  OPPONENT_TURN -> PLAYER_TURN
                                  any active state -> RECOVERING -> restored state
                                  any active state -> GAME_OVER -> POSTGAME

HELP is a panel substate, not a second game state. A session has one current server revision, one pending attempt, and one visible coaching event.
### Coaching-candidate envelope

Every source adapts existing facts into the same shape:

| Field | Meaning |
|---|---|
| candidate_id / turn_id | Idempotent identity |
| source | Existing detector or knowledge owner |
| timing | before_move, after_move, after_opponent, requested_help, postgame |
| category / concept_key | Canonical learning identity |
| claim | Exact board fact that may be said |
| evidence | FEN, move, engine/geometry proof, source version |
| transferable_instruction | Reusable thinking habit |
| visual | Verified squares and arrows |
| urgency | Immediate irreversible danger versus teachable note |
| focus_relevance | Primary, supporting, historical, or none |
| novelty / assistance | Whether already taught and how much help was used |
| abstention_reason | Why a candidate may not speak |

No adapter writes player-facing text directly to the UI. It either uses the central caption pipeline or supplies structured facts to a verified shared renderer.
### Personalization behavior

- New player: no claimed history; rating-safe fundamentals and observed opportunities only.
- Thin history: one provisional focus explained as “what I am watching today,” never “your recurring weakness.”
- Returning player: canonical primary focus, prior examples, prior assistance, last taught instruction, and later transfer evidence.
- Explicit lesson/opening entry: the requested topic becomes session intent if legal and stage-appropriate; it does not overwrite the long-term plan.
- Multiple active focuses: one primary owns the session, one quality-authorized supporting focus can win only when the position strongly demands it.
### Progressive help

Help depth is persisted per opportunity:

| Level | Player receives | Mastery treatment |
|---|---|---|
| 0 | No help | Independent evidence |
| 1 | Goal or threat | Light assistance |
| 2 | Relevant pieces/squares | Assisted |
| 3 | Candidate moves or calculation frame | Strongly assisted |
| 4 | Best move and verified continuation | Demonstration, not mastery |
### Opponent policy

The existing engine remains the legality and strength authority. A teaching preference can re-rank only sound candidates inside a data-locked evaluation tolerance. If no relevant sound move exists, the opponent plays normal chess. The tolerance is not chosen in this spec; it requires a candidate distribution and engine-quality review.
## 3. Schema / files touched

### Frontend ownership

| Path | Change |
|---|---|
| frontend/src/pages/CoachPlay.jsx | Legacy owner during rollout; no new V2 behavior. Retire after cutover. |
| frontend/src/pages/CoachPlayV2.jsx | New thin route-level composition; no chess or coaching decisions. |
| frontend/src/hooks/useCoachPlayV2.js | One reducer/state machine and command client; sole browser owner of view state. |
| frontend/src/components/coach/v2/CoachSetup.jsx | Two modes, focus explanation, recommended defaults, entitlement. |
| frontend/src/components/coach/v2/CoachWorkspace.jsx | Board plus one stable panel and responsive layout. |
| frontend/src/components/coach/v2/CoachPanel.jsx | Renders the server outcome; no source-specific branching. |
| frontend/src/components/coach/v2/HelpLadder.jsx | Up to three contextual actions and progressive reveal. |
| frontend/src/components/coach/v2/PostgameStory.jsx | Focus, evidence, turning point, one next action. |
| frontend/src/components/coach/CoachPlayBoard.jsx | Extract reusable board shell; remove PWC policy and legacy prompts from the V2 path. |
### Backend ownership

| Path | Change |
|---|---|
| backend/routes/coach_play.py | Keep legacy endpoints temporarily; extract V2 commands so routes become validation adapters. |
| backend/routes/coach_play_v2.py | Versioned command/query contract during migration; remove or alias after cutover. |
| backend/coach_play/coach_game_session.py | Remains the canonical session model/persistence owner; extend its existing action_revision and move compare-and-swap contract. |
| backend/coach_play/turn_runtime.py | Orchestrates one V2 turn through the canonical session owner; contains no second session model or direct duplicate state store. |
| backend/coach_play/coaching_conductor.py | Sole selector of zero or one candidate; no prose generation. |
| backend/coach_play/candidate_adapters.py | Adapts existing detectors and knowledge; contains no duplicate detection rules. |
| backend/coach_play/help_policy.py | Contextual action selection and help-level progression. |
| backend/coach_play/postgame_story.py | One evidence-backed closeout and next action. |
| backend/services/unified_pwc_coaching.py | Input to migration; retire when V2 owns all traffic. |
| backend/services/pwc_experience.py | Extend to version v2 and cohort allocation; keep default-off. |
| backend/services/caption_pipeline.py | Remains the central verified renderer; no parallel caption system. |
### Session additions

Extend the existing CoachGameSession and coach_sessions document; do not create a second session collection:

- experience_version: legacy, unified_v1, or pwc_v2; immutable after start.
- action_revision: retain the existing monotonic revision and require it on every V2 command; do not add a rival session_revision.
- runtime_state: current authoritative state and whose turn it is.
- pending_attempt: attempt_id, FEN revision, UCI, selected decision, expiry; at most one.
- coaching_context: retain the existing immutable canonical focus snapshot.
- coaching_decisions: retain and normalize the existing append-only selection/delivery/outcome trail; do not add coaching_events.
- coaching_help_events: retain and add opportunity_id plus help_level so assistance is derived rather than copied into another field.
- clock_evidence_valid: explicit truth gate for time coaching.
- conductor_version and caption_version: persist on each coaching decision so the reason for speaking is reproducible.

Before moving either existing event array to a dedicated collection, measure p95/p99 session document growth and write rate. Embedded storage remains canonical until evidence requires a migration.
### API contract

- GET /api/coach/play/experience returns selected version, eligibility, entitlement, defaults, and coaching context.
- POST /api/coach/play/v2/start creates a version-pinned session and returns revision 1.
- POST /api/coach/play/v2/turn accepts session_id, expected_revision, attempt_id, UCI, and measured client timing metadata; server validates timing before using it.
- POST /api/coach/play/v2/resolve accepts the warning decision: retry or play_anyway.
- POST /api/coach/play/v2/help accepts opportunity_id and one offered action key.
- GET /api/coach/play/v2/session/{id} is the recovery source of truth.
- POST /api/coach/play/v2/end handles resign/draw/abort idempotently and returns one postgame story.

Every mutation returns the new revision and the complete public view needed to render. A repeated attempt_id returns the original result and never commits twice.
## 4. New facts / data the system needs

- Valid client and server move timestamps, clock snapshots, and transport latency so time coaching cannot repeat the old zero-second falsehood.
- Opportunity identity shared across live coaching, help, postgame rehearsal, and later unassisted games.
- Assistance depth, warning override, and retry outcome per opportunity.
- Candidate shadow log containing all eligible candidates, selected candidate, suppression reason, policy version, and latency; no unverified prose.
- Focus-source quality identity for any supporting focus. Unauthorized runners-up remain hidden.
- Opening position identity based on canonical opening/transposition data, plus player readiness from the personalized opening coach already implemented.
- Positive-transfer evidence: the same canonical concept was relevant, the player acted correctly, and help level was zero.
- Opponent candidate evaluations sufficient to prove a teaching preference stayed inside the locked soundness tolerance.
- Entry source, entitlement outcome, setup exposure, first move, session completion, postgame action, return, and transfer opportunity.

No new user survey is required. One optional “Helpful / Not helpful” tap may annotate an event; it cannot be required to continue.
## 5. Gating — preventing the “personalized label on generic coaching” trap

1. **Truth gate:** legal position, correct side, engine/geometry proof, and verified caption. Failure means abstain.
2. **Focus gate:** a candidate claims personal relevance only from the canonical context snapshot and authorized source quality.
3. **Opportunity gate:** praise or mastery requires a real opportunity, not merely absence of a mistake.
4. **Assistance gate:** help level above zero cannot count as independent transfer.
5. **One-owner gate:** only the conductor can produce a visible live coaching decision.
6. **Mode gate:** Play mode rejects all live candidate generation server-side and renders no coaching-capable component client-side.
7. **Cadence gate:** inherited two-per-six advisory and three-warning limits remain ceilings until shadow evidence authorizes a change.
8. **Novelty gate:** the same concept and instruction are suppressed unless the board fact, behavior, or teaching level changed.
9. **Opponent gate:** pedagogical preference cannot cross the data-locked soundness tolerance.
10. **Recovery gate:** coaching failure never blocks a legal move; stale revisions force a session refresh, not a guessed local repair.
11. **Version gate:** active sessions never switch runtime, focus snapshot, conductor, or caption semantics mid-game.
12. **Voice gate:** every new teaching shape passes the repository's check-voice rules for 600–1500 players.
## 6. Test strategy

### Phase 1 — stateless chess and policy probes

- Golden FEN fixtures for openings/transpositions, traps and hard negatives, tactics, threats, positional plans, endgames, focus matches, positive transfer, and abstention.
- For every fixture: legal moves, exact board fact, acceptable candidate set, forbidden claims, help levels, and visuals.
- Three conductor candidates run on identical inputs; disagreement report is reviewed before one is locked.
- Mutation/property tests: wrong side, stale FEN, illegal move, absent engine depth, missing history, bad arrow, contradictory candidates, and duplicated attempt_id.
### Phase 2 — boundary and integration suite

- Full state-transition table, including warning retry, play anyway, opponent reply, reconnect at every state, timeouts, resign, checkmate, draw, and entitlement denial.
- Strict Play-mode tests at service, API, persistence, resume, DOM, and screenshot levels.
- One engine evidence packet per attempted move; no browser-supplied trusted evaluation.
- Existing session and postgame compatibility tests for legacy and Unified V1 during rollout.
- New player, thin history, returning player, multiple focuses, opening deep-link, and requested lesson fixtures.
### Phase 3 — deterministic journey snapshots

- Desktop and mobile snapshots for setup, quiet turn, advisory, warning, each help level, recovery, game over, and postgame.
- Copy snapshots assert one message, named piece/square when applicable, reusable instruction, and no unexplained jargon.
- Accessibility: keyboard play, focus order, screen-reader live regions, contrast, reduced motion, touch target, and board/panel reachability.
### Phase 4 — real-system QA

- Local isolated staging with real Stockfish, Mongo, frontend, and throttled/failing-network scenarios.
- Remote staging smoke on the actual deploy topology; the prior local-only HOLD cannot authorize production.
- Human chess audit by Mohit plus at least one target-band player in each of 600–900, 900–1200, and 1200–1500.
- Blind comparison: legacy, Unified V1, V2, and Chess.com on matched scenarios. Reviewers grade the ten scope dimensions without knowing the system; release requires at least 8.5/10 overall, no core dimension below 8/10, and a clear ChessGuru advantage in remembered context, individual relevance, explanation, continuity, and improvement proof.
### Phase 5 — learning validation

- Shadow first: log candidates and decisions without showing them.
- A/B by separately randomized new and returning cohorts.
- Primary outcome: later unassisted success on a verified opportunity for the session focus.
- Guardrails: false claim, Play leakage, stuck turn, duplicate commit, P95 latency, move-two abandonment, post-intervention abandonment, and support complaint.
- Numeric release gates are locked only after baseline and shadow distributions exist.

## 7. Risk + rollback

| Risk | Mitigation |
|---|---|
| New runtime diverges from stored sessions | Version-pin at start; recovery reads server state; compatibility fixtures. |
| Candidate conductor feels smart but chooses wrong lesson | Shadow all candidates; human disagreement audit; fail closed. |
| Engine latency ruins play | One search packet, bounded timeout, silent legal continuation, latency dashboard. |
| Focus overfitting makes coach ignore a decisive issue | Immediate irreversible danger outranks focus; non-focus lesson is named honestly. |
| Too much silence feels empty | Prepared-turn cues, requested help, and earned praise are candidates; do not lower truth gates. |
| Too much coaching recreates spam | One-owner plus cadence and novelty gates. |
| Event history grows session documents | Measure first; bounded event schema or dedicated indexed collection. |
| Rollout corrupts active games | Immutable experience_version; rollback affects new sessions only. |
| Legacy survives forever | Time-box fallback; deletion is an explicit release phase and metric. |

**Feature flag:** PWC_V2_ENABLED=false by default, with PWC_V2_ROLES and per-user allocation.
**Rollback:** set PWC_V2_ENABLED=false for new sessions; continue serving existing V2 sessions through their pinned runtime until completion or expiry. Never downgrade an active session in place. Revert the release commits only after confirming no resumable V2 sessions require their code.

## 8. What this spec does NOT cover

- Improving an individual detector's precision or adding missing opening/trap/endgame content; each follows its detector/content quality process.
- Redesigning Game Review or Training beyond the handoff payload.
- Voice, avatar, or free-form chat.
- Subscription price or packaging changes beyond early entitlement and instrumentation.
- Native mobile applications; responsive web is required.
- A new engine or LLM-based chess decision maker.
- Bulk migration of historical legacy sessions.

## 9. Implementation order

1. **Phase 0 — verify reality and instrument legacy (3–4 days).** Confirm production flags and Mohit's actual experience; complete existing Unified V1 UAT; add missing baseline events. Expected commit: “Measure the real PWC journey before replacement.”
2. **Phase 1 — contracts and shadow conductor (5–7 days).** Add versioned models, candidate envelope, adapters over existing sources, all-candidate shadow logging, golden fixtures, and conductor bake-off report. No player-facing V2. Expected commit: “Shadow one evidence contract across PWC coaching sources.”
3. **Sign-off gate A.** Mohit approves conductor choice, storage choice, help taxonomy, and numeric rollout gates from measured evidence. No Phase 2 without this decision.
4. **Phase 2 — authoritative backend runtime (5–7 days).** Implement revisioned commands, idempotent pending attempts, one search packet, warning resolution, recovery, help depth, and postgame event chain. Expected commit: “Make the server authoritative for coached turns.”
5. **Phase 3 — thin V2 experience (5–7 days).** Build the new route, state reducer, two-mode setup, board workspace, one panel, responsive behavior, accessibility, and strict Play isolation. Do not add V2 behavior to CoachPlay.jsx. Expected commit: “Replace PWC orchestration with one visible state machine.”
6. **Phase 4 — personalized teaching loop (5–7 days).** Wire canonical focus, personalized openings, requested topics, positive transfer, contextual help, opponent preparation, and honest postgame mastery. Expected commit: “Close the focus-to-transfer coaching loop.”
7. **Phase 5 — resilience and QA (4–6 days).** Run unit/integration/E2E, network failure, load, accessibility, security/privacy, desktop/mobile, and human chess audits. Fix every false claim and stuck state. Expected commit: “Gate PWC V2 with real-system and chess QA.”
8. **Ship default-off.** PWC_V2_ENABLED remains false; Mohit and Parth run side-by-side V1/V2 for one week with explicit user flags.
9. **Sign-off gate B.** Review blind comparison, truth sample, latency, abandonment, help usage, and qualitative UAT. Do not promote on code-test results alone.
10. **10% rollout for one week.** Randomize new and returning players separately; pause automatically on truth, leakage, duplicate-turn, stuck-state, or latency guardrail breach.
11. **100% rollout.** Promote only after the locked behavioral and safety gates pass. Keep active sessions version-pinned.
12. **Delete legacy after two clean weeks at 100%.** Remove CoachPlay.jsx legacy orchestration, CoachPlaySidebar legacy path, Unified V1 selector/panel, obsolete endpoints/states, and rollout flags. Preserve only compatibility readers required for historical records. Expected commit: “Delete legacy PWC after verified V2 cutover.”

## 10. Decisions / Open questions for Mohit

1. **Replacement boundary:** approve a new thin V2 runtime and eventual deletion of both legacy and Unified V1, while retaining verified services and data. **Recommendation: approve.**
2. **First comparison cohort:** returning players best demonstrate the differentiator, but new-player onboarding must be tested separately. **Recommendation: run both as separately randomized small cohorts; do not blend their metrics.**
3. **Retry semantics:** allow Try another before a warned move is committed; offer committed-move rehearsal after the game, not arbitrary live takebacks. **Recommendation: approve for V2, then test immediate rehearsal as a follow-up.**
4. **Conductor formula:** no winner is selected in this draft. **Required decision after the shadow bake-off: lexicographic, weighted expected-learning-value, or phase-specific rules.**
5. **Help actions:** approve the four-level help ladder and contextual maximum of three visible choices. Exact menus remain gated on fixture/usability testing.
6. **Scope restraint:** voice, avatars, unrestricted chat, new pricing, and new detector/content creation stay outside this migration. **Recommendation: approve so the teaching loop ships before cosmetic parity work.**
7. **Delivery assumption:** confirm whether planning should use one senior full-stack engineer plus part-time chess QA (6–8 implementation weeks) or a two-engineer split. The architecture should not be compressed by keeping the 4,075-line controller.
