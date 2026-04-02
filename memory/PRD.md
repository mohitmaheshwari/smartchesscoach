# ChessGuru PRD

## Original Problem Statement
A highly personalized, "coach-first" chess application that teaches structured concepts through gameplay, remembers user patterns (Chess DNA), and explains intent clearly. The architecture must be perfectly modular to support various lesson types (openings, traps, tactics, short wins, position commentary).

## Core Requirements
- Human Coach Game Review (Lab): 5-section narrative review (Diagnose → Drill → Track)
- Play with Coach: Dynamic teaching via 9-opening curriculum engine with trap detection
- Memory Brain: Tracks user weaknesses and habits across games
- Move Intent Analyzer: Explains moves in plain English
- Read the Board: Position analysis with tap-to-expand UI
- Progress Report: Behavioral coaching report focusing on weakness control

## Architecture

### Backend
- FastAPI + Motor (Async MongoDB) + Stockfish
- Modular routes in `/backend/routes/` (coach_play.py)
- Services: memory_brain.py, position_reader.py, move_intent_analyzer.py, coach_move_pipeline.py, progress_report_service.py, coach_review_service.py
- Data: opening_curriculum.json (9 openings, 14 traps)
- Tests: test_all_flows.py (38/38 E2E tests passing)
- LLM: OpenAI/GPT-4o-mini via emergentintegrations/EMERGENT_LLM_KEY

### Frontend
- React 18 + Tailwind CSS + Framer Motion + chess.js + LichessBoard
- CoachPlay refactored architecture:
  - `CoachPlay.jsx` (2,050 lines - orchestrator with core session/coaching state)
  - `useTeachingMode.js` - Pluggable teaching lesson system hook
  - `usePlayerData.js` - Pre-game data, streak, development tracking hook
  - `useGuardian.js` - Move intervention system hook
  - `CoachPlaySetup.jsx` - Pre-game screen component
  - `CoachPlayBoard.jsx` - Board + eval + controls component
  - `CoachPlaySidebar.jsx` - Coaching panels component

### Key API Endpoints
- POST /api/coach/play/start, POST /api/coach/play/move
- POST /api/coach/play/opening-guide, POST /api/coach/play/read-position
- GET /api/player-brain
- GET /api/lab-coach-pick
- POST /api/lab/{game_id}/complete-review
- GET /api/progress/journey

### Key DB Collections
- `games`, `game_analyses`, `coach_sessions`, `analysis_queue`

## What's Been Implemented

### April 2, 2026 (Session 2)
- **P0: Hook Extraction** — Extracted 3 focused hooks from CoachPlay.jsx:
  - `useTeachingMode.js` (~250 lines) — All teaching lesson state + handlers. Pluggable for new lesson types.
  - `usePlayerData.js` (~200 lines) — Pre-game data fetching, streak tracking, development tracking.
  - `useGuardian.js` (~100 lines) — Guardian intervention state, evaluateMove, cancelRiskyMove.
  - CoachPlay.jsx: 3,669 → 2,050 lines (44% total reduction across both sessions)
- **P1: Dead Code Cleanup** — Deleted 5 dead backend modules (coach_engine/coach_personality.py, interactive_coach.py, lichess_explorer.py, opening_knowledge_builder.py, opening_teaching_db.py). Deleted 6 dead frontend components (RatingTrajectory, LearningPath, MemoryLane, HabitChallenge, NotificationBell, DailyMissionCard).
- **P1: Dependency Cleanup** — Removed unused packages: boto3, botocore, s3transfer, huggingface_hub, fastuuid from backend. Removed axios from frontend.
- Testing: 100% pass (backend 38/38, frontend all pages verified)

### April 2, 2026 (Session 1)
- **P0: API URL Fix** — Fixed ~24 frontend files using process.env.REACT_APP_BACKEND_URL directly → centralized import { API } from "@/App"
- **P0: JSX Extraction** — Extracted render JSX from CoachPlay into CoachPlaySetup, CoachPlayBoard, CoachPlaySidebar

### Previous Sessions
- Built 5-section Human Coach Game Review
- Built Coach Play with 9-opening curriculum engine
- Built Think First coaching, Move Intent Analyzer, Read the Board, Memory Brain
- Refactored server.py from 14.5k → 10.8k lines
- Redesigned Lab, Home, Progress pages for narrative-driven behavioral insights
- Built progress_report_service.py and complete-review endpoint

## Prioritized Backlog

### P0 - Next Up
- Implement new Play with Coach lesson modes (traps, tactics, short wins, commentary) using the refactored architecture + useTeachingMode hook

### P1
- "Count Squares" teaching mode: Coach teaches users to count escape squares as a calculation technique
- Review data timing: Verify behavioral data attaches at analysis time, not just review time
- Training puzzle improvement tracking: Ensure solving puzzles updates metrics

### P2
- Dynamic error profile updates: If user wins 3 consecutive games, dashboard mood/data should shift (don't forget historical data, but update the "mood")
- Deeper opening variation trees for existing 9 curriculums
- Frontend E2E tests (Playwright)

*Last Updated: April 2, 2026*
