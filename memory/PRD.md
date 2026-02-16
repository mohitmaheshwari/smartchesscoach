# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a full-featured chess coaching application that analyzes games, identifies weaknesses, and provides personalized coaching with a GM-coach style coaching loop.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)

---

## GOLD FEATURE: Training Engine - Adaptive Behavioral Correction System ✅ NEW

### Core Philosophy: "Data-Driven, One Leak at a Time"
The Training Engine replaces the Focus + Coach pages with a unified, step-by-step training experience. It uses PURE DATA (not rating-band hardcoding) to identify the user's biggest weakness.

### The 4 Training Layers
Each layer computes a Cost Score from last 20 games:

1. **STABILITY** - Blunders, hanging pieces, threat blindness, one-move threats
2. **CONVERSION** - Win-state detection, eval drops when ahead, allowing counterplay
3. **STRUCTURE** - Opening deviation, equal-position stability, aimless play
4. **PRECISION** - Tactical misses, calculation depth, endgame technique

**Active Phase** = Highest cost layer (pure data, no rating hardcoding)
**Micro Habit** = Dominant pattern within the active phase

### Training Page Flow (Step-by-Step)
1. **Phase Context** - Which layer needs work (4-layer cost breakdown)
2. **Your Pattern** - Dominant micro habit within the phase (with percentage weights)
3. **Your 2 Rules** - Actionable rules tailored to rating tier (low/mid/high)
4. **Quick Reflection** - Tag what happened in last game (updates pattern weights)
5. **Training Drill** - Practice positions from user + similar users' mistakes

### Key Technical Concepts
- **Pattern Weights**: User reflections nudge pattern weights (engine still wins)
- **Cross-User Drills**: Positions from similar rating + same micro habit users
- **Recalculation Trigger**: Every 7 new games analyzed

### API Endpoints
- `GET /api/training/profile` - Get or generate training profile
- `POST /api/training/profile/regenerate` - Force regenerate
- `GET /api/training/reflection-options` - Get reflection tags for active phase
- `POST /api/training/reflection` - Save reflection (updates pattern weights)
- `GET /api/training/drills` - Get drill positions

### Key Files
- `backend/training_profile_service.py` - Core training engine (900+ lines)
- `frontend/src/pages/Training.jsx` - Step-by-step wizard UI
- `frontend/src/components/CoachBoard.jsx` - Reusable chess board wrapper (uses LichessBoard)
- `frontend/src/components/LichessBoard.jsx` - Lichess Chessground library wrapper
- Navigation: "Training" tab in main nav

### Chessboard Migration (Feb 2026) ✅ COMPLETE
Migrated from `react-chessboard` to Lichess `chessground` library for better UX:
- **LichessBoard.jsx**: New wrapper component for Chessground library
  - Smooth animations, professional Lichess styling
  - Arrow rendering for showing played vs better moves
  - Move destinations highlighting when interactive
  - Board orientation support (white/black perspective)
- **CoachBoard.jsx**: Updated to use LichessBoard internally
  - Maintains same API for Training.jsx compatibility
  - Supports drill mode, arrows, flip board, and position props
- **Libraries**: `chessground@9.2.1` for board, `chess.js@1.4.0` for move validation
- **Two-Arrow System**: Red arrow shows user's move (mistake), Blue arrow shows better move
- **Legend**: Clear legend below board explains arrow colors

### Example Position Filtering (Feb 2026) ✅ FIXED
Fixed data issue where tactical mistakes were shown in positional training phases:
- **Stricter Pawn Structure Filtering**: Only shows positions where user made a bad pawn push
- **Excludes Tactics**: Positions with >250 centipawn loss filtered out (usually tactical)
- **Uses Mistake Classifier**: Forks, pins, etc. properly excluded from positional phases
- **No Fallback to Unrelated Positions**: Shows helpful message instead of irrelevant examples

### "Show Plan on Board" Feature (Feb 2026) ✅ COMPLETE
Users can now show their plan by playing moves on the board instead of typing:
- **Plan Mode**: Click "Show on board" button in reflection step
- **Both Colors**: User can play moves for both sides to show expected sequence
- **Move Tracking**: Shows moves as they're played: 1. e4 e5 2. Nf3 etc.
- **LLM Conversion**: Backend endpoint converts move sequence to natural language
- **Controls**: Undo, Cancel, Done buttons for managing the plan
- **Technical Fix (Feb 2026)**: Board interactivity now works by destroying and recreating chessground instance when planMode changes. This is necessary because chessground doesn't bind event handlers when viewOnly:true initially.
- **Files**: 
  - `LichessBoard.jsx` - Chessground wrapper with planMode support, re-creates instance when shouldBeInteractive changes
  - `CoachBoard.jsx` - Orchestrates plan mode state, exposes plan move tracking
  - `server.py` - `/api/training/plan/describe` endpoint for LLM conversion

### Bug Fixes (Dec 2025)
- ✅ Example positions now load correct FEN (was showing starting position)
- ✅ Reflection step includes chessboard showing mistake position
- ✅ Phase Context framed as "This Week's Focus" / "Weekly Focus"

### Bug Fixes (Feb 2026)
- ✅ **Phase-Filtered Example Positions**: Example positions now match the current training phase
  - Opening Principles phase shows only moves 1-12
  - Pawn Structure phase shows moves 1-25
  - Each phase has specific filtering criteria (move range, cp loss threshold)
  - Backend: `collect_all_phase_relevant_positions()` and `filter_positions_for_phase()` in training_profile_service.py
- ✅ **Merged Training Systems**: Removed confusing "Training Areas" (layer-based cost system)
  - Now only shows the tier-based training journey (Opening Principles → Pawn Structure → etc.)
  - Simplified UI with single focus on current phase
- ✅ **Clearer Stats Display**:
  - "2 Clean Games (need 3)" instead of confusing "4/3"
  - "+16% Fewer mistakes" instead of confusing "↓ 90%"
  - Removed all raw "Cost" numbers from UI

### Enhanced Reflection System (Dec 2025) ✅ NEW
Per-position reflection with rich context:
- **Rating-Based Filtering**: Different thresholds per rating band
  - <1000: Blunders only (≥200cp)
  - 1000-1400: Blunders + big mistakes (≥150cp)
  - 1400-1800: All mistakes (≥100cp)
  - 1800+: Including inaccuracies (≥50cp)
- **Rich Context Per Position**:
  - "You played X" / "Better was Y" side-by-side
  - "Play the better line" interactive visualization
  - "Opponent's threat" display when applicable
  - "Why is Y better?" GPT explanation (using Stockfish data)
- **User Input**:
  - "What was your plan?" - User shares their thinking
  - Contextual tags (not static "rushing" but position-specific)
- **Per-Position Save**: Each milestone saved independently

### API Endpoints (Enhanced Reflection)
- `GET /api/training/last-game-for-reflection` - Get last analyzed game ID
- `GET /api/training/game/{game_id}/milestones` - Get filtered milestones with contextual options
- `POST /api/training/milestone/explain` - Generate GPT explanation
- `POST /api/training/milestone/reflect` - Save per-position reflection
- `GET /api/training/reflection-history` - Get reflection history with pattern evolution
- `GET /api/training/ai-insights` - AI analysis of thinking patterns (NEW)

### Reflection History View (Dec 2025) ✅ NEW
- Stats overview: Total reflections, patterns identified
- AI Analysis of thinking patterns using GPT
- Pattern breakdown with progress bars
- Recent reflections with user's written thoughts
- Pattern weights updated based on reflections

### Phase Progress & Graduation System (Dec 2025) ✅ ENHANCED
Rating-adaptive multi-tier training journey:

**6 Training Tiers (200 → 2200+ rating):**
1. **Fundamentals** (0-600): Piece Safety → Check Awareness → Capture Awareness
2. **Stability** (600-1000): Blunder Reduction → Threat Detection → Piece Activity  
3. **Structure** (1000-1400): Opening Principles → Pawn Structure → Piece Coordination
4. **Conversion** (1400-1800): Advantage Maintenance → Winning Technique → Endgame Basics
5. **Precision** (1800-2200): Calculation Depth → Positional Understanding → Complex Tactics
6. **Mastery** (2200+): Deep Preparation → Time Management → Psychological Resilience

**Progress Tracking:**
- Phase-specific metrics (e.g., "1.8 opening mistakes per game (target: ≤1.0)")
- Clean games count per phase definition
- Improvement trend tracking
- Visual phase roadmap showing journey

**Auto-Graduation:**
- System automatically advances user when criteria met
- No manual confirmation needed
- Graduation logged for history

---

## DEPRECATED: Focus Page (Replaced by Training Engine)

### What Was Replaced

#### C) Last Game Audit ✅ NEW
Shows how well user followed their focus in their most recent game:
- Overall alignment: Executed / Partial / Missed (with color coding)
- Rule-by-rule audit with EXECUTED/PARTIAL/MISSED badges
- Key moments to review (clickable violations)
- "Open in Lab" button to study the game

#### C) Opening Pack (Personalized)
- **As White**: Best opening from user's games
- **vs 1.e4**: Best black response
- **vs 1.d4**: Best black response
- Shows: games played, win rate, stability score

#### D) Guided Replay (Turning Points)
- Top 3 biggest eval swings from user's games
- Click to load position on board
- Shows: move number, phase, your move vs best move

#### E) Weekly Requirements (3 Progress Bars)
- Games with openings: 0/10
- Missions completed: 0/7
- Guided replays: 0/2

#### F) Daily Mission (15 Minute Focus)
- Active time tracking (only counts when interacting)
- Heartbeat events every 5 seconds
- Complete at 80%+ (12+ minutes)

### API Endpoints
- `GET /api/focus-plan` - Get complete focus plan
- `POST /api/focus-plan/regenerate` - Force new plan
- `POST /api/focus-plan/mission/start` - Start mission session
- `POST /api/focus-plan/mission/interaction` - Record event/heartbeat
- `POST /api/focus-plan/mission/complete` - Complete mission
- `GET /api/focus-plan/bucket-breakdown` - Debug bucket costs

### Key Files
- `backend/focus_plan_service.py` - Core deterministic coaching service
- `frontend/src/pages/FocusPage.jsx` - New Focus Page UI

---

## Previous Feature: Adaptive Performance Coach (v1) - DEPRECATED

The old adaptive coach at `/api/adaptive-coach` still exists with:
- 4-section layout (Diagnosis, Plan, Audit, Signals)
- Different data model (user_adaptive_plans collection)

Now the Focus page uses the new deterministic system (focus_plans collection).

---

### Key Files
- `frontend/src/pages/AdaptiveCoach.jsx` - Main component with 4 sections
- `backend/adaptive_coach_service.py` - All deterministic engines
- `backend/tests/test_adaptive_coach.py` - 12 comprehensive tests

---

## Previous Feature: Board-First Coach (v3.0) - REPLACED BY ADAPTIVE COACH

The old Board-First Coach at `/coach` route still exists with:
- 3-tab layout (Audit, Plan, Openings)
- Key Moments from last game
- Mission card with streak counter

Now the Focus page (`/focus`) uses the new Adaptive Performance Coach.

---

## API Endpoints Summary

### Coaching
- `GET /api/adaptive-coach` - Adaptive Performance Coach data (4 sections)
- `POST /api/adaptive-coach/audit-game/{game_id}` - Audit specific game
- `GET /api/round-preparation` - Old coaching loop plan
- `GET /api/plan-audit` - Old plan audit
- `GET /api/focus` - Old focus data (legacy)

### Games
- `GET /api/games` - User's games
- `GET /api/games/{game_id}` - Specific game
- `POST /api/analyze-game` - Analyze a game

---

## Completed Work (Dec 2025)

### Deterministic Personalized Coaching System - COMPLETE ✅ (Dec 2025)
- [x] Cost Score computation for 7 coaching buckets
- [x] Primary/Secondary focus selection (deterministic)
- [x] Rating band gates (<900, 900-1400, 1400-1800, 1800+)
- [x] Personalized opening recommendations from game data
- [x] ECO code to opening name mapping
- [x] Coach note generation (personalized text templates)
- [x] Daily mission with active time tracking (15 min goal)
- [x] Mission sessions with heartbeat events
- [x] Weekly requirements tracking
- [x] Turning points for guided replay
- [x] Full test coverage (15 backend tests passed)

### New Focus Page UI - COMPLETE ✅ (Dec 2025)
- [x] Coach Note (personalized from metrics)
- [x] Primary Focus card with 2 actionable rules
- [x] Opening Pack (white, vs e4, vs d4)
- [x] Guided Replay (turning points)
- [x] Weekly Requirements (3 progress bars)
- [x] Daily Mission with active timer
- [x] Interactive chessboard that updates on position clicks

### Previous Features - DEPRECATED
- Adaptive Performance Coach v1 (adaptive_coach_service.py) - replaced
- Board-First Coach (BoardFirstCoach.jsx) - replaced
- Old Focus page (Focus.jsx, AdaptiveCoach.jsx) - replaced

---

## Upcoming Tasks

### P1: Code Cleanup
- [ ] Delete deprecated files: FocusPage.jsx, Coach.jsx, Focus.jsx
- [ ] Delete deprecated backend: focus_service.py, adaptive_coaching_service.py
- [ ] Clean up old routing references

### P2: Drill Generation Logic
- [ ] Implement contextual drills based on user's active phase and micro-habit
- [ ] Source drills from user's mistakes + similar rating band users
- [ ] Add interactive drill mode with move validation

### P3: Reflection Reinforcement
- [ ] User reflections dynamically adjust pattern weights
- [ ] Analyze accumulated "gold data" for pattern discovery

### P4: Performance
- [ ] Optimize Stockfish analysis depth (18 → 12-14)

---

## What Were You Thinking? (Gold Data Collection) ✅ NEW

### Purpose
Collect user's thoughts at the moment of mistakes for future pattern analysis. This "gold data" captures what the user was thinking when they made an error.

### API Endpoints
- `POST /api/games/{game_id}/thought` - Save user thought
- `GET /api/games/{game_id}/thoughts` - Get all thoughts for a game
- `GET /api/thoughts/all` - Get all user thoughts for pattern analysis

### Data Model (user_thoughts collection)
```json
{
  "thought_id": "thought_xxx",
  "user_id": "user_xxx",
  "game_id": "xxx",
  "move_number": 15,
  "fen": "...",
  "thought_text": "I thought I could win material",
  "move_played": "Nc7+",
  "best_move": "Ne7+",
  "evaluation_type": "blunder",
  "cp_loss": 400,
  "user_rating": 1200,
  "created_at": "2026-02-15T..."
}
```

### Frontend UI ✅ COMPLETE (Feb 2026)
- [x] "What were you thinking?" prompt in Lab.jsx LearningMomentItem component
- [x] Users can enter and save thoughts for each mistake/blunder
- [x] Saved thoughts show checkmark indicator
- [x] Thoughts persist across page reloads
- [x] Test-ids: thought-section-{moveNumber}, thought-input-{moveNumber}, thought-save-{moveNumber}, thought-prompt-{moveNumber}
- [x] **"Play the better line on board"** - Visual variation player for learning moments (Feb 2026)
  - Shows the better move and continuation on the board
  - Step through moves with Next/Back controls
  - Green highlighting shows variation moves
  - Exit button returns to game position

---

## Test Reports
- `/app/test_reports/iteration_46.json` - "What were you thinking?" Gold Data UI (100% pass, all 7 features verified)
- `/app/test_reports/iteration_45.json` - Focus Plan V2 (Example cycling, Last Game Audit, User Thoughts API - 100% pass)
- `/app/test_reports/iteration_44.json` - Deterministic Focus Plan (100% pass, 15 tests)
- `/app/test_reports/iteration_43.json` - Focus Page 3-Section Redesign (100% pass)
- `/app/backend/tests/test_focus_plan.py` - Focus plan backend tests
- `/app/backend/tests/test_focus_plan_v2.py` - Focus plan v2 tests (example positions, audit, thoughts)

## Key Files
- `backend/focus_plan_service.py` - Core deterministic coaching service (1300+ lines) - includes audit_last_game()
- `frontend/src/pages/FocusPage.jsx` - Focus Page UI with Last Game Audit and Example Position cycling
- `frontend/src/pages/Lab.jsx` - Game Analysis (Lab) page with "What were you thinking?" Gold Data collection
- `backend/server.py` - API endpoints for /api/focus-plan/*, /api/games/{game_id}/thought*

## Credentials
- Test user: session_token=test_session_356539ff12b1 (user with 30+ analyzed games)
- Dev Login available on landing page

