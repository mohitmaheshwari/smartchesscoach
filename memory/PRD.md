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

### EVIDENCE LAYER & PATTERN DRILL MODE (Feb 2026 - LATEST)
**The Problem Solved**: Users said insights like "You relax when winning" were just abstract "gyaan" (advice). They couldn't see the actual positions where this happened.

**Evidence Layer Implementation:**
- Every insight now includes an **evidence array** with specific positions:
  - `game_id`, `move_number`, `fen_before`
  - `move_played`, `best_move`, `cp_loss`
  - `eval_before`, `opponent`, `mistake_type`
- Users can click "See 7 times this happened" to open Evidence Modal
- Modal shows: Position list (left) + Chessboard preview (right)
- Each position shows: "You had +464.0, You played Ke7, Better was Bxc3"
- "Full Game" and "Analyze" buttons to deep-dive

**Pattern Drill Mode Implementation:**
- "Train This" button starts drill session on user's own mistakes
- System selects 5 positions where user was winning (+2 or more) and blundered
- "What would you play?" prompt with draggable chessboard
- Validates moves against best_move
- Shows result: Correct/Incorrect with score tracking
- "Retry", "Full Game", "Next" navigation

**Pattern Trend Tracking (Closed Loop):**
- Compares last 7 games vs previous 7 games
- Shows trend indicator: "0 → 7 (+100%)" with direction (improving/worsening/stable)
- Enables users to track if their training is working over time

**Clickable Heatmap Evidence:**
- Hot squares on the Mistake Heatmap are now clickable
- Clicking a square opens Evidence Modal showing all mistakes on that square
- "Click hot squares" hint displayed

**New Components:**
- `EvidenceModal.jsx`: Shows evidence positions with board preview
- `DrillMode.jsx`: Interactive training from user's own games
- `TrendIndicator`: Shows pattern improvement/worsening trend

**Updated Components:**
- `Focus.jsx`: Rating Killer card now clickable with "See Examples" and "Train This" buttons
- `JourneyV2.jsx`: 
  - Weakness Ranking cards show evidence count, "See Examples", "Train This", and trend
  - Win State bars clickable to see blunders by game state
  - Mistake Heatmap squares clickable to see position evidence

**New API Endpoints:**
- `GET /api/focus` - Focus page data (one dominant weakness)
- `GET /api/journey/v2` - Journey page data (hierarchical analysis)
- `GET /api/lab/{game_id}` - Lab page data with core lesson
- `GET /api/weakness-ranking` - Dominant weakness ranking
- `GET /api/win-state` - Win state analysis with evidence
- `GET /api/heatmap` - Mistake heatmap data
- `GET /api/rating-impact` - Rating impact estimate
- `GET /api/identity` - Chess identity profile
- `GET /api/mission` - Current mission
- `GET /api/milestones` - Achievement milestones
- **`POST /api/drill/positions`** - Get drill positions filtered by pattern/state

**Behavioral Pattern System:**
Maps mistake types to human behaviors:
- "attacks_before_checking_threats" → "You attack before checking opponent threats"
- "loses_focus_when_winning" → "You lose focus immediately after gaining advantage"
- "misses_tactical_opportunities" → "You miss winning tactics that were available"
- etc.

### LAB PAGE - SURGICAL GAME CORRECTION ENVIRONMENT (Feb 2026 - Phase 1+3+4 COMPLETED)
**Purpose**: Deep correction of a single game. Not diagnosis, not trends - surgical understanding of where control was lost.

**Design Philosophy**: "I understand exactly where I lost control" - not "I read advice"

**Phase 1: Core Structure (COMPLETED)**
- Two-panel design: Board (left) + Tabs (right)
- Sticky header showing: opponent name, rating badge, WIN/LOSS result, accuracy
- Navigation controls: Play, Forward, Back, Flip Board, "Critical Only" toggle
- Move list with color-coded mistakes (red for blunders, orange for mistakes)
- 3 tabs: Summary, Strategy, Mistakes

**Phase 2: Strategy Tab (COMPLETED)**
- Rich content merged from old design with new layout
- Opening section with plan vs execution
- Pawn structure analysis
- Strategic themes with clickable critical moments
- "For Future Games Like This" section with personalized advice
- Scrolling fixed to show all content

**Phase 3: Mistakes Tab (STRUCTURE COMPLETED)**
- Grouped by type: Major Blunders, Hanging Pieces, Missed Tactics, Positional Errors
- Each mistake shows: move number, severity badge, played move vs best move, phase, context
- Clickable - jumps board to that position
- Mini prompt: "What should you have checked here?"
- User move detection fixed using FEN turn indicator

**Phase 4: Practice Mode (COMPLETED - Feb 2026)**
- "Practice Critical Moments" button appears when game has critical positions (cp_loss >= 150)
- Extracts up to 5 critical positions from the game
- Multiple choice format: best move vs played move (shuffled)
- Score tracking with progress bar
- Show hint feature with position context
- Correct/Incorrect feedback with detailed explanation
- Retry option for wrong answers
- Summary screen with performance message and percentage
- Try Again / Done buttons

**Dashboard Enhancements (COMPLETED)**
- Opponent names displayed from PGN extraction
- Opponent ratings shown as badges (e.g., "1340", "1303")
- Filter dropdown: All / Stronger / Equal / Weaker opponents
- Rating comparison based on user's estimated_elo from profile

**API Updates:**
- `GET /api/dashboard-stats` now extracts player names and ratings from PGN
- `GET /api/games/{game_id}` extracts WhiteElo and BlackElo from PGN
- `GET /api/lab/{game_id}` returns core_lesson, strategic_analysis, and move evaluations

**Files Created/Modified:**
- `/app/frontend/src/pages/Lab.jsx` - New Lab page with Practice Mode
- `/app/frontend/src/pages/Dashboard.jsx` - Added filter, opponent ratings
- `/app/backend/server.py` - Enhanced endpoints with PGN extraction
- `/app/backend/blunder_intelligence_service.py` - Improved core_lesson messages

### HUMAN-FRIENDLY EVALUATION DISPLAY (Feb 2026 - COMPLETED)
**The Problem Solved**: Users found raw engine evaluations like "+464.0" or "-9335 cp" (centipawns) confusing and intimidating - it felt like reading raw engine output.

**Solution: `evalFormatter.js` Utility**
Created a utility library that converts engine evaluations to intuitive language:

**Evaluation to Words (`formatEvalWithContext`):**
| Engine Value | Human-Friendly |
|-------------|----------------|
| 0 to 0.3    | Equal position |
| 0.3 to 1.0  | Slight edge / Slightly worse |
| 1.0 to 2.0  | Clear advantage / Clearly worse |
| 2.0 to 4.0  | Winning / Losing |
| 4.0+        | Completely winning / Hopeless |

**Centipawn Loss to Severity (`formatCpLoss`):**
| CP Loss | Human-Friendly |
|---------|----------------|
| 0-50    | Minor inaccuracy |
| 50-100  | Inaccuracy |
| 100-200 | Mistake |
| 200-400 | Serious mistake |
| 400+    | Blunder |

**Total CP Loss for Weaknesses (`formatTotalCpLoss`):**
- Converts centipawns to pawns (100cp = 1 pawn)
- Adds context: "15 pawns lost (major weakness)"

**Components Updated:**
- `EvidenceModal.jsx`: Shows "Completely winning → Ke7 (Blunder)" instead of "+9.3 → -499 cp"
- `DrillMode.jsx`: Shows "You were Completely winning" and "In the game, you played Bb6 (Blunder)"
- `JourneyV2.jsx`: Shows "374 pawns lost (major weakness)" instead of "~37400 cp lost"

## Upcoming Tasks (P0)
- None - all P0 tasks completed

## Next Tasks (P1)
1. **Improvement Trend vs Rating Trend Graph** - Compare blunder rate against rating over time

## Completed Tasks (This Session - Feb 2026)

### P0: "Show Only Critical Moves" Toggle Enhancement (COMPLETED)
- Toggle now shows count: "Critical (1)" when active
- Red styling (bg-red-500) when enabled
- Shows "No critical moves - great job!" message when filtered with no results
- data-testid="critical-toggle" added for testing

### P1: Rating Impact Visualization (COMPLETED)
- Added rating_impact to dashboard-stats endpoint
- Shows prominent "+X" potential gain card on Dashboard
- Message explains which weakness to fix: "Fixing 'X' could save ~Y rating points"
- data-testid="rating-impact-card" for testing

### P1: Multiple Weaknesses Display (COMPLETED)
- Dashboard Focus Areas already showed top weakness
- Now prominently displays "#1 Priority" with occurrence count
- Links to Focus page for details

### Backlog: Behavior Memory System (COMPLETED)
- `find_similar_pattern_games()` function in blunder_intelligence_service.py
- Finds games with same dominant pattern
- Displays "Similar Pattern Detected" section in Lab Summary tab
- Shows opponent name, result, and lesson preview
- Clickable to navigate to that game's Lab page
- data-testid="similar-game-X" for testing

### Backlog: Milestone Celebrations (COMPLETED)
- MilestoneBanner component with animated particles
- Shows unlocked milestones with icon, name, description
- Rarity-based styling (common=green, rare=blue, epic=purple)
- Dismissible via X button
- localStorage-based dismissed state (milestones queue)
- data-testid="milestone-banner" for testing

## Remaining Backlog
1. **Fix Focus Areas to Show Multiple Weaknesses** - Currently only shows one weakness on Dashboard
2. **Rating Impact Estimator Visualization** - Display "Fixing Hanging Pieces would have saved ~86 rating points" prominently
3. **Improvement Trend vs Rating Trend Graph** - Compare blunder rate against rating over time

## Future/Backlog Tasks (P2-P3)
1. **Lab Page Phase 5 (Advanced Features)** - Behavior Memory System (pattern cross-linking), relative strength tracking
2. **Improvement Milestones Celebration** - Banners for achievements like "First 0-blunder game"
3. **Personalized Puzzles from Mistakes** - Generate puzzles based on user's frequent mistake patterns
4. **"What If" Scenarios** - Enhance InteractiveBoard.jsx to allow users to explore alternative move sequences
5. **Opening Explorer Integration** - Connect user's game statistics to a database of chess openings
6. Production-Ready Cron Job - Robust background game sync/analysis
7. Stockfish persistence fix (currently needs reinstall on environment restart)

## Known Issues
1. Stockfish not persistent between environment restarts (temporary fix: reinstall manually)
2. Some games still need Stockfish analysis

## Test Credentials
- DEV_MODE=true in backend/.env enables dev login
- DEV_USER_ID=user_bdd07038f9c0 (test user with analyzed games)
