# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a full-featured chess coaching application that analyzes games, identifies weaknesses, and provides personalized coaching.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)

## Key Features Implemented

### Dashboard
- Displays games categorized into "Analyzed," "In Queue," "Not Analyzed"
- Shows accuracy, blunders, mistakes stats

### Focus Page (/coach route)
- Personalized coaching with "Missions" based on detected weaknesses
- **NEW: Coach-Like Feedback for Last Game**
  - For wins: Shows "What Worked" and "Still Needs Work"
  - For losses: Shows "Good Plays Despite the Loss" and "The Core Issue"
  - Deterministic logic (no LLM)
- **NEW: Streak-Based Mission System**
  - Progress requires consecutive games meeting criteria
  - Displays `current_streak` and `longest_streak`
  - Shows "Streak reset" message when broken
  - "Next Mission" button when completed

### Lab Page
- In-depth game analysis with move-by-move commentary
- "Strategy" tab with collapsible "Positional Insight (Advanced)" section
- RAG architecture for deep positional coaching

### Progress Page (/progress)
- "Before Coach" vs "After Coach" tabbed comparison
- Tracks baseline performance from when user joined

### Analysis Worker
- Multi-process Stockfish analysis worker
- Processes games from analysis queue asynchronously

### Game Sync System
- Background sync every 6 hours fetches games from chess.com/lichess
- Quick sync every 5 minutes for real-time game monitoring
- Auto-queues games for analysis

## Current Status

### Completed (This Session - Dec 2025)
- ✅ Coach-Like Feedback for Last Game Check
- ✅ Streak-Based Mission System with consecutive tracking
- ✅ "Next Mission" endpoint and button

### Known Issues
- analysis_worker in FATAL state (Stockfish executable issue - reinstall with `sudo apt-get install stockfish -y`)

## Prioritized Backlog

### P0 - Critical
- None (current features complete)

### P1 - High Priority
- Backfill script for historical games missing analysis

### P2 - Medium Priority
- Optimize Stockfish analysis speed (depth 18→12)

### P3 - Low Priority / Refactoring
- Rename `/coach` route to `/focus` for consistency

## Key Files
- `backend/server.py` - Main API server
- `backend/config.py` - Centralized configuration
- `backend/discipline_check_service.py` - Coach-like feedback logic
- `backend/blunder_intelligence_service.py` - Mission streak logic
- `backend/journey_service.py` - Game sync logic
- `backend/analysis_worker.py` - Stockfish analysis worker
- `frontend/src/pages/Focus.jsx` - Focus page UI

## 3rd Party Integrations
- OpenAI GPT-4o-mini (via Emergent LLM Key)
- Stockfish chess engine
- Chess.com API
- Lichess API

## Database Collections
- `users` - User profiles
- `games` - Imported games
- `game_analyses` - Analysis results
- `analysis_queue` - Pending analysis jobs
- `player_profiles` - Coaching profiles
- `mission_completions` - (NEW) Records completed missions

## API Endpoints
- `GET /api/focus` - Focus page data with streak-based missions
- `GET /api/discipline-check` - Last game coach feedback
- `POST /api/focus/next-mission` - Mark mission complete
- `GET /api/sync-status` - Game sync timer status
- `GET /api/progress/v2` - Progress page with baseline comparison

## Mocked Services
- `backend/services/subscription_service.py`

---
*Last Updated: December 2025*
