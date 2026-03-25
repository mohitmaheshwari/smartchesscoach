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

#### 6. Pedagogical Opponent Engine - NEW (March 2025)
- **Purpose**: Transform the coach from a "perfect engine" into an active teaching partner
- **Core Logic**: `/app/backend/services/pedagogical_opportunity_service.py`
  - `PedagogicalOpportunityService` - Main decision engine
  - `should_create_opportunity()` - Decides whether to play best move or pedagogical move
  - `evaluate_user_response()` - Analyzes if user found the opportunity
- **How It Works**:
  - **Opening Phase**: Always play correct theory (teach accuracy)
  - **Middlegame/Endgame**: ~25% chance to play "good but not best" move
  - **Targeted Learning**: Opportunities match user's known weaknesses
  - **Consequence-Based Feedback**: Eval bar hidden, revealed after user responds
- **Eval Sacrifice Ranges by Rating**:
  - Beginner (<1000): 0.5-2.5 pawns (easier to spot)
  - Intermediate (1000-1400): 0.3-1.5 pawns
  - Club (1400-1800): 0.2-1.0 pawns
  - Advanced (1800+): 0.15-0.8 pawns (very subtle)
- **Opportunity Types Detected**: Fork, Pin, Skewer, Hanging Piece, Back Rank, Passed Pawn, King Safety, Piece Activity, Outpost, Pawn Structure, Endgame Technique, General
- **Session State Tracking**:
  - `pedagogical_mode_active`: Boolean (default: true)
  - `pending_opportunity`: Current opportunity awaiting response
  - `opportunities_found` / `opportunities_missed`: Running counts
- **Frontend Integration**:
  - `EvalBar` component: `hidden` prop shows "?" with amber pulsing animation
  - `ConsequenceFeedback` component: Shows found/missed feedback with eval change
  - Hint overlay: "Find the opportunity!" when eval hidden

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
  // Pedagogical Opponent State (NEW)
  pedagogical_mode_active: Boolean,  // Default: true
  last_pedagogical_move_index: Number,  // -10 if never
  pending_opportunity: {
    type: String,  // "fork", "pin", "hanging_piece", etc.
    expected_moves: [String],  // Moves that exploit the opportunity
    target_squares: [String],  // Squares involved
    reason: String,  // Why this was chosen
    skill_explanation: String,  // What concept this tests
    eval_sacrifice: Number,  // How much eval given up
    hide_eval: Boolean,  // Whether to hide eval bar
  },
  opportunity_history: [Object],
  opportunities_found: Number,
  opportunities_missed: Number,
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
- `/app/backend/services/pedagogical_opportunity_service.py` (Pedagogical Opponent - NEW)
- `/app/backend/coach_play/coach_game_session.py` (Session management - UPDATED for pedagogical state)
- `/app/backend/services/opening_theory_json_service.py` (JSON theory loader)
- `/app/backend/data/coaching/opening_theory_tree.json` (Single source of truth for openings)
- `/app/backend/services/opening_teaching_integration.py` (Lesson system - REWRITTEN)
- `/app/backend/services/opening_mastery.py` (Now loads from JSON, detection + progress tracking)
- `/app/backend/services/shared_coaching_v5.py` (Shared V5 coaching logic)
- `/app/backend/services/player_habits_service.py` (Behavioral coaching)
- `/app/frontend/src/pages/CoachPlay.jsx` (Play with Coach page - UPDATED for pedagogical UI)
- `/app/frontend/src/components/coach-play/EvalBar.jsx` (Hidden state support - UPDATED)
- `/app/frontend/src/components/coach-play/ConsequenceFeedback.jsx` (NEW)
- `/app/backend/routes/coach_play.py` (Play with Coach API endpoints)

---

## Future Enhancements (Backlog)

### P1 - High Priority
- [ ] Interactive Board in Opening Explorer (clickable chessboard to step through lines)
- [ ] Variation Selector for Lessons (choose French: Advance vs Classical)
- [ ] Pattern Memory Injection ("You've made this mistake 3 times...")
- [ ] Refactor `GameDecryptionV5.jsx` to use shared `V5CoachingCard.jsx`

### P2 - Medium Priority
- [ ] Admin UI for theory database management
- [ ] Endgame theory tree (similar structure to openings)
- [ ] Habits Trend Dashboard (show improvement over time)
- [ ] Opening Proficiency in Coach Panel (show mastery, suggest variations)

### P3 - Nice to Have
- [ ] Voice coaching mode
- [ ] Weekly learning summary emails
- [ ] Major refactoring of `CoachPlay.jsx` (3500+ lines)
- [ ] Comparative analysis with similar-rated players

---

## Testing Status
- **Pedagogical Opponent (March 2025)**: Backend 15/15 tests passed, Frontend 100% verified
- **Opening Theory Consolidation (March 2025)**: Backend 21/21 tests passed, Frontend 100% verified
- **Expanded Opening Theory (March 2025)**: 16 new openings added, Backend 28/28 tests passed, Frontend 100%
- **Player Habits Engine (March 2025)**: Backend 7/9, Frontend 100%
- **Two-Moment Coaching Flow (March 2025)**: Backend 9/9, Frontend 100%
- **V5 Pipeline Unified (March 2025)**: Backend 10/10, Frontend 100%

---

*Last Updated: March 2025*
