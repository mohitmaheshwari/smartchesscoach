# Chess Coach - Product Requirements Document

## Original Problem Statement
Build an AI-powered chess coaching application that analyzes games, identifies patterns in player mistakes, and provides personalized coaching feedback. The Progress page should provide deep, personalized coaching with interactive chess boards, rating-aware explanations, and deterministic feedback (no LLM hallucinations).

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

### 8-Badge Chess DNA System
Each badge rated 1-5 stars with trend tracking:
1. Opening Mastery - Theory knowledge, development, avoiding early mistakes
2. Tactical Vision - Finding tactics, spotting threats, combinations
3. Positional Sense - Piece placement, pawn structure, long-term planning
4. Endgame Skills - Converting advantages, technique, theoretical knowledge
5. Defensive Resilience - Holding tough positions, finding resources when worse
6. Converting Wins - Closing out games when winning, not throwing leads
7. Focus & Discipline - Avoiding casual blunders, checking threats
8. Time Management - Using clock wisely, not rushing or flagging

### Interactive Badge Drill-Down (Completed Dec 2025)
**Key Architecture**: Engine + Rules = Truth, LLM = Storyteller

**1. Deterministic Mistake Classifier** (`backend/mistake_classifier.py`)
- Rule-based classification - NO LLM guessing
- **Efficient bitboard operations** using python-chess library
- Detects 14 mistake types including:
  - WALKED_INTO_FORK: Moved into a fork
  - WALKED_INTO_PIN: Created a pin against yourself
  - MISSED_FORK: Could have forked but didn't
  - MISSED_PIN: Could have created a pin but didn't
  - HANGING_PIECE: Piece left undefended
  - MATERIAL_BLUNDER: Lost material immediately
  - BLUNDER_WHEN_AHEAD: Was winning, threw it away
  - IGNORED_THREAT: Opponent had threat, player didn't address
  - And more...

**Tactical Pattern Detection Functions**:
- `find_forks()`: Uses `board.attacks()` bitboard for O(n) detection, handles FORK_VALUES (king=100 for tactics)
- `find_pins()`: Detects both absolute pins (to king via `board.is_pinned()`) and relative pins (to queen)
- `find_skewers()`: Detects sliding piece attacks where front piece must move, revealing behind piece

**2. Interactive Chess Board** (`BadgeDetailModal.jsx`)
- "Your Move" button: Replays user's move with red highlights
- "Best Move" button: Shows best move with green highlights  
- Line navigation (< >) to step through principal variation
- Uses chess.js for move validation and FEN management

**3. Rating-Aware Explanations**
- Simpler concepts for lower-rated players (<1400)
- More advanced ideas for higher ratings
- Context-aware: opening/tactical/endgame specific advice

### Authentication
- Google OAuth integration via Emergent Auth
- DEV_MODE for local testing (bypasses OAuth)

## Tech Stack
- **Frontend**: React.js with Shadcn/UI components, chess.js, react-chessboard
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Chess Engine**: Stockfish 15
- **LLM**: Emergent LLM Key integration (for personality layer only)

## Key Files
- `/app/backend/mistake_classifier.py` - **Deterministic** rule-based mistake classification
- `/app/backend/badge_service.py` - Badge calculation and drill-down logic
- `/app/backend/server.py` - Main backend with API endpoints
- `/app/frontend/src/components/BadgeDetailModal.jsx` - Interactive board + badge details UI
- `/app/frontend/src/pages/ProgressV2.jsx` - Progress page with badges

## API Endpoints
- `GET /api/badges` - Get all badge scores with trends
- `GET /api/badges/{badge_key}/details` - Get detailed drill-down for a badge
- `POST /api/game/{game_id}/ask` - Ask questions about a position
- `POST /api/analyze-game` - Analyze a game with Stockfish + AI
- `GET /api/analysis/{game_id}` - Get analysis for a game
- `POST /api/import-games` - Import games from Chess.com/Lichess
- `GET /api/auth/dev-login` - Dev mode login (when DEV_MODE=true)

## Recent Changes - December 2025

### Complete Tactical Pattern System
**New Detection Functions** (efficient bitboard operations):
- `find_forks()`: O(n) complexity using `board.attacks()`, FORK_VALUES (king=100)
- `find_pins()`: Absolute pins (to king) + relative pins (to queen)  
- `find_skewers()`: NEW - detects sliding piece attacks where front piece must move

**New Mistake Types** (25 total):
- Negative: WALKED_INTO_SKEWER, MISSED_SKEWER added
- Positive: EXECUTED_FORK, EXECUTED_PIN, EXECUTED_SKEWER
- Defensive: AVOIDED_FORK, AVOIDED_PIN, AVOIDED_SKEWER, AVOIDED_THREAT

### LLM Personality Layer (Refactored)
The `/api/game/{game_id}/ask` endpoint now follows the architecture:
- **Step 1**: Deterministic `classify_mistake()` generates structured facts
- **Step 2**: LLM receives ONLY those facts and verbalizes them
- **Result**: No more hallucinated chess analysis - LLM cannot invent tactics

### Badge Aggregation Updated
`classify_for_badge()` now tracks:
- `forks_executed`, `pins_executed`, `skewers_executed`
- `threats_avoided`
- `total_good_plays` (separate from mistakes)

## Upcoming Tasks (P1)
1. **Update LLM Prompt Layer** - Refactor `/api/game/{gameId}/ask` to use "personality layer" model (LLM only narrates structured facts from classifier)
2. **Detect Avoided Threats** - Positive feedback when user correctly spots threats
3. **"Today's Focus" Feature** - Dashboard component highlighting one actionable improvement area

## Future/Backlog Tasks (P2-P3)
1. **Aggregate Behavioral Patterns** - Identify recurring patterns across games (e.g., "You hang pieces when ahead")
2. **Production-Ready Cron Job** - Robust background game sync/analysis
3. Add data-testid to InteractiveBoard buttons for better test automation
4. Stockfish persistence fix (currently needs reinstall on environment restart)

## Known Issues
1. Stockfish not persistent between environment restarts (temporary fix: reinstall manually)
2. Some games still need Stockfish analysis

## Test Credentials
- DEV_MODE=true in backend/.env enables dev login
- DEV_USER_ID=user_bdd07038f9c0 (test user with analyzed games)
