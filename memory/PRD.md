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
- **Engine Version:** P2.4 (Step 6 Complete)

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

**Final Approved Explanations:**
| Archetype | Coach Explanation |
|-----------|------------------|
| Early Queen | "You tried to start an attack. The idea is aggressive, but bringing the queen out early can make it a target." |
| Missed Tactic | "Adjusting the position is fine, but here the position demanded something forcing." |
| Counterplay | "You tried to start an attack. You were worse here, so looking for counterplay makes sense." |

**Components Built:**
- `intent_recognition_service.py` - Deterministic intent detection (8 types)
- `intent_quality_calibrator.py` - Human coach judgment calibration
- Integration in `analysis_worker.py` - Enriches move evaluations
- Integration in `coach_narrative_engine.py` - Consumes intent_sentence

**Intent Fields Persisted (MongoDB):**
```
move_evaluations[].intent_type       # ATTACKING, DEFENDING, etc.
move_evaluations[].intent_quality    # excellent, good, reasonable, premature, incorrect
move_evaluations[].intent_sentence   # Full coach explanation
move_evaluations[].intent_pressure   # winning, better, equal, worse, losing
move_evaluations[].intent_confidence # Detection confidence
move_evaluations[].intent_timing_score # Phase-aware judgment
```

**Testing:** 50/50 unit tests passing

---

## Upcoming Tasks

### P1 - Step 7: Adaptive Teaching Style
- Coach style adapts to player type
- Novice: More explanation, encouragement
- Disciplined: Standard feedback
- Advanced: Minimalism, sharper tone

### P2 - Future
- UI for Memory/Intent display
- Coach Chat & Deep Session Expansions
- B2B Features for human coaches

---

## Key Technical Concepts

### Intent Types (8)
- ATTACKING, DEFENDING, DEVELOPING, IMPROVING_PIECE
- PREVENTING_THREAT, SIMPLIFYING, CREATING_THREAT, POSITIONAL_MANEUVER

### Quality Calibration (Affirm → Contrast → Correction)
- Position Pressure (winning/better/equal/worse/losing)
- Timing Score (phase-aware)
- Opportunity Awareness (forcing move available?)

### Indian Coach Tone Rules
- Never say "wrong move"
- Use contrast structure: "X is fine, but here Y"
- "Demanded" > "was available" (urgency)
- Validate counterplay when worse

---

## Key Files

### Intent Recognition (Step 6)
- `/app/backend/analysis/intent_recognition_service.py`
- `/app/backend/analysis/intent_quality_calibrator.py`
- `/app/backend/scripts/test_intent_realism.py`

### Integration Points
- `/app/backend/analysis_worker.py` - Calls intent services
- `/app/backend/coach_narrative_engine.py` - Consumes intent_sentence
- `/app/backend/engine_config.py` - Version P2.4

### Memory (Step 5)
- `/app/backend/coach_state/coach_memory_service.py`
- `/app/backend/coach_state/lesson_resolver.py`
