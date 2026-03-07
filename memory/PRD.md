# Chess Insight Hub - Product Requirements Document

## Vision
A hyper-personalized, data-driven chess coaching application that moves beyond generic engine analysis to provide Socratic-style, contextual feedback tailored to the user's individual playstyle.

## Core Features (Implemented)

### 1. Self-Learning Pattern Recognition System ✅
- **Smart Patterns Collection**: 9 learned patterns (fork, king_trapped, custom)
- **Batch Processing**: New endpoint to process pending feedback into smart patterns
- **Pattern Matching**: Matches new positions against learned rules during analysis
- **Status**: 31 feedback items processed (26 successful, 5 skipped without explanations)

### 2. Rich Game Tagging System ✅
- **33 distinct tags** for classifying mistakes:
  - Tactical: one_move_blunder, hung_piece, missed_fork, captured_in_fork, missed_pin, etc.
  - Positional: weakened_pawn_structure, bad_piece_trade, passive_move
  - Calculation: didnt_see_far_enough, missed_zwischenzug
  - Opening: early_queen_adventure, development_neglected
  - Endgame: endgame_technique_error, king_activity_mistake
- **Rating-appropriate filtering**: Tags filtered by player rating level
- **Phase detection**: Tags categorized by game phase (opening, middlegame, endgame)

### 3. Theory Linking ✅
- **30 theory modules** mapped to game tags
- **TAG_TO_THEORY_MAP**: Links tags to relevant instructional content
- **Lab Page Integration**: Tags and theory links displayed in Guided Analysis mode

### 4. Rolling Evolution Progress ✅
- **Rolling windows**: Compare recent 10 vs previous 10 games
- **Opening performance tracking**: Stats by opening name
- **Real-time trends**: Dynamic progress indicators

### 5. Server.py Refactoring (In Progress)
- **Extracted modules**:
  - `routes/auth.py`: 9 endpoints (login, logout, OAuth, sessions)
  - `routes/feedback.py`: 10 endpoints (pattern learning, stats, processing)
  - `routes/games.py`: 7 endpoints (list, details, blunders, best-moves)
- **Lines removed**: ~320 lines from server.py (14,560 → 14,240)
- **Remaining**: ~271 endpoints still in server.py monolith

## API Endpoints

### Pattern Learning
- `POST /api/coach/pattern-learning/feedback` - Submit pattern feedback
- `GET /api/coach/pattern-learning/stats` - System statistics
- `POST /api/coach/pattern-learning/process-pending-feedback` - Batch process feedback
- `GET /api/coach/pattern-learning/pending-feedback` - Get pending items

### Games (New Module)
- `GET /api/games` - List user's games
- `GET /api/games/analyzed` - List analyzed games with stats
- `GET /api/games/blunders` - Get all blunders
- `GET /api/games/best-moves` - Get best moves
- `GET /api/games/{game_id}` - Get single game details
- `GET /api/games/{game_id}/analysis-status` - Analysis status
- `POST /api/games/{game_id}/reanalyze` - Queue for re-analysis

### Progress & Evolution
- `POST /api/coach/evolution/rolling` - Get rolling window progress
- `POST /api/coach/evolution/openings` - Get opening performance

## Verified Bug Fixes

### 1. Reflect Page Loop ✅
- **Issue**: Page was stuck in infinite loading loop
- **Status**: Fixed and verified working

### 2. Prescribed Training Display ✅
- **Issue**: Puzzles not displaying properly
- **Status**: Fixed and verified working

### 3. Opening Name Import ✅
- **Issue**: Games imported without opening names
- **Status**: Fixed with ECO-to-name mapping, 296 games backfilled

### 4. Deep Strategy API Bug ✅
- **Issue**: Undefined variables (positions, i, prev_eval)
- **Status**: Fixed, tags and theory now displaying correctly

## Upcoming Tasks (Prioritized)

### P1 - High Priority
1. Continue server.py refactoring (extract coach, lab, training routes)
2. Enhance Reflect page (coach encouragement, celebratory animations)
3. Enhance Prescribed Training (Why this puzzle? context)

### P2 - Medium Priority
1. Enhance Play with Coach (memory of past games, visual hints)
2. Reconcile learned_rules vs smart_patterns collections

### Future/Backlog
- Identity Formation Layer (long-term playstyle evolution)
- B2B Model for Coaches
- Mobile App

## Database Collections

| Collection | Count | Purpose |
|------------|-------|---------|
| games | ~300 | Imported chess games |
| game_analyses | ~300 | Stockfish analysis results |
| smart_patterns | 9 | Learned pattern rules |
| learned_rules | 13 | Older rule system |
| pattern_feedback | 31 | User corrections (26 processed) |
| verified_corrections | 32 | Applied corrections |

## Tech Stack
- **Backend**: FastAPI + Python
- **Frontend**: React + Shadcn/UI
- **Database**: MongoDB
- **Chess Analysis**: Stockfish via python-chess
- **AI**: OpenAI GPT-4o-mini for explanations

## User Language
Plain, simple, direct Indian-English

---
*Last updated: 2026-03-07*
