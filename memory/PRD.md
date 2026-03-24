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

### What's Been Implemented (December 2025)

#### 1. Game Decryption V5 Service (`game_decryption_v5_service.py`)
- Coaches every single move (user and opponent)
- Extracts PLANS from Stockfish PV (not just moves)
- Integrates opening theory tree
- Tracks concept acknowledgment
- LLM enhancement for mistakes
- **FIXED**: Specific consequence analysis (March 2025)
  - Fixed syntax error in tactical pattern detection
  - Enhanced `_describe_consequence` function with fallback positional analysis
  - Added `_analyze_positional_weakness` for non-tactical issues

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

## Bug Fixes (March 2025)

### P0: Consequence Explanation Specificity
**Problem**: The consequence explanations were generic (e.g., "your position weakens") instead of specific (e.g., "your c7 pawn is attacked by 2 pieces and defended by only 1").

**Root Cause**:
1. Syntax error in `_detect_tactical_issue` function (duplicate/malformed return statement)
2. No fallback analysis when PV moves couldn't be parsed or no tactical issues found

**Fix Applied**:
1. Fixed syntax error in tactical pattern detection (back_rank_weakness handling)
2. Enhanced `_describe_consequence` to track whether PV was successfully parsed
3. Added new `_analyze_positional_weakness` function that checks:
   - Center control imbalances
   - Development issues (pieces on back rank)
   - King safety (castling rights lost, king in center)
   - Weak/isolated pawns
4. Consequence function now always returns SPECIFIC feedback

**Test Results**: All tests pass with specific output:
- "After d5, your pawn on e4 is totally undefended with 1 pieces eyeing it!"
- "After Nxe4, your Little Soldier on e4 gets chomped!"
- "After Nb5, you're behind in development! Get those pieces out!"

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
- `/app/backend/services/v5_llm_narrator.py` (LLM integration)
- `/app/backend/services/v5_learning_tracker.py` (Learning tracking)
- `/app/backend/services/opening_theory_tree_service.py` (Theory tree service)
- `/app/backend/data/coaching/opening_theory_tree.json` (Opening theory data)
- `/app/frontend/src/components/GameDecryptionV5.jsx` (V5 UI component)
- `/app/backend/routes/coach.py` (API endpoints)

---

## Future Enhancements (Backlog)

### P1 - High Priority
- [ ] Player Type Detection (adapt coaching tone based on playing style)
- [ ] Pattern Memory Injection ("You've made this mistake 3 times...")
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

---

*Last Updated: March 2025*
