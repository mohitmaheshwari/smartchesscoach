# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized, data-driven chess coaching application. The coach should feel like a calm, direct, Indian mentor - not a simple move-suggester.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)
- **Engine Version:** P2.6 (Step 8 Complete)

---

## Implementation Status

### Step 0-4: CoachState Foundation ✅
### Step 5: Memory Continuity Layer ✅
### Step 6: Intent Recognition Layer ✅
### Step 7: Adaptive Teaching Style ✅
### Step 8: Breakthrough & Plateau Detection ✅ (Mar 3, 2026)

**6 States Detected:**
| State | Trigger | Action |
|-------|---------|--------|
| TILT_RISK | High volatility + blunder spike | Recovery Mode |
| BREAKTHROUGH | 30% blunder drop + 20% volatility drop | Level Up |
| CONFIDENCE_ILLUSION | Stable CP but high lesson repeat | Focus Lock |
| PLATEAU | 10+ games, stable trajectory, same lesson | Deep Session |
| STABLE_GROWTH | Volatility decreasing, discipline up | Continue Path |
| NORMAL | No special signal | Standard Flow |

**Detection Order:** TILT → BREAKTHROUGH → CONFIDENCE_ILLUSION → PLATEAU → STABLE_GROWTH → NORMAL

**Thresholds:**
- HIGH_VOLATILITY = 3.0
- BREAKTHROUGH_BLUNDER_DROP = 0.30 (30%)
- LESSON_REPEAT_HIGH = 0.50
- BLUNDER_SPIKE = 0.40 (40%)

---

## ChessGuru Capabilities (P2.6)

1. Deterministic chess truth
2. Behavioral tagging + Context-aware moment selection
3. Intent interpretation + Timing calibration
4. Memory continuity
5. Adaptive teaching style (tier-appropriate)
6. **Breakthrough & Plateau Detection** (phase awareness)

---

## Key Files

### Step 8 - Breakthrough Detection
- `/app/backend/coach_state/breakthrough_service.py`
- `/app/backend/coach_state/tests/test_breakthrough_service.py`

### Step 7 - Adaptive Teaching
- `/app/backend/coach_state/teaching_style_service.py`

### Step 6 - Intent Recognition
- `/app/backend/analysis/intent_recognition_service.py`
- `/app/backend/analysis/intent_quality_calibrator.py`

---

## Testing
- 108/108 unit tests passing
- 6 state detection fixtures validated
- Tier-aware copy verified

---

## Next Steps

### P0 - Immediate
- Add API endpoint `GET /api/coach/breakthrough-signal`
- Display on Home page (Coach Weekly Signal card)

### P1 - Future
- Step 9+ as user defines
- UI for Memory/Intent display
- B2B features
