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
│   │   ├── chess_understanding.py         # Chess skills profiling
│   │   └── opening_library_service.py     # Opening training lab service
│   ├── routes/
│   │   ├── auth.py
│   │   ├── lab.py
│   │   └── openings.py                    # Opening Training Lab routes (NEW)
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
        │   ├── CoachPlay.jsx              # Live coach play with feedback
        │   └── OpeningLesson.jsx          # Opening lessons with practice mode
        └── components/
            ├── coach-play/                # Extracted CoachPlay components (NEW)
            │   ├── EvalBar.jsx
            │   └── MoveFeedbackPanel.jsx
            ├── openings/                  # Opening Training components (NEW)
            │   └── InteractivePractice.jsx
            ├── lab/
            │   ├── CriticalMoments.jsx
            │   └── MissedTactics.jsx
            └── PrescribedTraining.jsx
```

## What's Been Implemented

### March 12, 2026 - Expanded Trap Library + Coach Integration
- **Added 9 more openings** to database: French Defense, Slav Defense, Nimzo-Indian, Vienna Game, Queen's Indian, Grunfeld Defense, Benoni Defense (now 20 total)
- **Added 9 more traps** (now 27 total):
  - French Defense: Winawer Poisoned Pawn, Milner-Barry Gambit
  - Slav Defense: Main Line Trap
  - Nimzo-Indian: Hubner Trap (wins queen!)
  - Vienna Game: Frankenstein-Dracula
  - Queen's Indian: Bishop Trap
  - Grunfeld: Exchange Trap
  - Benoni: Snake Trap
- **New API endpoints:**
  - `GET /api/traps/statistics` - Trap library stats
  - `GET /api/traps/checkmates` - All checkmate traps
  - `GET /api/traps/difficulty/{level}` - Filter by difficulty
  - `POST /api/traps/suggest` - Get trap suggestion for position
- **Coach Integration:** Trap suggestions now appear in move feedback when a trap is within reach
- **Frontend:** "Browse All Opening Lessons" modal with trap counts

### March 12, 2026 - Comprehensive Trap Library Created
- **Created `/backend/services/trap_library.py`** with 18 chess-accurate traps:
  - Italian Game: 4 traps (Fried Liver, Legal's Mate, Blackburne Shilling, Scholar's Defense)
  - Sicilian Defense: 2 traps (Siberian Trap, Magnus Smith Trap)
  - Queen's Gambit: 2 traps (Elephant Trap, Lasker Trap)
  - Ruy Lopez: 2 traps (Noah's Ark, Mortimer Trap)
  - Petrov Defense: 1 trap (Stafford Gambit - checkmate!)
  - Budapest Gambit: 1 trap (Kieninger Trap - smothered mate!)
  - Dutch Defense: 1 trap (Dutch Defense Mate)
  - Caro-Kann: 1 trap (Smothered Mate)
  - Plus traps for King's Indian, Scandinavian, Philidor, London
- **Added 6 new openings** to the database: Ruy Lopez, Philidor, Petrov, Budapest, Dutch, Opera Game
- **All traps engine-verified** with chess.py for 100% accuracy
- **Added metadata:** difficulty (beginner/intermediate/advanced), result_type (checkmate/wins_queen/wins_piece/wins_material)

### March 12, 2026 - Interactive Practice Mode & Refactoring
- **P1 Feature: Interactive Practice Mode** in Opening Training Lab
  - New backend endpoints: `/api/openings/{key}/practice/start`, `/api/openings/practice/move`, `/api/openings/practice/{id}/hint`
  - Socratic feedback when user makes wrong moves
  - Coach plays opponent's moves automatically
  - Hint system with progressive detail (3 levels)
  - Session tracking for practice progress
- **P1 Backend Refactoring:**
  - Created `routes/openings.py` - extracted all opening training endpoints from server.py
  - Removed duplicate endpoints, server.py reduced by ~100 lines
- **P2 Frontend Refactoring:**
  - Extracted `EvalBar` component to `/components/coach-play/EvalBar.jsx`
  - Extracted `MoveFeedbackPanel` to `/components/coach-play/MoveFeedbackPanel.jsx`
  - Created `/components/openings/InteractivePractice.jsx` for practice mode
  - CoachPlay.jsx reduced from 2252 to 2058 lines

### March 12, 2026 - Opening Library Matching Bug Fix
- **P0 Fix:** Opening variations now correctly match to the library
  - "Giuoco Piano Game" now maps to "Italian Game"
  - "Sicilian Najdorf" maps to "Sicilian Defense"
  - All Italian Game variations (Two Knights, Evans Gambit, etc.) map correctly
- **New Backend Endpoint:** `GET /api/openings/match?opening_name=X&eco=Y`
  - Intelligent matching using ECO codes and opening aliases
  - Returns `library_key` and `library_name` if matched
- **Frontend Update:** HabitsToImprove component now uses backend matching instead of naive substring comparison
- **"Learn This Opening" button** now appears correctly for all opening variations

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
| `/api/openings/match` | GET | Match opening name to library |
| `/api/openings/{key}/practice/start` | POST | Start interactive practice |
| `/api/openings/practice/move` | POST | Make practice move |
| `/api/openings/practice/{id}/hint` | GET | Get practice hint |

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

### P0 - Completed
- [x] Opening library matching bug fix (Giuoco Piano -> Italian Game)

### P1 - Completed
- [x] Interactive Practice Mode in Opening Training Lab
- [x] Backend Refactoring: Created routes/openings.py (partial modularization)
- [x] Frontend Refactoring: Extracted EvalBar and MoveFeedbackPanel from CoachPlay.jsx

### P1 - Remaining
- [ ] Continue Backend Refactoring: Extract coach/play routes from server.py (~2500 lines)

### P2 - Medium Priority
- [ ] Continue refactoring `CoachPlay.jsx` - extract more hooks (useCoachSession, useChessboard)
- [ ] Break down `LabV2.jsx` into smaller components
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
- `CoachPlay.jsx` still has ~2000 lines, needs more component extraction
- `LabV2.jsx` remains a large component (~1000 lines)
- `server.py` still has ~12,000 lines - coach/play routes (~2500 lines) should be extracted
- Backend routes could be further modularized (training, journey, etc.)
