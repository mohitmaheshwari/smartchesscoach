# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized chess coaching application "Thinking Simulator" focusing on deep, insightful coaching for every move. Core features: "Play with Coach" and "The Lab" for post-game analysis. UX principle: "One screen = one job" — Home = Decision, Play = Experience, Review = Understand, Train = Cure, Progress = Confidence.

## Vision
NOT a "move explanation system" but a "Thinking Simulator" that trains the user's thinking process. Never generic coaching — always specific (naming exact pieces, diagonals, pawn breaks). We are NOT Chess.com or Duolingo.

---

## What's Been Implemented

### Community Intelligence Training (March 2025) - NEW
Every user's mistake is another user's training material.
- **Backend**: `community_training_service.py` — auto-extracts training positions from V5 decrypted games (cp_loss >= 150), stores in `community_training_positions` collection
- **API**: `GET /api/training/community-feed`, `POST /api/training/solve-attempt`, `GET /api/training/pattern-stats`, `GET /api/training/community-count`
- **Frontend**: `ThinkingTraining.jsx` — interactive board, source attribution ("From a game by Ravi, 1180"), pattern badges, solve feedback, "Your Patterns" progress tracker
- **Auto-extraction hook**: When game gets V5 decrypted, positions auto-extracted for community pool
- **Testing**: 100% backend (10/10), 100% frontend

### Personalized Opening Portrait (March 2025) - NEW
Replaced generic encyclopedia with "Your Opening World" personal portrait.
- **Frontend**: `OpeningsOverview.jsx` rewritten — shows user's openings by color, win rates, weakest opening as "Focus" card, Coach Taught section, mastery badges
- **Backend fix**: `opening_theory_json_service.py` — normalized hyphen/underscore key lookup so `/openings/italian-game` and `/openings/italian_game` both work
- **Uses existing endpoints**: `/api/openings/repertoire`, `/api/training/opening-progress`
- **Testing**: 100% backend (12/12), 100% frontend

### Previous Completions
- Rich Game Summaries (`game_summary_service.py`)
- Educational Opponent Blunder Detection
- Game Review UX Simplification (step-by-step V5 Decrypt default)
- "Show My Plan" Interactive Cognitive Analysis (`plan_analysis_service.py`)
- Dynamic Plateau Breaker (hidden unless 3+ consecutive losses)
- V5 Decryption Engine with opponent move evaluation
- Pedagogical Opponent Engine
- Opening Theory System (24 openings, 49 variations)
- Player Habits Engine

---

## Architecture
```
/app
├── backend/
│   ├── routes/
│   │   ├── openings.py          # Opening endpoints
│   │   ├── coach.py, reflect.py, etc.
│   ├── services/
│   │   ├── community_training_service.py   # NEW: Community training positions
│   │   ├── game_decryption_v5_service.py   # V5 coaching engine
│   │   ├── game_summary_service.py         # Rich dashboard summaries
│   │   ├── plan_analysis_service.py        # Cognitive gap analysis
│   │   ├── opening_theory_json_service.py  # FIXED: Key normalization
│   │   ├── opening_library_service.py      # Repertoire matching
│   ├── server.py
└── frontend/src/
    ├── pages/
    │   ├── ThinkingTraining.jsx    # NEW: Community Intelligence Training
    │   ├── OpeningsOverview.jsx    # NEW: Personal Opening Portrait
    │   ├── Dashboard.jsx, LabV2.jsx, HomePage.jsx
    ├── components/
    │   ├── Layout.jsx, GameDecryptionV5.jsx, LichessBoard.jsx
```

---

## Tech Stack
- Frontend: React, Tailwind CSS, Shadcn/UI
- Backend: FastAPI, MongoDB (Motor async)
- Chess: python-chess, Stockfish
- LLM: GPT-4.1-mini via emergentintegrations (Emergent LLM Key)

---

## Backlog

### P1 - High Priority
- [ ] Interactive Board on Opening Portrait (step through YOUR lines vs theory)
- [ ] Variation Selector for Lessons (choose specific variation to study)
- [ ] Pattern Memory Injection ("You've made this mistake 3 times..." during games)
- [ ] Refactor `GameDecryptionV5.jsx` to use shared `V5CoachingCard.jsx`

### P2 - Medium Priority
- [ ] Admin UI for theory database management
- [ ] Community position opt-in/opt-out
- [ ] "Did you find it?" stats ("73% of players at your level missed this")
- [ ] Pattern clustering by theme (forks, pins, back rank)
- [ ] Endgame theory tree
- [ ] Habits Trend Dashboard
- [ ] Opening Proficiency in Coach Panel

### P3 - Nice to Have
- [ ] Voice coaching mode
- [ ] Major refactoring of `CoachPlay.jsx` (3500+ lines)
- [ ] Weekly learning summary
- [ ] Comparative analysis with similar-rated players

---

## Critical Notes for Future Agents
- **Never generic LLM text**: Prompts must demand specific explanations
- **Clear V5 cache**: If tweaking V5 coaching logic, clear `game_analyses` cache for that game
- **DB_NAME**: `test_database` (from .env), NOT `chess_coach`
- **Key normalization**: Opening keys can be hyphenated or underscored — `opening_theory_json_service.py` handles both

*Last Updated: March 2025*
