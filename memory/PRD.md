# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach with Socratic-style, contextual feedback tailored to the user's playstyle.

## What's Been Implemented

### March 16, 2026 - "Explain Move" Feature + Turning Point Fix + Blind Spots Migration

#### P0 COMPLETE: "Explain Move" Button
- Added expandable "Explain this move" button to Turning Point and Biggest Blunder cards in GameSummary.jsx
- Turning Point: reveals missed idea, opponent's idea, thinking error, how to spot checklist
- Biggest Blunder: on-demand API call to `/api/explain-mistake` for rich explanation
- Smooth AnimatePresence animations for expand/collapse

#### P1 COMPLETE: Fixed "View Position" Arrows
- Added `move_uci` and `best_move_uci` to backend `biggest_blunder` response
- Arrows now correctly show red (user's move) and green (better move) on the chessboard

#### CRITICAL BUG FIX: Turning Point Detection (v4)
- **Root cause**: `move_evaluations` only contains the USER's moves, but `is_user_move()` was filtering out half of them using odd/even logic meant for both sides
- **Fix**: Removed the incorrect `is_user_move` filter. All evaluations ARE user moves.
- **Fix**: Changed opponent accuracy check to detect when eval improved significantly between user moves (indicating opponent gave back advantage)
- **Fix**: Fixed `asyncio.get_event_loop().run_until_complete()` -> `await` for the async explainer
- Now correctly finds turning points for all games with significant mistakes

#### P1 COMPLETE: Blind Spots Migration
- Created `/app/backend/scripts/migrate_turning_points.py` to backfill turning point data
- Successfully computed and stored turning points for 7 of 14 existing games
- `/api/blind-spots` now returns rich data: Tactical Blindness (3 games), Positional Mistake (2), etc.

### Previous Sessions (Summary)
- **Mar 16**: Homepage redesign (4-section layout), Game Analysis Lab 5-tab refactor
- **Mar 15**: Chess Brain Deterministic Coaching Engine (18 detectors, 7 teaching modes)
- **Mar 14**: Clean UI Mode UX Overhaul, Resume Game Fix, Inline Teaching System
- Earlier: Backend refactoring, Break the Habit, Memory Lane, Opening Training Lab

## Code Architecture
```
/app
├── backend/
│   ├── routes/
│   │   ├── lab.py             # Turning point v4, explain-mistake, deep-strategy
│   │   ├── coach.py           # Coach routes
│   │   └── coach_play.py      # Play with coach (21 endpoints)
│   ├── services/
│   │   ├── chess_brain/        # Deterministic coaching engine
│   │   └── turning_point_explainer.py  # Rich behavioral explanations
│   ├── scripts/
│   │   └── migrate_turning_points.py   # Backfill turning points
│   └── server.py              # Main server (~12K lines)
└── frontend/
    └── src/
        ├── components/
        │   ├── lab/
        │   │   └── GameSummary.jsx    # Explain Move + View Position
        │   └── coach-play/            # Clean UI components
        └── pages/
            ├── HomePage.jsx           # Blind Spots widget
            └── LabV2.jsx              # 5-tab game review
```

## Prioritized Backlog

### P0 - Complete
- [x] "Explain Move" button (Turning Point + Biggest Blunder)
- [x] "View Position" arrows fix (UCI moves)
- [x] Turning Point detection fix (v4)
- [x] Blind Spots migration + homepage widget

### P1 - Next
- [ ] Fix Onboarding/Navigation flow (unreliable Demo Mode)
- [ ] Consolidate explanation templates with feedback_collector.py
- [ ] Integrate MistakeFingerprint + ReinforcementEngine into analysis pipeline

### P2 - Backlog
- [ ] Lesson flow bug verification (Fried Liver Attack)
- [ ] Shareable "Chess DNA" report (viral growth)
- [ ] Internal coaching debug dashboard
- [ ] Enhanced "Ask Coach" prompts
- [ ] Break down LabV2.jsx into smaller components
- [ ] Migrate remaining backend endpoints (/start, /move)

## Testing Status
- Backend: 18/18 tests passed (iteration_120)
- Frontend: All UI tests passed
- Test files: `/app/backend/tests/test_lab_and_blindspots.py`

## Key Technical Notes
- `move_evaluations` only contains USER's moves (not both sides)
- Turning point explainer is async - must be `await`ed, not `run_until_complete`
- User data is in `test_database`, DEV_USER_ID=user_4dad2b14e380
- Real user email: bhutramohit@gmail.com
