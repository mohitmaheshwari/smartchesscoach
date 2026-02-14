# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a full-featured chess coaching application that analyzes games, identifies weaknesses, and provides personalized coaching with a GM-coach style coaching loop.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)

## GOLD FEATURE: Board-First Coach (v3.0) - PHASE 1 COMPLETE

### Core Philosophy: "Show Me, Don't Tell Me"
Every critical insight must be backed by a clickable position on the board. Minimize text, maximize board interaction.

### Layout
- **LEFT:** Sticky, always-visible interactive chessboard with:
  - Position jumping (by FEN or move number)
  - Square highlighting
  - Arrow drawing
  - "Drill Mode" - user plays moves, validated by Stockfish
  
- **RIGHT:** 3-tab coach panel
  - **Audit Tab:** Key Moments from last game
  - **Plan Tab:** Next game plan (1 Opening + 2 Habits + 3 Drills)
  - **Openings Tab:** Your Repertoire trainer

### Audit Tab - "Show Me Where I Broke The Plan"
- 3-5 Key Moments from last game (not text-based audit)
- Each Key Moment card shows:
  - Label (e.g., "Piece Left Hanging", "Lost Winning Position")
  - Move number and move played
  - Eval swing (e.g., -6.7 pawns)
  - "Better" hint (e.g., "Better: Qxb6")
  - **View button:** Jumps board to position with highlighting
  - **Try Again button:** Activates drill mode for mini-exercise

### Plan Tab - "Next Game Plan = 1 Opening Line + 2 Habits + 3 Drills"
- Opening Line drill section with "Practice Line" button
- Focus Habits (max 2 high-level habits)
  - e.g., "When winning, simplify the position"
  - e.g., "Check threats before every move"
- Practice Drills (3 positions from user's own games)
  - Each drill shows: difficulty, target weakness, hint
  - "Start Drill" button for interactive practice

### Openings Tab - "Your Repertoire Trainer"
- As White: Recommended opening (or "More data needed")
- As Black: Recommended opening (or "More data needed")
- "Line to Know Today" with board demo (future)

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

## Previous System: Deterministic Adaptive Coach (v2.0)
(Still active in backend, powering the Board-First UI)

### Rating Bands (Granular - 4 bands)
- **600-1000 (beginner_low)**: Focus on not hanging pieces
- **1000-1400 (beginner_high)**: Basic tactics and simple plans  
- **1400-1800 (intermediate)**: Positional understanding
- **1800+ (advanced)**: Nuanced strategic advice

### Training Intensity (5 Levels)
- **Level 1 (Light)**: Outcome focus, gentle reminders
- **Level 2 (Normal)**: Clear behavior rules (DEFAULT)
- **Level 3 (Focused)**: Simplified rules, higher stakes language
- **Level 4 (Intense)**: Micro-habits, single rule per domain
- **Level 5 (Critical)**: Emergency mode - ONE rule for entire game

## API Endpoints

### Coaching Loop
- `GET /api/round-preparation` - Returns drills, cards, training_block, games_analyzed
- `GET /api/plan-audit` - Returns key_moments, audit results
- `GET /api/coaching-loop/profile` - Full coaching profile
- `GET /api/sync-status` - Sync status for header display

## Key Files

### Board-First Coach (NEW)
- `frontend/src/pages/BoardFirstCoach.jsx` - Main coach page with 3-tab layout
- `frontend/src/components/CoachBoard.jsx` - Interactive chessboard with drill mode
- `frontend/src/components/KeyMomentCard.jsx` - Key moment cards for Audit tab
- `frontend/src/components/DrillCard.jsx` - Drill cards for Plan tab

### Backend Services
- `backend/deterministic_coach_service.py` - Core logic including:
  - `extract_key_moments()` - Selects 3-5 teaching moments
  - `generate_drill_positions()` - Creates interactive drills
  - `generate_round_preparation()` - Full plan with drills
  - `generate_plan_audit()` - Audit with key_moments

## Technical Notes
- Using `react-chessboard` library for board rendering
- FEN positions stored for each key moment and drill
- Drill validation accepts top moves from Stockfish analysis
- Board highlights squares in yellow (warnings) and green (correct moves)

## Completed Work (Feb 2026)

### Phase 1: Board-First Coach - COMPLETE
- [x] Interactive CoachBoard component with drill mode
- [x] 3-tab layout (Audit, Plan, Openings)
- [x] Key Moments with View/Try Again buttons
- [x] View jumps board to position with highlighting
- [x] Try Again activates drill mode
- [x] Plan tab with Opening Line, Focus Habits, Practice Drills
- [x] Openings tab with Your Repertoire
- [x] Backend extract_key_moments() and generate_drill_positions()
- [x] Full testing: 12 backend tests, all frontend elements verified

### Previous: Deterministic Coach (v2.0)
- [x] 5-level intensity system
- [x] Granular rating bands
- [x] Evidence-backed audits
- [x] Domain history tracking
- [x] GM-style concise tone

## Upcoming Tasks

### P0: Board-First Coach Phase 2
- [ ] Opening line trainer (playback + repeat mode)
- [ ] Stockfish validation of drill moves (accept top 2-3 moves)
- [ ] Complete repertoire from user's opening stats
- [ ] "Line to Know Today" feature

### P1: Data Quality
- [ ] Historical game analysis script (find games missing analysis)
- [ ] Tactics Audit Data Inconsistency fix (verify blunder detection)

### P2: Performance
- [ ] Optimize Stockfish analysis depth (18 → 12-14)

## Test Reports
- `/app/test_reports/iteration_41.json` - Board-First Coach Phase 1 (100% pass)
- `/app/backend/tests/test_board_first_coach.py` - Backend tests

## Credentials
- Test user: session_token=test_session_356539ff12b1 (user with 30+ analyzed games)
- Dev Login available on landing page
