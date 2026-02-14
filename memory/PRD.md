# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a full-featured chess coaching application that analyzes games, identifies weaknesses, and provides personalized coaching with a GM-coach style coaching loop.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)

## GOLD FEATURE: Deterministic Adaptive Coach (v2.0) - IMPLEMENTED

### The Core Principle
Two different players (800-rated vs 1800-rated) should see entirely different plans, strictness thresholds, and failure interpretations. No generic templates - everything is deterministically computed from player data.

### Rating Bands (Granular - 4 bands)
- **600-1000 (beginner_low)**: Focus on not hanging pieces
- **1000-1400 (beginner_high)**: Basic tactics and simple plans  
- **1400-1800 (intermediate)**: Positional understanding
- **1800+ (advanced)**: Nuanced strategic advice

Each band has different:
- Evaluation thresholds (blunder, mistake, acceptable loss)
- Success criteria values
- Language and rule complexity

### Training Intensity (5 Levels)
- **Level 1 (Light)**: Outcome focus, gentle reminders
- **Level 2 (Normal)**: Clear behavior rules (DEFAULT)
- **Level 3 (Focused)**: Simplified rules, higher stakes language
- **Level 4 (Intense)**: Micro-habits, single rule per domain
- **Level 5 (Critical)**: Emergency mode - ONE rule for entire game

Intensity auto-adjusts based on consecutive misses/executions:
- Each consecutive miss: +1 intensity (max 5)
- 4+ consecutive misses: Force level 5
- Each consecutive execution: -1 intensity (min 1)
- 3+ consecutive executions: Back to level 1

### The Adaptive Loop
1. **Generate Plan** → User plays game
2. **Audit Game** → For each domain: executed/partial/missed
3. **Adjust Intensity** → Based on miss streaks
4. **Generate Next Plan** → With new intensity levels

### Plan Generation Inputs (Last 25 Games)
1. **Rating Band** - Determines thresholds and language
2. **Fundamentals Profile** - Scores 0-100 for Opening, Middlegame, Tactics, Endgame, Time
3. **Weakness Patterns** - Primary (e.g., piece_safety) and Secondary (e.g., advantage_collapse)
4. **Opening Stability** - Which openings are most stable for user
5. **Domain History** - Consecutive misses/executions per domain
6. **Critical Insights** - Tactical patterns from last game's deep analysis

### Round Preparation (Next Game Plan)
- 5 domains: Opening, Middlegame, Tactics, Endgame, Time
- Each domain has:
  - Priority (primary/secondary/baseline) based on weakness patterns
  - Goal (intensity-specific one-liner)
  - Rules (count based on intensity: 4/3/2/1/1)
  - Success criteria (rating-band adjusted)
  - Escalation info (is_escalated, consecutive_misses)
  - Intensity level (1-5)
- Training block with name, intensity (1-5), description
- Focus Items from last game's critical mistakes
- Situational Rules (when ahead, when behind, time pressure)

### Plan Audit (Last Game Evaluation)
- Evaluates game against EXACT previous plan
- Each domain shows:
  - Status (executed/partial/missed/n/a)
  - Data points (computed facts like "Had winning position: Yes")
  - Evidence links (clickable move references with eval delta)
  - Coach note (deterministic feedback)
- Audit summary with execution score (X/Y), opponent, result, color, opening
- Evidence-backed: Every "missed" item links to specific move

### PlanCard Schema (v2.0)
```json
{
  "plan_id": "uuid",
  "rating_band": "beginner_high",
  "rating_label": "1000-1400",
  "training_block": {"name": "Piece Safety", "intensity": 3, "intensity_name": "Focused"},
  "cards": [
    {
      "domain": "tactics",
      "priority": "primary",
      "intensity": 3,
      "intensity_name": "Focused",
      "goal": "CCT every move: Checks, Captures, Threats",
      "rules": ["Look for opponent's threats first", "Check all pieces defended"],
      "success_criteria": [{"metric": "blunders", "op": "<=", "value": 1}],
      "escalation": {"is_escalated": true, "consecutive_misses": 2},
      "audit": {"status": null, "data_points": [], "evidence": [], "coach_note": null}
    }
  ],
  "focus_items": [{"pattern": "piece_trap", "move_number": 24, "goal": "..."}],
  "situational_rules": [{"condition": "When ahead material", "rules": ["Trade pieces"]}]
}
```

### GM Tone
- Concise, direct, no praise
- Max 4 bullets per domain
- At intensity 4-5: Single micro-habit rule only
- Examples: "CCT every move", "KING TO CENTER", "ONE RULE: trade when ahead"

## API Endpoints

### Coaching Loop
- `GET /api/round-preparation` - Next game plan (deterministic)
- `GET /api/plan-audit` - Last game evaluation
- `GET /api/coaching-loop/profile` - Full coaching profile with all inputs
- `POST /api/coaching-loop/regenerate-plan` - Force new plan
- `POST /api/coaching-loop/audit-game/{game_id}` - Manual audit trigger

## Key Files
- `backend/deterministic_coach_service.py` - Core deterministic logic (NEW)
- `backend/coaching_loop_service.py` - Legacy service (deprecated for core loop)
- `frontend/src/pages/Focus.jsx` - Focus page UI

## Other Features

### Focus Page (/coach and /focus routes)
- Round Preparation section with training block badge
- Domain cards with L1-L5 intensity indicators
- Escalation warnings ("CRITICAL: One rule for game")
- Plan Audit section with execution score
- Evidence links to game moves
- Focus Items from last game

### Progress Page (/progress)
- Before Coach vs After Coach comparison
- Separate baseline and current weakness patterns

### Lab Page
- In-depth game analysis with move-by-move commentary

## Technical Notes
- All MongoDB responses exclude _id field
- Plan inserted to DB copies dict first to avoid _id contamination
- Domain history tracks last 10 audited plans
- Fundamentals calculated from last 25 analyzed games

## Completed Work (Feb 2026)
- [x] Deterministic Adaptive Coach implementation
- [x] 5-level intensity system
- [x] Granular rating bands (4 bands)
- [x] Evidence-backed audits with move links
- [x] Domain history tracking
- [x] Focus Items from last game
- [x] GM-style concise tone
- [x] Testing: 25 backend tests, full frontend validation

## Upcoming/Future Tasks
- P1: Route cleanup (both /coach and /focus now work)
- P2: Historical game analysis script
- P3: Optimize Stockfish depth (18 → 12-14)
