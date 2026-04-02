# ChessGuru PRD

## Vision
A personalized chess coaching platform that teaches players HOW TO THINK about chess. The coach knows the player, adapts to their level, and provides structured training through real games.

## Core Pages

### Home (`/home`) — REDESIGNED
- Coach message hero: Top pattern shown prominently ("Leaving Pieces Hanging is showing up in almost every game")
- Review progress strip: Shows pending reviews with progress bar, links to Lab
- Last game card: Behavioral insight + opening + result (not just stats)
- Actions: Primary CTA tied to top weakness + Play with Coach, Study Openings, Review in Lab
- Patterns Across Games: Frequency + severity badges
- Chess DNA: Archetype + biggest leak

### Lab Queue (`/lab`) — REDESIGNED
- Coach's Pick with meaningful "why" tied to recurring patterns
- Game cards with behavioral story (lesson_label + behavioral_insight)
- Auto-rotates Coach's Pick after completing a review

### Game Review (`/game/:gameId`) — REDESIGNED
- Accuracy ring header, result badge, consistent tab system
- Coach tab: Hero diagnosis, stat bar, worst move card, drill section
- Decrypt tab: Story-driven landing with core lesson narrative
- "Done reviewing" → completion overlay with summary + next game CTA

### Progress (`/progress`) — REDESIGNED
- Coaching headline based on actual trends (not generic)
- Accuracy Journey chart with clickable colored dots
- Win Rate with correct insight (compares rates, not absolutes)
- Blunders Rising: Red alert when blunders increase
- Danger Zones: Clickable patterns with severity badges
- Review Progress: Games reviewed / total with progress bar
- Chess Identity + Last 10 Games bar chart

### Play with Coach — Structured Opening Training
Guided game with curriculum enforcement, Think First approach, 9 openings

## Key Endpoints
- GET /api/home/dashboard-v2 (accuracy fallback, review_progress, behavioral data)
- GET /api/progress/journey (win_trend, accuracy journey, blunder stats)
- GET /api/lab-coach-pick (behavioral game cards, rotating pick)
- POST /api/lab/{game_id}/complete-review (review stats, summary, next game)
- POST /api/lab-mark-reviewed/{game_id}
- GET /api/lab/{game_id}/coach-action, /api/lab/{game_id}/coach-insight
- GET /api/coach/decryption/v5/{game_id}

## Testing Status
- All pages: 100% pass rate (backend + frontend verified)
- Backend E2E: 38/38 PASSING (test_all_flows.py)

## Completed (April 2026)
- Home page redesign: coach message, review progress strip, behavioral last game card
- Progress page redesign: coaching headlines, fixed win rate insight, blunders rising alert
- Lab queue redesign: behavioral game cards, Coach's Pick with pattern-based reasoning
- Game review redesign: accuracy ring, coach tab hero, story-driven decrypt landing
- Review completion flow: "Done reviewing" → summary overlay → next game CTA
- Fixed: 0% accuracy bug (fallback to game_analyses), misleading "Holding steady" insight

## Pending Tasks
### P0 — Fix Frontend API URL Imports (~24 files)
~24 files use process.env.REACT_APP_BACKEND_URL directly instead of API import.

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
