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
- CoachPlay page refactored into modular components:
  - `CoachPlay.jsx` (2,430 lines - orchestrator with state/logic)
  - `CoachPlaySetup.jsx` (pre-game screen)
  - `CoachPlayBoard.jsx` (board + eval + controls)
  - `CoachPlaySidebar.jsx` (coaching panels)

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

### April 2, 2026
- **P0 Fix: API URL Imports** — Fixed ~24 frontend files using `process.env.REACT_APP_BACKEND_URL` directly. All now use centralized `import { API } from "@/App"`.
- **P0 Refactor: CoachPlay.jsx** — Broke down the 3,669-line monolith into modular components:
  - Extracted `CoachPlaySetup.jsx` (pre-game screen with color selection, opening suggestions, past games memory)
  - Extracted `CoachPlayBoard.jsx` (board + eval bar + teaching overlays + controls)
  - Extracted `CoachPlaySidebar.jsx` (coaching panels: clean UI mode, legacy chat, guardian, feedback)
  - CoachPlay.jsx reduced from 3,669 → 2,430 lines (34% reduction)
  - Testing: 100% pass (backend 38/38, frontend all UI elements verified)

### Previous Sessions
- Built 5-section Human Coach Game Review
- Built Coach Play with 9-opening curriculum engine
- Built Think First coaching, Move Intent Analyzer, Read the Board, Memory Brain
- Refactored server.py from 14.5k → 10.8k lines
- Redesigned Lab (/lab, /game/:gameId) for narrative-driven behavioral insights
- Rebuilt Home (/home) and Progress (/progress) pages
- Built progress_report_service.py and complete-review endpoint

## Prioritized Backlog

### P0 - Next Up
- Extract remaining state/logic from CoachPlay.jsx into focused hooks (second phase of refactor)
- Implement new Play with Coach lesson modes (openings, traps, tactics, short wins, commentary)

### P1
- Dead code cleanup: Delete orphaned backend/chess_coach_core/, dead coach_engine modules, dead frontend components
- Dependency cleanup: Remove unused packages (boto3, huggingface_hub, etc.)

### P2 — Backlog
- "Count Squares" teaching mode: Coach teaches users to count escape squares as a calculation technique
- Review data timing: Verify behavioral data attaches at analysis time, not just review time
- Training puzzle improvement tracking: Ensure solving puzzles updates metrics
- Dynamic error profile updates: If user wins 3 consecutive games, dashboard mood/data should shift to reflect improvement (don't forget training data, but update the "mood")
- Deeper opening variation trees for existing 9 curriculums
- Frontend E2E tests (Playwright)

*Last Updated: April 2, 2026*
