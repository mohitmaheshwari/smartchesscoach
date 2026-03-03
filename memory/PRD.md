# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized, data-driven chess coaching application. The central goal is to create a coach that moves beyond generic engine analysis to provide Socratic-style, contextual feedback tailored to the user's individual playstyle, habits, and past mistakes. The coach should feel like a calm, direct, Indian mentor, not a simple move-suggester.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish with intelligent caching
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)
- **Opening Data:** Lichess Opening Explorer API
- **Engine Version:** P2.5 (Step 7 Complete)

---

## Implementation Status

### Step 0-4: CoachState Foundation ✅ COMPLETE
- CoachState for per-user coaching continuity
- GameCoachSummary for structured game analysis
- Deep Coaching Sessions with 6-step flow
- Behavioral Maturity Layer with adaptive tone

### Step 5: Memory Continuity Layer ✅ COMPLETE
- Lesson resolver for canonical lesson identification
- Coach memory service for long-term memory
- Memory-aware narrative modifications
- 6-Game Realism Test: 4.02/5 PASS

### Step 6: Intent Recognition Layer ✅ COMPLETE (Mar 3, 2026)
- Deterministic intent detection (8 types)
- Human coach judgment calibration
- Contrast-structure phrasing ("X is fine, but here Y")
- 3-Game Realism Test: PASS

### Step 7: Adaptive Teaching Style ✅ COMPLETE (Mar 3, 2026)

**User Request:** Same truth, different delivery based on user maturity.

**Components Built:**
- `teaching_style_service.py` - StyleDirective, tier defaults, strictness switch
- Wording palettes for deterministic phrase rotation
- Strategy-specific component lists (PATTERN, TACTICAL, TURNING_POINT, POSITIVE)

**Cross-Tier Outputs:**
| Tier | Sentences | Key Features |
|------|-----------|--------------|
| Novice | 5 | Full explanation + encouragement + example cue |
| Developing | 4 | Clear guidance + light firmness |
| Disciplined | 3 | Crisp, direct, no comfort |
| Advanced | 2 | Minimal shorthand, no intent |

**Strictness Switch:**
- declining + lesson_repeated → firmer tone
- improving → add encouragement (Novice/Developing)

**Testing:** 87/87 unit tests passing

---

## Key Technical Concepts

### StyleDirective Schema
```python
@dataclass(frozen=True)
class StyleDirective:
    tier: MaturityTier
    strategy: StrategyType
    max_sentences: int
    include_intent: bool
    include_consequence: bool
    include_rule: bool
    include_encouragement: bool
    include_example_cue: bool
    firmness: FirmnessLevel  # soft | neutral | firm
    reduce_fluff: bool
    wording_palette_id: str
```

### Component Order per Strategy
- TACTICAL_COACHING Novice: [intent, break_point, consequence, rule, encouragement]
- TACTICAL_COACHING Advanced: [consequence, rule]

---

## Upcoming Tasks

### P1 - Next Steps
- User review of Step 7 tier progression
- Real game testing with actual user data

### P2 - Future
- UI for Memory/Intent display
- Coach Chat & Deep Session Expansions
- B2B Features for human coaches

---

## Key Files

### Step 7 - Adaptive Teaching
- `/app/backend/coach_state/teaching_style_service.py`
- `/app/backend/coach_state/tests/test_teaching_style_service.py`
- `/app/backend/scripts/test_step7_cross_tier.py`

### Step 6 - Intent Recognition
- `/app/backend/analysis/intent_recognition_service.py`
- `/app/backend/analysis/intent_quality_calibrator.py`

### Integration Points
- `/app/backend/coach_narrative_engine.py` - Uses StyleDirective
- `/app/backend/analysis_worker.py` - Enriches with intent
- `/app/backend/engine_config.py` - Version P2.5
