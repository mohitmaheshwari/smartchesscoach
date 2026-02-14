# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a full-featured chess coaching application that analyzes games, identifies weaknesses, and provides personalized coaching with a GM-coach style coaching loop.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)

## GOLD FEATURE: Adaptive Performance Coach (Focus Page v2) - COMPLETE ✅

### Core Philosophy: "Behavioral Coaching"
Focus page analyzes THINKING PATTERNS across games, not just move mistakes. It feels like a personal coach preparing you for your NEXT game, not reviewing the past.

### The 4 Sections

#### 1️⃣ Coach Diagnosis - "Your Current Growth Priority"
- Identifies ONE primary leak limiting user's rating
- Rating-band aware:
  - 600-1000: Hanging Pieces
  - 1000-1600: Tactical Awareness  
  - 1600-2000: Advantage Discipline
  - 2000+: Conversion Precision
- **"See Typical Pattern" button** loads representative position on board
- Secondary leak shown when available

#### 2️⃣ Next Game Plan - 5 Domains
- **Opening Strategy**: Based on opening stability score, not popularity
- **Middlegame Objective**: Based on primary weakness
- **Tactical Protocol**: Rating-specific (e.g., "Checks, captures, threats")
- **Endgame Reminder**: Only if endgame issues detected
- **Time Discipline**: Only if time trouble pattern exists
- Intensity levels (1-5) adjust based on compliance

#### 3️⃣ Plan Audit - "Last Game Execution Review"
- Audits last game against PREVIOUS PLAN (not Lab-style analysis)
- 3-5 audit cards showing: Executed ✅ / Partial ⚠️ / Missed ❌
- Each card has:
  - Single data line (e.g., "Advantage lost on move 7")
  - Eye icon to view position on board
- Score shown (e.g., "1/3")

#### 4️⃣ Skill Signals - "Live Performance Monitoring"
- Shows 5 skill dimensions with trends:
  - Opening Stability: ↑ ↓ →
  - Tactical Awareness: ↑ ↓ →
  - Advantage Discipline: ↑ ↓ →
  - Endgame Technique: ↑ ↓ →
  - Time Control: ↑ ↓ →
- Each signal has: trend arrow, short reason, click-to-view example

### Deterministic Engines (Backend)
All 12 engines implemented in `/app/backend/adaptive_coach_service.py`:
- `compute_primary_leak()` / `compute_secondary_leak()`
- `compute_opening_stability()` / `compute_hanging_piece_frequency()`
- `compute_tactical_miss_rate()` / `compute_advantage_collapse_rate()`
- `compute_endgame_conversion_rate()` / `compute_time_trouble_pattern()`
- `generate_next_game_plan()` / `audit_last_game_against_plan()`
- `compute_skill_trends()` / `get_adaptive_coach_data()`

### Adaptive Loop (Critical)
After every analyzed game:
1. Audit previous plan → 2. Update skill signals → 3. Recalculate primary leak → 4. Adjust intensity → 5. Generate next plan → 6. Persist new active plan

### API Endpoints
- `GET /api/adaptive-coach` - Returns all 4 sections
- `POST /api/adaptive-coach/audit-game/{game_id}` - Manual audit trigger

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

## Completed Work (Feb 2026)

### Adaptive Performance Coach - COMPLETE ✅
- [x] 12 deterministic engines for behavioral analysis
- [x] Rating-band aware leak detection
- [x] 4-section UI: Diagnosis, Plan, Audit, Signals
- [x] Board-first interaction (click-to-view positions)
- [x] Plan audit with execution review
- [x] Skill trends with arrows
- [x] Full test coverage (12 backend tests)

### Board-First Coach (v3.0) - COMPLETE ✅
- [x] Interactive CoachBoard component
- [x] Key Moments with explanations
- [x] Mission card with streak counter

---

## Upcoming Tasks

### P1: Adaptive Coach Enhancements
- [ ] Persist audit results to show improvement over time
- [ ] Add opening line practice in Plan section
- [ ] Intensity history visualization

### P2: Data Quality
- [ ] Historical game analysis script (find games missing analysis)

### P3: Performance
- [ ] Optimize Stockfish analysis depth (18 → 12-14)

---

## Test Reports
- `/app/test_reports/iteration_42.json` - Adaptive Coach (100% pass, 12 tests)
- `/app/backend/tests/test_adaptive_coach.py` - Backend test file

## Credentials
- Test user: session_token=test_session_356539ff12b1 (user with 30+ analyzed games)
- Dev Login available on landing page
