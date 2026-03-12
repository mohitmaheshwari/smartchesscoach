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
│   │   ├── realtime_coaching_feedback.py  # Real-time move feedback generation
│   │   ├── coach_personality_service.py   # Defines player levels and coaching language
│   │   ├── player_understanding_service.py # Multi-dimensional chess understanding
│   │   └── chess_understanding.py         # Chess skills profiling
│   ├── routes/
│   │   ├── auth.py
│   │   └── lab.py
│   ├── coach_play/
│   │   └── coach_commentary.py            # Coach commentary and analysis
│   └── server.py
└── frontend/
    └── src/
        ├── hooks/
        │   └── useSound.js                # Web Audio API hook
        ├── pages/
        │   ├── LabV2.jsx                  # Game review page
        │   ├── Dashboard.jsx              # User dashboard
        │   └── CoachPlay.jsx              # Live coach play with feedback
        └── components/
            ├── lab/
            │   ├── CriticalMoments.jsx
            │   └── MissedTactics.jsx
            └── PrescribedTraining.jsx
```

## What's Been Implemented

### March 12, 2026 - Real-time Move Feedback
- **MoveFeedbackPanel Component:** Comprehensive feedback display after each user move
  - Shows move quality (excellent/good/inaccuracy/mistake/blunder) with emoji indicators
  - Displays coaching message explaining the move
  - Shows "Best was {move}" section when user's move wasn't optimal
  - Displays coach's counter-move with explanation
  - Includes personalized feedback based on player's weaknesses
  - Dismiss button functionality
- **Backend API:** `/api/coach/play/feedback/{session_id}` endpoint
- **Testing:** 23 tests pass (13 backend + 10 frontend)

### Previous Sessions
- **Multi-Dimensional Player Understanding:** Backend service that profiles chess understanding across dimensions (Tactical Vision, Positional Sense, Opening Knowledge, Consistency)
- **Personalized Coaching Language:** Dynamic feedback adaptation based on player's specific weaknesses
- **Animated Punishing Move:** In CriticalMoments training, opponent's counter-move animates on the board
- **Audio Feedback:** Custom sound effects using Web Audio API
- **"View" Button Fix:** Correct navigation and arrow display in Ideas tab
- **"Next Moment" Button:** Advance to next puzzle after correct move
- **"Reset Game History":** Backend endpoint and UI button for data reset

## Key API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/coach/play/feedback/{session_id}` | GET | Real-time move feedback |
| `/api/coach/play/start` | POST | Start new coach game |
| `/api/coach/play/move/{session_id}` | POST | Make a move |
| `/api/coach/play/state/{session_id}` | GET | Get session state |
| `/api/lab/deep-strategy/{game_id}` | GET | Game review data |
| `/api/auth/reset-user-data` | POST | Clear user game data |

## Database Schema
- **player_profiles:** user_id, estimated_elo, top_weaknesses, strengths
- **games:** Game PGNs and metadata
- **games_analysis:** Detailed analysis for each game
- **coach_sessions:** Coach play sessions and move history

## 3rd Party Integrations
- **Stockfish:** Engine analysis via python-chess
- **OpenAI GPT-4o-mini:** Natural language explanations
- **chess.js:** Frontend move validation
- **chessground:** Frontend chessboard library

## Prioritized Backlog

### P1 - High Priority
- [ ] Backend Refactoring: Modularize `server.py` into service files
- [ ] Frontend Refactoring: Break down `LabV2.jsx` into smaller components

### P2 - Medium Priority
- [ ] Refactor `CoachPlay.jsx` (known fragility) into smaller components and hooks
- [ ] Add more sophisticated tactical analysis to move feedback
- [ ] Implement move animation when showing best move

### P3 - Future
- [ ] Human Coach Training Dashboard for reviewing AI explanations
- [ ] Advanced memory features for long-term player tracking
- [ ] Multi-game pattern recognition in feedback

## Test Credentials
- Backend runs in `DEV_MODE` with default test user `user_bdd07038f9c0`
- No login required for testing

## Known Technical Debt
- `CoachPlay.jsx` is fragile and should be refactored into smaller components
- `LabV2.jsx` remains a very large component
- `server.py` needs further modularization
