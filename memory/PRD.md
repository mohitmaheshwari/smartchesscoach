# ChessGuru PRD

## Vision
A personalized chess coaching platform that teaches players HOW TO THINK about chess — not just what moves to play. The coach knows the player, adapts to their level, and provides structured training through real games.

## Core Product

### Play with Coach (Structured Training)
Flagship feature. Guided game where coach picks an opening, teaches via "Think First" approach, enforces curriculum moves, and explains every move.

### Game Review (Lab) — `/game/:gameId`
Three view modes with redesigned header:
- **Coach tab** — Diagnose → Drill → Track (hero diagnosis, stat bar, worst move card)
- **Habits tab** — Pass/fail habit checklist + Chess DNA
- **Decrypt tab** — Move-by-move AI walkthrough with story-driven landing
- **"Done reviewing" button** — Triggers review completion flow

### Lab Queue — `/lab`
Coach-driven game review queue:
- **Verdict strip**: W/L record with behavioral insight
- **Coach's Pick**: Most educational game with meaningful "why" tied to actual patterns
- **Game cards**: Each shows player's behavioral story (lesson_label + behavioral_insight)
- **Auto-rotation**: After completing a review, Coach's Pick rotates to next game

### Review Completion Flow
When user clicks "Done reviewing":
1. Backend saves review stats (concepts learned, drills solved, tabs visited, moves viewed)
2. Game marked as reviewed with timestamp
3. Completion overlay shows: lesson summary, takeaway, stats
4. "Next game: vs {opponent}" button navigates to next unreviewed game
5. Lab queue auto-rotates Coach's Pick

## Architecture
```
/app/backend/
  routes/coach_play.py             # Coach play routes
  services/                        # Core logic modules
  data/opening_curriculum.json     # Opening teaching trees
  tests/test_all_flows.py          # 38-test E2E backend suite
  tests/test_review_completion.py  # Review completion tests
  server.py                        # Main FastAPI app

/app/frontend/
  components/Lab/                  # Lab sub-components
  components/GameDecryptionV5.jsx  # Move-by-move walkthrough
  pages/Dashboard.jsx              # Lab queue page
  pages/LabV2.jsx                  # Game review page + ReviewCompleteOverlay
  pages/CoachPlay.jsx              # Play with Coach
```

## Key Endpoints
- POST /api/coach/play/start, /api/coach/play/move
- GET /api/lab-coach-pick (returns behavior, lesson_label, lesson per game)
- POST /api/lab/{game_id}/complete-review (saves stats, marks reviewed, returns summary + next_game)
- POST /api/lab-mark-reviewed/{game_id}
- GET /api/lab/{game_id}/coach-action, /api/lab/{game_id}/coach-insight
- GET /api/coach/decryption/v5/{game_id}
- GET /api/analysis/{game_id}/enriched

## Testing Status
- Backend E2E: 38/38 PASSING (test_all_flows.py)
- Review completion flow: 100% (9 backend + frontend verified)
- Lab queue redesign: 100%
- Game review redesign: 100%

## Completed Work

### Review Completion Flow (April 2026)
- "Done reviewing" button in game review header
- POST /api/lab/{game_id}/complete-review endpoint (saves stats, marks reviewed, returns summary + next_game)
- ReviewCompleteOverlay: lesson summary, takeaway, next game CTA, lab queue link
- Coach's Pick auto-rotates after completing a review
- Button hidden for already-reviewed games

### Lab Queue Redesign (April 2026)
- Game cards show behavioral story per game (lesson_label, behavioral_insight)
- Coach's Pick uses actual recurring patterns for pick_reason
- Verdict strip with W/L + behavioral trend insight

### Game Review Redesign (April 2026)
- Header with accuracy ring, result badge, opening info
- Coach tab: hero diagnosis, stat bar, worst move card
- Decrypt tab: story-driven landing with core lesson narrative

### Previous Work (March 2026)
- 5-section Human Coach Game Review, opening curriculum engine (9 openings)
- Think First coaching, move intent analyzer, position reader, memory brain
- server.py refactor (14.5k → 10.8k lines), 38-test E2E suite

## Pending Tasks

### P0 — Fix Frontend API URL Imports (~24 files)
~24 files use process.env.REACT_APP_BACKEND_URL directly instead of import { API } from "@/App". Some missing /api suffix.

### P1 — Dead Code Removal
Delete orphaned backend/chess_coach_core/, dead coach_engine modules, dead frontend components.

### P2 — Dependency & Script Cleanup
Remove unused deps, move utility scripts to backend/scripts/.

### Upcoming
- Wire extracted components into CoachPlay.jsx (break 3,669-line monolith)
- Deeper opening variation trees

### Future
- Position summary improvements, Frontend E2E tests, endgame expansion, voice coaching

*Last Updated: April 2026*
