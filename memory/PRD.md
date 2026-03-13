# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach. The central goal is to move beyond generic analysis and provide Socratic-style, contextual feedback tailored to the user's playstyle.

## What's Been Implemented

### March 13, 2026 - Major Refactoring Session

#### Backend Refactoring (Phase 2 Complete)
**21 endpoints migrated from server.py to coach_play.py:**
- `/api/coach/play/stats` - Session statistics
- `/api/coach/play/active` - Active sessions
- `/api/coach/play/history` - Session history
- `/api/coach/play/identity` - Player cognitive identity
- `/api/coach/play/cpr/history` - CPR score history
- `/api/coach/play/behaviors/{id}` - Session behavior events
- `/api/coach/play/feedback` - Submit feedback on coach message
- `/api/coach/play/state/{id}` - Session state
- `/api/coach/play/move-feedback/{id}` - Last move coaching feedback
- `/api/coach/play/end` - End session (resign/abort)
- `/api/coach/play/analysis` - Post-game analysis
- `/api/coach/play/messages/{id}` - Poll coach messages
- `/api/coach/play/reflect` - Socratic reflection
- `/api/coach/play/chat` - Chat with coach
- `/api/coach/play/evaluate` - Pre-move guardian
- `/api/coach/play/move/confirm` - Confirm risky move
- `/api/coach/play/teaching/start` - Start opening lesson
- `/api/coach/play/teaching/move` - Teaching mode move
- `/api/coach/play/teaching/exit` - Exit teaching mode
- `/api/coach/play/teaching/skip` - Skip teaching offer
- `/api/coach/play/opening-plan` - Opening guidance

**Remaining in server.py (~3 complex endpoints):**
- `/api/coach/play/start` - Start new session (~150 lines)
- `/api/coach/play/move` - Make a move (~250 lines + helper functions)
- Endgame endpoints

#### Frontend Refactoring (Phase 1 Complete)
**New components extracted from CoachPlay.jsx:**
1. `useCoachSession.js` - Custom hook for session state management (~280 lines)
2. `GuardianWarning.jsx` - Pre-move guardian intervention modal
3. `CoachChat.jsx` - Chat interface with the coach
4. `GameSetupPanel.jsx` - Pre-game color selection panel

**Component exports updated in `/components/coach-play/index.js`**

### Previous Session - "95% Vision" Features
- **Break the Habit Challenge** - Practice positions from past mistakes
- **Memory Lane** - Coach references specific past games
- **LearningPath Integration** - Personalized recommendations

## Code Architecture
```
/app
├── backend/
│   ├── routes/
│   │   ├── coach.py           # ~2500 lines - Coach routes (memory, learning path, habits)
│   │   ├── coach_play.py      # ~1500 lines - 21 coach/play endpoints (REFACTORED)
│   │   └── ...
│   └── server.py              # ~9000 lines - Still has /start and /move endpoints
└── frontend/
    └── src/
        ├── hooks/
        │   └── useCoachSession.js    # NEW: Session state management
        ├── components/
        │   ├── coach-play/
        │   │   ├── EvalBar.jsx
        │   │   ├── MoveFeedbackPanel.jsx
        │   │   ├── GuardianWarning.jsx   # NEW
        │   │   ├── CoachChat.jsx         # NEW
        │   │   ├── GameSetupPanel.jsx    # NEW
        │   │   └── index.js
        │   ├── LearningPath.jsx
        │   ├── MemoryLane.jsx
        │   └── HabitChallenge.jsx
        └── pages/
            ├── Dashboard.jsx
            ├── CoachPlay.jsx      # ~2000 lines - Can use new components
            └── LabV2.jsx          # ~1000 lines - Needs refactoring
```

## Prioritized Backlog

### ✅ P0 - Complete
- [x] Break the Habit Challenge
- [x] Memory Lane
- [x] LearningPath Integration

### ✅ P1 - Backend Refactoring (90% Complete)
- [x] Migrated 21 endpoints to coach_play.py
- [ ] Migrate /start and /move endpoints (complex, ~400 lines combined)

### ✅ P2 - Frontend Refactoring (Phase 1 Complete)
- [x] Created useCoachSession custom hook
- [x] Extracted GuardianWarning component
- [x] Extracted CoachChat component
- [x] Extracted GameSetupPanel component
- [ ] Integrate new components into CoachPlay.jsx
- [ ] Break down LabV2.jsx (~1000 lines)

### P3 - Future Features
- [ ] Human Coach Training Dashboard
- [ ] Spaced repetition for opening memorization

## Testing Status
- All migrated backend endpoints tested and working
- New frontend components created and linted
- Integration pending with CoachPlay.jsx

## Database Collections
- coach_sessions: Game sessions with coach
- coach_messages: Coach commentary during games
- coach_feedback: User feedback on coach messages
- coach_memory: User's habits and patterns
- game_analyses: Analyzed games with move evaluations
- player_identity: Cognitive identity profiles

## 3rd Party Integrations
- **Stockfish:** Engine analysis via python-chess
- **OpenAI GPT-4o-mini:** Natural language explanations
- **chess.js:** Frontend move validation
- **chessground:** Frontend chessboard library
