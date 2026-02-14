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

### Adaptive Intensity Escalation (NEW)
When a domain is missed consecutively, the system automatically escalates:
- **2 consecutive misses**: Increase intensity, simplify rules
- **4 consecutive misses**: Force micro-habit level (intensity 3)
- **3 consecutive executions**: Mark domain as stable, reduce verbosity

Intensity Levels:
- **Level 1**: Outcome focus (e.g., "convert winning positions")
- **Level 2**: Behavior focus (e.g., "pause 5 seconds when +1.5")
- **Level 3**: Micro-habit (e.g., "ONE RULE: trade a piece when ahead")

UI Indicators:
- Escalated domains show orange border + "⚡ Escalated" badge
- L2/L3 intensity indicator shown
- At L3: "Micro-habit mode" warning box

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

## Bug Fixes (February 2026)
- **Fixed**: Opening names now display as human-readable names (e.g., "Sicilian Defense") instead of ECO codes (e.g., "B30")
  - Updated `_extract_opening_name()` to handle ECO codes in game object's `opening` field
  - Fixed game-analysis matching in `calculate_opening_stability()` using game_id lookup instead of index
  - Fixed field name from `classification` to `evaluation` for blunder detection
  - Fixed `games[-30:]` to `games[:30]` to get most recent games instead of oldest
- **Fixed**: Plan Audit correctly shows "Played: Philidor Defense" instead of "Played: unknown"
- **Fixed**: Plan Audit now shows opponent name and game result (e.g., "vs Niwzey · WIN (white)")
- **Fixed**: Analysis worker now auto-checks and installs Stockfish if missing
- **Fixed**: Added 10-minute timeout for stuck analysis jobs - automatically reset for retry or marked as failed
- **Fixed**: Plan Audit now shows the latest analyzed game instead of cached old game
- **Improved**: Deep tactical analysis for mistake explanations
  - Added piece trapping detection (e.g., "Trapped queen" instead of misleading "fork")
  - Added mobility restriction analysis
  - Added multi-threat detection
  - Now validates if "fork" targets are actually capturable before reporting
- **NEW (Feb 2026)**: Focus Items from Last Game - Critical Tactical Patterns
  - Extracts tactical patterns (piece traps, forks, etc.) missed in the last game
  - Creates actionable "Focus Items" in the next game's plan
  - Displays in new "FOCUS FROM LAST GAME" section on Focus page
  - Closes the feedback loop: Analyze Mistake → Create Plan to Fix Mistake
- **NEW (Feb 2026)**: Before/After Coach Pattern Comparison
  - Journey page tabs now show DIFFERENT weakness data based on selected period
  - "Before Coach" tab shows weaknesses from first 10 games (baseline)
  - "After Coach" tab shows weaknesses from last 25 games (current)
  - "Your Growth" tab shows improvement/regression for each weakness
  - Pattern comparison tracks: fixed weaknesses, improved weaknesses, new weaknesses
  - Blunder context (when winning/equal/losing) also changes per tab

## Prioritized Backlog

### P1 - High Priority
- Backfill script for historical games missing analysis

### P2 - Medium Priority
- Optimize Stockfish analysis speed (depth 18→12)

### P3 - Low Priority
- Rename `/coach` route to `/focus`

---
*Last Updated: February 2026*
