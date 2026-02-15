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

## GOLD FEATURE: Deterministic Personalized Coaching (Focus Page) - COMPLETE ✅

### Core Philosophy: "Same User + Same Inputs = Same Plan"
Focus page uses DETERMINISTIC PERSONALIZATION - not random LLM outputs. All coaching recommendations are computed from user's actual game data using rule-based engines.

### Key Properties
- **Deterministic**: Same user + same inputs = same plan (consistent, not random)
- **Personalized**: Different users + different inputs = different plan (actually personalized)
- **Rating Band Gated**: Different advice for <900, 900-1400, 1400-1800, 1800+

### The 7 Coaching Buckets (Cost Score System)
Each bucket computes a Cost Score from last 25 games:
```
CostScore = Σ(EvalDrop × ContextWeight × SeverityWeight) + FrequencyWeight × count(events)
```

1. **PIECE_SAFETY** - Hanging pieces (cp_loss >= 300)
2. **THREAT_AWARENESS** - Missed opponent threats
3. **TACTICAL_EXECUTION** - Missed tactics (blunders)
4. **ADVANTAGE_DISCIPLINE** - Failed conversion when ahead
5. **OPENING_STABILITY** - Weak first 10-12 moves
6. **TIME_DISCIPLINE** - Late-game blunders
7. **ENDGAME_FUNDAMENTALS** - Conversion failures

**Primary Focus** = Highest cost bucket (within rating band)
**Secondary Focus** = Second highest if >= 70% of primary

### Focus Page Layout

#### A) Coach Note (Personalized)
"You're stable at 1200 but you've peaked at 1350. The 150-point gap is mainly from Piece Safety. This week: Check all pieces after opponent's move"

#### B) This Week's Focus Card
- Primary Focus bucket with percentage affected
- 2 actionable rules (rating-band specific)
- "See Example Positions" button → **NEW: Cycling UI with prev/next buttons to view up to 5 example positions**

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

### P1: Mission Runner UI
- [ ] Build interactive mission drills (opening positions, threat awareness)
- [ ] Position bank for missions (beyond user's own games)
- [ ] Mission step completion tracking

### P2: Data Quality
- [ ] Historical game analysis script (find games missing analysis)

### P3: Performance
- [ ] Optimize Stockfish analysis depth (18 → 12-14)

### P4: Code Cleanup
- [ ] Delete unused files: BoardFirstCoach.jsx, AdaptiveCoach.jsx, Focus.jsx
- [ ] Consolidate coaching services

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
- `backend/server.py` - API endpoints for /api/focus-plan/*, /api/games/{game_id}/thought*

## Credentials
- Test user: session_token=test_session_356539ff12b1 (user with 30+ analyzed games)
- Dev Login available on landing page

