# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach with Socratic-style, contextual feedback tailored to the user's playstyle.

## What's Been Implemented

### March 16, 2026 (Session 2) - Moments Tab Interactive Training Loop

#### P0 COMPLETE: Moments Tab Redesign as Interactive Training Loop
- **Backend**: Created `coaching_moment_enricher.py` service that transforms raw moments into structured coaching objects
  - Thinking Lens: maps 15+ backend tags to guided attention lenses (Opening Decision, Tactical Opportunity, Hanging Piece, etc.)
  - Coach Prompts: contextual introductions based on position characteristics
  - Thinking Questions: 2-3 guiding questions per moment
  - Lesson Takeaway: short learning summary
  - Reflection: prompt + 4 selectable options aligned with thinking patterns
- **Backend**: Integrated enricher into `/api/lab/{gameId}/deep-strategy` endpoint
- **Frontend**: Complete rewrite of `CriticalMoments.jsx` with mandatory guided flow:
  1. INTRO: Coach prompt + Thinking Lens + "Start Thinking" button
  2. THINKING: Lens reminder + 3 questions + "Try move on board" + "Reveal"
  3. REVEAL: Best move + why it works + your move + consequence + board arrows
  4. REFLECTION: What did you overlook? + 4 options
  5. LESSON: Takeaway + "Next Moment"
- Best move is NEVER visible before user interaction
- Progress dots for navigation between moments

### March 16, 2026 (Session 1) - Explain Move + Turning Point Fix + Blind Spots

#### P0 COMPLETE: "Explain Move" Button
- Expandable "Explain this move" button on Turning Point and Biggest Blunder cards
- Turning Point: reveals missed idea, opponent's idea, thinking error, how to spot
- Biggest Blunder: on-demand API call to `/api/explain-mistake`

#### P1 COMPLETE: "View Position" Arrows Fix
- Added `move_uci` and `best_move_uci` to backend responses
- Red arrow (user's move) + green arrow (better move) on chessboard

#### CRITICAL BUG FIX: Turning Point Detection (v4)
- Root cause: `move_evaluations` only contains USER's moves, but `is_user_move()` filtered half out
- Fixed opponent accuracy check to use eval improvement between user moves
- Fixed async explainer call

#### P1 COMPLETE: Blind Spots Migration
- Created migration script, backfilled 7/14 games
- Homepage Blind Spots widget shows real data

### Previous Sessions
- Homepage redesign, Game Analysis Lab 5-tab refactor
- Chess Brain Deterministic Coaching Engine
- Clean UI Mode UX Overhaul, Resume Game Fix, Inline Teaching System

## Code Architecture
```
/app
├── backend/
│   ├── routes/lab.py              # Turning point v4, deep-strategy with coaching enrichment
│   ├── services/
│   │   ├── coaching_moment_enricher.py  # NEW: Thinking lens, prompts, questions, lessons
│   │   ├── chess_brain/                 # Deterministic coaching engine
│   │   └── turning_point_explainer.py   # Rich behavioral explanations
│   ├── scripts/migrate_turning_points.py
│   └── server.py
└── frontend/
    └── src/
        ├── components/lab/
        │   ├── CriticalMoments.jsx      # REWRITTEN: Interactive training loop
        │   └── GameSummary.jsx          # Explain Move + View Position
        └── pages/
            ├── HomePage.jsx             # Blind Spots widget
            └── LabV2.jsx                # 5-tab game review
```

## Prioritized Backlog

### P0 - Complete
- [x] "Explain Move" button (Turning Point + Biggest Blunder)
- [x] "View Position" arrows fix
- [x] Turning Point detection fix (v4)
- [x] Blind Spots migration
- [x] Moments tab interactive training loop

### P1 - Next
- [ ] Fix Onboarding/Navigation flow (unreliable Demo Mode)
- [ ] Add "What You Did Well" section to Summary (celebrate good moves)
- [ ] Consolidate explanation templates with feedback_collector.py

### P2 - Backlog
- [ ] Lesson flow bug verification (Fried Liver Attack)
- [ ] Integrate MistakeFingerprint + ReinforcementEngine
- [ ] Shareable "Chess DNA" report (viral growth)
- [ ] Internal coaching debug dashboard
- [ ] Enhanced "Ask Coach" prompts
- [ ] Positive pattern tracking on homepage (strengths alongside blind spots)

## Testing Status
- Backend: 31/31 tests passed (iteration_120 + iteration_121)
- Frontend: All UI tests passed
- Test files: `/app/backend/tests/test_lab_and_blindspots.py`, `/app/backend/tests/test_moments_coaching.py`

## Key Technical Notes
- `move_evaluations` only contains USER's moves (not both sides)
- Turning point explainer is async - must be `await`ed
- User data in `test_database`, DEV_USER_ID=user_4dad2b14e380
- All coaching logic lives in backend services, frontend only renders
