# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach. The central goal is to move beyond generic analysis and provide Socratic-style, contextual feedback tailored to the user's playstyle.

### Core Requirements
- **AI Teaching Coach:** An AI that plays instructive moves and provides real-time, explanatory feedback
- **Human-like Interaction:** Memory of past games, Socratic questioning, and real-time conversational guidance in simple Indian-English
- **Active Teaching Framework:** Proactively suggest and guide learning during gameplay and in post-game analysis
- **Deep Post-Game Analysis:** Analyze performance accurately, check for recurring habits using memory, and provide personalized feedback

## Code Architecture
```
/app
├── backend/
│   ├── services/
│   │   ├── realtime_coaching_feedback.py  # Real-time move feedback with Socratic mode
│   │   ├── human_coach_integration.py     # Unified human-like coaching (Indian-English)
│   │   ├── coach_personality.py           # Defines player levels and coaching language
│   │   ├── coach_memory.py                # Memory of past games and patterns
│   │   ├── socratic_engine.py             # Socratic questioning system
│   │   ├── player_understanding_service.py # Multi-dimensional chess understanding
│   │   ├── chess_understanding.py         # Chess skills profiling
│   │   ├── opening_library_service.py     # Opening training lab service
│   │   └── trap_library.py                # Chess trap definitions (27+ traps)
│   ├── routes/
│   │   ├── auth.py
│   │   ├── lab.py
│   │   ├── coach.py                       # Coach routes: learning-path, memory-lane, habit-challenge
│   │   ├── coach_play.py                  # Coach play routes (helper functions migrated)
│   │   └── openings.py                    # Opening Training Lab routes
│   └── server.py
└── frontend/
    └── src/
        ├── pages/
        │   ├── LabV2.jsx                  # Game review page
        │   ├── Dashboard.jsx              # User dashboard with LearningPath, MemoryLane, HabitChallenge
        │   ├── CoachPlay.jsx              # Live coach play with feedback
        │   └── OpeningLesson.jsx          # Opening lessons with practice mode
        └── components/
            ├── LearningPath.jsx           # Personalized learning recommendations
            ├── MemoryLane.jsx             # Coach's memories of past games
            ├── HabitChallenge.jsx         # Break the Habit training mode (NEW)
            ├── coach-play/
            │   ├── EvalBar.jsx
            │   └── MoveFeedbackPanel.jsx  # Socratic mode UI with input
            ├── openings/
            │   ├── InteractivePractice.jsx # Visual move indicators (✓/✗)
            │   └── TrapPractice.jsx        # Interactive trap practice
            └── lab/
                ├── TrapAnalysis.jsx        # Trap detection in games
                └── HabitsToImprove.jsx
```

## What's Been Implemented

### March 13, 2026 - "95% Vision" Achievement

#### ✅ NEW: Break the Habit Challenge Mode
- **HabitChallenge.jsx Component**: Interactive training from user's past mistakes
- **Backend `/api/coach/habit-challenge` endpoint**: Extracts positions from user's blunders/mistakes
- **Backend `/api/coach/habit-challenge/check` endpoint**: Validates user's answer
- **Features**:
  - Presents 5 positions from user's actual games where they made mistakes
  - Shows original wrong move with centipawn loss
  - User must find the correct move on an interactive board
  - Hint system available
  - Score tracking with personalized feedback
  - Indian-English messages throughout

#### ✅ Memory Lane Feature
- **MemoryLane.jsx Component**: Coach references specific past games
- **Backend `/api/coach/memory-lane` endpoint**: Returns memorable moments from games
- **Features**:
  - "Mohit, yesterday you played Ba4 and it was costly. Watch out for similar positions!"
  - "Dekho Mohit, you've had this pattern multiple times. Today, let's break the habit!"
  - Links to specific games for review

#### ✅ LearningPath Integration
- **LearningPath.jsx Component** now visible in Dashboard
- Shows "Today's Focus" with personalized recommendations
- "Your Coach Says" section with Indian-English messages
- "You're Improving" section showing progress areas

### Previous Sessions
- Multi-Dimensional Player Understanding
- Personalized Coaching Language
- Opening Training Lab with 20+ openings
- Comprehensive trap library (27 traps)
- Socratic Mode UI in MoveFeedbackPanel
- Visual Move Indicators (✓/✗) in practice mode
- Interactive Trap Practice

## Key API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/coach/habit-challenge` | GET | Get positions from user's past mistakes for practice |
| `/api/coach/habit-challenge/check` | POST | Check if user's move is correct |
| `/api/coach/memory-lane` | GET | Coach's memories of past games |
| `/api/coach/learning-path` | GET | Personalized learning recommendations |
| `/api/coach/play/feedback/{session_id}` | GET | Real-time move feedback |
| `/api/coach/socratic/start` | POST | Start Socratic dialogue |
| `/api/coach/socratic/respond` | POST | User responds to Socratic question |
| `/api/openings/{key}/practice/start` | POST | Start interactive practice |
| `/api/openings/practice/move` | POST | Make practice move |

## Database Schema
- **player_profiles:** user_id, estimated_elo, top_weaknesses, strengths
- **games:** Game PGNs and metadata
- **games_analysis:** Detailed analysis including move_evaluations, blunders
- **coach_sessions:** Coach play sessions and move history
- **coach_memory:** Habits, weaknesses, improving areas, recurring patterns

## 3rd Party Integrations
- **Stockfish:** Engine analysis via python-chess
- **OpenAI GPT-4o-mini:** Natural language explanations
- **chess.js:** Frontend move validation
- **chessground:** Frontend chessboard library

## Vision Progress: 95% Complete

### ✅ Completed (The "Human-like Coach" Vision)
1. **Personalized Learning Path** - Dashboard shows tailored recommendations
2. **Memory Lane** - Coach references specific past games by name and date
3. **Break the Habit Challenge** - Practice positions from user's actual mistakes
4. **Socratic Mode UI** - Input field for user answers to Socratic questions
5. **Visual Move Indicators** - Chess.com style feedback during practice
6. **Interactive Trap Practice** - Learn and practice 27+ chess traps
7. **Indian-English Conversational Style** - Throughout all coaching messages

### Remaining 5%
- [ ] **P1 Backend Refactoring** - Migrate ~2500 lines from server.py to coach_play.py
- [ ] **P2 Frontend Refactoring** - Break down CoachPlay.jsx and LabV2.jsx
- [ ] **Deep Memory in Real-time Play** - Reference past games during live coach play

## Prioritized Backlog

### P1 - Backend Refactoring
- [ ] Continue migrating routes from server.py to coach_play.py

### P2 - Frontend Refactoring
- [ ] Break down `CoachPlay.jsx` (~2000 lines) into smaller components
- [ ] Extract custom hooks: useCoachSession, useChessboard
- [ ] Break down `LabV2.jsx` into smaller components

### P3 - Future Features
- [ ] Human Coach Training Dashboard for reviewing AI explanations
- [ ] Spaced repetition for opening memorization
- [ ] Multi-game pattern recognition in real-time feedback

## Test Credentials
- Backend runs in `DEV_MODE` with default test user
- No login required for testing

## Known Technical Debt
- `server.py` still has ~9000+ lines - coach/play routes need migration
- `CoachPlay.jsx` has ~2000 lines, needs component extraction
- `LabV2.jsx` remains a large component (~1000 lines)

## Testing Status
- Break the Habit API tested and working
- HabitChallenge component rendering correctly with interactive board
- Memory Lane API tested and working
- LearningPath API returns proper data
- Frontend components rendering correctly
