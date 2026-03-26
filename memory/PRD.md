# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized chess coaching application "Thinking Simulator" focusing on deep, insightful coaching for every move. Core features: "Play with Coach" and "The Lab" for post-game analysis. UX principle: "One screen = one job" — Home = Decision, Play = Experience, Review = Understand, Train = Cure, Progress = Confidence.

## Vision
NOT a "move explanation system" but a "Thinking Simulator" that trains the user's thinking process. Never generic coaching — always specific (naming exact pieces, diagonals, pawn breaks). We are NOT Chess.com or Duolingo.

---

## What's Been Implemented

### Interactive Board on Opening Portrait (March 2025) - NEW
- Click any opening row on `/openings-overview` to expand an inline board preview
- Step through theory main line with forward/back/reset buttons + clickable move list
- Shows variation count, "Full Lesson" button navigates to the lesson page
- Uses existing `/api/openings/{key}` endpoint

### Variation Selector for Lessons (March 2025) - NEW
- Pill buttons above lesson content to switch between variations (e.g., French: Advance vs Classical vs Winawer)
- Backend: Added `?variation=key` query parameter to `GET /api/openings/{key}` endpoint
- Frontend: `selectedVariation` state in OpeningLesson.jsx, resets board on variation change
- French Defense: 5 variations (12-18 moves each), Italian Game: 2 variations

### Pattern Memory Injection (March 2025) - NEW
- During Play with Coach, when user makes a mistake (cp_loss >= 100), checks for recurring patterns
- Surfaces "You've had tactical misses X times in your last Y games" in coaching card
- Backend: Hooked `pattern_memory_service.py` → `coach_play.py` in the V5 coaching pipeline
- Frontend: `V5CoachingCard.jsx` renders `pattern_memory` in an amber warning box
- Also added `pattern_memory` field to `V5Coaching` dataclass

### Community Intelligence Training (March 2025)
- Every user's mistake becomes training for similar-rated players
- Backend: `community_training_service.py` with 4 API endpoints
- Frontend: `ThinkingTraining.jsx` — interactive board, source attribution, pattern tracking
- Auto-extraction hook in V5 decryption pipeline

### Personalized Opening Portrait (March 2025)
- `OpeningsOverview.jsx` → "Your Opening World" personal portrait
- Shows repertoire by color, win rates, Focus card for weakest opening, Coach Taught section
- Fixed hyphen/underscore key normalization in `opening_theory_json_service.py`

### Previous Completions
- Rich Game Summaries, Educational Opponent Blunder Detection
- Game Review UX Simplification (step-by-step V5 Decrypt default)
- "Show My Plan" Interactive Cognitive Analysis
- Dynamic Plateau Breaker (hidden unless 3+ consecutive losses)
- V5 Decryption Engine, Pedagogical Opponent Engine
- Opening Theory System (24 openings, 49 variations)
- Player Habits Engine

---

## Architecture
```
/app
├── backend/
│   ├── routes/
│   │   ├── openings.py              # UPDATED: ?variation= parameter
│   │   ├── coach_play.py            # UPDATED: Pattern memory injection
│   ├── services/
│   │   ├── community_training_service.py
│   │   ├── pattern_memory_service.py  # Existing, now wired into live coaching
│   │   ├── shared_coaching_v5.py      # UPDATED: pattern_memory field
│   │   ├── opening_theory_json_service.py  # UPDATED: Key normalization
│   │   ├── game_decryption_v5_service.py
│   │   ├── plan_analysis_service.py
│   ├── server.py
└── frontend/src/
    ├── pages/
    │   ├── OpeningsOverview.jsx       # UPDATED: InlineBoardPreview
    │   ├── OpeningLesson.jsx          # UPDATED: Variation selector
    │   ├── ThinkingTraining.jsx
    │   ├── HomePage.jsx, Dashboard.jsx, LabV2.jsx
    ├── components/
    │   ├── shared/V5CoachingCard.jsx  # UPDATED: pattern_memory display
    │   ├── Layout.jsx, GameDecryptionV5.jsx, LichessBoard.jsx
```

---

## Tech Stack
- Frontend: React, Tailwind CSS, Shadcn/UI, chess.js, Chessground
- Backend: FastAPI, MongoDB (Motor async), python-chess, Stockfish
- LLM: GPT-4.1-mini via emergentintegrations (Emergent LLM Key)

---

## Backlog

### P1 - High Priority
- [ ] Refactor `GameDecryptionV5.jsx` to use shared `V5CoachingCard.jsx`
- [ ] Cross-screen progress tracking (opening taught by coach → applied in real game = milestone)

### P2 - Medium Priority
- [ ] Admin UI for theory database management
- [ ] Community position opt-in/opt-out
- [ ] "Did you find it?" stats ("73% of players at your level missed this")
- [ ] Pattern clustering by theme
- [ ] Endgame theory tree
- [ ] Habits Trend Dashboard
- [ ] Opening Proficiency in Coach Panel
- [ ] "Theory Applied" celebration during games

### P3 - Nice to Have
- [ ] Voice coaching mode
- [ ] Major refactoring of `CoachPlay.jsx` (3500+ lines)
- [ ] Weekly learning summary
- [ ] Comparative analysis with similar-rated players

---

## Testing Status (All Passed)
- Community Training: Backend 10/10, Frontend 100%
- Opening Portrait: Backend 12/12, Frontend 100%
- Interactive Board + Variation Selector + Pattern Memory: Backend 15/15, Frontend 100%

## Critical Notes for Future Agents
- **Never generic LLM text**: Prompts must demand specific explanations
- **Clear V5 cache**: If tweaking coaching logic, clear `game_analyses` for that game
- **DB_NAME**: `test_database` (from .env)
- **Key normalization**: Opening keys can be hyphenated or underscored — handled in `opening_theory_json_service.py`
- **Pattern Memory**: Only triggers for cp_loss >= 100 and severity in (mistake, blunder, inaccuracy)

*Last Updated: March 2025*
