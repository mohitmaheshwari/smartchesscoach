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

### What's Been Implemented (December 2025 - March 2025)

#### 1. Shared Coaching Layer (`shared_coaching_v5.py`) - NEW!
- **Single source of truth** for V5 coaching used by BOTH Lab and Play with Coach
- `generate_move_coaching()` - Main entry point for all V5 coaching
- `get_stockfish_candidates()` - Multi-PV for real candidate moves (no more bad suggestions like Qd6!)
- `describe_consequence()` - Specific consequences (not generic)
- `detect_fork_in_pv()` - Detects actual forked pieces (Rook + Queen, not King + Queen)
- Same fun language everywhere (Horsey, Naughty Knight, Slicey Boi)

#### 2. Shared Frontend Component (`V5CoachingCard.jsx`) - NEW!
- Unified UI component used by both Lab and Play with Coach
- Clickable candidate moves from Stockfish
- "I understand" button for concept tracking
- Color-coded move types (counter_attack, prophylactic, development, etc.)
- Golden Rules / Transferable Learning section

#### 3. Play with Coach V5 Integration - NEW!
- Added V5 endpoints to `coach_play.py`:
  - `POST /api/coach/play/v5/feedback` - Get V5 coaching for a move during live play
  - `GET /api/coach/play/v5/session/{session_id}/moves` - Get V5 coaching for all moves after game ends
  - `POST /api/coach/play/v5/interactive-feedback` - Two-part coaching: user move + coach move explanation
- Updated `CoachPlay.jsx` to fetch and display V5 coaching
- **Interactive Coaching Panel** integrated (March 2025): After each move cycle, the panel shows:
  1. Feedback on user's move (severity, narrative, consequence, better approach, candidate moves)
  2. Coach's move explanation (what the coach is doing, its plan, threats created, teaching point)
  3. "Your turn!" prompt with hints and threat reminders
- Uses `InteractiveCoachingPanel.jsx` shared component for the coaching dialogue
- V5 coaching displays when available, falls back to legacy UI otherwise

#### 4. Game Decryption V5 Service (`game_decryption_v5_service.py`)
- Coaches every single move (user and opponent)
- Extracts PLANS from Stockfish PV (not just moves)
- Integrates opening theory tree
- Tracks concept acknowledgment
- LLM enhancement for mistakes

#### 2. LLM Narrator (`v5_llm_narrator.py`)
- GPT-4.1-mini via emergentintegrations
- Generates concise, memorable narratives (under 20 words)
- LLM is ONLY a language translator - no chess analysis

#### 3. Opening Theory Tree (`opening_theory_tree.json` + `opening_theory_tree_service.py`)
- Structured tree format with main lines and variations
- Critical positions with best moves and mistake patterns
- Transferable learnings for each opening
- Supports: Italian Game, Sicilian Dragon, French Defense, Caro-Kann

#### 4. Learning Tracker (`v5_learning_tracker.py`)
- Tracks concepts user has demonstrated correctly
- Tracks "I understand" acknowledgments
- Builds "What you're getting better at" profile
- Detects improvement trends

#### 5. Frontend V5 Component (`GameDecryptionV5.jsx`)
- "I understand" button for concept acknowledgment
- Clickable moves in explanations (shows future on board)
- Opponent moves coaching ("What's your plan now?")
- Good move recognition with concept tracking
- Color-coded severity indicators

---

### Bug Fixes & Enhancements (March 2025)

### P0: Consequence Explanation Specificity (FIXED)
**Problem**: The consequence explanations were generic (e.g., "your position weakens") instead of specific (e.g., "your c7 pawn is attacked by 2 pieces and defended by only 1").

**Fix Applied**:
1. Fixed syntax error in tactical pattern detection
2. Enhanced `_describe_consequence` to track whether PV was successfully parsed
3. Added new `_analyze_positional_weakness` function for fallback analysis
4. Consequence function now always returns SPECIFIC feedback

### Multiple Candidate Moves with Ideas (NEW)
**Problem**: The coaching only showed "Bb5 was better" without explaining WHY or showing alternatives.

**Solution**: Added rich candidate move analysis that shows:
- Multiple alternative moves (up to 3)
- The strategic IDEA behind each move (counter-attack, prophylactic, development, etc.)
- Transferable learning derived from the types of good moves available

**New Functions**:
- `_analyze_candidate_moves()`: Finds up to 3 candidate moves with diverse strategic ideas
- `_explain_move_idea()`: Categorizes moves as counter_attack, prophylactic, development, central, tactical, etc.
- `_format_better_approach()`: Creates readable explanation from best candidate
- `_derive_transferable_learning()`: Generates learning based on available move types

**Example Output**:
```
Problem: Your Horsey wandered to the edge with Na3!
Consequence: After d5, your pawn on e4 is totally undefended!
Better approach: Bb5 attacks their Horsey - forces them to respond!
Learning: Look for counter-attacks! When opponent threatens, find YOUR threat!

Alternative Ideas:
★ Bb5: attacks their Horsey - forces them to respond! [counter_attack]
○ Nxe5: plants a piece in the center - maximum influence! [central]  
○ Bc4: develops with a purpose - aims at the center [development]
```

**Frontend Update**: Added new UI section in `GameDecryptionV5.jsx` to display candidate moves with color-coded strategic types.

---

## Data Models

### user_concept_understanding
```javascript
{
  user_id: String,
  concept_id: String,      // e.g., "italian_premature_d5"
  concept_type: String,    // "opening" | "endgame" | "tactical" | "positional"
  concept_text: String,    // The transferable learning
  shown_count: Number,     // Times we've shown this
  acknowledged: Boolean,   // User clicked "I understand"
  acknowledged_at: Date,
  applied_correctly_count: Number,
  failed_to_apply_count: Number
}
```

### user_learning_progress
```javascript
{
  user_id: String,
  games_analyzed: [{ game_id, date, accuracy, best_move_rate, concepts_applied }],
  total_games_analyzed: Number,
  total_best_moves_found: Number,
  concept_applications: { concept_id: count }
}
```

---

## API Endpoints

### V5 Decryption
- `GET /api/coach/decryption/v5/{game_id}` - Get V5 coaching for a game
- `POST /api/coach/decryption/acknowledge` - Mark concept as understood

### Learning Progress
- `GET /api/coach/concepts/acknowledged` - Get user's acknowledged concepts
- `GET /api/coach/concepts/learning-progress` - Get learning summary
- `GET /api/coach/learning/insights` - Get detailed learning insights

---

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI
- **Backend**: FastAPI, MongoDB (Motor async driver)
- **Chess**: python-chess, Stockfish
- **LLM**: GPT-4.1-mini via emergentintegrations (Emergent LLM Key)

---

## Files of Reference
- `/app/backend/services/game_decryption_v5_service.py` (Main V5 orchestrator)
- `/app/backend/services/shared_coaching_v5.py` (Shared V5 coaching logic for Lab + Play)
- `/app/backend/services/v5_llm_narrator.py` (LLM integration)
- `/app/backend/services/v5_learning_tracker.py` (Learning tracking)
- `/app/backend/services/opening_theory_tree_service.py` (Theory tree service)
- `/app/backend/data/coaching/opening_theory_tree.json` (Opening theory data)
- `/app/frontend/src/components/GameDecryptionV5.jsx` (V5 UI component)
- `/app/frontend/src/components/shared/InteractiveCoachingPanel.jsx` (Two-part coaching dialogue)
- `/app/frontend/src/components/shared/V5CoachingCard.jsx` (Shared V5 coaching card)
- `/app/frontend/src/pages/CoachPlay.jsx` (Play with Coach page)
- `/app/backend/routes/coach_play.py` (Play with Coach API endpoints)
- `/app/backend/routes/coach.py` (Lab API endpoints)

---

## Future Enhancements (Backlog)

### P1 - High Priority
- [ ] Player Type Detection (adapt coaching tone based on playing style)
- [ ] Pattern Memory Injection ("You've made this mistake 3 times...")
- [ ] Refactor `GameDecryptionV5.jsx` to use shared `V5CoachingCard.jsx`
- [ ] More opening theory trees (Sicilian Najdorf, Queen's Gambit, etc.)

### P2 - Medium Priority
- [ ] Admin UI for theory database management
- [ ] Endgame theory tree (similar structure to openings)
- [ ] User question layer integration with V5

### P3 - Nice to Have
- [ ] Voice coaching mode
- [ ] Weekly learning summary emails
- [ ] Comparative analysis with similar-rated players

---

## Known Limitations
- LLM calls add ~1 second per mistake to generation time
- Opening theory tree currently covers 4 major openings
- Concept tracking starts fresh (no historical data migration)

---

## Testing Status
- V5 endpoint: Tested with multiple games
- LLM integration: Working with GPT-4.1-mini
- "I understand" button: Saves to database
- Frontend rendering: All components displaying correctly
- **Consequence analysis: FIXED and tested (March 2025)**
- **Interactive Coaching Panel: INTEGRATED and tested (March 2025)** - Backend 8/8 tests passed, Frontend 100% verified
- **V5 Pipeline Unified (March 2025)** - Play with Coach now uses the EXACT same `generate_move_coaching()` as Lab. Coach move explanations show plan, threats, teaching points. User move feedback shows V5CoachingCard with clickable candidates. Generic "What's your plan?" removed. Backend 10/10, Frontend 100%.
- **Two-Moment Coaching Flow (March 2025)** - User move feedback appears IMMEDIATELY after playing (before coach responds). Coach move explanation appears ONLY after coach finishes thinking. Backend supports `phase` param (user_move/coach_move). Quick Stockfish eval runs inline when stored analysis not yet available. Backend 9/9, Frontend 100%.

---

*Last Updated: March 2025*
