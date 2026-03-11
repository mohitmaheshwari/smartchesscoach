# Chess Coach AI - Product Requirements Document

## Original Problem Statement
The user's vision is to create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach. The central goal is to move beyond generic analysis and provide Socratic-style, contextual feedback tailored to the user's playstyle.

## Core Requirements (User-defined)
- **AI Teaching Coach:** An AI that plays instructive moves, guides the user through openings, and creates learning opportunities
- **Human-like Interaction:** The coach must have memory of past games, use Socratic questioning, and provide real-time, conversational guidance in simple Indian-English
- **Active Teaching Framework:** Provide in-game teaching for openings, middlegames, and endgames
- **Deep Post-Game Analysis:** Analyze performance accurately, check for recurring habits using memory, provide personalized feedback

## Architecture

### Backend (FastAPI)
- `/app/backend/server.py` - Main API routes
- `/app/backend/routes/lab.py` - Lab/game review routes
- `/app/backend/services/player_identity.py` - Deep memory/profile system
- `/app/backend/services/memory_injection.py` - Memory injection for coaching prompts
- `/app/backend/services/coach_personality.py` - Personalized coaching language by player level
- `/app/backend/services/breakthrough_service.py` - Analysis services

### Frontend (React)
- `/app/frontend/src/pages/LabV2.jsx` - Game Review page with interactive board
- `/app/frontend/src/components/LichessBoard.jsx` - Chessground wrapper component
- `/app/frontend/src/components/lab/CriticalMoments.jsx` - Critical moments UI
- `/app/frontend/src/components/DeepMemoryPanel.jsx` - Player profile visualization

### Database (MongoDB)
- `games` - Game history
- `player_identities` - Deep player profiles with blunder taxonomy, style analysis

## What's Been Implemented (March 2025)

### Session 1 - Deep Memory System
- Created `PlayerIdentity` service for tracking player patterns
- Added `memory_injection.py` for personalized coaching prompts
- Built `DeepMemoryPanel.jsx` for visualizing player profile
- Enhanced Coach Weekly Signal with data-driven insights

### Session 2 - Interactive Critical Moments (COMPLETED March 2025)
**Completed:**
- ✅ Fixed board navigation to show correct position for critical moments
- ✅ Implemented `movableColor` prop to restrict moves to user's pieces only
- ✅ Fixed coordinate calculations for Black's board orientation
- ✅ Connected `movable.events.after` callback for move completion
- ✅ Implemented "Correct!" feedback with green arrow for best move
- ✅ Implemented "Try again" feedback with red arrow for wrong move
- ✅ Toast notifications for move feedback
- ✅ Automatic play of best line continuation after correct move
- ✅ Position Hint feature - contextual clue before user attempts (e.g., "Opponent's Q on c2 is undefended")
- ✅ Enhanced wrong move feedback - shows missed threat explanation + "Try Again" button
- ✅ **Punishing counter-move animation** - opponent plays their best response after wrong move
- ✅ **Sound effects** - thud sound on punishment, success chime on correct, buzz on wrong
- ✅ Navigation between moments (prev/next buttons) working correctly
- ✅ "Yes, I get it" button advances to next moment

### Session 3 - Personalized Coaching Language (COMPLETED March 2025)
**Completed:**
- ✅ **Player Level System** - Categorizes players as Rookie, Beginner, Casual, Amateur, Intermediate, Advanced, Expert, Master
- ✅ **Rating-based categorization**: 0-800 Rookie, 800-1000 Beginner, 1000-1200 Casual, 1200-1400 Amateur, etc.
- ✅ **Personalized coaching language**: All prompts, feedback, and explanations adapt to player level
- ✅ **Player level badge**: Shows in Critical Moments header (e.g., "⭐ Amateur")
- ✅ **Level-specific Socratic prompts**: From "Look at the board carefully" (Rookie) to "Your move" (Master)
- ✅ **Level-specific wrong move feedback**: From gentle encouragement (Rookie) to direct analysis (Expert)
- ✅ **Level-specific try again prompts**: From "No rush" (Rookie) to "Recalculate" (Advanced)
- ✅ **Backend coach_personality.py service**: Complete language template system
- ✅ **API returns player level**: deep-strategy endpoint includes player_level, player_level_display, coaching_voice

**Player Level Language Examples:**
- Rookie: "Look at the board carefully. What piece can help you here?"
- Amateur: "Critical position. Find the best continuation."
- Expert: "Find the optimal move."

**How It Works:**
1. User navigates to "Moments" tab in Game Review
2. Position hint shows context (e.g., threats, undefended pieces)
3. User clicks "Try Move on Board" to enter interactive mode
4. Board shows "Your turn - find the best move!" indicator
5. User makes a move by clicking/dragging piece
6. If correct: Shows "Excellent!" + green arrow + auto-plays best line continuation
7. If incorrect: Shows feedback with red arrow + opponent plays punishing counter-move + explanation
8. User sees the consequence of their wrong move on the board (e.g., "Opponent punishes with Qxg2+!")
9. "Try Again" resets board to original position for another attempt
9. After reviewing, "Yes, I get it" advances to next moment

## Prioritized Backlog

### P0 (Immediate)
- ✅ All P0 items completed

### P1 (High Priority)
- Show missed threat arrow on PrescribedTraining page
- Backend refactoring: modularize server.py into route files

### P2 (Medium Priority)
- Game number confusion fix (Reset Game History button)
- Frontend refactoring: break down LabV2.jsx and CoachPlay.jsx

### P3 (Future)
- Human Coach Training Dashboard
- Additional coaching features

## Key Technical Notes

### Board Orientation (Black's View)
- Files: h=col0, g=col1, f=col2, e=col3, d=col4, c=col5, b=col6, a=col7
- Ranks: rank1=row0 (top), rank8=row7 (bottom)
- Example: c6 = col5, row5; b8 = col6, row7

### Chessground Configuration
- Use `movable.events.after` for move callbacks (not `events.move`)
- Set `movable.color` to restrict which pieces can be moved
- Use `getMovesForColor()` to calculate destinations for specific color

## 3rd Party Integrations
- **Stockfish:** Engine analysis via python-chess
- **OpenAI GPT-4o-mini:** Natural language explanations
- **chess.js:** Frontend move validation and SAN-to-UCI conversion
- **Chessground:** Interactive chess board rendering

## Test Credentials
Backend is in DEV_MODE - uses default test user `user_bdd07038f9c0`
