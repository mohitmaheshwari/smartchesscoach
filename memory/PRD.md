# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized, data-driven chess coaching application. The coach should feel like a calm, direct, Indian mentor - not a simple move-suggester.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)
- **Engine Version:** P2.7 (Step 9 Complete)

---

## Implementation Status

### Step 0-4: CoachState Foundation ✅
### Step 5: Memory Continuity Layer ✅
### Step 6: Intent Recognition Layer ✅
### Step 7: Adaptive Teaching Style ✅
### Step 8: Breakthrough & Plateau Detection ✅
### Step 9: Focus Lock Mode ✅ (Mar 3, 2026)

**Core Service:** `focus_lock_service.py`

**Compliance Heuristics:**
| Lesson Key | Rule | Metric |
|------------|------|--------|
| FORCING_BLIND | Check forcing moves first | 1 - (missed_forcing / total_forcing_opportunities) |
| STOPPED_CALCULATION_EARLY | Calculate deeper at critical moments | 1 - (early_stop / total_critical_moments) |
| THREAT_VERIFICATION | Verify opponent threats | 1 - (missed_threat / total_threat_opportunities) |

**Lock States:**
- ACTIVE → In progress
- EXTENDED → Compliance < 75%, first failure
- STRICT → Declining trend or second failure
- COMPLETED → Success (avg ≥ 75%)
- FAILED → 2 failures → Deep Review required

**Thresholds:**
- Strong: ≥80% | Partial: 60-79% | Failed: <60%
- Completion: 75%
- Default games: 5 | Extension: +3

---

## ChessGuru Capabilities (P2.7)

1. Deterministic chess truth
2. Behavioral tagging + Context-aware moment selection
3. Intent interpretation + Timing calibration
4. Memory continuity
5. Adaptive teaching style (tier-appropriate)
6. Breakthrough & Plateau Detection (phase awareness)
7. **Focus Lock Mode** (behavioral enforcement)

---

## Key Files

### Step 9 - Focus Lock
- `/app/backend/coach_state/focus_lock_service.py`
- `/app/backend/coach_state/tests/test_focus_lock_service.py`

### Step 8 - Breakthrough Detection
- `/app/backend/coach_state/breakthrough_service.py`

### Step 7 - Adaptive Teaching
- `/app/backend/coach_state/teaching_style_service.py`

---

## Testing
- 128/128 unit tests passing
- 3 simulated lock runs validated

---

## Next Steps

### P0 - Step 9 Integration ✅ COMPLETED (Mar 3, 2026)
- ✅ Wire compliance calculation into analysis_worker
- ✅ API endpoint: `GET/POST /api/coach/focus-lock`
- ✅ UI: Focus Lock card on Dashboard (overrides Weekly Signal)
- ✅ **Step 9.1: Micro Reinforcement** - Minimal badge on Lab page + one-line coach feedback
- ✅ **Internal Analytics** - Silent logging to `focus_lock_analytics` collection

### 🛑 OBSERVATION PHASE (Do Not Add Features)
Wait for real user data before Step 10:
- Need: 10+ completed locks, 5+ extended locks, 3+ strict-mode triggers, 2+ deep-sessions
- Track: Completion rate, compliance distribution, quit patterns

### P1 - Step 10: Identity Formation Layer
- Long-term, identity-level feedback (e.g., "You are becoming a tactical player")
- Only starts after 10+ users complete full Focus Lock cycle
- Need real compliance distributions first

### P2 - Future Tasks
- Escalation psychology tuning
- UI for Memory/Intent display
- B2B features for human coaches
- Analytics dashboards
- RAG/LLM-based commentary

---

## API Reference (Step 9)

### Focus Lock Endpoints
```
GET  /api/coach/focus-lock
POST /api/coach/focus-lock/activate  {lesson_key: string, games?: number}
POST /api/coach/focus-lock/deactivate
```

### Response: GET /api/coach/focus-lock (when active)
```json
{
  "active": true,
  "lesson_key": "FORCING_BLIND",
  "rule_description": "Forcing moves before every decision.",
  "state": "ACTIVE",
  "headline": "Rule locked for 5 games.",
  "message": "...",
  "progress": {"completed": 2, "required": 5, "text": "2 of 5 games"},
  "compliance": {"average": 75, "color": "yellow", "text": "..."},
  "strict_mode": false,
  "should_trigger_deep_session": false,
  "failed_cycles": 0
}
```
