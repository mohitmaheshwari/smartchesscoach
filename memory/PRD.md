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
│   │   └── opening_teaching_db.py       # Curated teaching content
│   └── server.py                        # Main server
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
