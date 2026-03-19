# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach with Socratic-style, contextual feedback tailored to the user's playstyle.

## What's Been Implemented

### Core Features
- **Play with Coach**: Move-by-move coaching during opening phase (every move gets commentary)
- **Intelligent Position Coaching**: Position-based coaching for middlegame and endgame phases using pawn structure classification, strategic plan database, and tactical detectors
- **Human Coach Layer (NEW - 9/10 Experience)**: Lab page now provides human-coach-like insights including:
  - **"WHY THIS HAPPENED"**: Behavioral tags (impatience, hope_chess, laziness, overconfidence, tunnel_vision, etc.) explaining the psychology behind mistakes
  - **Reflection Questions**: Coach-like questions ("What did this move do to your pawn structure?")
  - **Cross-Game Pattern Detection**: "This is the 3rd time you've made this type of mistake"
  - **Coach Voice Summaries**: Natural language game narratives with actionable takeaways
  - **Enriched Memory Tab**: Real aggregated data showing playing style, worst phase, most common mistakes
- **Unified Opening Detection**: Now detects 22+ openings (up from 9) including Vienna, Scotch, Petrov, King's Indian, Slav, Dutch, Nimzo-Indian, Benoni, Budapest, etc.
- **Opening Detection After Coach's Move**: Opening teaching now triggers immediately after the coach plays the defining move (e.g., French Defense detected after 1.e4 e6, not delayed)
- **"Explain My Position" Feature**: On-demand position analysis via POST /api/coach/play/explain-position - users can ask the coach to explain their current position at any time
- **Dynamic Coaching in Practice Mode**: Opening Practice mode now uses the Behavioral Coaching Layer and Intelligent Position Coach for personalized feedback
- **Deep Opening Context Engine**: Live coach now merges direct opening plans with family-level variation trees so sub-lines like QGD / Slav can inherit richer teaching
- **Expanded Deep Opening Coverage**: Added deeper variation trees for Italian, London, Sicilian, French, Caro-Kann, and King's Indian coaching
- **Game Analysis Lab**: 5-tab structure (Summary, Moments, Ideas, Habits, Memory)
- **Moments Tab**: Interactive training loop (Intro → Thinking → Try Move → Reveal → Reflection → Lesson)
- **Turning Point Detection**: v4 logic, correctly handles user-only move evaluations
- **Blind Spots**: Homepage widget showing recurring mistake patterns
- **Explain Move**: Expandable explanations for turning points and biggest blunders
- **Opening Teaching**: Rich teaching moments for Queen's Gambit, Italian, London, etc.
- **Deviation Guidance**: If a user leaves the main line, the coach now keeps teaching by naming the expected move and explaining the idea instead of going generic/silent
- **Trap Awareness**: QGD family trap warnings (including Elephant Trap context) now surface from the live coaching engine
- **Color-Aware Plans**: Variation teaching now returns side-aware plan suggestions for both White and Black openings
- **Safer Redirect Flow**: Protected route auth/onboarding flow now preserves intended destination and supports demo-mode bypass from onboarding without redirect loops
- **Frontend Runtime Stability**: Disabled cross-origin iframe recording in analytics to prevent the `PerformanceServerTiming` `DataCloneError` on page load
- **Typed Opening Schema Foundation**: Added a structured opening catalog layer for families, variations, rating-aware teaching nodes, traps, deviation rules, and coverage metadata
- **Duplicate SAN Support**: Opening teaching now supports move-index-aware teaching nodes so repeated SAN moves in the same line can still teach correctly
- **Undo Move in Play with Coach**: Added an `Undo Move` control near the board that rewinds the user's last move in normal play and rewinds the student's last move in lesson mode
- **Self-Healing Analysis Queue**: Added stuck-job retry metadata, fallback queue processing, and Lab-page queue/failure status messaging so analysis jobs do not silently sit forever
- **Verified Trap Source-of-Truth**: Added a canonical trap registry for live coaching so traps are only offered and taught when the exact opening line matches a verified legal sequence
- **Opening/Trap Correction Loop**: Users can now submit corrected PGN or SAN directly from Play with Coach and /openings, with current moves auto-filled and live overwrite behavior via DB-backed corrections
- **Admin Opening Feedback Manager**: Added `/admin/openings` with Monaco JSON editor, schema validation, MongoDB save/fetch, version history, and rating-bucket preview panels

## Code Architecture
```
/app
├── backend/
│   ├── routes/lab.py                    # Game analysis, turning points, deep-strategy
│   ├── services/
│   │   ├── move_by_move_coach.py        # NEW: Opening coaching commentary
│   │   ├── coaching_moment_enricher.py  # Thinking lens, questions, lessons
│   │   └── turning_point_explainer.py   # Behavioral explanations
│   ├── coach_engine/
│   │   ├── opening_plans.py             # Opening theory + coaching context builder + expanded variation trees
│   │   ├── opening_schema.py            # NEW: Typed family/variation/node/trap schema + validation
│   │   └── opening_teaching_db.py       # Curated teaching content
│   ├── analysis_worker.py               # Queue processing + stuck-job retry logic
│   ├── routes/admin_openings.py         # NEW: Admin feedback CRUD + validation endpoints
│   ├── services/opening_correction_service.py # NEW: PGN/SAN correction intake + live override helpers
│   ├── services/verified_opening_traps.py # Canonical verified trap registry + validators
│   └── server.py                        # Main server + live move undo endpoint + fallback queue processor
└── frontend/
    └── src/
        ├── App.js                       # Protected route + stored redirect handling
        ├── components/lab/
        │   ├── CriticalMoments.jsx      # Interactive training loop
        │   └── GameSummary.jsx          # Explain Move + View Position
        ├── components/openings/OpeningCorrectionDialog.jsx # NEW: correction submission modal
        └── pages/
            ├── AdminOpenings.jsx        # NEW: Monaco-based opening feedback manager
            ├── AuthCallback.jsx         # Post-auth redirect restoration
            ├── CoachPlay.jsx            # Play with Coach (fixed polling)
            ├── HomePage.jsx             # Blind Spots widget
            ├── Lab.jsx                  # Queue status UX for analysis-in-progress / failed games
            ├── Landing.jsx              # Dev login / auth redirect entry
            ├── Onboarding.jsx           # Demo mode bypass
            └── LabV2.jsx                # 5-tab game review
```

## Prioritized Backlog

### P0 - Critical Issues
All P0 issues resolved in this session.

### Improvement Engine - Phase 1 (Completed March 19, 2026)
- [x] **Opening Fundamentals Checker**: Backend service (`opening_fundamentals_checker.py`) that analyzes player adherence to basic opening principles (castling early, center control, piece development, etc.)
- [x] **Opening Fundamentals API**: `GET /api/analysis/{game_id}/opening-fundamentals` returns score (0-100), violations list, adherences list, and summary
- [x] **Opening Fundamentals UI**: `OpeningFundamentals.jsx` component renders in Lab page Habits tab - shows score, principles followed, principles violated (with expandable thinking prompts), and coach advice

### Improvement Engine - Phase 2 (Completed March 19, 2026)
- [x] **Pre-Move Checklist UI**: `PreMoveChecklist.jsx` component in Play with Coach page - shows contextual prompts based on move number, castling status, and player weaknesses. Items are checkable, expandable/collapsible, dismissible.
- [x] **Thinking Coach Service**: Backend service (`thinking_coach.py`) that teaches players HOW to think:
  - `POST /api/thinking-coach/walkthrough` - Step-by-step thought process for any position
  - `POST /api/thinking-coach/principle-feedback` - Connects mistakes to fundamental principles
  - `POST /api/thinking-coach/behavioral-intervention` - Specific interventions for patterns like hope_chess, tunnel_vision
  - `POST /api/thinking-coach/mindset-prompt` - Position-specific questions based on characteristics
  - `GET /api/thinking-coach/pre-move-checklist` - Contextual checklist items for game state

### Improvement Engine - Phase 3 (Completed March 19, 2026)
- [x] **ThoughtProcessWalkthrough UI**: `ThoughtProcessWalkthrough.jsx` component in Lab page Moments tab - shows step-by-step thinking process in REVEAL stage with "How Should I Have Thought Here?" button. Displays phases (Check Threats, King Safety, Find Targets, etc.), questions, observations, and key takeaways.
- [x] **PrincipleFeedback UI**: `PrincipleFeedback.jsx` component in Lab page Summary tab - connects biggest mistakes to fundamental principles. Shows principle name, explanation, applied context, thinking habit, and what to do instead.
- [x] **BehavioralIntervention UI**: `BehavioralIntervention.jsx` component in Lab page Summary tab - appears when cross-game patterns detected. Shows diagnosed pattern, intervention habit, and practice rule with commitment button.
- [x] **Enhanced PreMoveChecklist**: Added player-specific weakness mapping (hope_chess -> response_check, impulsive_play -> verify_check, tunnel_vision -> whole_board_check, etc.) for personalized prompts.

### P1 - Next
- [ ] Fully verify onboarding/navigation reliability with a fresh un-onboarded test user
- [ ] Add automatic profile creation during game sync if it doesn't exist (currently relies on analysis worker)
- [ ] Add "What You Did Well" section to Summary (celebrate good moves)
- [ ] Expand deep variation trees to the remaining repertoire gaps (Ruy Lopez, Scotch, Vienna, Nimzo, Scandinavian, Philidor, Petrov)
- [ ] Add richer trap setup / trap-avoidance coaching for the newly covered openings in `move_by_move_coach.py`
- [ ] Add multi-plan candidate suggestions directly in live coach messages
- [ ] Start consuming the typed opening schema more directly at runtime instead of only exporting it through catalog helpers
- [ ] Add move-preview + undo/redo design polish for coaching mode
- [ ] Surface queue status consistently across the newer LabV2 flow too, not just the legacy Lab page
- [ ] Audit the remaining trap libraries and migrate them fully onto the verified trap registry
- [ ] Apply correction overrides more broadly across all legacy opening/trap training endpoints, not just the lesson and coach-trap flows
- [ ] Connect live coach runtime directly to the new admin-managed opening feedback collection where appropriate

### P2 - Backlog
- [ ] Lesson flow bug verification (Fried Liver Attack)
- [ ] Integrate MistakeFingerprint + ReinforcementEngine
- [ ] Positive pattern tracking on homepage (strengths alongside blind spots)
- [ ] Shareable "Chess DNA" report
- [ ] Enhanced "Ask Coach" prompts

## Testing Status
- All features tested: iterations 120, 121, 122 (all passed)
- Deep opening teaching fix tested: iteration 123 (30/30 backend tests passed)
- Expanded opening coverage self-tested + unit-tested (`test_play_with_coach_opening_context.py`, `test_expanded_opening_variations.py` → 10/10 passed)
- Frontend routing/demo-mode smoke tested and checked with frontend testing agent (critical flows working; fresh-user onboarding still needs one final verification)
- PostHog `PerformanceServerTiming` DataCloneError fix verified by frontend testing agent (console clean after page load and interaction)
- Typed opening schema/catalog phase verified in iteration 124 (48/48 backend tests passed)
- Undo Move feature verified with live API checks and frontend testing agent after service restart
- Analysis queue recovery verified by backend and frontend testing agents, including Lab-page failed/processing status messaging
- Verified trap registry and exact-line trap selection tested (registry legality + Siberian/QGD selection integration)
- Opening/trap correction loop verified by frontend testing agent, including immediate lesson overwrite from submitted SAN/PGN
- Admin Opening Feedback Manager MVP verified by frontend testing agent (fetch, validate, save, preview, reload persistence all working)
- **Intelligent Position Coaching**: iteration 125-126 (19/19 backend tests passed, 7/7 frontend tests passed)
- **Unified Opening Detection & Features**: iteration 127-128 (30/30 backend tests passed) - verifies 22+ openings, explain-position endpoint, dynamic coaching
- **Human Coach Layer**: iteration 129 (28/28 tests passed, 13/13 backend, 15/15 frontend) - verifies behavioral insights, coach voice summaries, enriched memory tab
- **Opening Fundamentals Bug Fix**: iteration 130 (19/19 tests passed, 13/13 backend, 6/6 frontend) - verifies OpeningFundamentals component renders correctly in Habits tab
- **Thinking Coach/Improvement Engine Phase 2**: iteration 131 (32/32 tests passed, 15/15 backend, 17/17 frontend) - verifies Pre-Move Checklist, all Thinking Coach APIs, regression tests
- **Improvement Engine Phase 3**: iteration 132 (42/42 tests passed, 15/15 backend, 27/27 frontend) - verifies ThoughtProcessWalkthrough in Moments tab, PrincipleFeedback/BehavioralIntervention in Summary tab, enhanced PreMoveChecklist with weakness mapping
- Test files: `/app/backend/tests/test_*.py`, `/app/tests/e2e/*.spec.ts`

## New Files Created
- `/app/backend/services/human_coach_layer.py`: Behavioral tagging system with 11 psychological tags, cross-game pattern detection, coach voice generation
- `/app/backend/tests/test_human_coach_layer_api.py`: API tests for enriched analysis
- `/app/tests/e2e/lab-human-coach-layer.spec.ts`: Frontend tests for behavioral insights UI
- `/app/backend/services/opening_fundamentals_checker.py`: Checks player adherence to basic opening principles (castle early, center control, piece development, etc.)
- `/app/frontend/src/components/lab/OpeningFundamentals.jsx`: UI component showing opening principles score, violations, adherences, and coach advice
- `/app/tests/e2e/opening-fundamentals.spec.ts`: Frontend tests for OpeningFundamentals component
- `/app/backend/tests/test_opening_fundamentals_api.py`: API tests for opening fundamentals endpoint
- `/app/backend/services/thinking_coach.py`: Teaches players HOW to think - thought process walkthroughs, principle-based feedback, behavioral interventions, mindset prompts
- `/app/frontend/src/components/coach/PreMoveChecklist.jsx`: UI component showing contextual pre-move prompts in Play with Coach
- `/app/tests/e2e/pre-move-checklist.spec.ts`: Frontend tests for PreMoveChecklist component
- `/app/backend/tests/test_thinking_coach_api.py`: API tests for all Thinking Coach endpoints
- `/app/frontend/src/components/lab/ThoughtProcessWalkthrough.jsx`: UI component showing step-by-step thinking process in Moments tab
- `/app/frontend/src/components/lab/PrincipleFeedback.jsx`: UI component connecting mistakes to fundamental principles
- `/app/frontend/src/components/lab/BehavioralIntervention.jsx`: UI component for behavioral pattern interventions
- `/app/tests/e2e/improvement-engine.spec.ts`: Frontend tests for ThoughtProcessWalkthrough, PrincipleFeedback, BehavioralIntervention

## Key Technical Notes
- `move_evaluations` only contains USER's moves (not both sides)
- `get_opening_by_moves` returns `OpeningPlan` dataclass, use `getattr()` not `.get()`
- User data in `test_database`, DEV_USER_ID=user_4dad2b14e380
- Coach messages stored in `coach_messages` collection with trigger="opening_teaching"
- Live opening coaching now uses `build_opening_coaching_context(moves)` to merge direct openings with family variation trees before calling `generate_move_commentary(...)`
- `get_variation_teaching(...)` now supports main-line guidance even when the player deviates from the expected move
- `get_variation_teaching(...)` now also returns `plans_for_user` so Black and White get side-aware plan suggestions from the same opening tree
- Frontend protected routes now store `post_auth_redirect` in session storage and allow `demo=true` onboarding bypass for demo exploration
- Frontend analytics config now keeps `recordCrossOriginIframes: false` to avoid non-cloneable `PerformanceServerTiming` objects during `postMessage`
- `get_opening_family_catalog()` and `get_opening_catalog_validation_report()` now provide typed family-level coverage data for the opening library
- Ruy Lopez now includes structured Steinitz Exchange Queenless and Berlin variations, and repeated SAN teaching is handled through `teaching_nodes` with `move_index`
- `/api/coach/play/undo` now rewinds the latest user move in normal play and the latest student move in teaching mode, with stale lesson-state fallback and action-revision protection against late async coach writes
- Analysis queue now tracks `retry_count`, `retrying`, `last_error`, `last_error_at`, `started_at`, and `failed_at`; only stale `processing` jobs older than 10 minutes are retried, up to 3 times
- `server.py` now runs a fallback queue processor loop so pending jobs can still be analyzed even when a separate analysis worker process is absent
- Live opening coaching now prefers the verified trap registry over loose per-opening trap lists, which prevents trap-name hallucinations like mismatched Siberian lines
- `/api/openings/corrections` now accepts corrected PGN or SAN plus current moves/FEN and stores DB-backed live overrides that the /openings lesson flow and coach trap flow can consume immediately
- `/api/admin/openings` now supports list/fetch, `/validate` performs schema validation, and `/save` stores MongoDB-backed opening feedback with version history in `opening_feedback_versions`
- **Intelligent Position Coaching**: `/app/backend/services/intelligent_position_coach.py` orchestrates `PawnStructureClassifier`, `StructurePlanDatabase`, `DetectorRegistry`, and `position_strategy_analyzer` to provide contextual coaching for any position. Triggers after 12+ moves when no opening teaching is active. Frontend component: `PositionCoachingPanel.jsx`
