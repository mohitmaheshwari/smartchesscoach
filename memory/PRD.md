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

### Lab Queue — `/lab` — REDESIGNED
Coach-driven game review queue showing:
- **Verdict strip**: W/L record with behavioral insight (e.g., "2 games thrown from winning positions")
- **Coach's Pick**: Most educational game with meaningful "why" tied to actual patterns
- **Game cards**: Each shows player's behavioral story (e.g., "Positional Wanderer", "Panic Under Pressure") not just stats
- **Behavioral labels per game**: lesson_label, behavioral_insight from enriched analysis

## Architecture
```
/app/backend/
  routes/coach_play.py             # Coach play routes
  services/                        # Core logic modules
  data/opening_curriculum.json     # Opening teaching trees
  tests/test_all_flows.py          # 38-test E2E backend suite
  server.py                        # Main FastAPI app (~10.8k lines)

/app/frontend/
  components/Lab/                  # Lab sub-components
  components/GameDecryptionV5.jsx  # Move-by-move walkthrough
  pages/Dashboard.jsx              # Lab queue page (redesigned)
  pages/LabV2.jsx                  # Game review page (redesigned)
  pages/CoachPlay.jsx              # Play with Coach
```

## Key Endpoints
- POST /api/coach/play/start, /api/coach/play/move
- GET /api/lab-coach-pick (enhanced: returns behavior, lesson_label, lesson per game)
- GET /api/lab/{game_id}/coach-action, /api/lab/{game_id}/coach-insight
- GET /api/coach/decryption/v5/{game_id}
- GET /api/analysis/{game_id}/enriched

## Testing Status
- Backend E2E: 38/38 PASSING
- Lab queue redesign: TESTED (100% backend + frontend)
- Game review redesign: TESTED (100% frontend)

## Completed Work

### Lab Queue Redesign (April 2026)
- Game cards show behavioral story per game (lesson_label, behavioral_insight)
- Coach's Pick uses actual recurring patterns for pick_reason
- Verdict strip with W/L + behavioral trend insight
- Better empty state, accuracy dots, and layout
- Fixed: decryption_v5_data list/dict type handling bug

### Game Review Redesign (April 2026)
- Header with accuracy ring, result badge, opening info
- Consistent tab system, coach narrative strip
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
Remove unused deps (boto3, huggingface_hub, etc.), move utility scripts to backend/scripts/.

### Upcoming
- Wire extracted components into CoachPlay.jsx (break 3,669-line monolith)
- Deeper opening variation trees

### Future
- Position summary improvements, Frontend E2E tests, endgame expansion, voice coaching

*Last Updated: April 2026*
