# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized, data-driven chess coaching application. The coach should feel like a calm, direct, Indian mentor - not a simple move-suggester. Moves beyond generic engine analysis to provide Socratic-style, contextual feedback tailored to the user's individual playstyle, habits, and past mistakes.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish with intelligent caching
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)
- **Engine Version:** P2.5 (Step 7 Complete)

---

## Implementation Status

### Step 0-4: CoachState Foundation ✅ COMPLETE
### Step 5: Memory Continuity Layer ✅ COMPLETE
### Step 6: Intent Recognition Layer ✅ COMPLETE
### Step 7: Adaptive Teaching Style ✅ COMPLETE (Mar 3, 2026)

**Final Cross-Tier Outputs:**
| Tier | Sentences | Output |
|------|-----------|--------|
| Novice | 5 | Full explanation + encouragement |
| Developing | 4 | Clear guidance + actionable cue |
| Disciplined | 3 | Crisp, direct, no comfort |
| Advanced | 2 | Minimal shorthand |

**Key Components:**
- `teaching_style_service.py` - StyleDirective, tier defaults, strictness switch
- Strategy-specific component lists (PATTERN, TACTICAL, TURNING_POINT, POSITIVE)
- Lesson-key-aware cues (tactical → "Check forcing moves first")
- Trend-based strictness adjustment

---

## ChessGuru Capabilities (P2.5)

1. **Deterministic chess truth** - No hallucination
2. **Behavioral tagging** - Pattern recognition across games
3. **Context-aware moment selection** - CRS scoring
4. **Intent interpretation** - 8 intent types, quality calibration
5. **Timing calibration** - Phase-aware judgment
6. **Memory continuity** - Long-term coaching awareness
7. **Adaptive teaching style** - Tier-appropriate delivery

---

## Upcoming Tasks

### P0 - Step 8: Breakthrough & Plateau Detection
- Detect stagnation blocks
- Detect breakthrough weeks
- Detect "confidence illusion" (high accuracy but same pattern mistake)
- Not LLM-based - deterministic behavioral analysis

### P1 - Future
- UI for Memory/Intent display
- Coach Chat & Deep Session Expansions
- B2B Features for human coaches

---

## Key Files

### Step 7 - Adaptive Teaching
- `/app/backend/coach_state/teaching_style_service.py`
- `/app/backend/coach_narrative_engine.py`

### Step 6 - Intent Recognition
- `/app/backend/analysis/intent_recognition_service.py`
- `/app/backend/analysis/intent_quality_calibrator.py`

### Core
- `/app/backend/analysis_worker.py`
- `/app/backend/engine_config.py` - Version P2.5

---

## Testing
- 87/87 unit tests passing
- Cross-tier realism test: PASS
- All tier outputs validated by user
