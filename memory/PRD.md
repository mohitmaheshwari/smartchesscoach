# ChessGuru PRD

## Original Problem Statement
A highly personalized, "coach-first" chess application with a modular, pedagogical chess engine with pluggable teaching modes (openings, traps, tactics, short wins, endgames). The platform teaches structured concepts, remembers user patterns, and explains intent clearly using a generic teaching engine and dynamic front-end UI.

## Core Architecture
```
/app/
├── backend/
│   ├── routes/               # coach_play.py, training.py
│   ├── services/             # teaching_engine.py, escape_squares_service.py, pattern_decay_service.py, puzzle_extraction_service.py
│   ├── data/                 # opening_curriculum.json, traps.json, endgames.json
│   ├── coach_play/           # coach_game_session.py
│   ├── home_intelligence_service.py
│   ├── community_learning_service.py
│   ├── server.py             # Lab coach-pick (decay model), pattern-puzzles (auto-backfill), extract-puzzles
│   ├── tests/
├── frontend/
│   ├── src/
│   │   ├── components/coach/ # LessonPicker, CoachPlaySidebar, EscapeSquaresQuiz
│   │   ├── hooks/            # useTeachingMode, usePlayerData, useGuardian
│   │   └── pages/            # CoachPlay, CoachHome, Dashboard (Lab), PatternTraining, HomePage
```

## What's Been Implemented

### Phase 1-2 — Core Platform + Teaching Modes (Complete)
- Real-time coaching, opening curriculum, postgame analysis, coach memory
- 18 Trap + 10 Endgame pluggable lessons with LessonPicker UI

### Phase 3 — P1 Features (Complete - April 2, 2026)
1. Count Escape Squares — Interactive quiz during tactical moments
2. Immediate Review Data Attachment — Auto-analysis on game end
3. Dynamic Dashboard Mood via Win Streaks — Momentum banner + suppression

### Phase 4 — Pattern Decay & Community Puzzles (Complete - April 3, 2026)
1. **Recency-Weighted Decay Model** — Exponential decay (0.85/game) + recovery credit. States: active/declining/fading. Lab Coach's Pick shows realistic counts.
2. **Auto Puzzle Extraction Pipeline** — Blunder positions auto-extracted from analyzed games as community training puzzles. Infers cognitive gaps from position characteristics when not explicitly tagged. Auto-backfill on first pattern training visit.
3. **Pattern Training Page** (`/training/pattern/:pattern`) — Own game positions first, then community puzzles. Tracks solve progress, never re-shows solved. Real user data: 158 puzzles across 3 patterns (calculation_depth: 101, tactical_oversight: 56, missed_tactic: 1).
4. **"Practice [pattern] puzzles"** button on Lab Coach's Pick card.
5. **Merged coaching intelligence into HomePage** — Win streak banner, progress trend, mood suppression.

## Key API Endpoints
- `GET /api/lab-coach-pick` — Lab dashboard with decay-model pick_pattern
- `GET /api/training/pattern-puzzles/:pattern` — Pattern puzzles (auto-backfills on first call)
- `POST /api/training/extract-puzzles` — Manual backfill trigger
- `POST /api/training/puzzle-attempt` — Record puzzle solve
- `GET /api/admin/feedback/export` — Export feedback as structured JSON for developer handoff

## Key DB Collections
- `community_puzzles`: {fen, best_move_san, issue_type, shared_by, source, approved, solve_rate, difficulty}
- `puzzle_attempts`: {user_id, puzzle_id, correct, time_taken_ms, weakness_type}

## Prioritized Backlog

### P2
- More sophisticated puzzle matching (rating-aware, difficulty progression)
- Puzzle solve rate feeds back into decay model as recovery credit

### Future
- Add "Tactics" and "Short Wins" pluggable lesson modes
- Deeper opening variation trees
- Daily puzzle streak / challenge system

## 3rd Party Integrations
- OpenAI/GPT-4o-mini via Emergent LLM Key
- Chess.com / Lichess APIs (open/external)
- Google OAuth (Emergent-managed)

*Last Updated: April 3, 2026*
