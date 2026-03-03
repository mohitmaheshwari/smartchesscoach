# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a full-featured chess coaching application that analyzes games, identifies weaknesses, and provides personalized coaching with a GM-coach style coaching loop. The central goal is to create a hyper-personalized, data-driven chess coach that moves beyond generic engine analysis to provide Socratic-style, contextual feedback tailored to the user's individual playstyle, habits, and past mistakes. The coach should feel like a calm, direct, Indian mentor, not a simple move-suggester.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish with intelligent caching
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)
- **Opening Data:** Lichess Opening Explorer API (statistics only)
- **Engine Version:** P2.4 (Step 6: Intent Recognition Layer)

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

### Step 6: Intent Recognition Layer ✅ IN PROGRESS (Mar 3, 2026)

**User Request:** Enable the coach to infer the player's probable idea behind a move, evaluating the idea's quality separately from the move's quality.

**Phase 1: Core Services** ✅ COMPLETE
- `/app/backend/analysis/intent_recognition_service.py` - Deterministic intent detection
- `/app/backend/analysis/intent_quality_calibrator.py` - Human coach judgment calibration
- 50 unit tests passing

**Phase 2: Runtime Integration** ✅ COMPLETE
- Modified `analysis_worker.py` to call intent services during analysis
- Modified `coach_narrative_engine.py` to consume `intent_sentence`
- Intent fields attached to in-memory move evaluations
- Structured JSON logging for debugging

**Phase 3: 3-Game Realism Test** ✅ COMPLETE
| Archetype | Coach Explanation | Status |
|-----------|------------------|--------|
| Early Queen Attack | "You tried to start an attack. The idea is aggressive, but queen out early can become a target." | PASS |
| Missed Tactic While Winning | "You adjusted your position. The position demanded something forcing." | PASS |
| Counterplay While Worse | "You tried to start an attack. You were worse here, so looking for counterplay makes sense." | PASS |

**Phase 4: DB Schema Persistence** ⏳ PENDING USER APPROVAL
- Fields to add: `intent_type`, `intent_quality`, `intent_description`, `intent_sentence`
- Waiting for user confirmation that phrasing feels human before committing schema

**Key Design Decisions:**
- Intent only affects phrasing (intent_mirror_line), NOT analysis
- Intent recognition is deterministic (no LLM)
- Quality calibration uses human coach judgment model
- Pressure-aware phrasing makes coach feel observant

---

## Upcoming Tasks

### P0 - Immediate
- User review of 3-game realism test explanations
- If approved: Persist intent fields to DB schema

### P1 - Next Phase  
- Step 7: Adaptive Teaching Style
  - Coach style adapts to player behavior
  - Different phrasing for different learner types

### P2 - Future
- UI for Memory/Intent display
- Coach Chat & Deep Session Expansions
- B2B Features for human coaches

---

## Key Technical Concepts

### Intent Recognition (8 Types)
- ATTACKING, DEFENDING, DEVELOPING, IMPROVING_PIECE
- PREVENTING_THREAT, SIMPLIFYING, CREATING_THREAT, POSITIONAL_MANEUVER

### Quality Calibration Factors
1. **Position Pressure** (winning/better/equal/worse/losing)
2. **Timing Score** (phase-aware judgment)
3. **Opportunity Awareness** (forcing move available?)

### Indian Coach Tone Rules
- Never say "wrong move"
- Say "Idea was right, timing early"
- Say "Position needed different approach"
- Acknowledge counterplay when worse

---

## Key Files Reference

### Intent Recognition (Step 6)
- `/app/backend/analysis/intent_recognition_service.py`
- `/app/backend/analysis/intent_quality_calibrator.py`
- `/app/backend/analysis/__init__.py`
- `/app/backend/scripts/test_intent_realism.py`

### Integration Points
- `/app/backend/analysis_worker.py` - Calls intent services during analysis
- `/app/backend/coach_narrative_engine.py` - Consumes intent_sentence

### Memory (Step 5)
- `/app/backend/coach_state/coach_memory_service.py`
- `/app/backend/coach_state/lesson_resolver.py`

---

## Test Reports
- 50/50 intent recognition unit tests passing
- 3/3 realism test archetypes passing
- Engine version: P2.4
