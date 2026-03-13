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
│   │   ├── coach.py                       # Coach routes including learning-path
│   │   ├── coach_play.py                  # Coach play routes modularization (IN PROGRESS)
│   │   └── openings.py                    # Opening Training Lab routes
│   └── server.py
└── frontend/
    └── src/
        ├── pages/
        │   ├── LabV2.jsx                  # Game review page
        │   ├── Dashboard.jsx              # User dashboard with LearningPath
        │   ├── CoachPlay.jsx              # Live coach play with feedback
        │   └── OpeningLesson.jsx          # Opening lessons with practice mode
        └── components/
            ├── LearningPath.jsx           # Personalized learning recommendations
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

### December 2025 / March 2026 - "90% Vision" Human-Like Coaching

#### ✅ COMPLETED:
1. **LearningPath Component Integrated into Dashboard**
   - Added `<LearningPath />` component to Dashboard.jsx
   - Shows "Today's Focus" with personalized recommendations
   - "Your Coach Says" section with Indian-English messages
   - "You're Improving" section showing progress areas
   - Backend endpoint `/api/coach/learning-path` working

2. **Socratic Mode UI in MoveFeedbackPanel**
   - Input field for user responses to Socratic questions
   - "Share my thinking" and "Show answer" buttons
   - Pattern reference and memory reference display
   - Indian-English coaching messages

3. **Backend Services Fully Integrated:**
   - `human_coach_integration.py` - Indian-English templates
   - `realtime_coaching_feedback.py` - Socratic mode fields
   - `socratic_engine.py` - Full Socratic dialogue system
   - `coach_memory.py` - Deep memory integration

4. **Visual Move Indicators** (Chess.com style)
   - Green checkmark for correct/book moves
   - Red X for wrong moves
   - Animated icons on destination squares

5. **Interactive Trap Practice**
   - 27+ chess-accurate traps
   - Practice mode with coach playing victim moves
   - Hint system showing full trap sequence

6. **UI Flicker Fix**
   - Separated FEN and lastMove updates into different useEffect hooks
   - Wrong moves shown for 2 seconds before resetting

### Previous Sessions
- Multi-Dimensional Player Understanding
- Personalized Coaching Language
- Opening Training Lab with 20+ openings
- Comprehensive trap library (27 traps)

## Key API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/coach/learning-path` | GET | Personalized learning recommendations |
| `/api/coach/play/feedback/{session_id}` | GET | Real-time move feedback |
| `/api/coach/socratic/start` | POST | Start Socratic dialogue |
| `/api/coach/socratic/respond` | POST | User responds to Socratic question |
| `/api/coach/human-coach/welcome` | GET | Human-like greeting |
| `/api/openings/{key}/practice/start` | POST | Start interactive practice |
| `/api/openings/practice/move` | POST | Make practice move |

## Database Schema
- **player_profiles:** user_id, estimated_elo, top_weaknesses, strengths
- **games:** Game PGNs and metadata
- **games_analysis:** Detailed analysis for each game
- **coach_sessions:** Coach play sessions and move history
- **coach_memory:** Habits, weaknesses, improving areas

## 3rd Party Integrations
- **Stockfish:** Engine analysis via python-chess
- **OpenAI GPT-4o-mini:** Natural language explanations
- **chess.js:** Frontend move validation
- **chessground:** Frontend chessboard library

## Prioritized Backlog

### ✅ P0 - Completed
- [x] LearningPath component in Dashboard
- [x] Socratic Mode UI in MoveFeedbackPanel
- [x] Visual Move Indicators in practice mode
- [x] Interactive Trap Practice
- [x] UI Flicker fix for wrong moves

### P1 - Backend Refactoring (IN PROGRESS)
- [ ] Continue migrating routes from server.py to coach_play.py (~2500 lines remaining)
- [ ] The migration pattern is established with `/api/coach/play/stats` endpoint

### P2 - Frontend Refactoring
- [ ] Break down `CoachPlay.jsx` (~2000 lines) into smaller components
- [ ] Extract custom hooks: useCoachSession, useChessboard
- [ ] Break down `LabV2.jsx` into smaller components

### P3 - Future Features
- [ ] Human Coach Training Dashboard for reviewing AI explanations
- [ ] Spaced repetition for opening memorization
- [ ] Multi-game pattern recognition in feedback

## Test Credentials
- Backend runs in `DEV_MODE` with default test user
- No login required for testing

## Known Technical Debt
- `server.py` still has ~9000+ lines - coach/play routes need migration
- `CoachPlay.jsx` has ~2000 lines, needs component extraction
- `LabV2.jsx` remains a large component (~1000 lines)

## Testing Status
- Backend Socratic endpoints tested and working
- LearningPath API returns proper data
- Frontend components rendering correctly
- Practice mode visual indicators working
