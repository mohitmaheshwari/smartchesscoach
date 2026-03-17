# ChessGuru - E2 Handoff Summary
## March 15, 2026

### Project Overview
ChessGuru is a hyper-personalized chess coaching application with a deterministic "Chess Brain" engine at its core. The user's vision is to move beyond generic LLM-based analysis to provide Socratic-style, contextual coaching based on deep pedagogical principles.

---

## What Was Just Completed (This Session)

### Chess Brain V1 - COMPLETE ✅
Implemented the foundational deterministic coaching engine at `/app/backend/services/chess_brain/`:

**Files Created:**
1. `enums.py` - 7 TeachingModes, GamePhase, MistakeCategory, TacticalPattern, StrategicConcept, BehavioralPattern
2. `schemas.py` - PositionInsightObject, LessonCandidate, SelectedLesson, MistakeFingerprint, LessonMemory, DetectorResult
3. `detector_registry.py` - 18 detectors (10 tactical, 5 strategic, 3 behavioral)
4. `lesson_selection_engine.py` - Weighted scoring: (Severity×0.4 + Clarity×0.3 + Relevance×0.3) × Priority × Freshness
5. `chess_brain.py` - Main orchestrator with `ChessBrain.analyze_move()`
6. `integration.py` - Bridge to existing `realtime_coaching_feedback.py`

**Integration Done:**
- Modified `/app/backend/services/realtime_coaching_feedback.py` to use Chess Brain
- Flag `use_chess_brain=True` enables deterministic coaching
- Falls back to legacy system if Chess Brain fails
- Logs show: "Chess Brain analyzed move X: quality, mode=teaching_mode"

**Testing:** 100% (31/31 tests passed)
- `/app/backend/tests/test_chess_brain.py`
- `/app/backend/tests/test_chess_brain_integration.py`

---

## User's Architectural Blueprint (CRITICAL - Follow This)

The user provided extremely detailed architecture in previous sessions. Key principles:

1. **Deterministic over LLM**: Chess Brain must make pedagogical decisions via rules, NOT LLM
2. **7 Teaching Modes**: Each interaction uses exactly ONE mode
3. **Lesson Selection Formula**: Score = (Severity×0.4 + Clarity×0.3 + Relevance×0.3) × Priority × Freshness
4. **Anti-spam**: Same pattern can't be taught within 5 moves (LessonMemory)
5. **Mistake Fingerprinting**: Track user's recurring weaknesses across sessions
6. **LLM Only for Polish**: Optional final layer for language variation, NOT for chess logic

---

## Immediate P1 Tasks (Resume Here)

### 1. Enhance Tactical Detectors
Current detectors are basic. Need full implementations for:
- `detect_skewer()` - Currently returns empty result
- `detect_overload()` - Currently returns empty result  
- `detect_removal()` - Currently returns empty result

Reference the existing `detect_fork()` and `detect_pin()` implementations in `detector_registry.py` as patterns.

### 2. Explanation Template Library
Create structured templates per teaching mode at `/app/backend/services/chess_brain/templates/`:
```
templates/
├── tactical_patterns.py    # Fork, pin, skewer templates
├── strategic_concepts.py   # Pawn structure, piece activity
├── mistake_corrections.py  # Blunder/mistake explanations
└── reinforcement.py        # Positive feedback variations
```

### 3. MistakeFingerprint Persistence
- Currently `MistakeFingerprint` is a dataclass
- Need MongoDB collection `player_fingerprints`
- Schema: `{user_id, tactical: {pattern: {count, last_seen, decay_score}}, strategic: {...}, behavioral: {...}}`
- Update fingerprint after each mistake detected

### 4. Reinforcement Engine
- Detect when user avoids a recurring mistake (compare current position to fingerprint)
- Create `HABIT_BREAKTHROUGH` lesson candidate
- Celebrate: "You usually miss this pattern, but this time you got it!"

---

## Key Files Reference

**Chess Brain (NEW):**
- `/app/backend/services/chess_brain/__init__.py`
- `/app/backend/services/chess_brain/detector_registry.py` (18 detectors)
- `/app/backend/services/chess_brain/lesson_selection_engine.py`
- `/app/backend/services/chess_brain/chess_brain.py`

**Integration Point:**
- `/app/backend/services/realtime_coaching_feedback.py` (lines 403-440 - Chess Brain integration)

**Existing Services to Integrate:**
- `/app/backend/services/blunder_intelligence_service.py` (has sophisticated analysis)
- `/app/backend/services/mistake_classifier.py` (has pattern detection)
- `/app/backend/services/coach_moment_selector.py` (has CRS scoring)

**Frontend:**
- `/app/frontend/src/pages/CoachPlay.jsx` (main play interface)
- `/app/frontend/src/components/coach-play/CoachInsightCard.jsx` (displays coaching)

**Documentation:**
- `/app/memory/PRD.md` (full requirements and completed work)
- `/app/ARCHITECTURE_MAP.md` (existing component map)

---

## API Endpoints

- `POST /api/coach/play/start` - Start coaching session
- `POST /api/coach/play/move` - Make a move (triggers Chess Brain analysis)
- `GET /api/coach/play/feedback/{session_id}` - Get coaching feedback
- Backend URL: `https://coach-variations.preview.emergentagent.com`

---

## Testing

Run Chess Brain tests:
```bash
cd /app/backend && PYTHONPATH=/app/backend python -m pytest tests/test_chess_brain.py tests/test_chess_brain_integration.py -v
```

---

## User Preferences

- **Language**: Plain, simple, direct Indian-English
- **Coaching Tone**: Socratic questioning before giving answers
- **UX Principle**: "One move → one insight → one next action"
- **No LLM for Chess Logic**: Deterministic rules only
