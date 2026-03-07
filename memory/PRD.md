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
- **33 distinct tags** for classifying mistakes
- **Rating-appropriate filtering**: Tags filtered by player rating level
- **Phase detection**: Tags categorized by game phase (opening, middlegame, endgame)
- **Theory Linking**: Tags linked to 30 theory modules

### 3. Lab Page Enhancements ✅
- **Tags displayed** on critical moments (e.g., "Endgame Technique Error")
- **Phase badges** showing game phase
- **Theory links** with name & key insight
- **Deep strategy loading** when Summary tab is active

### 4. Reflect Page Enhancements ✅
- **Coach encouragement messages** after each reflection submission
- **Celebratory animation** when game review is complete
- **Trophy animation with confetti** for all-reflections-done milestone
- **Multiple encouragement categories**: reflection_submitted, game_complete, all_done

### 5. Prescribed Training Enhancements ✅
- **"Why This Puzzle?"** section explaining the connection to weakness
- **Encouraging feedback** on correct/incorrect answers
- **Streak counter** with special messages for 3+ streak
- **Category-specific encouragements**: correct, incorrect, streak, complete

### 6. Rolling Evolution Progress ✅
- **Rolling windows**: Compare recent 10 vs previous 10 games
- **Opening performance tracking**: Stats by opening name
- **Real-time trends**: Dynamic progress indicators

### 7. Server.py Refactoring ✅ (Ongoing)
- **Extracted modules**:
  - `routes/auth.py`: 9 endpoints
  - `routes/feedback.py`: 10 endpoints (including batch processing)
  - `routes/games.py`: 7 endpoints
  - `routes/lab.py`: 4 endpoints (lab page, deep-strategy, mistake context, explain)
  - `routes/reflect.py`: 11 endpoints (V1 engine, post-loss, pending, submit)
  - `routes/training.py`: 13 endpoints (sessions, cards, prescribed, habits)
  - `routes/coach.py`: 17 endpoints (coach state, memory, play, analytics)
  - `routes/journey.py`: 11 endpoints (dashboard, account linking, sync, intelligence)
  - `routes/cognitive.py`: 18 endpoints (cognitive gaps, patterns, TSI, training priority)
  - `routes/behavioral.py`: 9 endpoints (behavioral analysis, missions, reanalysis)
  - `routes/notifications.py`: 8 endpoints (notifications, push, device registration)
- **Total extracted**: 117 endpoints
- **Lines in server.py**: 11,600 (down from 14,560 - **2,960 lines removed**)
- **Remaining**: ~220 endpoints in server.py
- **Candidates for next extraction**: missions (8), settings (5)

### 8. Pattern Collections Reconciliation ✅
- **smart_patterns**: 11 patterns (active, primary system)
- **learned_rules**: 13 patterns (deprecated, migrated useful ones)
- **Migrated**: 2 tactical patterns from learned_rules to smart_patterns

### 9. Tag Feedback Integration ✅ (NEW)
- **Created**: `services/tag_feedback_service.py` - Connects 33 game tags to auto-correction
- **New endpoints**:
  - `POST /api/coach/pattern-learning/tag-feedback` - Submit tag corrections
  - `GET /api/coach/pattern-learning/tag-feedback/stats` - Tag correction statistics
  - `GET /api/coach/pattern-learning/tag-feedback/pending` - Pending corrections
  - `GET /api/coach/pattern-learning/available-tags` - List all 33 game tags
- **Enhanced**: `game_tagging_service.py` with `tag_critical_moment_with_corrections()`
- **New collection**: `tag_correction_patterns` - Stores learned tag corrections
- **How it works**:
  1. User disagrees with a tag (e.g., "This isn't a missed_fork, it's a hung_piece")
  2. Feedback creates a `tag_correction_pattern` with position features
  3. Future tagging checks for corrections before applying tags
  4. System learns and improves over time

## API Endpoints

### Pattern Learning (Enhanced)
- `POST /api/coach/pattern-learning/feedback` - Submit explanation corrections
- `POST /api/coach/pattern-learning/tag-feedback` - Submit tag corrections (NEW)
- `GET /api/coach/pattern-learning/stats` - System statistics
- `GET /api/coach/pattern-learning/tag-feedback/stats` - Tag correction stats (NEW)
- `GET /api/coach/pattern-learning/available-tags` - List 33 game tags (NEW)
- `POST /api/coach/pattern-learning/process-pending-feedback` - Batch process feedback
- `GET /api/coach/pattern-learning/pending-feedback` - Get pending items

### Games Module
- `GET /api/games` - List user's games
- `GET /api/games/analyzed` - List analyzed games with stats
- `GET /api/games/blunders` - Get all blunders
- `GET /api/games/best-moves` - Get best moves
- `GET /api/games/{game_id}` - Get single game details
- `GET /api/games/{game_id}/analysis-status` - Analysis status
- `POST /api/games/{game_id}/reanalyze` - Queue for re-analysis

## Verified Bug Fixes

### All Previously Reported Issues ✅
- Reflect page loop - Fixed and verified
- Prescribed Training display - Fixed and verified
- Opening name import - Fixed with ECO mapping
- Deep strategy API bug - Fixed undefined variables

## Upcoming Tasks (Prioritized)

### P1 - High Priority
1. Continue server.py refactoring (extract lab, coach, training routes)

### P2 - Medium Priority
1. Reconcile learned_rules vs smart_patterns collections
2. Enhance Play with Coach (memory of past games, visual hints)

### Future/Backlog
- Identity Formation Layer (long-term playstyle evolution)
- B2B Model for Coaches
- Mobile App

## Database Collections

| Collection | Count | Purpose |
|------------|-------|---------|
| games | ~300 | Imported chess games |
| game_analyses | ~300 | Stockfish analysis results |
| smart_patterns | 11 | Active learned pattern rules |
| learned_rules | 13 | Legacy rules (deprecated, migrated) |
| pattern_feedback | 31 | User corrections (26 processed, 5 skipped) |
| verified_corrections | 32 | Applied corrections |

## Tech Stack
- **Backend**: FastAPI + Python
- **Frontend**: React + Shadcn/UI + Framer Motion
- **Database**: MongoDB
- **Chess Analysis**: Stockfish via python-chess
- **AI**: OpenAI GPT-4o-mini for explanations

## User Language
Plain, simple, direct Indian-English

---
*Last updated: 2026-03-07*
