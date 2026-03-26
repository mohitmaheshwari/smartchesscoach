# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized chess coaching application "Thinking Simulator" focusing on deep, insightful coaching for every move. Core features: "Play with Coach" and "The Lab" for post-game analysis. UX principle: "One screen = one job" — Home = Decision, Play = Experience, Review = Understand, Train = Cure, Progress = Confidence.

## Vision
NOT a "move explanation system" but a "Thinking Simulator" that trains the user's thinking process. Never generic coaching — always specific. We are NOT Chess.com or Duolingo.

---

## What's Been Implemented

### Endgame Lesson System - NEW (March 2026)
- **Study page** now has Openings | Endgames tabs
- **10 endgame lessons** across 3 categories:
  - King & Pawn (5): Opposition, Key Squares, Rule of the Square, Pawn Breakthrough, King to Center
  - Rook Endgames (3): Lucena (Bridge), Philidor (3rd Rank Defense), Rook Activity
  - Queen vs Pawn (2): Stopping Promotion, Stalemate Tricks
- **30 validated positions** (all verified with python-chess for legal moves + both kings)
- **Interactive lesson UX**: Position → User tries move → Correct/Wrong feedback → Rule → Next Position
- **Completion screen** with score and the one rule to remember
- APIs: `GET /api/endgames/categories`, `GET /api/endgames/lesson/{cat}/{key}`, `POST /api/endgames/check-move`
- Home page Study card updated to "Openings & Endgames"

### Pattern Prescription on Home Page
- Home page shows "Patterns to Fix" card with top 3 recurring patterns
- Shows pattern label + "Xx recently" + severity indicator
- API: `GET /api/home/pattern-prescription`

### Cross-Screen Progress Tracking
- During Play with Coach, when user plays a book move, records "theory applied"
- Increments `times_applied_in_games` and `correct_applications`

### "Theory Applied" Moment
- Green note when user plays book move in taught opening during live play

### Interactive Board on Opening Portrait
- Click any opening row to expand inline board preview
- Step through theory main line with forward/back/reset

### Variation Selector for Lessons
- Pill buttons above lesson content to switch between variations

### Pattern Memory Injection
- Surfaces "You've had tactical misses X times" during Play with Coach

### Community Intelligence Training
- Every user's mistake becomes training for similar-rated players
- Pattern clustering/filtering tabs
- "Did you find it?" miss-rate stats

### Personalized Opening Portrait
- "Your Opening World" — repertoire by color, Focus card, Coach Taught section

### Previous Completions
- Rich Game Summaries, V5 Decryption Engine, Pedagogical Opponent
- "Show My Plan" Cognitive Analysis, Dynamic Plateau Breaker
- Opening Theory System (24 openings, 49 variations), Player Habits Engine
- Habit Insight cards on Home page

---

## Architecture
```
/app
├── backend/
│   ├── data/coaching/
│   │   ├── opening_theory_tree.json      # 3293 lines, 24 openings
│   │   └── endgame_theory_tree.json      # NEW: 30 positions, 10 lessons
│   ├── routes/
│   │   ├── openings.py
│   │   ├── coach_play.py
│   ├── services/
│   │   ├── endgame_theory_service.py     # NEW: Endgame lesson serving + move check
│   │   ├── community_training_service.py
│   │   ├── shared_coaching_v5.py
│   │   ├── opening_theory_json_service.py
│   ├── server.py                          # Endgame endpoints added
└── frontend/src/
    ├── pages/
    │   ├── HomePage.jsx                   # Study card → "Openings & Endgames"
    │   ├── OpeningsOverview.jsx           # UPDATED: Openings | Endgames tabs
    │   ├── EndgameLesson.jsx              # NEW: Interactive Position→Try→Teach
    │   ├── OpeningLesson.jsx
    │   ├── ThinkingTraining.jsx
    ├── components/
    │   ├── shared/V5CoachingCard.jsx
```

---

## Tech Stack
- Frontend: React, Tailwind CSS, Shadcn/UI, chess.js, Chessground
- Backend: FastAPI, MongoDB (Motor async), python-chess, Stockfish
- LLM: GPT-4.1-mini via emergentintegrations (Emergent LLM Key)

---

## Backlog

### P0 - Immediate
- [ ] Super Admin Dashboard (role-based access, user management, feedback queue)

### P1 - High Priority
- [ ] Refactor `GameDecryptionV5.jsx` to use shared `V5CoachingCard.jsx`
- [ ] User feedback on moves (Lab/Coach "This doesn't seem right" button → admin queue)

### P2 - Medium Priority
- [ ] Admin UI for theory database management (openings + endgames)
- [ ] Community position opt-in/opt-out
- [ ] "Theory Applied" celebration streak indicator
- [ ] Endgame theory expansion (minor piece endgames, more positions)
- [ ] Habits Trend Dashboard

### P3 - Nice to Have
- [ ] Voice coaching mode
- [ ] Major refactoring of `CoachPlay.jsx` (3500+ lines)
- [ ] Weekly learning summary
- [ ] Comparative analysis with similar-rated players

---

## Testing Status (All Passed)
- Iteration 155: Community Training — Backend 10/10, Frontend 100%
- Iteration 156: Opening Portrait — Backend 12/12, Frontend 100%
- Iteration 157: Interactive Board + Variations + Pattern Memory — Backend 15/15, Frontend 100%
- Iteration 158: Pattern Prescription + Theory Applied + Cross-screen — Backend 14/14, Frontend 100%
- Iteration 159: Pattern Clustering + Miss-rate + Habit Insights — Backend 3/3, Frontend 100%
- Iteration 160: Endgame Lesson System — Backend 22/22, Frontend 100%

## Critical Notes for Future Agents
- **Never generic LLM text**: Prompts must demand specific explanations
- **Clear V5 cache**: If tweaking coaching logic, clear `game_analyses` for that game
- **DB_NAME**: `test_database` (from .env)
- **Key normalization**: Opening keys handled in `opening_theory_json_service.py`
- **Endgame JSON cached**: Backend caches `endgame_theory_tree.json` in memory. Restart backend after changes.
- **All endgame positions validated**: Both kings present, all correct_move_uci verified as legal moves

*Last Updated: March 2026*
