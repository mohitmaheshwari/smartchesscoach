# ChessGuru PRD

## Original Problem Statement
A highly personalized, "coach-first" chess application with a modular, pedagogical chess engine with pluggable teaching modes (openings, traps, tactics, short wins, endgames). The platform teaches structured concepts, remembers user patterns, and explains intent clearly using a generic teaching engine and dynamic front-end UI.

## Core Architecture
```
/app/
├── backend/
│   ├── routes/               # coach_play.py (teaching, escape-squares endpoints)
│   ├── services/             # teaching_engine.py, escape_squares_service.py, pattern_decay_service.py, puzzle_extraction_service.py
│   ├── data/                 # opening_curriculum.json, traps.json, endgames.json
│   ├── coach_play/           # coach_game_session.py (session management)
│   ├── home_intelligence_service.py  # Dashboard intelligence with win streak
│   ├── community_learning_service.py # Community puzzle sharing
│   ├── server.py             # Lab coach-pick (decay model), pattern-puzzles, extract-puzzles endpoints
│   ├── tests/
├── frontend/
│   ├── src/
│   │   ├── components/coach/ # LessonPicker, CoachPlaySetup, CoachPlayBoard, CoachPlaySidebar, EscapeSquaresQuiz
│   │   ├── hooks/            # useTeachingMode, usePlayerData, useGuardian
│   │   └── pages/            # CoachPlay, CoachHome, Dashboard (Lab), PatternTraining, HomePage
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
- 18 Trap lessons, 10 Endgame lessons
- LessonPicker UI in coaching sidebar
- Hook-based frontend orchestration

### Phase 3 — P1 Features (Complete - April 2, 2026)
1. **Count Escape Squares** — Interactive quiz during tactical moments
2. **Immediate Review Data Attachment** — Auto-analysis on game end
3. **Dynamic Dashboard Mood via Win Streaks** — Momentum banner + negative profiling suppression

### Phase 4 — Pattern Decay & Community Puzzles (Complete - April 3, 2026)
1. **Recency-Weighted Decay Model** — Mistake counts use exponential decay (0.85/game) + recovery credit (0.3/clean game). States: active/declining/fading. The Lab Coach's Pick now shows realistic counts ("2 times recently") instead of inflated raw counts.
2. **Auto Puzzle Extraction Pipeline** — When games are analyzed, blunder positions are automatically extracted as community training puzzles tagged with cognitive gap patterns.
3. **Pattern Training Page** (`/training/pattern/:pattern`) — Shows user's own game positions first, then community puzzles. Tracks solve progress, never shows already-solved puzzles.
4. **"Practice [pattern] puzzles" button** on Lab Coach's Pick card to navigate directly to pattern-specific training.
5. **Merged coaching intelligence into HomePage** — Win streak banner, progress trend, mood suppression on the existing `/home` page.

## Key API Endpoints
- `GET /api/lab-coach-pick` — Lab dashboard with decay-model pick_pattern field
- `GET /api/training/pattern-puzzles/:pattern` — Pattern-specific puzzles (own + community, excludes solved)
- `POST /api/training/extract-puzzles` — Backfill puzzles from analyzed games
- `POST /api/training/puzzle-attempt` — Record puzzle solve attempt
- `POST /api/coach/play/escape-squares/check` — Escape squares quiz check
- `POST /api/coach/play/escape-squares/answer` — Validate escape squares answer
- `GET /api/coach/home-intelligence` — Dashboard data with win_streak + mood_override

## Key DB Collections
- `coach_sessions`: {session_id, current_fen, teaching_mode, escape_square_quizzes, result}
- `games`, `game_analyses`: Source of truth for patterns + puzzle extraction
- `community_puzzles`: {fen, best_move_san, issue_type, shared_by, source, approved, solve_rate}
- `puzzle_attempts`: {user_id, puzzle_id, correct, time_taken_ms, weakness_type}

## Prioritized Backlog

### P2
- Track community training puzzles to improve user error profiles
- More sophisticated puzzle matching (rating-aware, difficulty progression)

### Future
- Add "Tactics" and "Short Wins" pluggable lesson modes
- Deeper opening variation trees
- Streak leaderboard / daily challenge system

## 3rd Party Integrations
- OpenAI/GPT-4o-mini via Emergent LLM Key
- Chess.com / Lichess APIs (open/external)
- Google OAuth (Emergent-managed)

*Last Updated: April 3, 2026*
