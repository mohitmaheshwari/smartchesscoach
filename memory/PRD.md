# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a full-featured chess coaching application that analyzes games, identifies weaknesses, and provides personalized coaching with a GM-coach style coaching loop.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)

## GOLD FEATURE: Board-First Coach (v3.0) - COMPLETE

### Core Philosophy: "Show Me, Don't Tell Me"
Every critical insight must be backed by a clickable position on the board. Minimize text, maximize board interaction.

### Layout
- **LEFT:** Sticky, always-visible interactive chessboard with:
  - Position jumping (by FEN or move number)
  - Square highlighting
  - Arrow drawing
  - "Drill Mode" - user plays moves, validated by Stockfish
  - **Mission card with streak counter** below board
  
- **RIGHT:** 3-tab coach panel
  - **Audit Tab:** Key Moments from last game WITH COACH EXPLANATIONS
  - **Plan Tab:** Next game plan (1 Opening + 2 Habits + 3 Drills)
  - **Openings Tab:** Your Repertoire trainer

### Audit Tab - "Show Me Where I Broke The Plan"
- 3-5 Key Moments from last game (not text-based audit)
- Each Key Moment card shows:
  - Label (e.g., "Piece Left Hanging", "Lost Winning Position")
  - Move number and move played
  - Eval swing (e.g., -6.7 pawns)
  - **Coach Explanation**: "You played Bc7, but your piece was left undefended."
  - **Lesson Box (yellow)**: "Before moving ANY piece, always ask: 'Will my piece be safe on this square?' This is the #1 rule at every level."
  - **More details** expandable section with thinking error, better move, correction
  - **View Position button:** Jumps board to position with highlighting (STAYS ON TAB)
  - **Try Again button:** Activates drill mode for mini-exercise (STAYS ON TAB)

### Plan Tab - "Next Game Plan = 1 Opening Line + 2 Habits + 3 Drills"
- Opening Line section with ACTUAL opening name (e.g., "French Defense")
  - "Practice Line on Board" button plays moves then lets user repeat
- Focus Habits (max 2 high-level habits)
  - e.g., "When winning, simplify the position"
  - e.g., "Check threats before every move"
- Practice Drills (3 positions from user's own games)
  - Each drill shows: difficulty, target weakness, hint
  - **"Start Drill" button works on board without switching tabs**

### Openings Tab - "Your Repertoire Trainer"
- Coach intro: "Based on your games, here are your most successful openings."
- **As White:** Actual opening name (e.g., "French Defense")
- **As Black:** Actual opening name (e.g., "Queens Pawn Opening")
- "Avoid" recommendations when available
- Win rate stats when available

### Mission System (Restored)
- Current Mission with name and goal
- Streak counter (X / target)
- Progress bar
- "Streak reset" or "Last game counted" feedback
- Personal best streak display

### Key Moment Selection Logic (Backend)
Deterministic selection from game analysis:
1. Biggest eval drops (blunders/mistakes)
2. First plan violation
3. Hung pieces (cp_loss >= 300)
4. Advantage collapse (had advantage, lost it)
5. Late-game mistakes (move 40+)

### Drill Position Selection Logic (Backend)
- Targets user's primary weakness pattern
- Filtered by weakness type (piece_safety, tactical_blindness, etc.)
- Includes hint about what to avoid
- Correct moves validated by Stockfish analysis

## API Endpoints

### Coaching Loop
- `GET /api/round-preparation` - Returns drills, cards, training_block, games_analyzed, opening_recommendation
- `GET /api/plan-audit` - Returns key_moments, audit results
- `GET /api/focus` - Returns mission, opening_to_play, opening_stats
- `GET /api/sync-status` - Sync status for header display

## Key Files

### Board-First Coach
- `frontend/src/pages/BoardFirstCoach.jsx` - Main coach page with 3-tab layout + mission
- `frontend/src/components/CoachBoard.jsx` - Interactive chessboard with drill mode
- `frontend/src/components/KeyMomentCard.jsx` - Key moment cards with COACH EXPLANATIONS
- `frontend/src/components/DrillCard.jsx` - Drill cards for Plan tab

### Backend Services
- `backend/deterministic_coach_service.py` - Core logic including:
  - `extract_key_moments()` - Selects 3-5 teaching moments
  - `generate_drill_positions()` - Creates interactive drills
  - `generate_round_preparation()` - Full plan with drills
  - `generate_plan_audit()` - Audit with key_moments

## Completed Work (Feb 2026)

### Board-First Coach - COMPLETE
- [x] Interactive CoachBoard component with drill mode
- [x] 3-tab layout (Audit, Plan, Openings)
- [x] Key Moments with View/Try Again buttons
- [x] **Coach explanations for each key moment** (what went wrong, why it matters, lesson)
- [x] View jumps board to position with highlighting
- [x] Try Again activates drill mode (STAYS ON SAME TAB)
- [x] Plan tab with Opening Line, Focus Habits, Practice Drills
- [x] **Actual opening names displayed** (French Defense, Queens Pawn Opening)
- [x] **Start Drill works on board without switching tabs**
- [x] Openings tab with Your Repertoire
- [x] **Mission card with streak counter** restored
- [x] Backend extract_key_moments() and generate_drill_positions()
- [x] Full testing: 12 backend tests, all frontend elements verified

## Upcoming Tasks

### P0: Board-First Coach Enhancements
- [ ] Opening line trainer (full playback + repeat mode with validation)
- [ ] Stockfish real-time validation of drill moves (accept top 2-3 moves)
- [ ] Complete repertoire with win rates per opening

### P1: Data Quality
- [ ] Historical game analysis script (find games missing analysis)

### P2: Performance
- [ ] Optimize Stockfish analysis depth (18 → 12-14)

## Test Reports
- `/app/test_reports/iteration_41.json` - Board-First Coach Phase 1 (100% pass)
- `/app/backend/tests/test_board_first_coach.py` - Backend tests

## Credentials
- Test user: session_token=test_session_356539ff12b1 (user with 30+ analyzed games)
- Dev Login available on landing page
