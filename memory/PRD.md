# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized chess coaching application "Thinking Simulator" focusing on deep, insightful coaching for every move. Core features: "Play with Coach" and "The Lab" for post-game analysis. UX principle: "One screen = one job" — Home = Decision, Play = Experience, Review = Understand, Train = Cure, Progress = Confidence.

## Vision
NOT a "move explanation system" but a "Thinking Simulator" that trains the user's thinking process. Never generic coaching — always specific. We are NOT Chess.com or Duolingo.

---

## What's Been Implemented (Session: March 2025)

### Pattern Prescription on Home Page - NEW
- Home page shows "Patterns to Fix" card with top 3 recurring patterns
- Shows pattern label + "Xx recently" + severity indicator (critical/concerning)
- Shows "X positions waiting" when matching training positions exist
- Clicking navigates to `/training`
- API: `GET /api/home/pattern-prescription`

### Cross-Screen Progress Tracking - NEW
- During Play with Coach, when user plays a book move in a taught opening, records it as "theory applied"
- Increments `times_applied_in_games` and `correct_applications` in `UserOpeningProgress`
- Opening Portrait Coach Progress shows "Applied Xx in games" when > 0
- Wired in `coach_play.py` → `opening_mastery.py` → `opening_teaching_integration.py`

### "Theory Applied" Moment - NEW
- When user plays the book move in a taught opening during live play, coaching card shows green note
- "You played the book move in the Italian Game. The theory is sticking."
- Subtle, not patronizing. Just a quiet acknowledgment.
- Frontend: V5CoachingCard renders `theory_applied` in emerald green box

### Interactive Board on Opening Portrait
- Click any opening row to expand inline board preview
- Step through theory main line with forward/back/reset + clickable move list
- Shows variation count, "Full Lesson" button

### Variation Selector for Lessons
- Pill buttons above lesson content to switch between variations
- Backend `?variation=key` parameter on `GET /api/openings/{key}`
- French Defense: 5 variations, Italian Game: 2 variations

### Pattern Memory Injection
- During Play with Coach, surfaces "You've had tactical misses X times" for recurring mistakes
- Backend: `pattern_memory_service.py` → `coach_play.py` → `V5CoachingCard.jsx`

### Community Intelligence Training
- Every user's mistake becomes training for similar-rated players
- Backend: `community_training_service.py` with 4 API endpoints
- Auto-extraction hook in V5 decryption pipeline

### Personalized Opening Portrait
- "Your Opening World" — shows repertoire by color, Focus card, Coach Taught section
- Fixed key normalization (hyphen/underscore)

### Previous Completions
- Rich Game Summaries, V5 Decryption Engine, Pedagogical Opponent
- "Show My Plan" Cognitive Analysis, Dynamic Plateau Breaker
- Opening Theory System (24 openings, 49 variations), Player Habits Engine

---

## Architecture
```
/app
├── backend/
│   ├── routes/
│   │   ├── openings.py              # Variation parameter
│   │   ├── coach_play.py            # Pattern memory + Theory applied
│   ├── services/
│   │   ├── community_training_service.py
│   │   ├── pattern_memory_service.py
│   │   ├── shared_coaching_v5.py      # pattern_memory + theory_applied fields
│   │   ├── opening_theory_json_service.py  # Key normalization
│   ├── server.py                      # Pattern prescription endpoint
└── frontend/src/
    ├── pages/
    │   ├── HomePage.jsx               # Pattern Prescription card
    │   ├── OpeningsOverview.jsx       # InlineBoardPreview + Coach Progress
    │   ├── OpeningLesson.jsx          # Variation selector
    │   ├── ThinkingTraining.jsx       # Community Intelligence
    ├── components/
    │   ├── shared/V5CoachingCard.jsx  # pattern_memory + theory_applied
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

### P2 - Medium Priority
- [ ] Admin UI for theory database management
- [ ] Community position opt-in/opt-out
- [ ] "Did you find it?" aggregate stats ("73% missed this")
- [ ] Pattern clustering by theme
- [ ] Endgame theory tree
- [ ] Habits Trend Dashboard
- [ ] Opening Proficiency in Coach Panel

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

## Critical Notes for Future Agents
- **Never generic LLM text**: Prompts must demand specific explanations
- **Clear V5 cache**: If tweaking coaching logic, clear `game_analyses` for that game
- **DB_NAME**: `test_database` (from .env)
- **Key normalization**: Opening keys handled in `opening_theory_json_service.py`
- **Pattern Memory**: Triggers for cp_loss >= 100 and severity in (mistake, blunder, inaccuracy)
- **Theory Applied**: Only triggers in first 24 moves, severity in (good, excellent, book)

*Last Updated: March 2025*
