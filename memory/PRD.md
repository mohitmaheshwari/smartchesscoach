# ChessGuru PRD

## Vision
A personalized chess coaching platform that teaches players HOW TO THINK about chess — not just what moves to play. The coach knows the player, adapts to their level, and provides structured training through real games.

## Core Product

### Play with Coach (Structured Training)
The flagship feature. A guided game where:
- Coach picks an opening to teach (currently: London System)
- Assesses what the user already knows from their game history
- Introduces the opening before the game starts
- Asks questions (not gives answers) — "Think first" approach
- Enforces the curriculum moves — wrong moves get rejected with explanation
- Coach (bot) plays curriculum responses (not random Stockfish)
- Explains every opponent move in the right panel
- Transitions to engine picks after opening ends

### Game Review (Lab)
Three view modes:
- **Coach tab** — Diagnose → Drill → Track (action-oriented)
- **Habits tab** — Summary/Habits/Memory panel
- **Decrypt tab** — Move-by-move analysis

### Opening Walkthrough
Guided replay of user's actual game in their opening with coach commentary.

## Architecture
```
/app/backend/
  services/
    opening_curriculum_engine.py     # Walks the curriculum tree, returns guidance
    opening_assessment_service.py    # Assesses user's opening knowledge from games
    coach_action_service.py          # Diagnose → Drill → Track for game review
    coach_review_service.py          # 5-section narrative review (preserved)
    move_intent_analyzer.py          # Analyzes WHAT a move does on the board
    smart_coach_feedback.py          # Rating-filtered feedback
    opening_walkthrough_service.py   # Guided opening replay
  data/
    opening_curriculum.json          # THE source of truth for opening teaching

/app/frontend/
  components/
    CandidateMoves.jsx              # Right panel: intro → feedback → opponent → hint → engine picks
    Lab/CoachAction.jsx             # Diagnose → Drill → Track
    Lab/CoachReview.jsx             # 5-section narrative (preserved)
  pages/
    CoachPlay.jsx                   # Play with Coach (3500+ lines, needs refactor)
    OpeningWalkthrough.jsx          # Guided opening replay
```

## Key Endpoints
- POST /api/coach/play/start — Start game with opening_key
- POST /api/coach/play/move — Play move (with curriculum enforcement)
- POST /api/coach/play/opening-guide — Curriculum guidance per position
- POST /api/coach/play/candidates — Stockfish top 3 (off-book only)
- POST /api/coach/play/smart-feedback — Intent-aware move feedback
- GET /api/coach/play/pregame-intro — Pre-game intro based on assessment
- GET /api/coach/play/opening-assessment — User's opening knowledge
- GET /api/lab/{game_id}/coach-action — Diagnose → Drill → Track
- GET /api/lab/{game_id}/coach-review — 5-section narrative

## Testing Status
- Backend curriculum flow: PASSING (end-to-end test verified)
- Frontend integration: NEEDS TESTING on server
- Coach timeout fix: Applied (dataclass field + fast path)
- Old coaching system conflicts: Partially resolved

## DO NOT TOUCH
1. backend/.env (Contains OpenAI Key, Google Keys, DB credentials)
2. backend/llm_service.py (Emergent vs Direct OpenAI switch logic)
3. frontend/.env (Backend URLs)
4. backend/routes/auth.py (Google OAuth)

## Upcoming Features (Priority Order)

### P0 — Fix & Stabilize
- Deploy and test full London curriculum on server
- Fix any remaining coach timeout issues
- Ensure right panel always shows content (feedback + opponent + hints)
- Fix Chess.com rating during onboarding

### P1 — Position Summary Section (NEXT FEATURE)
- New section in the right panel showing overall position assessment
- Updates every move during middlegame and endgame
- Shows: who's better, key features (open files, weak squares, piece activity), what to focus on
- Opponent move highlighted in its own dedicated section (separated from hints)
- Uses Stockfish eval + position analysis, not LLM

### P1 — More Opening Curriculums
- Italian Game curriculum
- Scandinavian Defense curriculum
- Auto-select opening based on user's weakest area

### P2 — Deeper Features
- Track improvement per session (re-assess after each coach game)
- Bot deliberately steers into user's weak variations
- "Fix It" drills connected to coach review insights
- Refactor CoachPlay.jsx (3500+ lines → smaller components)
- Refactor server.py (14k+ lines → modular routes)

### P3 — Future
- Endgame expansion
- Voice coaching mode
- "Your Week in Chess" digest
- Pre-game briefing

## Deployment
- Docker multi-container: backend + mongodb + frontend-builder
- Host: Hostinger VPS with Nginx proxy
- Utility scripts: diagnostics.py, requeue_missing.py, fix_indexes.py, backfill_training.py

*Last Updated: March 2026*
