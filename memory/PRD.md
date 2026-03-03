# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized, data-driven chess coaching application. The coach should feel like a calm, direct, Indian mentor - not a simple move-suggester.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)
- **Engine Version:** P2.6 (Step 8 + Integration Complete)

---

## Implementation Status

### Step 0-4: CoachState Foundation ✅
### Step 5: Memory Continuity Layer ✅
### Step 6: Intent Recognition Layer ✅
### Step 7: Adaptive Teaching Style ✅
### Step 8: Breakthrough & Plateau Detection ✅ (Mar 3, 2026)

**API Endpoint:** `GET /api/coach/breakthrough-signal`
- Returns state, headline, message, CTA
- Computes from last 20 games
- `show_card: false` for < 10 games

**Home Page Card:** `CoachWeeklySignalCard`
- Above Daily Mission
- State-aware styling
- CTA routes to relevant action

**6 States:**
| State | Headline | CTA |
|-------|----------|-----|
| TILT_RISK | "Rough stretch. Time to stabilize." | Recovery Mission |
| BREAKTHROUGH | "This week was real progress!" | Advanced Drill |
| CONFIDENCE_ILLUSION | "Looks okay — but the same pattern repeats." | Lock One Rule |
| PLATEAU | "You're stuck in the same mistake loop." | Deep Review |
| STABLE_GROWTH | "Consistency is improving." | Continue |
| NORMAL | "Keep going. Stay consistent." | Play Next |

---

## Key Files

### Step 8 - Breakthrough Detection
- `/app/backend/coach_state/breakthrough_service.py`
- `/app/backend/server.py` (endpoint: `/api/coach/breakthrough-signal`)
- `/app/frontend/src/components/Home/CoachWeeklySignalCard.jsx`
- `/app/frontend/src/pages/Dashboard.jsx` (card integration)

---

## Testing
- 108/108 unit tests passing
- Endpoint verified via curl
- Card hides for < 10 games

---

## Next Steps

### P0 - Step 9: Focus Lock Mode
- System enforces one rule for 5 games
- Tracks compliance per game
- Shows lock status in UI
- Unlocks after successful completion

### P1 - Future
- UI for Memory/Intent display
- Coach Chat expansions
- B2B features
