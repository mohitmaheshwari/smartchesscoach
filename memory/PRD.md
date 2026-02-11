# Chess Coach - Product Requirements Document

## Original Problem Statement
Build an AI-powered chess coaching application that analyzes games, identifies patterns in player mistakes, and provides personalized coaching feedback.

## Core Features Implemented

### Game Analysis
- Import games from Chess.com and Lichess
- Stockfish engine analysis (depth 18) for accurate move evaluation
- AI-powered coaching commentary with habit-based feedback
- Phase-aware strategic coaching (opening/middlegame/endgame)

### Ask About This Move Feature
- Interactive Q&A about specific positions
- Stockfish-powered position evaluation
- Context-aware conversation history for follow-up questions
- **Analyzes position BEFORE the move** to correctly identify user's best alternative
- Correctly distinguishes between user's best move and opponent's response

### Player Profile System
- Tracks recurring mistake patterns
- Identifies strengths and weaknesses
- Provides personalized coaching based on history

### Authentication
- Google OAuth integration via Emergent Auth

## Recent Changes (Feb 2026)

### Bug Fixes - Feb 9, 2026
1. **Fixed suggested question always showing "mistake"**
   - Added `getCurrentMoveEvaluation()` function
   - Questions now adapt based on actual move evaluation (blunder/mistake/good/etc.)

2. **Fixed LLM hallucinating illegal moves**
   - Added position description with all pieces listed
   - Added legal moves list to LLM context
   - Explicit instructions to only mention legal moves

3. **Fixed LLM confusing user moves with opponent moves**
   - Now sends `fen_before` (position before move) to backend
   - Backend analyzes BOTH positions: before (for user's best) and after (for opponent's response)
   - LLM prompt clearly states which move belongs to which player
   - Response includes `user_best_move` - what the user SHOULD have played

### Documentation & Deployment - Feb 9, 2026
- Created Docker deployment files (Dockerfile, docker-compose.yml)
- Created comprehensive DEVELOPER.md documentation
- Added nginx and supervisor configuration for production

## Tech Stack
- **Frontend**: React.js with Shadcn/UI components
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Chess Engine**: Stockfish 15
- **LLM**: Emergent LLM Key integration

## Key Files
- `/app/backend/server.py` - Main backend with /ask endpoint
- `/app/frontend/src/pages/GameAnalysis.jsx` - Game analysis page with Ask feature
- `/app/frontend/src/components/ChessBoardViewer.jsx` - Chess board with FEN access
- `/app/backend/stockfish_service.py` - Stockfish integration
- `/app/DEVELOPER.md` - Developer documentation
- `/app/Dockerfile` - Production container build

## Recent Changes - Feb 10-11, 2026

### Stockfish Fix (Feb 10)
- Reinstalled Stockfish (was missing from environment)
- Analyzed 10 games with Stockfish - all successful
- Now 21 games have valid `stockfish_analysis.move_evaluations`

### Interactive Badge Drill-Down (Feb 11 - Enhanced)
Major feature overhaul for badge drill-down:

**1. Interactive Chess Board**
- Play through best move lines (PV) with Next/Prev/Reset buttons
- Visual highlights for played vs best squares
- "Show Best" instant demonstration

**2. Ask AI Integration**
- Chat interface for each position
- Suggested questions + custom input
- AI responses include playable lines

**3. Deeper Explanations**
- Context-aware: opening/tactical/focus/endgame specific advice
- Includes PV lines in explanations
- Actionable coaching tips

**Files Modified:**
- `frontend/src/components/BadgeDetailModal.jsx` - Complete rewrite with interactive features
- `backend/badge_service.py` - Enhanced explanation generators, added pv_after_best to all moves

## In Progress
1. **Focus-aware Game Analysis** - When user clicks "View Game" from badge detail, commentary should focus on that badge category
2. **Testing** - E2E testing of interactive badge drill-down needed

## Known Issues / Backlog
1. Missing `data-testid="get-started-btn"` on landing page (affects automated testing)
2. Stockfish not persistent between environment restarts (temporary fix applied)
3. 17 games still need Stockfish analysis

## API Endpoints
- `POST /api/game/{game_id}/ask` - Ask questions about a position (supports fen_before)
- `POST /api/analyze-game` - Analyze a game with Stockfish + AI
- `GET /api/analysis/{game_id}` - Get analysis for a game
- `POST /api/import-games` - Import games from Chess.com/Lichess
- `GET /api/health` - Health check endpoint
