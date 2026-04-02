# ChessGuru PRD

## Original Problem Statement
A highly personalized, "coach-first" chess application with a modular, pedagogical chess engine with pluggable teaching modes (openings, traps, tactics, short wins, endgames). The platform teaches structured concepts, remembers user patterns, and explains intent clearly using a generic teaching engine and dynamic front-end UI.

## Core Architecture
```
/app/
├── backend/
│   ├── routes/               # coach_play.py (teaching, escape-squares endpoints)
│   ├── services/             # teaching_engine.py, escape_squares_service.py, postgame_analysis.py
│   ├── data/                 # opening_curriculum.json, traps.json, endgames.json
│   ├── coach_play/           # coach_game_session.py (session management)
│   ├── home_intelligence_service.py  # Dashboard intelligence with win streak
│   ├── tests/                # test_all_flows.py (38 tests), test_p1_features.py (16 tests)
├── frontend/
│   ├── src/
│   │   ├── components/coach/ # LessonPicker, CoachPlaySetup, CoachPlayBoard, CoachPlaySidebar, EscapeSquaresQuiz
│   │   ├── hooks/            # useTeachingMode, usePlayerData, useGuardian
│   │   └── pages/            # CoachPlay, CoachHome (with win streak), Dashboard
```

## What's Been Implemented

### Phase 1 — Core Coaching Platform (Complete)
- Real-time coaching feedback during games
- Opening curriculum with progression tracking
- Postgame analysis with blunder/mistake detection
- Coach memory that persists across sessions
- Import pipeline from Chess.com/Lichess

### Phase 2 — Pluggable Teaching Modes (Complete)
- Generic teaching engine dispatcher (teaching_engine.py)
- 18 Trap lessons with interactive board teaching
- 10 Endgame lessons with guided practice
- LessonPicker UI in coaching sidebar
- Hook-based frontend orchestration (useTeachingMode, useGuardian)

### Phase 3 — P1 Features (Complete - April 2, 2026)
1. **Count Escape Squares** — Interactive quiz that prompts users to count opponent's king escape squares during tactical moments (checks, restricted kings, back-rank threats). Backend service detects teaching moments, frontend shows number-picker quiz with validation and detailed feedback.
2. **Immediate Review Data Attachment** — Game analysis (postgame_analysis.py) now runs automatically when a coach game ends, attaching detailed mistake patterns and habits to the user's profile immediately without waiting for manual "Review" click.
3. **Dynamic Dashboard Mood via Win Streaks** — Home intelligence service calculates consecutive win streaks. When 3+ consecutive wins, the dashboard suppresses negative pattern profiling and shows a positive momentum banner with streak count.

## Key API Endpoints
- `POST /api/coach/play/teaching/start` — Start a trap/endgame lesson
- `POST /api/coach/play/teaching/move` — Make a move in a lesson
- `POST /api/coach/play/teaching/exit` — Exit a lesson
- `GET /api/coach/play/teaching/catalog` — Get all available lessons (18 traps, 10 endgames)
- `POST /api/coach/play/escape-squares/check` — Check if position is a teaching moment for escape squares
- `POST /api/coach/play/escape-squares/answer` — Validate user's escape squares answer
- `GET /api/coach/home-intelligence` — Dashboard data with win_streak and mood_override fields

## Key DB Collections
- `coach_sessions`: {session_id, current_fen, teaching_mode, teaching_state, escape_square_quizzes, result}
- `games`, `game_analyses`: Source of truth for dashboard mood
- `postgame_analyses`: Detailed game analysis data

## Testing
- Backend: 38/38 core tests passing (test_all_flows.py)
- Backend: 16/16 P1 feature tests passing (test_p1_features.py)
- Frontend: LessonPicker verified via testing agent (iteration_174)
- P1 features verified via testing agent (iteration_175)

## Prioritized Backlog

### P2
- Track community training puzzles to improve user error profiles

### Future
- Add "Tactics" pluggable lesson mode to teaching_engine.py
- Add "Short Wins" pluggable lesson mode
- Deeper opening variation trees for existing curriculums

## 3rd Party Integrations
- OpenAI/GPT-4o-mini via Emergent LLM Key
- Chess.com / Lichess APIs (open/external)
- Google OAuth (Emergent-managed)

*Last Updated: April 2, 2026*
