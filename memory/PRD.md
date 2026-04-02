# ChessGuru PRD

## Vision
A personalized chess coaching platform that teaches players HOW TO THINK about chess. The coach knows the player, adapts to their level, and provides structured training through real games.

## Core Pages

### Home (`/home`)
- Coach message hero: Top pattern shown prominently
- Review progress strip: Pending reviews with progress bar → Lab
- Last game card: Behavioral insight + opening + result
- Actions: Primary CTA tied to weakness + Play with Coach, Study Openings, Review in Lab
- Patterns Across Games + Chess DNA

### Lab Queue (`/lab`)
- Coach's Pick with meaningful "why" tied to recurring patterns
- Game cards with behavioral story (lesson_label + behavioral_insight)
- Auto-rotates Coach's Pick after completing a review

### Game Review (`/game/:gameId`)
- Accuracy ring header, result badge, consistent tab system
- Coach tab: Hero diagnosis, stat bar, worst move card, drill section
- Decrypt tab: Story-driven landing with core lesson narrative
- "Done reviewing" → completion overlay → next game CTA

### Progress (`/progress`) — COACHING PROGRESS REPORT
Not a stats dashboard. A coach telling you how you're growing:
- **Recent Form (Last 5) vs Big Picture**: Side-by-side accuracy, W/L, blunder rate
- **Weakness Control**: Each pattern tracked over time — improving/worsening/stable with visual indicators
- **Chess Understanding by Phase**: Opening/Middlegame/Endgame scores, weakest flagged only if < 75%
- **Review Impact**: Before/after blunder rate and accuracy proving reviews work
- **Game Timeline**: Horizontal bars per game with opponent, accuracy, result, lesson label, reviewed check

### Play with Coach
Guided game with curriculum enforcement, Think First approach, 9 openings

## Architecture
```
/app/backend/
  routes/coach_play.py
  services/
    progress_report_service.py     # NEW: Coaching progress computation
    opening_curriculum_engine.py
    coach_action_service.py
    coach_review_service.py
    memory_brain.py
    position_reader.py
    coach_move_pipeline.py
  data/opening_curriculum.json
  tests/
    test_all_flows.py              # 38-test E2E suite
    test_coaching_progress_report.py  # NEW: Progress report tests
  server.py

/app/frontend/
  pages/
    Dashboard.jsx                  # Lab queue
    LabV2.jsx                      # Game review + ReviewCompleteOverlay
    HomePage.jsx                   # Home
    UnifiedProgress.jsx            # Coaching Progress Report
    CoachPlay.jsx                  # Play with Coach
```

## Key Endpoints
- GET /api/progress/coaching-report (NEW: weakness control, habits, phases, review impact)
- GET /api/home/dashboard-v2 (accuracy fallback, review_progress, behavioral data)
- GET /api/lab-coach-pick (behavioral game cards, rotating pick)
- POST /api/lab/{game_id}/complete-review (review stats, summary, next game)

## Testing Status
- All pages: 100% pass rate (backend + frontend verified)
- Backend E2E: 38/38 PASSING

## Pending Tasks
### P0 — Fix Frontend API URL Imports (~24 files)
### P1 — Dead Code Removal
### P2 — Dependency & Script Cleanup
### Upcoming — CoachPlay.jsx monolith refactor, deeper opening trees
### Future — E2E tests, endgame expansion, voice coaching

*Last Updated: April 2026*
