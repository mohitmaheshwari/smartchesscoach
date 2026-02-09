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
- Legal move validation to prevent hallucinated responses

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

## Tech Stack
- **Frontend**: React.js with Shadcn/UI components
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Chess Engine**: Stockfish 15
- **LLM**: Emergent LLM Key integration

## Key Files
- `/app/backend/server.py` - Main backend with /ask endpoint
- `/app/frontend/src/pages/GameAnalysis.jsx` - Game analysis page with Ask feature
- `/app/backend/stockfish_service.py` - Stockfish integration

## Known Issues / Backlog
1. Missing `data-testid="get-started-btn"` on landing page (affects automated testing)

## API Endpoints
- `POST /api/game/{game_id}/ask` - Ask questions about a position
- `POST /api/analyze-game` - Analyze a game with Stockfish + AI
- `GET /api/analysis/{game_id}` - Get analysis for a game
- `POST /api/import-games` - Import games from Chess.com/Lichess
