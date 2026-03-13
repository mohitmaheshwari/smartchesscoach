# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach. The central goal is to move beyond generic analysis and provide Socratic-style, contextual feedback tailored to the user's playstyle.

### Core Requirements
- **AI Teaching Coach:** An AI that plays instructive moves and provides real-time, explanatory feedback
- **Human-like Interaction:** Memory of past games, Socratic questioning, and real-time conversational guidance in simple Indian-English
- **Active Teaching Framework:** Proactively suggest and guide learning during gameplay and in post-game analysis
- **Deep Post-Game Analysis:** Analyze performance accurately, check for recurring habits using memory, and provide personalized feedback

## Backend Refactoring Progress

### Migrated to coach_play.py (✅ Complete)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/coach/play/stats` | GET | Session statistics |
| `/api/coach/play/active` | GET | Active sessions |
| `/api/coach/play/history` | GET | Session history |
| `/api/coach/play/identity` | GET | Player cognitive identity |
| `/api/coach/play/cpr/history` | GET | CPR score history |
| `/api/coach/play/behaviors/{session_id}` | GET | Session behavior events |
| `/api/coach/play/feedback` | POST | Submit feedback on coach message |
| `/api/coach/play/state/{session_id}` | GET | Session state |
| `/api/coach/play/move-feedback/{session_id}` | GET | Last move coaching feedback |
| `/api/coach/play/end` | POST | End session (resign/abort) |
| `/api/coach/play/analysis` | POST | Post-game analysis |

### Still in server.py (Remaining ~1500 lines)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/coach/play/start` | POST | Start new session |
| `/api/coach/play/move` | POST | Make a move |
| `/api/coach/play/messages/{session_id}` | GET | Get coach messages |
| `/api/coach/play/reflect` | POST | Reflect on game |
| `/api/coach/play/chat` | POST | Chat with coach |
| `/api/coach/play/evaluate` | POST | Evaluate position |
| `/api/coach/play/move/confirm` | POST | Confirm move |
| `/api/coach/play/endgame/start` | POST | Start endgame lesson |
| `/api/coach/play/endgame/move` | POST | Endgame lesson move |
| `/api/coach/play/opening-plan` | GET | Opening plan |
| `/api/coach/play/teaching/start` | POST | Start teaching mode |
| `/api/coach/play/teaching/move` | POST | Teaching mode move |
| `/api/coach/play/teaching/exit` | POST | Exit teaching mode |
| `/api/coach/play/teaching/skip` | POST | Skip teaching |

## Features Implemented

### March 13, 2026 - "95% Vision" + Backend Refactoring

#### ✅ Break the Habit Challenge Mode
- **HabitChallenge.jsx Component**: Interactive training from user's past mistakes
- Backend `/api/coach/habit-challenge` and `/api/coach/habit-challenge/check` endpoints
- Presents 5 positions from user's actual games with mistakes
- Interactive chessboard with move validation
- Score tracking with Indian-English feedback

#### ✅ Memory Lane Feature
- **MemoryLane.jsx Component**: Coach references specific past games
- Backend `/api/coach/memory-lane` endpoint
- Indian-English conversational messages

#### ✅ LearningPath Integration
- **LearningPath.jsx Component** in Dashboard
- Personalized recommendations based on weaknesses

#### ✅ Backend Refactoring Phase 1
- Migrated 11 endpoints from server.py to coach_play.py
- ~1000 lines of code modularized
- All endpoints tested and working

### Previous Sessions
- Multi-Dimensional Player Understanding
- Personalized Coaching Language
- Opening Training Lab with 20+ openings
- Comprehensive trap library (27 traps)
- Socratic Mode UI in MoveFeedbackPanel
- Visual Move Indicators (✓/✗) in practice mode
- Interactive Trap Practice

## Code Architecture
```
/app
├── backend/
│   ├── routes/
│   │   ├── coach.py           # ~2500 lines - Coach routes
│   │   ├── coach_play.py      # ~900 lines - Coach play routes (GROWING)
│   │   └── ...
│   └── server.py              # ~10000 lines - Still has remaining coach/play routes
└── frontend/
    └── src/
        ├── components/
        │   ├── LearningPath.jsx
        │   ├── MemoryLane.jsx
        │   ├── HabitChallenge.jsx
        │   └── ...
        └── pages/
            ├── Dashboard.jsx
            ├── CoachPlay.jsx   # ~2000 lines - Needs refactoring
            └── LabV2.jsx       # ~1000 lines - Needs refactoring
```

## Prioritized Backlog

### ✅ P0 - Complete
- [x] Break the Habit Challenge
- [x] Memory Lane
- [x] LearningPath Integration
- [x] Backend refactoring Phase 1 (11 endpoints)

### P1 - Backend Refactoring Phase 2 (IN PROGRESS)
- [ ] Migrate remaining ~13 coach/play endpoints from server.py
- [ ] Focus on: /start, /move, /messages - the core gameplay endpoints

### P2 - Frontend Refactoring
- [ ] Break down `CoachPlay.jsx` (~2000 lines)
- [ ] Break down `LabV2.jsx` (~1000 lines)
- [ ] Extract custom hooks: useCoachSession, useChessboard

### P3 - Deep Memory Integration
- [ ] Reference past games during live coach play
- [ ] Pattern recognition across multiple games

## Test Credentials
- Backend runs in `DEV_MODE` with default test user
- No login required for testing

## Testing Status
- All migrated endpoints tested and working
- Break the Habit API tested
- Memory Lane API tested
- LearningPath API tested
