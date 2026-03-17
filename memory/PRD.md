# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach with Socratic-style, contextual feedback tailored to the user's playstyle.

## What's Been Implemented

### Core Features
- **Play with Coach**: Move-by-move coaching during opening phase (every move gets commentary)
- **Deep Opening Context Engine**: Live coach now merges direct opening plans with family-level variation trees so sub-lines like QGD / Slav can inherit richer teaching
- **Game Analysis Lab**: 5-tab structure (Summary, Moments, Ideas, Habits, Memory)
- **Moments Tab**: Interactive training loop (Intro → Thinking → Try Move → Reveal → Reflection → Lesson)
- **Turning Point Detection**: v4 logic, correctly handles user-only move evaluations
- **Blind Spots**: Homepage widget showing recurring mistake patterns
- **Explain Move**: Expandable explanations for turning points and biggest blunders
- **Opening Teaching**: Rich teaching moments for Queen's Gambit, Italian, London, etc.
- **Deviation Guidance**: If a user leaves the main line, the coach now keeps teaching by naming the expected move and explaining the idea instead of going generic/silent
- **Trap Awareness**: QGD family trap warnings (including Elephant Trap context) now surface from the live coaching engine

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
│   │   ├── opening_plans.py             # Opening theory + coaching context builder + family variation inheritance
│   │   └── opening_teaching_db.py       # Curated teaching content
│   └── server.py                        # Main server
└── frontend/
    └── src/
        ├── components/lab/
        │   ├── CriticalMoments.jsx      # Interactive training loop
        │   └── GameSummary.jsx          # Explain Move + View Position
        └── pages/
            ├── CoachPlay.jsx            # Play with Coach (fixed polling)
            ├── HomePage.jsx             # Blind Spots widget
            └── LabV2.jsx                # 5-tab game review
```

## Prioritized Backlog

### P1 - Next
- [ ] Fix Onboarding/Navigation flow (unreliable Demo Mode)
- [ ] Add "What You Did Well" section to Summary (celebrate good moves)
- [ ] Expand deep variation trees beyond Queen's Gambit family (Italian, Sicilian, French, Caro-Kann, etc.)
- [ ] Add richer trap setup / trap-avoidance coaching for more openings in `move_by_move_coach.py`
- [ ] Add stronger color-aware next-plan suggestions for black-side opening coaching

### P2 - Backlog
- [ ] Lesson flow bug verification (Fried Liver Attack)
- [ ] Integrate MistakeFingerprint + ReinforcementEngine
- [ ] Positive pattern tracking on homepage (strengths alongside blind spots)
- [ ] Shareable "Chess DNA" report
- [ ] Enhanced "Ask Coach" prompts

## Testing Status
- All features tested: iterations 120, 121, 122 (all passed)
- Deep opening teaching fix tested: iteration 123 (30/30 backend tests passed)
- Test files: `/app/backend/tests/test_*.py`

## Key Technical Notes
- `move_evaluations` only contains USER's moves (not both sides)
- `get_opening_by_moves` returns `OpeningPlan` dataclass, use `getattr()` not `.get()`
- User data in `test_database`, DEV_USER_ID=user_4dad2b14e380
- Coach messages stored in `coach_messages` collection with trigger="opening_teaching"
- Live opening coaching now uses `build_opening_coaching_context(moves)` to merge direct openings with family variation trees before calling `generate_move_commentary(...)`
- `get_variation_teaching(...)` now supports main-line guidance even when the player deviates from the expected move
