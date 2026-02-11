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

## Recent Changes - February 2026

### Discovered Attack & Overloaded Defender Detection (Feb 2026)
- Added `find_discovered_attacks()` function with full ray-tracing logic
- Added `find_overloaded_defenders()` function for tactical exploitation
- Added 6 new MistakeTypes for discovered attacks and overloaded defenders
- Updated `classify_for_badge()` to track the new patterns
- Updated `calculate_tactical_ratio()` to include new tactics in metrics
- Tests: `/app/backend/tests/test_new_tactics.py` (8/8 passing)

## Changes - December 2025

### Tactical Ratio Feature (NEW - Dec 2025)
A motivating metric on the Progress page showing:
- **Ratio**: (Executed + Avoided) / (Executed + Avoided + Fallen Into)
- **Visual Progress Bar**: Color-coded (green ≥75%, amber ≥50%, red <50%)
- **Three Stat Boxes**: Tactics Executed, Threats Avoided, Fell Into
- **Breakdown**: Shows forks/pins/skewers for each category
- **Trend Message**: Encouraging feedback based on performance
- **Weakness Detection**: Highlights which tactic type needs most practice

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
- `discovered_attacks_executed`, `overloaded_exploited` (NEW)
- `discovered_attacks_missed`, `overloaded_missed` (NEW)
- `discovered_attacks_walked_into` (NEW)
- `threats_avoided`
- `total_good_plays` (separate from mistakes)

### Discovered Attack & Overloaded Defender Detection (NEW - Feb 2026)
Added advanced tactical pattern detection:
- **`find_discovered_attacks()`**: Detects when moving a piece reveals an attack from a sliding piece behind it. Handles discovered checks and double attacks.
- **`find_overloaded_defenders()`**: Identifies pieces defending multiple targets that are under attack.
- **New MistakeTypes**: 
  - `EXECUTED_DISCOVERED_ATTACK`, `MISSED_DISCOVERED_ATTACK`, `WALKED_INTO_DISCOVERED_ATTACK`
  - `EXPLOITED_OVERLOADED_DEFENDER`, `MISSED_OVERLOADED_DEFENDER`
  - `AVOIDED_DISCOVERED_ATTACK`
- **Updated `calculate_tactical_ratio()`**: Now includes discovered attacks and overloaded defender patterns in the tactical performance metrics.

### BLUNDER REDUCTION SYSTEM (NEW - Feb 2026)
Major product transformation from "analysis tool" to "Blunder Reduction System for 600-1600 players".

**Page Structure Redesign:**
- Coach → **Focus** (TODAY - What to focus on NOW)
- Progress → **Journey** (TREND - How you're evolving)
- Games → **Lab** (DETAIL - What actually happened)

**New Backend Service: `blunder_intelligence_service.py`**
1. **Core Lesson Engine**: Extracts ONE dominant behavioral cause per game
2. **Dominant Weakness Ranking**: "#1 Rating Killer" prioritization
3. **Win-State Analysis**: "63% of blunders happen when winning"
4. **Mistake Heatmap**: Visual board showing where mistakes occur
5. **Rating Impact Estimator**: "Fixing X saves ~Y rating points"
6. **Identity Profile**: "Aggressive but careless" labels
7. **Mission System**: 10-game improvement missions
8. **Milestone Detection**: Achievement triggers

**New API Endpoints:**
- `GET /api/focus` - Focus page data (one dominant weakness)
- `GET /api/journey/v2` - Journey page data (hierarchical analysis)
- `GET /api/lab/{game_id}` - Lab page data with core lesson
- `GET /api/weakness-ranking` - Dominant weakness ranking
- `GET /api/win-state` - Win state analysis
- `GET /api/heatmap` - Mistake heatmap data
- `GET /api/rating-impact` - Rating impact estimate
- `GET /api/identity` - Chess identity profile
- `GET /api/mission` - Current mission
- `GET /api/milestones` - Achievement milestones

**New Frontend Pages:**
- `Focus.jsx` - Stripped-down coach with ONE focus, ONE mission, ONE puzzle
- `JourneyV2.jsx` - Hierarchical weakness display, heatmap, win-state analysis

**Behavioral Pattern System:**
Maps mistake types to human behaviors:
- "attacks_before_checking_threats" → "You attack before checking opponent threats"
- "loses_focus_when_winning" → "You lose focus immediately after gaining advantage"
- "misses_tactical_opportunities" → "You miss winning tactics that were available"
- etc.

## Upcoming Tasks (P0)
1. **"What If" Scenarios** - Enhance InteractiveBoard.jsx to allow users to explore alternative move sequences
2. **Personalized Puzzles** - Generate puzzles based on user's frequent mistake patterns

## Next Tasks (P1)
1. **"Today's Focus" Feature** - Dashboard component highlighting one actionable improvement area based on recent mistake patterns
2. **Populate Tactical Ratio with Real Data** - Update game analysis to store mistake_type in move_evaluations so tactical ratio can track real patterns

## Future/Backlog Tasks (P2-P3)
1. **Aggregate Behavioral Patterns** - Identify recurring patterns across games (e.g., "You hang pieces when ahead")
2. **Production-Ready Cron Job** - Robust background game sync/analysis
3. Add data-testid to InteractiveBoard buttons for better test automation
4. Stockfish persistence fix (currently needs reinstall on environment restart)
5. **Opening Explorer Integration** - Connect user's game statistics to a database of chess openings
6. **Long-term King Safety Metric** - Track and visualize king safety trends across games

## Known Issues
1. Stockfish not persistent between environment restarts (temporary fix: reinstall manually)
2. Some games still need Stockfish analysis

## Test Credentials
- DEV_MODE=true in backend/.env enables dev login
- DEV_USER_ID=user_bdd07038f9c0 (test user with analyzed games)
