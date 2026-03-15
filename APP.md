# ChessGuru - Application Documentation

**Generated:** March 3, 2026  
**Version:** P2.8  
**Status:** Production Ready - Full Coaching Engine Complete

---

## Table of Contents
1. [Application Overview](#application-overview)
2. [The 5 Coaching Layers](#the-5-coaching-layers)
3. [Tech Stack](#tech-stack)
4. [Database Collections](#database-collections)
5. [UI Pages & Routes](#ui-pages--routes)
6. [Core Coaching Services](#core-coaching-services)
7. [Focus Lock System (Step 9)](#focus-lock-system-step-9)
8. [Pattern Injection Engine (Step 10)](#pattern-injection-engine-step-10)
9. [API Endpoints Reference](#api-endpoints-reference)
10. [Data Models](#data-models)
11. [Configuration](#configuration)

---

## Application Overview

ChessGuru is a **hyper-personalized, data-driven chess coaching application** that goes beyond traditional engine analysis. Unlike Chess.com or Lichess which show what went wrong, ChessGuru shows **why it went wrong behaviorally** and **enforces habit change**.

### Core Philosophy

> "Not an analyzer. Not a mentor simulator. A **discipline system**."

### What Makes It Different

| Traditional Analysis | ChessGuru |
|---------------------|-----------|
| Shows engine best move | Shows why YOU made that choice |
| Generic advice | Personalized to your rating & patterns |
| Passive feedback | Active enforcement via Focus Lock |
| One-time lesson | Tracks pattern across games |
| Treats each game separately | Memory continuity across sessions |

### The 5 Coaching Layers (P2.8)

| Layer | Name | Purpose |
|-------|------|---------|
| 1 | Tactical Analysis | Stockfish-powered move evaluation |
| 2 | Behavioral Memory | Long-term pattern tracking |
| 3 | Phase Awareness | Breakthrough/Plateau detection |
| 4 | Discipline Enforcement | Focus Lock system |
| 5 | Pattern Injection | Theory modules + auto-lock |

---

## The 5 Coaching Layers

### Layer 1: Tactical Analysis (Steps 0-4)
**What:** Stockfish-powered move evaluation  
**Output:** Accuracy %, blunders, mistakes, best moves

```python
# stockfish_service.py
analyze_game_with_stockfish(pgn, user_color, depth=18)
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
```

### Layer 3: Phase Awareness (Steps 6-8)
**What:** Understanding player's current learning phase  
**Output:** NORMAL, PLATEAU, BREAKTHROUGH, CONFIDENCE_ILLUSION, TILT_RISK

```python
# breakthrough_service.py
def get_breakthrough_signal_for_user(analyses, memory) -> BreakthroughSignal
```

### Layer 4: Discipline Enforcement (Step 9)
**What:** Focus Lock system that forces habit change  
**Output:** Locked rule for N games, compliance tracking

```python
# focus_lock_service.py
class FocusLock:
    lesson_key: str           # FORCING_BLIND, etc.
    state: LockState          # ACTIVE, EXTENDED, STRICT, COMPLETED, FAILED
    games_required: int       # Usually 5
    compliance_scores: List[float]
```

### Layer 5: Pattern Injection (Step 10)
**What:** Theory module detection and auto-lock  
**Output:** Injected concept + potential auto-lock

```python
# theory_modules.py - 30 modules across 5 categories
# module_trigger_service.py - Detection and auto-lock logic
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + Vite + TailwindCSS + Shadcn/UI |
| Backend | FastAPI (Python 3.11) |
| Database | MongoDB |
| Chess Engine | Stockfish (local binary) |
| LLM | GPT-4o-mini via Emergent LLM Key |
| Chess UI | react-chessboard + chess.js |

### Ports
- Frontend: 3000
- Backend: 8001 (proxied via `/api`)

---

## Database Collections

### Core Collections (Active)
| Collection | Purpose |
|------------|---------|
| `users` | User accounts |
| `user_sessions` | Auth sessions |
| `games` | Imported game metadata |
| `game_analyses` | Stockfish + coaching analysis |
| `coach_states` | Memory, Focus Lock, phase state |
| `module_injections` | Theory module triggers |
| `focus_lock_analytics` | Lock completion metrics |

### Analytics Collections
| Collection | Purpose |
|------------|---------|
| `focus_lock_analytics` | Track lock outcomes: completed/extended/failed/quit |
| `module_injections` | Track which theory modules trigger |

---

## UI Pages & Routes

### Public Routes
| Route | Page | Component |
|-------|------|-----------|
| `/` | Landing | `Landing.jsx` |

### Protected Routes (Require Auth)
| Route | Component | Description |
|-------|-----------|-------------|
| `/dashboard` | `Dashboard.jsx` | Main dashboard with Focus Lock/Weekly Signal |
| `/game/:gameId` | `Lab.jsx` | Game analysis with "One Thing Fix" |
| `/games` | `Games.jsx` | Game list with filters |
| `/training` | `Training.jsx` | Training hub |
| `/progress` | `Progress.jsx` | Rating & improvement charts |
| `/play-with-coach` | `CoachPlay.jsx` | Interactive coach game |
| `/settings` | `Settings.jsx` | User settings |

### Dashboard Card Priority
```javascript
{focusLock?.active ? (
  <FocusLockCard />           // Highest - overrides all
) : breakthroughSignal?.show_card ? (
  <CoachWeeklySignalCard />   // Second priority
) : (
  <DailyMissionCard />        // Default
)}
```

---

## Core Coaching Services

### Directory: `/app/backend/coach_state/`

| File | Purpose |
|------|---------|
| `coach_narrative_engine.py` | Story generation |
| `coach_memory_service.py` | Long-term memory |
| `lesson_resolver.py` | Lesson selection |
| `teaching_style_service.py` | Adaptive tone (Step 7) |
| `breakthrough_service.py` | Phase detection (Step 8) |
| `focus_lock_service.py` | Discipline enforcement (Step 9) |
| `theory_modules.py` | 30 theory modules (Step 10) |
| `module_trigger_service.py` | Pattern injection (Step 10) |

### Analysis Worker (`analysis_worker.py`)

Background job processor:
```python
def process_job(db, job):
    # Phase 1: Stockfish analysis
    # Phase 2: Intent recognition
    # Phase 3: Coach narrative generation
    # Phase 4: Focus Lock compliance update
    # Phase 5: Module trigger detection
```

---

## Focus Lock System (Step 9)

### What It Does
Forces users to follow a specific rule for N games and measures compliance.

### Lock States
```
ACTIVE → (complete 5 games)
  → compliance ≥ 75% → COMPLETED ✓
  → compliance < 75% → EXTENDED (+3 games)
    → still failing + declining → STRICT mode
    → 2 failures → FAILED → Deep Session
```

### Available Lessons
| Lesson Key | Rule |
|------------|------|
| `FORCING_BLIND` | Check forcing moves before every decision |
| `STOPPED_CALCULATION_EARLY` | Calculate deeper at critical moments |
| `THREAT_VERIFICATION` | Verify opponent threats before moving |

### Compliance Thresholds
- **Complete:** ≥75% average compliance
- **Strong:** ≥80% (green)
- **Partial:** ≥60% (yellow)
- **Weak:** <60% (red)

### API Endpoints
```http
GET  /api/coach/focus-lock
POST /api/coach/focus-lock/activate  {"lesson_key": "FORCING_BLIND", "games": 5}
POST /api/coach/focus-lock/deactivate
```

---

## Pattern Injection Engine (Step 10)

### 30 Theory Modules

**Category A - Tactical (8):**
LPDO, Forcing Moves First, Overloaded Defender, Back Rank Weakness, Discovered Attack, Zwischenzug, Remove the Defender, Deflection

**Category B - Conversion (6):**
Simplify When Ahead, Don't Rush Pawns, Activate King in Endgame, Convert by Restriction, Trade Active Pieces, Avoid Counterplay

**Category C - Endgame (6):**
Square Rule, Opposition, Rook Behind Passer, Outside Passed Pawn, Wrong Bishop Corner, Push Passers Carefully

**Category D - Positional (6):**
Good vs Bad Bishop, Knight Outposts, Minor Piece Superiority, Pawn Break Awareness, Open File Control, Improve Worst Piece

**Category E - Opening (4):**
Don't Move Same Piece Twice, Castle Before Attacking, Fight for Center, Queen Out Too Early

### Trigger Logic
- Max 1 module per game
- Priority: High-intensity (≥300cp), Repeated lesson, Endgame collapse
- 10-game cooldown per module

### Auto-Lock (Option C)
When module triggers 3+ times in 10 games with high confidence:
1. Map module to Focus Lock lesson
2. Auto-activate Focus Lock
3. User must complete lock before seeing same module again

### API Endpoints
```http
GET /api/coach/module/{game_id}
GET /api/coach/modules/stats
GET /api/coach/modules/all
```

---

## Lab Page Structure (Redesigned Step 10.1)

### Summary Tab - Final Structure
```
SUMMARY TAB
────────────────────────

⭐ Main Lesson          ← Most impactful moment
   Concept + Move + Rule

📘 Supporting Lesson    ← Optional (max 2)
📘 Supporting Lesson    

⚠ Coach Notice          ← Pattern reminder (similar games)

🔒 Focus Lock           ← If active

📖 Coach Full Review    ← Collapsed by default
```

### Component Hierarchy
```
Lab.jsx
├── Header
│   ├── Game info (opponent, result, accuracy)
│   ├── Coach/Engine mode toggle
│   └── Focus Lock badge (if active)
│
├── Board Section
│   ├── Chessboard
│   └── Move list
│
└── Right Panel (Tabs)
    ├── Summary Tab
    │   ├── LessonCard (main)     ← ⭐ Main Lesson
    │   ├── LessonCard (supporting) × 2
    │   ├── CoachNotice           ← Pattern reminder
    │   ├── FocusLockStatus       ← If active
    │   └── Coach Full Review     ← Collapsed
    │
    ├── Strategy Tab
    │   └── Opening/Phase analysis (simplified)
    │
    └── Milestones Tab
        └── Brilliant moves, mistakes
```

### New Lab Components
| Component | Purpose |
|-----------|---------|
| `LessonCard` | Main/Supporting lesson display |
| `CoachNotice` | Pattern reminder with similar games |
| `FocusLockStatus` | Compact lock progress display |

---

## API Endpoints Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/google/login` | Start Google OAuth |
| GET | `/api/auth/google/callback` | OAuth callback |
| GET | `/api/auth/dev-login` | Dev mode login |
| POST | `/api/auth/demo-login` | Demo account login |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/logout` | Logout |

### Games
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/import-games` | Import from platform |
| GET | `/api/games` | List user's games |
| GET | `/api/games/{game_id}` | Get game details |
| POST | `/api/analyze-game` | Queue analysis |

### Coaching (Steps 8-10)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/coach/breakthrough-signal` | Get weekly phase signal |
| GET | `/api/coach/focus-lock` | Get focus lock state |
| POST | `/api/coach/focus-lock/activate` | Activate focus lock |
| POST | `/api/coach/focus-lock/deactivate` | Deactivate lock |
| GET | `/api/coach/module/{game_id}` | Get module trigger for game |
| GET | `/api/coach/modules/stats` | Get injection stats |
| GET | `/api/coach/modules/all` | Get all 30 modules |

### Play with Coach
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/coach/play/start` | Start session |
| POST | `/api/coach/play/move` | Make a move |
| POST | `/api/coach/play/chat` | Chat with coach |
| GET | `/api/coach/play/state/{session_id}` | Get session state |
| POST | `/api/coach/play/end` | End session |

### Training
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/training/profile` | Get training profile |
| GET | `/api/training/drills` | Get recommended drills |
| GET | `/api/missions/today` | Get daily missions |

---

## Data Models

### Focus Lock State
```javascript
// In coach_states collection
{
  user_id: "...",
  focus_lock: {
    lesson_key: "FORCING_BLIND",
    state: "ACTIVE",  // ACTIVE, EXTENDED, STRICT, COMPLETED, FAILED
    games_required: 5,
    games_completed: 2,
    compliance_scores: [0.8, 0.75],
    strict_mode: false,
    failed_cycles: 0,
    created_at: "...",
    updated_at: "..."
  }
}
```

### Module Injection
```javascript
// module_injections collection
{
  user_id: "...",
  game_id: "...",
  module_key: "SIMPLIFY_WHEN_AHEAD",
  confidence: "high",
  cp_loss: 388,
  injected_at: "...",
  auto_locked: false
}
```

### Focus Lock Analytics
```javascript
// focus_lock_analytics collection
{
  user_id: "...",
  lock_started_at: "...",
  lesson_key: "FORCING_BLIND",
  games_required: 5,
  games_completed: 5,
  final_compliance: 78.5,
  failed_cycles: 0,
  strict_mode_triggered: false,
  deep_session_triggered: false,
  completed_successfully: true,
  outcome: "completed"  // completed | extended | failed | quit_mid_lock
}
```

---

## Configuration

### Backend `.env`
```bash
MONGO_URL=mongodb://localhost:27017
DB_NAME=chessguru
STOCKFISH_PATH=/usr/bin/stockfish
EMERGENT_LLM_KEY=<key>
```

### Frontend `.env`
```bash
REACT_APP_BACKEND_URL=https://chess-habit-forge.preview.emergentagent.com
```

### Key Constants
```python
# focus_lock_service.py
DEFAULT_LOCK_GAMES = 5
EXTENSION_GAMES = 3
COMPLETION_COMPLIANCE_THRESHOLD = 0.75
MAX_LOCK_FAILURES = 2

# module_trigger_service.py
AUTO_LOCK_TRIGGER_THRESHOLD = 3
AUTO_LOCK_WINDOW_GAMES = 10
HIGH_CONFIDENCE_CP_SWING = 300
```

---

## Current State Summary (P2.8)

### What WORKS
1. ✅ User authentication (Google OAuth + Demo)
2. ✅ Game import from Lichess/Chess.com
3. ✅ Stockfish analysis with behavioral tagging
4. ✅ Focus Lock system (Steps 9 + 9.1)
5. ✅ Pattern Injection Engine (Step 10)
6. ✅ Auto-lock with guardrails
7. ✅ Redesigned Lab page with "One Thing Fix"
8. ✅ Weekly Signal / Breakthrough detection
9. ✅ Internal analytics for Focus Lock cycles

### Metrics to Monitor
```javascript
// Focus Lock completion rate (target: ≥70%)
db.focus_lock_analytics.aggregate([
  { $group: { _id: "$outcome", count: { $sum: 1 } }}
])

// Most triggered modules
db.module_injections.aggregate([
  { $group: { _id: "$module_key", count: { $sum: 1 } }},
  { $sort: { count: -1 }}
])
```

### Red Flags
- Quit mid-lock rate >25% → Enforcement too harsh
- Extension rate >60% → 75% threshold too high
- Strict mode >40% → System too aggressive

---

## Version History

| Version | Date | Major Features |
|---------|------|----------------|
| P2.8 | Mar 3, 2026 | Pattern Injection Engine, Lab redesign, Auto-lock |
| P2.7 | Mar 3, 2026 | Focus Lock Mode, Micro reinforcement |
| P2.6 | Feb 2026 | Breakthrough Detection, Weekly Signal |
| P2.5 | Feb 2026 | Adaptive Teaching Style |
| P2.4 | Feb 2026 | Intent Recognition |
| P2.3 | Feb 2026 | Memory Continuity |
| P2.0-2.2 | Jan 2026 | CoachState Foundation |

---

## File Reference

### Core Coaching Services
```
/app/backend/coach_state/
├── focus_lock_service.py        # Step 9: Discipline enforcement
├── theory_modules.py            # Step 10: 30 theory modules
├── module_trigger_service.py    # Step 10: Detection & auto-lock
├── breakthrough_service.py      # Step 8: Phase detection
├── teaching_style_service.py    # Step 7: Adaptive tone
├── coach_memory_service.py      # Step 5: Long-term memory
├── coach_narrative_engine.py    # Story generation
└── lesson_resolver.py           # Lesson selection
```

### Frontend Components
```
/app/frontend/src/
├── pages/
│   ├── Dashboard.jsx            # Main dashboard
│   └── Lab.jsx                  # Game analysis (redesigned)
├── components/
│   ├── Home/
│   │   ├── FocusLockCard.jsx    # Step 9 UI
│   │   └── CoachWeeklySignalCard.jsx  # Step 8 UI
│   └── Lab/
│       ├── OneThingFix.jsx      # Step 10: Anchor
│       └── ConceptCard.jsx      # Step 10: Theory module
```
