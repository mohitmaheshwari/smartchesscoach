# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized chess coaching application. The core feature is a "Game Decryption Engine" that provides a move-by-move narrative explaining the strategic story of the game.

## Vision: "Thinking Simulator" (V5)
The system is NOT a "move explanation system" but a **"Thinking Simulator"**. It trains the user's thinking process and helps them see the board like a stronger player, focusing on future consequences rather than just the current move.

### Core Principles
1. **Coach on EVERY move** (user + opponent)
2. **Show PLANS** (transferable knowledge, not just moves)
3. **LLM = Language translator ONLY** (all chess logic from existing layers)
4. **Smart theory** (track what user has acknowledged understanding)
5. **Simple language** (1200-friendly, under 20 words)
6. **Show the future** (next 1-2 moves in the variation)
7. **SPECIFIC consequences** - Never generic "position weakens", always explain WHAT gets weak and WHY

---

## V5 Implementation Status: COMPLETE

### What's Been Implemented

#### 1. Shared Coaching Layer (`shared_coaching_v5.py`)
- Single source of truth for V5 coaching used by BOTH Lab and Play with Coach
- `generate_move_coaching()` - Main entry point for all V5 coaching
- `get_stockfish_candidates()` - Multi-PV for real candidate moves
- `describe_consequence()` - Specific consequences (not generic)
- `detect_fork_in_pv()` - Detects actual forked pieces

#### 2. Shared Frontend Component (`V5CoachingCard.jsx`)
- Unified UI component used by both Lab and Play with Coach
- Clickable candidate moves from Stockfish
- "I understand" button for concept tracking
- Color-coded move types

#### 3. Play with Coach V5 Integration
- Two-part coaching: user move feedback + coach move explanation
- Behavioral coaching (habits engine) integrated
- Interactive Coaching Panel in right-hand panel

#### 4. Player Habits Engine (`player_habits_service.py`)
- Detects behavioral patterns: impulse moves, tilt, overthinking
- Integrated into both Play with Coach and Lab
- Provides behavioral coaching alongside tactical feedback

#### 5. Opening Theory System - CONSOLIDATED (March 2025)
- **Single source of truth**: `/data/coaching/opening_theory_tree.json`
- **24 openings, 49 variations, all 12-26 moves deep** - zero stubs remaining
- **JSON loader service**: `opening_theory_json_service.py`
- **Legacy hardcoded data removed**: `opening_mastery.py` now loads from JSON
- **Critical position enrichment**: Lesson instructions include context-aware explanations
- Full opening coverage: Italian, French, Queen's Gambit, London, Sicilian (General/Dragon/Najdorf), Caro-Kann, Ruy Lopez, Philidor, Vienna, Scotch, Petrov, King's Indian, Grunfeld, Nimzo-Indian, Queen's Indian, Slav, QGD, Benoni, Budapest, Dutch, Scandinavian, Nimzowitsch

---

## Data Models

### user_concept_understanding
```javascript
{
  user_id: String,
  concept_id: String,
  concept_type: String,
  concept_text: String,
  shown_count: Number,
  acknowledged: Boolean,
  acknowledged_at: Date,
  applied_correctly_count: Number,
  failed_to_apply_count: Number
}
```

### coach_sessions
```javascript
{
  session_id: String,
  user_id: String,
  user_color: String,
  detected_opening: String,
  teaching_mode: String,  // "main_line" | "trap" | null
  teaching_data: {
    variation_name: String,
    variation_key: String,
    main_line_moves: [String],  // 12-24 moves deep from JSON
    current_move_index: Number,
    critical_positions: Object,
    key_ideas: [String],
    user_plays_white: Boolean,
    teaching_fen: String,
  },
  move_history: [Object],
  behavior_events: [Object],
  habits_report: Object,
}
```

---

## API Endpoints

### V5 Decryption
- `GET /api/coach/decryption/v5/{game_id}` - Get V5 coaching for a game
- `POST /api/coach/decryption/acknowledge` - Mark concept as understood

### Play with Coach
- `POST /api/coach/play/v5/interactive-feedback` - Two-part coaching
- `POST /api/coach/play/teaching/start` - Start opening lesson (now 12-24 moves deep!)
- `POST /api/coach/play/teaching/move` - Process teaching move
- `POST /api/coach/play/teaching/exit` - Exit teaching mode

### Learning Progress
- `GET /api/coach/concepts/acknowledged` - Get user's acknowledged concepts
- `GET /api/coach/concepts/learning-progress` - Get learning summary

---

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI
- **Backend**: FastAPI, MongoDB (Motor async driver)
- **Chess**: python-chess, Stockfish
- **LLM**: GPT-4.1-mini via emergentintegrations (Emergent LLM Key)

---

## Files of Reference
- `/app/backend/services/opening_theory_json_service.py` (JSON theory loader - NEW)
- `/app/backend/data/coaching/opening_theory_tree.json` (Single source of truth for openings)
- `/app/backend/services/opening_teaching_integration.py` (Lesson system - REWRITTEN)
- `/app/backend/services/opening_mastery.py` (Now loads from JSON, detection + progress tracking)
- `/app/backend/services/shared_coaching_v5.py` (Shared V5 coaching logic)
- `/app/backend/services/player_habits_service.py` (Behavioral coaching)
- `/app/frontend/src/pages/CoachPlay.jsx` (Play with Coach page)
- `/app/backend/routes/coach_play.py` (Play with Coach API endpoints)

---

## Future Enhancements (Backlog)

### P1 - High Priority
- [ ] Opening Proficiency in Coach Panel (show mastery, suggest variations)
- [ ] Pattern Memory Injection ("You've made this mistake 3 times...")
- [ ] Refactor `GameDecryptionV5.jsx` to use shared `V5CoachingCard.jsx`

### P2 - Medium Priority
- [ ] Admin UI for theory database management
- [ ] Endgame theory tree (similar structure to openings)
- [ ] Habits Trend Dashboard (show improvement over time)

### P3 - Nice to Have
- [ ] Voice coaching mode
- [ ] Weekly learning summary emails
- [ ] Major refactoring of `CoachPlay.jsx` (3500+ lines)
- [ ] Comparative analysis with similar-rated players

---

## Testing Status
- **Opening Theory Consolidation (March 2025)**: Backend 21/21 tests passed, Frontend 100% verified
- **Expanded Opening Theory (March 2025)**: 16 new openings added, Backend 28/28 tests passed, Frontend 100%
- **Player Habits Engine (March 2025)**: Backend 7/9, Frontend 100%
- **Two-Moment Coaching Flow (March 2025)**: Backend 9/9, Frontend 100%
- **V5 Pipeline Unified (March 2025)**: Backend 10/10, Frontend 100%

---

*Last Updated: March 2025*
