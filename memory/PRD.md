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

### Game Review (Lab) — REDESIGNED
Three view modes with a redesigned header and improved UX:
- **Coach tab** — Diagnose → Drill → Track (action-oriented, hero diagnosis section)
- **Habits tab** — Pass/fail habit checklist + Chess DNA
- **Decrypt tab** — Move-by-move AI walkthrough with story-driven landing state

**Lab Header**: Accuracy ring (SVG), result badge (Won/Lost/Draw), opponent name, opening + time control
**Tab System**: Consistent pill-style tabs (Coach / Habits / Decrypt) with bg-muted container
**Coach Narrative Strip**: Shows key observation under header on Coach/Habits tabs

### Opening Walkthrough
Guided replay of user's actual game in their opening with coach commentary.

## Architecture
```
/app/backend/
  routes/                          # Modular API routes
    coach_play.py                  # All coach play routes
  services/
    opening_curriculum_engine.py   # Walks the curriculum tree
    opening_assessment_service.py  # Assesses user's opening knowledge
    coach_action_service.py        # Diagnose → Drill → Track
    coach_review_service.py        # 5-section narrative review
    move_intent_analyzer.py        # Analyzes WHAT a move does
    smart_coach_feedback.py        # Rating-filtered feedback
    memory_brain.py                # Central brain for user patterns
    position_reader.py             # Read the Board features
    coach_move_pipeline.py         # Unified coach move pipeline
  data/
    opening_curriculum.json        # THE source of truth for opening teaching
  tests/
    test_all_flows.py              # 38-test E2E backend suite

/app/frontend/
  components/
    Lab/
      CoachAction.jsx              # Diagnose → Drill → Track (enhanced)
      CoachInsightPanel.jsx        # Habits + Chess DNA
    GameDecryptionV5.jsx           # Move-by-move walkthrough (enhanced landing)
    CandidateMoves.jsx             # Right panel coaching
    coach/                         # Extracted coach play components
  hooks/
    useCoachGame.js
  pages/
    LabV2.jsx                      # Main Lab page (redesigned)
    CoachPlay.jsx                  # Play with Coach (3500+ lines, needs refactor)
```

## Key Endpoints
- POST /api/coach/play/start — Start game with opening_key
- POST /api/coach/play/move — Play move (with curriculum enforcement)
- POST /api/coach/play/opening-guide — Curriculum guidance per position
- GET /api/lab/{game_id}/coach-action — Diagnose → Drill → Track
- GET /api/lab/{game_id}/coach-insight — Habits + Chess DNA
- GET /api/coach/decryption/v5/{game_id} — Move-by-move V5 analysis
- GET /api/analysis/{game_id}/enriched — Full analysis with coach_summary

## Testing Status
- Backend E2E: 38/38 PASSING (test_all_flows.py)
- Lab page redesign: TESTED (100% frontend pass, both test games verified)
- Coach timeout fix: Applied
- Curriculum fast path: Working

## DO NOT TOUCH
1. backend/.env (Contains keys, DB credentials)
2. backend/llm_service.py (Emergent vs Direct OpenAI switch logic)
3. frontend/.env (Backend URLs)
4. backend/routes/auth.py (Google OAuth)

## Completed Work

### Lab Page Redesign (April 2026)
- Redesigned header with accuracy ring (SVG), result badge, opening info
- Consistent pill-style tab system (Coach/Habits/Decrypt)
- Coach tab: Hero diagnosis section with stat bar, worst move card, improved drill empty state
- Decrypt tab: Story-driven landing with core lesson narrative hook, Begin walkthrough CTA
- Coach narrative strip showing key observation on non-decrypt tabs

### Previous Work (March 2026)
- Built 5-section "Human Coach" Game Review
- Built CoachAction.jsx for Lab (Diagnose → Drill → Track)
- Rebuilt "Play with Coach" with opening_curriculum_engine.py (9 openings, 14 traps)
- "Think First" coaching, move_intent_analyzer.py, position_reader.py, memory_brain.py
- MAJOR REFACTOR: server.py from 14.5k to 10.8k lines
- 38-test E2E backend test suite

## Pending Tasks

### P0 — Fix Frontend API URL Imports (~24 files)
- ~24 files use process.env.REACT_APP_BACKEND_URL directly instead of import { API } from "@/App"
- Some missing /api suffix — causes broken API calls in production

### P1 — Dead Code Removal
- Delete orphaned backend/chess_coach_core/ directory
- Delete dead backend modules in coach_engine/
- Delete dead frontend components (RatingTrajectory, LearningPath, MemoryLane, etc.)

### P2 — Dependency & Script Cleanup
- Remove unused backend deps (boto3, huggingface_hub, scikit-learn, etc.)
- Remove axios from frontend package.json
- Move root-level utility scripts to backend/scripts/

### Upcoming
- Wire extracted components into CoachPlay.jsx (break down 3,669-line monolith)
- Deeper opening variation trees for existing 9 curriculums

### Future
- Position summary improvements in middlegame
- Frontend E2E tests (Playwright)
- Endgame expansion, voice coaching, weekly digest

## Deployment
- Docker multi-container: backend + mongodb + frontend-builder
- Host: Hostinger VPS with Nginx proxy

*Last Updated: April 2026*
