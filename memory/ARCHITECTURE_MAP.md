# ChessGuru Architecture Mapping

**Last Updated:** March 14, 2026

This document maps the ideal ChessGuru architecture against what's already implemented.

---

## Executive Summary

| Layer | Ideal Architecture | Current Status | Gap |
|-------|-------------------|----------------|-----|
| Layer 1: Chess Truth Engine | Stockfish + DBs + Detectors | ✅ 90% DONE | Minor gaps |
| Layer 2: Position Insight Object | Single source of facts | 🟡 70% DONE | Needs consolidation |
| Layer 3: Player Model | User strengths/weaknesses | ✅ 85% DONE | Needs unification |
| Layer 4: Lesson Candidate Generator | Multiple lessons per position | 🟡 60% DONE | Exists but scattered |
| Layer 5: 7 Teaching Modes | Structured teaching modes | 🟡 50% DONE | Partially implemented |
| Layer 6: Lesson Selection Engine | Scoring + prioritization | ✅ 80% DONE | Needs integration |
| Layer 7: Mistake Fingerprint | Pattern tracking + decay | ✅ 85% DONE | Needs wiring |
| Language Layer | Template + optional LLM | 🟡 60% DONE | LLM over-used |

**Overall Assessment:** ~70% of the architecture EXISTS but is scattered across services and not properly integrated into the Play with Coach flow.

---

## Layer 1: Chess Truth Engine

### Required Components
| Component | Status | File | Notes |
|-----------|--------|------|-------|
| Stockfish integration | ✅ DONE | `stockfish_service.py` | Full engine integration |
| Opening database | ✅ DONE | `services/opening_mastery.py` | 1808 lines, comprehensive |
| Trap library | ✅ DONE | `services/trap_library.py` | 20+ traps with sequences |
| Tactical pattern detection | ✅ DONE | `mistake_classifier.py` | Fork, pin, skewer, discovery, etc. |
| Game phase detection | ✅ DONE | `mistake_classifier.py` | By piece count, not move number |
| Material analysis | ✅ DONE | `position_analyzer.py` | Full material tracking |
| King safety analysis | ✅ DONE | `position_analyzer.py` | Pawn shield, open files |

### Key Files
```
/app/backend/stockfish_service.py (95 lines - StockfishEngine class)
/app/backend/mistake_classifier.py (1884 lines - Deterministic classifier)
/app/backend/position_analyzer.py (analysis functions)
/app/backend/services/opening_mastery.py (1808 lines - Opening DB)
/app/backend/services/trap_library.py (Trap sequences)
```

### Gap Analysis
- ✅ All core truth components exist
- ⚠️ Not unified into single "Chess Truth Engine" class
- ⚠️ Pattern detection scattered across multiple files

---

## Layer 2: Position Insight Object

### Ideal Schema
```json
{
  "fen": "string",
  "move_number": 14,
  "game_phase": "middlegame",
  "played_move": "h3",
  "best_move": "Nd5",
  "eval_before_cp": 40,
  "eval_after_cp": -135,
  "eval_loss_cp": 175,
  "quality_label": "mistake",
  "themes_detected": ["missed_fork", "weak_center"],
  "tactical_patterns": ["knight_fork"],
  "strategic_patterns": ["center_control"],
  "king_safety": {"white": "safe", "black": "exposed"},
  "trap_context": {"known_trap_available": false}
}
```

### Current Implementation
| Field | Status | Source |
|-------|--------|--------|
| FEN, move_number | ✅ | Throughout |
| game_phase | ✅ | `mistake_classifier.py` GamePhase enum |
| played_move, best_move | ✅ | Stockfish analysis |
| eval_before/after | ✅ | Stockfish |
| quality_label | ✅ | `mistake_classifier.py` MistakeType enum |
| themes_detected | ✅ | `cognitive_gap_service.py`, `awareness_gap_rules.py` |
| tactical_patterns | ✅ | `mistake_classifier.py` |
| strategic_patterns | 🟡 | Partial in `position_analyzer.py` |
| king_safety | ✅ | `position_analyzer.py` |
| trap_context | ✅ | `trap_library.py` |

### Key Files
```
/app/backend/mistake_classifier.py - MistakeContext dataclass (line 91)
/app/backend/coach_moment_selector.py - ScoredMove dataclass (line 58)
/app/backend/awareness_gap_rules.py - AwarenessGapEngine (line 175)
```

### Gap Analysis
- ⚠️ No single unified "PositionInsight" object
- ⚠️ Context scattered across multiple dataclasses
- 📋 TODO: Create unified `PositionInsightObject` class

---

## Layer 3: Player Model

### Ideal Schema
```json
{
  "player_id": "U123",
  "rating_estimate": 1050,
  "experience_band": "beginner",
  "strengths": ["basic_opening_development"],
  "weaknesses": ["missed_fork", "hanging_piece"],
  "coach_style": "friendly",
  "mistake_fingerprint_summary": {
    "top_tactical_issue": "missed_fork",
    "top_strategic_issue": "king_safety_neglect",
    "top_behavioral_issue": "tunnel_vision"
  }
}
```

### Current Implementation
| Component | Status | File |
|-----------|--------|------|
| Rating bands | ✅ DONE | `deterministic_coach_service.py` line 50 |
| Player identity profile | ✅ DONE | `services/player_identity.py` (1402 lines) |
| Strengths/weaknesses | ✅ DONE | `player_identity.py` PlayerIdentity class |
| Blunder taxonomy | ✅ DONE | `player_identity.py` BlunderType enum (line 40) |
| Play style classification | ✅ DONE | `player_identity.py` PlayStyle enum (line 78) |
| Coach memory | ✅ DONE | `services/coach_memory.py` CoachMemory class (line 76) |
| Habit tracking | ✅ DONE | `coach_memory.py` UserHabit class (line 37) |
| Learning progress | ✅ DONE | `coach_memory.py` LearningProgress class (line 51) |

### Key Files
```
/app/backend/services/player_identity.py (1402 lines)
/app/backend/services/coach_memory.py (787 lines)
/app/backend/deterministic_coach_service.py (1975 lines)
/app/backend/behavioral_maturity_service.py
```

### Gap Analysis
- ✅ Comprehensive player model exists
- ⚠️ Multiple overlapping systems (player_identity vs coach_memory)
- 📋 TODO: Unify into single PlayerModel class

---

## Layer 4: Lesson Candidate Generator

### Ideal Behavior
One position → Multiple lesson candidates → Score each → Pick best

### Current Implementation
| Component | Status | File |
|-----------|--------|------|
| Lesson key mapping | ✅ DONE | `lesson_key_mapping.py` |
| Lesson resolver | ✅ DONE | `lesson_resolver.py` (327 lines) |
| Lesson registry | ✅ DONE | `lesson_resolver.py` LESSON_REGISTRY (line 55) |
| Core lesson extraction | ✅ DONE | `blunder_intelligence_service.py` get_core_lesson() |

### Key Files
```
/app/backend/lesson_resolver.py - LESSON_REGISTRY dict
/app/backend/lesson_key_mapping.py - derive_lesson_key()
/app/backend/blunder_intelligence_service.py - get_core_lesson() (line 155)
```

### Gap Analysis
- ⚠️ Currently picks ONE lesson, doesn't generate candidates
- 📋 TODO: Generate multiple candidates, then score

---

## Layer 5: 7 Teaching Modes

### Required Modes
| Mode | Ideal Use | Current Status | File |
|------|-----------|----------------|------|
| 1. Immediate Mistake Correction | Error just happened | 🟡 Partial | `realtime_coaching_feedback.py` |
| 2. Tactical Pattern Teaching | Fork/pin/skewer present | ✅ DONE | `active_teaching_engine.py`, `trap_library.py` |
| 3. Strategic Concept Teaching | No tactic, positional idea | 🟡 Partial | `phase_theory_service.py` |
| 4. Opening Guidance | Early game positions | ✅ DONE | `opening_mastery.py`, `opening_teaching_integration.py` |
| 5. Trap Alert | Known trap nearby | ✅ DONE | `trap_library.py` |
| 6. Reinforcement | User found good move | 🟡 Partial | `active_teaching_engine.py` |
| 7. Endgame Principle | Simplified position | 🟡 Partial | `server.py` endgame lesson endpoints |

### Key Files
```
/app/backend/services/active_teaching_engine.py (729 lines) - FeedbackType enum
/app/backend/services/realtime_coaching_feedback.py - Immediate feedback
/app/backend/services/opening_teaching_integration.py (698 lines)
/app/backend/phase_theory_service.py - Strategic lessons
```

### Gap Analysis
- ⚠️ Modes exist but not as explicit enum/selector
- 📋 TODO: Create TeachingMode enum and mode selector

---

## Layer 6: Lesson Selection Engine (THE MOAT)

### Ideal Scoring Formula
```python
lesson_score = (
    severity * 0.28 +
    clarity * 0.17 +
    player_relevance * 0.16 +
    teachability * 0.14 +
    recurrence * 0.10 +
    novelty * 0.05 +
    phase_relevance * 0.05 +
    curriculum_fit * 0.05
) - (
    repetition_penalty * 0.10 +
    overload_penalty * 0.08
)
```

### Current Implementation
| Component | Status | File |
|-----------|--------|------|
| CRS (Coaching Relevance Score) | ✅ DONE | `coach_moment_selector.py` line 39 |
| Behavior score | ✅ DONE | `coach_moment_selector.py` |
| Turning point score | ✅ DONE | `coach_moment_selector.py` |
| Tactical score | ✅ DONE | `coach_moment_selector.py` |
| Context score | ✅ DONE | `coach_moment_selector.py` |
| Pattern frequency tracking | ✅ DONE | `coach_moment_selector.py` ScoredMove.pattern_frequency |
| Selection reason | ✅ DONE | `coach_moment_selector.py` SelectionReason enum (line 29) |

### Key Files
```
/app/backend/coach_moment_selector.py (449 lines) - CRS system
/app/backend/lesson_resolver.py - Lesson intensity scoring
/app/backend/position_context_service.py - Context scoring
```

### Gap Analysis
- ✅ Scoring system EXISTS and is sophisticated
- ⚠️ Not integrated into Play with Coach flow!
- 📋 TODO: Wire CRS into real-time coaching

---

## Layer 7: Mistake Fingerprint System

### Ideal Buckets
1. Tactical (missed_fork, hanging_piece, etc.)
2. Strategic (weak_center, king_safety_neglect, etc.)
3. Phase (opening_errors, middlegame_tactics, endgame_technique)
4. Behavioral (tunnel_vision, greedy_capture, rushed_move)

### Current Implementation
| Bucket | Status | File |
|--------|--------|------|
| Tactical patterns | ✅ DONE | `blunder_intelligence_service.py` BEHAVIORAL_PATTERNS |
| Strategic patterns | ✅ DONE | `player_identity.py` BlunderType enum |
| Phase tracking | ✅ DONE | `mistake_classifier.py` GamePhase enum |
| Behavioral inference | ✅ DONE | `blunder_intelligence_service.py` |
| Decay system | 🟡 Partial | `behavioral_maturity_service.py` |
| Session fingerprint | 🟡 Partial | `coach_state_service.py` |

### Key Files
```
/app/backend/blunder_intelligence_service.py (3951 lines) - Core fingerprinting
/app/backend/services/player_identity.py - Long-term identity
/app/backend/behavioral_maturity_service.py - Behavioral tracking
```

### Gap Analysis
- ✅ Fingerprinting exists and is comprehensive
- ⚠️ Not surfaced in Play with Coach UI
- 📋 TODO: Show fingerprint insights in coaching

---

## Language Layer

### Current LLM Usage
| Endpoint | Uses LLM? | Should Use LLM? |
|----------|-----------|-----------------|
| Move explanation | ✅ YES | 🟡 Optional |
| Training plan description | ✅ YES | 🟡 Optional |
| Teaching feedback | ❌ NO | ✅ Correct |
| Trap teaching | ❌ NO | ✅ Correct |
| Opening guidance | ❌ NO | ✅ Correct |

### Key Files
```
/app/backend/services/active_teaching_engine.py - Template-based (NO LLM)
/app/backend/services/realtime_coaching_feedback.py - Template-based (NO LLM)
/app/backend/llm_service.py - LLM calls
/app/backend/server.py lines 6485-6503 - Move explanation LLM
```

### Gap Analysis
- ⚠️ LLM used for move explanations (could be template)
- 📋 TODO: Make LLM optional, template as fallback

---

## Integration Gap: Play with Coach

### The Critical Issue
All these powerful services exist but are NOT wired into `/coach/play/*` endpoints!

### Current Flow (Broken)
```
User Move → Stockfish eval → Generic feedback → Display
```

### Ideal Flow
```
User Move 
    → Stockfish eval 
    → Position Insight Object 
    → Lesson Candidate Generator 
    → Lesson Selection Engine (CRS) 
    → Teaching Mode Selector 
    → Explanation Builder 
    → Display
```

### Files to Modify
```
/app/backend/server.py - /coach/play/move endpoint (line ~8936)
/app/backend/routes/coach_play.py - Additional endpoints
/app/frontend/src/pages/CoachPlay.jsx - UI integration
```

---

## Priority Implementation Plan

### Phase 1: Wire Existing Systems (1-2 weeks)
1. Create unified `PositionInsightObject` from existing components
2. Wire `coach_moment_selector.py` CRS into `/coach/play/move`
3. Wire `lesson_resolver.py` into real-time feedback
4. Surface `mistake_fingerprint` in CoachInsightCard

### Phase 2: Teaching Mode Selector (1-2 weeks)
1. Create `TeachingMode` enum with 7 modes
2. Build `select_teaching_mode()` function
3. Route to appropriate template system per mode
4. Integrate with existing `active_teaching_engine.py`

### Phase 3: Language Layer Cleanup (1 week)
1. Make LLM calls optional with template fallback
2. Expand template variety in `realtime_coaching_feedback.py`
3. Add tone variation without LLM

### Phase 4: UI Polish (1 week)
1. Show teaching mode in UI
2. Display fingerprint insights
3. Single-lesson-per-moment enforcement

---

## File Reference Quick Lookup

### Core Chess Truth
- `stockfish_service.py` - Engine
- `mistake_classifier.py` - Pattern detection
- `position_analyzer.py` - Position analysis

### Player Model
- `services/player_identity.py` - Identity system
- `services/coach_memory.py` - Memory system
- `deterministic_coach_service.py` - Rating bands

### Lesson System
- `coach_moment_selector.py` - CRS scoring
- `lesson_resolver.py` - Lesson registry
- `blunder_intelligence_service.py` - Fingerprinting

### Teaching
- `services/active_teaching_engine.py` - Teaching feedback
- `services/realtime_coaching_feedback.py` - Real-time templates
- `services/opening_teaching_integration.py` - Opening teaching

### Current Play with Coach
- `server.py` lines 8778-9200 - Core endpoints
- `routes/coach_play.py` - Additional routes
- `frontend/src/pages/CoachPlay.jsx` - Frontend

---

## Conclusion

**You have built 70-80% of a world-class chess coaching engine.**

The problem is not missing code. The problem is:
1. Code exists but is scattered
2. Sophisticated systems not wired into Play with Coach
3. No unified orchestration layer

**Next step:** Create a `ChessCoachOrchestrator` class that:
1. Takes a position + user move
2. Calls existing services in correct order
3. Returns unified coaching response
4. Wires into `/coach/play/move` endpoint
