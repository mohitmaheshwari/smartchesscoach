# ChessGuru - Complete Application Documentation

**Version:** P2.8  
**Last Updated:** March 3, 2026  
**Status:** Production Ready

---

## Table of Contents

1. [Product Overview](#product-overview)
2. [User Journey](#user-journey)
3. [System Architecture](#system-architecture)
4. [The 5 Coaching Layers](#the-5-coaching-layers)
5. [Core Services Deep Dive](#core-services-deep-dive)
6. [API Reference](#api-reference)
7. [Data Models](#data-models)
8. [Frontend Components](#frontend-components)
9. [Configuration & Environment](#configuration--environment)
10. [Testing](#testing)
11. [Deployment](#deployment)

---

## Product Overview

### What is ChessGuru?

ChessGuru is a **hyper-personalized, data-driven chess coaching application** that goes beyond traditional engine analysis. Unlike Chess.com or Lichess which show what went wrong, ChessGuru shows **why it went wrong behaviorally** and **enforces habit change**.

### Core Philosophy

> "Not an analyzer. Not a mentor simulator. A **discipline system**."

The coach feels like a calm, direct, Indian mentor who:
- Detects behavioral patterns (not just tactical errors)
- Remembers your history across games
- Adapts teaching style to your maturity
- Enforces specific rules through Focus Locks
- Injects theory concepts when patterns repeat

### What Makes It Different

| Traditional Analysis | ChessGuru |
|---------------------|-----------|
| Shows engine best move | Shows why YOU made that choice |
| Generic advice | Personalized to your rating & patterns |
| Passive feedback | Active enforcement via Focus Lock |
| One-time lesson | Tracks pattern across games |
| Treats each game separately | Memory continuity across sessions |

---

## User Journey

### 1. Onboarding
```
User → Links Chess.com account → Games sync automatically
```

### 2. Game Analysis Flow
```
Game played → Queued for analysis → Stockfish + Behavioral tagging → 
Coach commentary generated → Module trigger detected → Stored
```

### 3. Lab Page (Game Review)
```
User opens game → Sees "If You Fix Only One Thing" →
Evidence (move + cp loss) → Rule to follow →
Optional: Concept explanation, Coach's full take
```

### 4. Focus Lock Activation
```
3+ triggers of same pattern → Auto-lock activated →
User must play 5 games following the rule →
Compliance measured each game → Complete at 75%+ avg
```

### 5. Dashboard Hierarchy
```
Focus Lock Active? → Show Focus Lock Card (overrides everything)
Else Breakthrough Signal? → Show Weekly Signal Card
Else → Show normal dashboard
```

---

## System Architecture

### Tech Stack

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  React 18 + Vite + TailwindCSS + Shadcn/UI                  │
│  Port: 3000                                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        BACKEND                               │
│  FastAPI + Python 3.11                                       │
│  Port: 8001 (internal), /api/* (external)                   │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│    MongoDB       │ │   Stockfish  │ │  OpenAI GPT-4o   │
│  (All data)      │ │  (Analysis)  │ │  (Commentary)    │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

### Directory Structure

```
/app
├── backend/
│   ├── server.py                 # Main FastAPI app (~13k lines)
│   ├── analysis_worker.py        # Background job processor
│   ├── stockfish_service.py      # Stockfish integration
│   ├── llm_service.py            # GPT integration via Emergent
│   ├── config.py                 # Configuration
│   │
│   ├── coach_state/              # Core coaching engine
│   │   ├── coach_narrative_engine.py    # Story generation
│   │   ├── coach_memory_service.py      # Long-term memory
│   │   ├── lesson_resolver.py           # Lesson selection
│   │   ├── teaching_style_service.py    # Adaptive tone
│   │   ├── breakthrough_service.py      # Phase detection
│   │   ├── focus_lock_service.py        # Discipline enforcement
│   │   ├── theory_modules.py            # 30 theory modules
│   │   ├── module_trigger_service.py    # Pattern injection
│   │   └── tests/                        # Unit tests
│   │
│   ├── analysis/                 # Intent recognition
│   │   ├── intent_recognition_service.py
│   │   └── intent_quality_calibrator.py
│   │
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.js                # Routes & auth
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx     # Main dashboard
│   │   │   ├── Lab.jsx           # Game analysis (redesigned)
│   │   │   ├── Games.jsx         # Game list
│   │   │   ├── Training.jsx      # Drills
│   │   │   └── ...
│   │   │
│   │   ├── components/
│   │   │   ├── Home/
│   │   │   │   ├── FocusLockCard.jsx      # Step 9
│   │   │   │   ├── CoachWeeklySignalCard.jsx  # Step 8
│   │   │   │   └── ...
│   │   │   ├── Lab/
│   │   │   │   ├── OneThingFix.jsx        # Step 10
│   │   │   │   └── ConceptCard.jsx        # Step 10
│   │   │   └── ui/               # Shadcn components
│   │   │
│   │   └── utils/
│   │
│   └── package.json
│
└── memory/
    ├── PRD.md                    # Product requirements
    ├── CHANGELOG.md              # Version history
    └── app.md                    # This file
```

---

## The 5 Coaching Layers

### Layer 1: Tactical Analysis (Steps 0-4)
**What:** Stockfish-powered move evaluation  
**Output:** Accuracy %, blunders, mistakes, best moves

```python
# stockfish_service.py
analyze_game_with_stockfish(pgn, user_color, depth=18)
# Returns: move_evaluations, accuracy, critical_moments
```

### Layer 2: Behavioral Memory (Step 5)
**What:** Long-term pattern tracking across games  
**Output:** Recurring weaknesses, improvement trends

```python
# coach_memory_service.py
class CoachMemory:
    lesson_history: List[LessonEvent]      # Last 50 lessons
    recurring_patterns: Dict[str, int]     # Pattern frequencies
    improvement_areas: List[str]           # Active focus areas
    last_advice_given: Dict                # Prevents repetition
```

**Key Insight:** If user makes same mistake 3+ times, it becomes a "recurring pattern" and triggers stronger intervention.

### Layer 3: Phase Awareness (Steps 6-8)
**What:** Understanding player's current learning phase  
**Output:** NORMAL, PLATEAU, BREAKTHROUGH, CONFIDENCE_ILLUSION, TILT_RISK

```python
# breakthrough_service.py
def get_breakthrough_signal_for_user(analyses, memory) -> BreakthroughSignal:
    # Analyzes 5/10/20 game windows
    # Returns phase + confidence + recommended action
```

**Phase Definitions:**
- **NORMAL:** Steady progress, no intervention needed
- **PLATEAU:** Skill stagnant, needs new input
- **BREAKTHROUGH:** Rapid improvement, reinforce good habits
- **CONFIDENCE_ILLUSION:** Winning but with bad habits
- **TILT_RISK:** Losing streak, needs recovery

### Layer 4: Discipline Enforcement (Step 9)
**What:** Focus Lock system that forces habit change  
**Output:** Locked rule for N games, compliance tracking

```python
# focus_lock_service.py
class FocusLock:
    lesson_key: str           # FORCING_BLIND, etc.
    state: LockState          # ACTIVE, EXTENDED, STRICT, COMPLETED, FAILED
    games_required: int       # Usually 5
    games_completed: int
    compliance_scores: List[float]
    strict_mode: bool
    failed_cycles: int        # For escalation
```

**Compliance Calculation:**
| Lesson | How It's Measured |
|--------|-------------------|
| FORCING_BLIND | Did user check forcing moves before deciding? |
| STOPPED_CALCULATION_EARLY | Did user calculate deep enough at critical moments? |
| THREAT_VERIFICATION | Did user verify opponent's threats? |

**Lock Lifecycle:**
```
ACTIVE → (complete 5 games)
  → compliance ≥ 75% → COMPLETED ✓
  → compliance < 75% → EXTENDED (+3 games)
    → still failing + declining → STRICT mode
    → 2 failures → FAILED → Deep Session
```

### Layer 5: Pattern Injection (Step 10)
**What:** Theory module detection and auto-lock  
**Output:** Injected concept + potential auto-lock

```python
# theory_modules.py - 30 modules across 5 categories
CATEGORIES:
  A. Tactical Awareness (8): LPDO, Forcing Moves, Overloaded Defender...
  B. Conversion (6): Simplify When Ahead, Avoid Counterplay...
  C. Endgame (6): Square Rule, Opposition, Rook Behind Passer...
  D. Positional (6): Good vs Bad Bishop, Knight Outposts...
  E. Opening (4): Castle Before Attacking, Fight for Center...
```

**Auto-Lock Guardrails:**
1. Must have 3+ triggers of same module in 10 games
2. Must be high-confidence trigger (≥300cp swing)
3. Must not have active lock already

---

## Core Services Deep Dive

### Analysis Worker (`analysis_worker.py`)

Background job processor that handles game analysis.

```python
def process_job(db, job):
    # Phase 1: Stockfish analysis
    stockfish_result = analyze_game_with_stockfish(pgn, user_color, depth=18)
    
    # Phase 2: Intent recognition
    for move in move_evaluations:
        intent = recognize_intent(fen, san, best_move, user_color)
        move["intent_type"] = intent.intent_type
        move["intent_quality"] = calibrate_with_forcing_context(...)
    
    # Phase 3: Coach narrative generation
    coach_summary = generate_game_coach_summary(analysis_data)
    
    # Phase 4: Focus Lock compliance update
    update_focus_lock_compliance(db, user_id, move_evaluations)
    
    # Phase 5: Module trigger detection
    detect_and_inject_module(db, user_id, game_id, user_rating)
```

### Focus Lock Service (`focus_lock_service.py`)

Handles all discipline enforcement logic.

```python
# Create a new lock
lock = create_focus_lock("FORCING_BLIND", games=5)

# After each game
compliance = calculate_compliance(lesson_key, move_evaluations)
updated_lock = update_lock_after_game(lock, compliance, trend)

# Check UI state
ui_state = get_lock_ui_state(lock)  # Returns dict for frontend

# Check deep session trigger
if should_trigger_deep_session(lock):  # failed_cycles >= 2
    trigger_deep_session(user_id)
```

### Module Trigger Service (`module_trigger_service.py`)

Detects and injects theory modules.

```python
# Detect module for a game
trigger = detect_module_for_game(game_analysis, user_rating, recent_injections)
# Returns: ModuleTrigger with module_key, rule, evidence, confidence

# Check auto-lock condition
should_lock, count = check_auto_lock_condition(
    module_key, confidence, recent_triggers, has_active_lock
)
# Returns: (True/False, trigger_count)

# Map module to Focus Lock lesson
lesson = get_focus_lock_lesson_for_module("SIMPLIFY_WHEN_AHEAD")
# Returns: "STOPPED_CALCULATION_EARLY"
```

---

## API Reference

### Authentication
All endpoints require session cookie: `Cookie: session_token=<token>`

### Game Analysis

```http
GET /api/games
# List user's games with analysis status

GET /api/games/{game_id}
# Get single game with full analysis

POST /api/games/{game_id}/reanalyze
# Queue game for re-analysis

GET /api/games/{game_id}/analysis-status
# Check analysis status
```

### Coaching Endpoints

```http
GET /api/coach/focus-lock
# Get current focus lock state
Response: {
  "active": true,
  "lesson_key": "FORCING_BLIND",
  "state": "ACTIVE",
  "progress": {"completed": 2, "required": 5},
  "compliance": {"average": 75, "color": "yellow"},
  "strict_mode": false
}

POST /api/coach/focus-lock/activate
Body: {"lesson_key": "FORCING_BLIND", "games": 5}
# Activate new focus lock (with guardrails)

POST /api/coach/focus-lock/deactivate
# Force-deactivate (admin use)

GET /api/coach/breakthrough-signal
# Get weekly phase signal
Response: {
  "show_card": true,
  "state": "PLATEAU",
  "confidence": 0.8,
  "headline": "...",
  "message": "...",
  "cta": {...}
}

GET /api/coach/module/{game_id}
# Get theory module trigger for game
Response: {
  "triggered": true,
  "module_key": "SIMPLIFY_WHEN_AHEAD",
  "module_name": "Simplify When Ahead",
  "rule": "Trade pieces, reduce counterplay.",
  "evidence_move": 23,
  "evidence_cp_loss": 388,
  "confidence": "high"
}

GET /api/coach/modules/all
# Get all 30 theory modules

GET /api/coach/modules/stats
# Get user's module injection stats
```

### Lab Data

```http
GET /api/lab/game/{game_id}
# Get full lab data for a game
Response: {
  "core_lesson": {...},
  "similar_games": [...],
  "focus_module": {...},
  "strategic_analysis": {...}
}
```

---

## Data Models

### MongoDB Collections

#### `users`
```javascript
{
  user_id: "user_xxx",
  email: "user@example.com",
  name: "Mohit",
  chess_com_username: "killerknightroyalrook",
  created_at: ISODate(),
  rating_history: [...]
}
```

#### `games`
```javascript
{
  game_id: "uuid",
  user_id: "user_xxx",
  pgn: "1. e4 e5...",
  platform: "chess.com",
  result: "win",
  user_color: "white",
  white_rating: 1200,
  black_rating: 1250,
  played_at: ISODate()
}
```

#### `game_analyses`
```javascript
{
  game_id: "uuid",
  user_id: "user_xxx",
  stockfish_analysis: {
    move_evaluations: [...],
    accuracy: 78.5,
    critical_moments: [...]
  },
  game_coach_summary: {
    lesson_key: "FORCING_BLIND",
    core_lesson: {...},
    summary_p1: "...",
    summary_p2: "..."
  },
  module_trigger: {
    triggered: true,
    module_key: "SIMPLIFY_WHEN_AHEAD",
    confidence: "high",
    ...
  },
  analyzed_at: ISODate()
}
```

#### `coach_states`
```javascript
{
  user_id: "user_xxx",
  focus_lock: {
    lesson_key: "FORCING_BLIND",
    state: "ACTIVE",
    games_required: 5,
    games_completed: 2,
    compliance_scores: [0.8, 0.75],
    strict_mode: false,
    failed_cycles: 0,
    ...
  },
  memory: {
    lesson_history: [...],
    recurring_patterns: {...}
  }
}
```

#### `module_injections`
```javascript
{
  user_id: "user_xxx",
  game_id: "uuid",
  module_key: "SIMPLIFY_WHEN_AHEAD",
  confidence: "high",
  cp_loss: 388,
  injected_at: ISODate(),
  auto_locked: false
}
```

#### `focus_lock_analytics`
```javascript
{
  user_id: "user_xxx",
  lock_started_at: ISODate(),
  lesson_key: "FORCING_BLIND",
  games_required: 5,
  games_completed: 5,
  final_compliance: 78.5,
  failed_cycles: 0,
  strict_mode_triggered: false,
  deep_session_triggered: false,
  completed_successfully: true,
  lock_ended_at: ISODate(),
  outcome: "completed"  // completed | extended | failed | quit_mid_lock
}
```

---

## Frontend Components

### Key Pages

| Page | Path | Purpose |
|------|------|---------|
| Dashboard | `/dashboard` | Main hub, shows Focus Lock or Weekly Signal |
| Lab | `/game/:gameId` | Game analysis with "One Thing Fix" |
| Games | `/games` | Game list with filters |
| Training | `/training` | Drill modules |
| Progress | `/progress` | Rating & improvement charts |

### Component Hierarchy (Lab Page)

```
Lab.jsx
├── Header
│   ├── Game info (opponent, result, accuracy)
│   ├── Coach/Engine mode toggle
│   └── Focus Lock badge (if active)
│
├── Board Section
│   ├── Chessboard
│   ├── Move list
│   └── Navigation controls
│
└── Right Panel (Tabs)
    ├── Summary Tab
    │   ├── OneThingFix         ← Step 10 anchor
    │   ├── ConceptCard         ← Theory module
    │   ├── Focus Lock status   ← Step 9
    │   └── Coach's Full Take   ← Collapsed
    │
    ├── Strategy Tab
    │   └── Opening/Phase analysis
    │
    └── Milestones Tab
        └── Brilliant moves, mistakes
```

### Dashboard Card Priority

```javascript
// Dashboard.jsx - Card display logic
{focusLock?.active ? (
  <FocusLockCard />           // Highest priority - overrides all
) : breakthroughSignal?.show_card ? (
  <CoachWeeklySignalCard />   // Second priority
) : (
  <DailyMissionCard />        // Default
)}
```

---

## Configuration & Environment

### Backend `.env`
```bash
MONGO_URL=mongodb://localhost:27017
DB_NAME=chessguru
STOCKFISH_PATH=/usr/bin/stockfish
EMERGENT_LLM_KEY=<key>
```

### Frontend `.env`
```bash
REACT_APP_BACKEND_URL=https://chess-mentor-36.preview.emergentagent.com
```

### Key Constants

```python
# focus_lock_service.py
DEFAULT_LOCK_GAMES = 5
EXTENSION_GAMES = 3
COMPLETION_COMPLIANCE_THRESHOLD = 0.75
MAX_LOCK_FAILURES = 2
STRONG_COMPLIANCE = 0.80
PARTIAL_COMPLIANCE = 0.60

# module_trigger_service.py
AUTO_LOCK_TRIGGER_THRESHOLD = 3
AUTO_LOCK_WINDOW_GAMES = 10
HIGH_CONFIDENCE_CP_SWING = 300
INJECTION_COOLDOWN_GAMES = 10
```

---

## Testing

### Backend Tests

```bash
# Run all focus lock tests
cd /app/backend
python -m pytest coach_state/tests/test_focus_lock_service.py -v

# Test theory modules
python -c "from coach_state.theory_modules import ALL_MODULES; print(len(ALL_MODULES))"
```

### API Testing

```bash
# Get focus lock state
curl -s "$API/coach/focus-lock" -H "Cookie: session_token=<token>"

# Activate focus lock
curl -X POST "$API/coach/focus-lock/activate" \
  -H "Content-Type: application/json" \
  -H "Cookie: session_token=<token>" \
  -d '{"lesson_key": "FORCING_BLIND"}'

# Get module for game
curl -s "$API/coach/module/<game_id>" -H "Cookie: session_token=<token>"
```

### Frontend Testing

```bash
# Playwright tests in /app/tests/e2e/
npx playwright test
```

---

## Deployment

### Services (Supervisor)

```bash
# Check status
sudo supervisorctl status

# Restart services
sudo supervisorctl restart backend
sudo supervisorctl restart analysis_worker
sudo supervisorctl restart frontend
```

### Logs

```bash
# Backend logs
tail -f /var/log/supervisor/backend.err.log

# Analysis worker logs
tail -f /var/log/supervisor/analysis_worker.err.log

# Frontend logs
tail -f /var/log/supervisor/frontend.err.log
```

### Health Checks

```bash
# Backend health
curl $API/health

# Check analysis queue
curl $API/admin/queue-status
```

---

## Metrics to Monitor

### Focus Lock Analytics
```javascript
// Query focus_lock_analytics collection
db.focus_lock_analytics.aggregate([
  { $group: {
    _id: "$outcome",
    count: { $sum: 1 },
    avg_compliance: { $avg: "$final_compliance" }
  }}
])
```

**Key Metrics:**
- Completion rate (target: ≥70%)
- Extension rate (target: 30-40%)
- Strict mode frequency (target: 10-20%)
- Quit mid-lock rate (red flag if >25%)

### Module Injection Stats
```javascript
// Most common triggers
db.module_injections.aggregate([
  { $group: { _id: "$module_key", count: { $sum: 1 } }},
  { $sort: { count: -1 }}
])
```

---

## Version History

| Version | Date | Major Features |
|---------|------|----------------|
| P2.8 | Mar 3, 2026 | Pattern Injection Engine, Lab redesign |
| P2.7 | Mar 3, 2026 | Focus Lock Mode, Micro reinforcement |
| P2.6 | Feb 2026 | Breakthrough Detection, Weekly Signal |
| P2.5 | Feb 2026 | Adaptive Teaching Style |
| P2.4 | Feb 2026 | Intent Recognition |
| P2.3 | Feb 2026 | Memory Continuity |
| P2.0-2.2 | Jan 2026 | CoachState Foundation |

---

## Quick Reference

### Adding a New Theory Module

1. Add to `theory_modules.py`:
```python
NEW_MODULE = TheoryModule(
    key="NEW_MODULE",
    name="Human Readable Name",
    category=ModuleCategory.TACTICAL,
    trigger_pattern="When this happens",
    rule="The one rule to follow",
    explanation="Short explanation",
    detection_keys=["LESSON_KEY_1", "LESSON_KEY_2"],
    min_rating=0,
    max_rating=2000,
)
```

2. Add to `ALL_MODULES` dict

3. Update `get_focus_lock_lesson_for_module()` if needed

### Adding a New Focus Lock Lesson

1. Add compliance calculator in `focus_lock_service.py`
2. Add to `RULE_DESCRIPTIONS`
3. Update `calculate_compliance()` dispatcher
4. Add UI copy in `get_lock_copy()`

---

## Contact

For questions about this codebase:
- Architecture decisions → Review PRD.md
- Recent changes → Check CHANGELOG.md
- API behavior → Check server.py endpoints
- Coaching logic → Check coach_state/ directory
