# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach with Socratic-style, contextual feedback tailored to the user's playstyle.

## What's Been Implemented

### Core Features
- **Play with Coach**: Move-by-move coaching during opening phase (every move gets commentary)
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
│   └── server.py                        # Main server + live move undo endpoint + fallback queue processor
└── frontend/
    └── src/
        ├── App.js                       # Protected route + stored redirect handling
        ├── components/lab/
        │   ├── CriticalMoments.jsx      # Interactive training loop
        │   └── GameSummary.jsx          # Explain Move + View Position
        └── pages/
            ├── AuthCallback.jsx         # Post-auth redirect restoration
            ├── CoachPlay.jsx            # Play with Coach (fixed polling)
            ├── HomePage.jsx             # Blind Spots widget
            ├── Lab.jsx                  # Queue status UX for analysis-in-progress / failed games
            ├── Landing.jsx              # Dev login / auth redirect entry
            ├── Onboarding.jsx           # Demo mode bypass
            └── LabV2.jsx                # 5-tab game review
```

## Prioritized Backlog

### P1 - Next
- [ ] Fully verify onboarding/navigation reliability with a fresh un-onboarded test user
- [ ] Add "What You Did Well" section to Summary (celebrate good moves)
- [ ] Expand deep variation trees to the remaining repertoire gaps (Ruy Lopez, Scotch, Vienna, Nimzo, Scandinavian, Philidor, Petrov)
- [ ] Add richer trap setup / trap-avoidance coaching for the newly covered openings in `move_by_move_coach.py`
- [ ] Add multi-plan candidate suggestions directly in live coach messages
- [ ] Start consuming the typed opening schema more directly at runtime instead of only exporting it through catalog helpers
- [ ] Add move-preview + undo/redo design polish for coaching mode
- [ ] Surface queue status consistently across the newer LabV2 flow too, not just the legacy Lab page

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
- Test files: `/app/backend/tests/test_*.py`

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
