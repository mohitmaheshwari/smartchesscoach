# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a full-featured chess coaching application that analyzes games, identifies weaknesses, and provides personalized coaching with a GM-coach style coaching loop.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)

## GOLD FEATURE: Coaching Loop System

### Plan → Play → Audit → Adjust

The core differentiator of ChessGuru.ai. A GM-coach style system that:
- "I gave you a plan"
- "I watched your game"
- "You followed / didn't follow"
- "Here's the adjusted plan"

### Round Preparation (Next Game Plan)
- 5 domains: Opening, Middlegame, Tactics, Endgame, Time
- Each domain has:
  - Priority (primary/secondary/baseline)
  - Goal (1-line coach objective)
  - Rules (4 for primary, 2 for secondary, 1 for baseline)
  - Success criteria (measurable)
- Training block with intensity (1-3)
- Personalized based on: rating band, behavior patterns, fundamentals profile, opening stability

### Plan Audit (Last Game)
- Evaluates last game against EXACT previous plan
- Each domain shows:
  - Status (executed/partial/missed/n/a)
  - Data points (computed facts)
  - Evidence links (clickable move references with eval delta)
  - Coach note (deterministic feedback)
- Execution score (X/Y domains executed)
- Game result displayed

### PlanCard Schema (Single Source of Truth)
```json
{
  "plan_id": "uuid",
  "training_block": {"name": "...", "intensity": 1-3},
  "cards": [
    {
      "domain": "opening|middlegame|tactics|endgame|time",
      "priority": "primary|secondary|baseline",
      "goal": "1-line objective",
      "rules": ["..."],
      "success_criteria": [{"metric": "...", "op": "<=", "value": 0}],
      "audit": {"status": "...", "data_points": [], "evidence": [], "coach_note": "..."}
    }
  ]
}
```

### Deterministic Logic
- All plan selection, criteria evaluation, compliance scoring is deterministic
- No LLM dependency for correctness
- Intensity auto-adjusts based on consecutive misses

## Other Key Features

### Focus Page (/coach route)
- Round Preparation section (top)
- Plan Audit section
- Rating Killer with evidence
- Streak-based Mission system
- Opening Guidance

### Lab Page
- In-depth game analysis
- Move-by-move commentary
- Strategy tab with positional insights

### Progress Page (/progress)
- Before Coach vs After Coach comparison
- Baseline tracking from when user joined

### Dashboard
- Game categorization (Analyzed, In Queue, Not Analyzed)
- Stats display

## API Endpoints

### Coaching Loop (GOLD)
- `GET /api/round-preparation` - Next game plan
- `GET /api/plan-audit` - Last game audit
- `POST /api/coaching-loop/audit-game/{game_id}` - Trigger audit for specific game
- `POST /api/coaching-loop/regenerate-plan` - Force new plan
- `GET /api/coaching-loop/profile` - Get all personalization inputs

### Focus & Analysis
- `GET /api/focus` - Focus page data
- `GET /api/discipline-check` - Legacy discipline check
- `GET /api/coach/today` - Today's coaching data

### Games & Journey
- `GET /api/progress/v2` - Progress page data
- `GET /api/sync-status` - Sync timer status

## Database Collections
- `users` - User profiles
- `games` - Imported games
- `game_analyses` - Analysis results
- `user_plans` - Coaching plans (NEW)
- `analysis_queue` - Pending analysis
- `mission_completions` - Completed missions

## Key Files
- `backend/coaching_loop_service.py` - GOLD FEATURE logic
- `backend/server.py` - API endpoints
- `backend/blunder_intelligence_service.py` - Weakness detection
- `frontend/src/pages/Focus.jsx` - Focus page with coaching loop UI

## Mocked Services
- `backend/services/subscription_service.py`

## Known Issues
- analysis_worker FATAL state (Stockfish needs reinstall: `sudo apt-get install stockfish -y`)

## Prioritized Backlog

### P1 - High Priority
- Backfill script for historical games missing analysis

### P2 - Medium Priority
- Optimize Stockfish analysis speed (depth 18→12)

### P3 - Low Priority
- Rename `/coach` route to `/focus`

---
*Last Updated: December 2025*
