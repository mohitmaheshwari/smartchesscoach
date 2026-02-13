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
- **NEW: Plan Audit System** - Phase-based execution evaluation
  - Evaluates last game across 5 domains: Opening, Middlegame, Endgame, Tactics, Time
  - Each domain shows: Plan, What Happened (bullet points), Data Snapshot, Verdict
  - Only shows domains where plan existed OR something meaningful happened
  - Execution Score (X/Y domains executed)
  - Verdicts: pass (green), partial (amber), fail (orange)
  - Training focus recommendation
- Streak-Based Mission System with consecutive tracking
- Rating Killer identification with evidence

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
- ✅ Plan Audit System for Focus Page (5 domains: Opening, Middlegame, Endgame, Tactics, Time)
- ✅ Phase-based execution evaluation with deterministic verdicts
- ✅ Coach-Like Feedback for Last Game Check (replaced with Plan Audit)
- ✅ Streak-Based Mission System with consecutive tracking

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
- `backend/plan_audit_service.py` - Plan Audit logic (5 domain audits)
- `backend/discipline_check_service.py` - Legacy discipline check
- `backend/blunder_intelligence_service.py` - Mission streak logic
- `backend/analysis_worker.py` - Stockfish analysis worker
- `frontend/src/pages/Focus.jsx` - Focus page with Plan Audit UI

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
- `mission_completions` - Records completed missions

## API Endpoints
- `GET /api/plan-audit` - Plan Audit data (5 domain evaluation)
- `GET /api/focus` - Focus page data with streak-based missions
- `GET /api/discipline-check` - Legacy discipline check
- `POST /api/focus/next-mission` - Mark mission complete
- `GET /api/sync-status` - Game sync timer status
- `GET /api/progress/v2` - Progress page with baseline comparison

## Mocked Services
- `backend/services/subscription_service.py`

---
*Last Updated: December 2025*
