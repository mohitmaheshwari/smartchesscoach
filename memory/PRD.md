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

### Focus Page
- Personalized coaching with "Missions" based on detected weaknesses
- Mission progress tracking (fixed - working correctly)

### Lab Page
- In-depth game analysis with move-by-move commentary
- "Strategy" tab with collapsible "Positional Insight (Advanced)" section
- RAG architecture for deep positional coaching

### Analysis Worker
- Multi-process Stockfish analysis worker
- Processes games from analysis queue asynchronously

### Game Sync System
- Background sync every 6 hours fetches games from chess.com/lichess
- Auto-queues games for analysis
- NOT real-time monitoring

## Current Status

### Completed (This Session)
- ✅ Positional Coaching Layer (RAG-backed) - full feature
- ✅ Bug Fix: Mission progress calculation
- ✅ Bug Fix: Stuck game in analysis queue (Stockfish path)
- ✅ Real-time game monitoring (5-minute quick sync)

### Known Issues
- analysis_worker in FATAL state - needs investigation

## Prioritized Backlog

### P0 - Critical
- Real-time game monitoring service (if user requests)

### P1 - High Priority
- Backfill script for 76 historical games missing analysis

### P2 - Medium Priority
- Optimize Stockfish analysis speed (depth 18→12)

### P3 - Low Priority / Refactoring
- Rename `/coach` route to `/focus` for consistency

## Key Files
- `backend/server.py` - Main API server
- `backend/config.py` - Centralized configuration
- `backend/journey_service.py` - Game sync logic
- `backend/analysis_worker.py` - Stockfish analysis worker
- `backend/blunder_intelligence_service.py` - Blunder analysis + positional coaching
- `backend/knowledge_base/` - RAG knowledge documents
- `frontend/src/pages/Lab.jsx` - Game analysis UI
- `frontend/src/pages/Focus.jsx` - Coaching missions UI

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

## Mocked Services
- `backend/services/subscription_service.py`

---
*Last Updated: December 2025*
