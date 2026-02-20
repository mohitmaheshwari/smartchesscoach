# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a full-featured chess coaching application that analyzes games, identifies weaknesses, and provides personalized coaching with a GM-coach style coaching loop.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)

---

## GOLD FEATURE: Training Engine - Adaptive Behavioral Correction System ✅ NEW

### Core Philosophy: "Data-Driven, One Leak at a Time"
The Training Engine replaces the Focus + Coach pages with a unified, step-by-step training experience. It uses PURE DATA (not rating-band hardcoding) to identify the user's biggest weakness.

### The 4 Training Layers
Each layer computes a Cost Score from last 20 games:

1. **STABILITY** - Blunders, hanging pieces, threat blindness, one-move threats
2. **CONVERSION** - Win-state detection, eval drops when ahead, allowing counterplay
3. **STRUCTURE** - Opening deviation, equal-position stability, aimless play
4. **PRECISION** - Tactical misses, calculation depth, endgame technique

**Active Phase** = Highest cost layer (pure data, no rating hardcoding)
**Micro Habit** = Dominant pattern within the active phase

### Training Page Flow (Streamlined 3-Step Wizard) ✅ POLISHED Feb 2026
The wizard was condensed from 5 steps to 3 focused steps:

1. **Focus** - Your weakness + pattern + rules (combined view)
   - Shows active layer (Stability/Conversion/Structure/Precision)
   - Your main pattern (e.g., "Threat Blindness" at 46%)
   - Your 2 actionable rules
   - Example positions from your games
   - 4-layer cost breakdown visualization

2. **Reflect** - Review critical moments from last game
   - Per-position reflection with explanations
   - "Show on board" plan mode
   - Contextual quick-tags

3. **Practice** - Training drills
   - Interactive positions to find best moves
   - Sourced from your mistakes + similar users

### Key Technical Concepts
- **Pattern Weights**: User reflections nudge pattern weights (engine still wins)
- **Cross-User Drills**: Positions from similar rating + same micro habit users
- **Recalculation Trigger**: Every 7 new games analyzed

### API Endpoints
- `GET /api/training/profile` - Get or generate training profile
- `POST /api/training/profile/regenerate` - Force regenerate
- `GET /api/training/reflection-options` - Get reflection tags for active phase
- `POST /api/training/reflection` - Save reflection (updates pattern weights)
- `GET /api/training/drills` - Get drill positions

### Key Files
- `backend/training_profile_service.py` - Core training engine (900+ lines)
- `frontend/src/pages/Training.jsx` - Step-by-step wizard UI
- `frontend/src/components/CoachBoard.jsx` - Reusable chess board wrapper (uses LichessBoard)
- `frontend/src/components/LichessBoard.jsx` - Lichess Chessground library wrapper
- Navigation: "Training" tab in main nav

### Chessboard Migration (Feb 2026) ✅ COMPLETE
Migrated from `react-chessboard` to Lichess `chessground` library for better UX:
- **LichessBoard.jsx**: New wrapper component for Chessground library
  - Smooth animations, professional Lichess styling
  - Arrow rendering for showing played vs better moves
  - Move destinations highlighting when interactive
  - Board orientation support (white/black perspective)
- **CoachBoard.jsx**: Updated to use LichessBoard internally
  - Maintains same API for Training.jsx compatibility
  - Supports drill mode, arrows, flip board, and position props
- **Libraries**: `chessground@9.2.1` for board, `chess.js@1.4.0` for move validation
- **Two-Arrow System**: Red arrow shows user's move (mistake), Blue arrow shows better move
- **Legend**: Clear legend below board explains arrow colors

### Example Position Filtering (Feb 2026) ✅ FIXED
Fixed data issue where tactical mistakes were shown in positional training phases:
- **Stricter Pawn Structure Filtering**: Only shows positions where user made a bad pawn push
- **Excludes Tactics**: Positions with >250 centipawn loss filtered out (usually tactical)
- **Uses Mistake Classifier**: Forks, pins, etc. properly excluded from positional phases
- **No Fallback to Unrelated Positions**: Shows helpful message instead of irrelevant examples

### "Show Plan on Board" Feature (Feb 2026) ✅ COMPLETE
Users can now show their thinking by playing moves on the board instead of typing:
- **Plan Mode**: Click "Show on board" button in reflection step
- **Both Colors**: User can play moves for both sides to show:
  - Their own plans (what they intended)
  - Opponent threats they were worried about
  - Threats they missed (what opponent could do)
- **Context-Aware LLM**: Backend analyzes which color was moved and generates appropriate description
  - If user moves their color: "I was planning to..."
  - If user moves opponent color: "I was worried about..." or "I missed that..."
- **Move Tracking**: Shows moves as they're played: 1. e4 e5 2. Nf3 etc.
- **Controls**: Undo, Cancel, Done buttons for managing the plan
- **Technical Fix (Feb 2026)**: Board interactivity now works by destroying and recreating chessground instance when planMode changes.
- **Files**: 
  - `LichessBoard.jsx` - Chessground wrapper with planMode support
  - `CoachBoard.jsx` - Orchestrates plan mode state
  - `server.py` - `/api/training/plan/describe` endpoint with rich context (user_playing_color, turn_to_move, user_move, best_move)

### Bug Fixes (Dec 2025)
- ✅ Example positions now load correct FEN (was showing starting position)
- ✅ Reflection step includes chessboard showing mistake position
- ✅ Phase Context framed as "This Week's Focus" / "Weekly Focus"

### Bug Fixes (Feb 2026)
- ✅ **Phase-Filtered Example Positions**: Example positions now match the current training phase
  - Opening Principles phase shows only moves 1-12
  - Pawn Structure phase shows moves 1-25
  - Each phase has specific filtering criteria (move range, cp loss threshold)
  - Backend: `collect_all_phase_relevant_positions()` and `filter_positions_for_phase()` in training_profile_service.py
- ✅ **Merged Training Systems**: Removed confusing "Training Areas" (layer-based cost system)
  - Now only shows the tier-based training journey (Opening Principles → Pawn Structure → etc.)
  - Simplified UI with single focus on current phase
- ✅ **Clearer Stats Display**:
  - "2 Clean Games (need 3)" instead of confusing "4/3"
  - "+16% Fewer mistakes" instead of confusing "↓ 90%"
  - Removed all raw "Cost" numbers from UI

### Enhanced Reflection System (Dec 2025) ✅ NEW
Per-position reflection with rich context:
- **Rating-Based Filtering**: Different thresholds per rating band
  - <1000: Blunders only (≥200cp)
  - 1000-1400: Blunders + big mistakes (≥150cp)
  - 1400-1800: All mistakes (≥100cp)
  - 1800+: Including inaccuracies (≥50cp)
- **Rich Context Per Position**:
  - "You played X" / "Better was Y" side-by-side
  - "Play the better line" interactive visualization
  - "Opponent's threat" display when applicable
  - "Why is Y better?" GPT explanation (using Stockfish data)
- **User Input**:
  - "What was your plan?" - User shares their thinking
  - Contextual tags (not static "rushing" but position-specific)
- **Per-Position Save**: Each milestone saved independently

### API Endpoints (Enhanced Reflection)
- `GET /api/training/last-game-for-reflection` - Get last analyzed game ID
- `GET /api/training/game/{game_id}/milestones` - Get filtered milestones with contextual options
- `POST /api/training/milestone/explain` - Generate GPT explanation
- `POST /api/training/milestone/reflect` - Save per-position reflection
- `GET /api/training/reflection-history` - Get reflection history with pattern evolution
- `GET /api/training/ai-insights` - AI analysis of thinking patterns (NEW)

### Reflection History View (Dec 2025) ✅ NEW
- Stats overview: Total reflections, patterns identified
- AI Analysis of thinking patterns using GPT
- Pattern breakdown with progress bars
- Recent reflections with user's written thoughts
- Pattern weights updated based on reflections

### Phase Progress & Graduation System (Dec 2025) ✅ ENHANCED
Rating-adaptive multi-tier training journey:

**6 Training Tiers (200 → 2200+ rating):**
1. **Fundamentals** (0-600): Piece Safety → Check Awareness → Capture Awareness
2. **Stability** (600-1000): Blunder Reduction → Threat Detection → Piece Activity  
3. **Structure** (1000-1400): Opening Principles → Pawn Structure → Piece Coordination
4. **Conversion** (1400-1800): Advantage Maintenance → Winning Technique → Endgame Basics
5. **Precision** (1800-2200): Calculation Depth → Positional Understanding → Complex Tactics
6. **Mastery** (2200+): Deep Preparation → Time Management → Psychological Resilience

**Progress Tracking:**
- Phase-specific metrics (e.g., "1.8 opening mistakes per game (target: ≤1.0)")
- Clean games count per phase definition
- Improvement trend tracking
- Visual phase roadmap showing journey

**Auto-Graduation:**
- System automatically advances user when criteria met
- No manual confirmation needed
- Graduation logged for history

---

## DEPRECATED: Focus Page (Replaced by Training Engine)

### What Was Replaced

#### C) Last Game Audit ✅ NEW
Shows how well user followed their focus in their most recent game:
- Overall alignment: Executed / Partial / Missed (with color coding)
- Rule-by-rule audit with EXECUTED/PARTIAL/MISSED badges
- Key moments to review (clickable violations)
- "Open in Lab" button to study the game

#### C) Opening Pack (Personalized)
- **As White**: Best opening from user's games
- **vs 1.e4**: Best black response
- **vs 1.d4**: Best black response
- Shows: games played, win rate, stability score

#### D) Guided Replay (Turning Points)
- Top 3 biggest eval swings from user's games
- Click to load position on board
- Shows: move number, phase, your move vs best move

#### E) Weekly Requirements (3 Progress Bars)
- Games with openings: 0/10
- Missions completed: 0/7
- Guided replays: 0/2

#### F) Daily Mission (15 Minute Focus)
- Active time tracking (only counts when interacting)
- Heartbeat events every 5 seconds
- Complete at 80%+ (12+ minutes)

### API Endpoints
- `GET /api/focus-plan` - Get complete focus plan
- `POST /api/focus-plan/regenerate` - Force new plan
- `POST /api/focus-plan/mission/start` - Start mission session
- `POST /api/focus-plan/mission/interaction` - Record event/heartbeat
- `POST /api/focus-plan/mission/complete` - Complete mission
- `GET /api/focus-plan/bucket-breakdown` - Debug bucket costs

### Key Files
- `backend/focus_plan_service.py` - Core deterministic coaching service
- `frontend/src/pages/FocusPage.jsx` - New Focus Page UI

---

## Previous Feature: Adaptive Performance Coach (v1) - DEPRECATED

The old adaptive coach at `/api/adaptive-coach` still exists with:
- 4-section layout (Diagnosis, Plan, Audit, Signals)
- Different data model (user_adaptive_plans collection)

Now the Focus page uses the new deterministic system (focus_plans collection).

---

### Key Files
- `frontend/src/pages/AdaptiveCoach.jsx` - Main component with 4 sections
- `backend/adaptive_coach_service.py` - All deterministic engines
- `backend/tests/test_adaptive_coach.py` - 12 comprehensive tests

---

## Previous Feature: Board-First Coach (v3.0) - REPLACED BY ADAPTIVE COACH

The old Board-First Coach at `/coach` route still exists with:
- 3-tab layout (Audit, Plan, Openings)
- Key Moments from last game
- Mission card with streak counter

Now the Focus page (`/focus`) uses the new Adaptive Performance Coach.

---

## API Endpoints Summary

### Coaching
- `GET /api/adaptive-coach` - Adaptive Performance Coach data (4 sections)
- `POST /api/adaptive-coach/audit-game/{game_id}` - Audit specific game
- `GET /api/round-preparation` - Old coaching loop plan
- `GET /api/plan-audit` - Old plan audit
- `GET /api/focus` - Old focus data (legacy)

### Games
- `GET /api/games` - User's games
- `GET /api/games/{game_id}` - Specific game
- `POST /api/analyze-game` - Analyze a game

---

## Completed Work (Dec 2025)

### Deterministic Personalized Coaching System - COMPLETE ✅ (Dec 2025)
- [x] Cost Score computation for 7 coaching buckets
- [x] Primary/Secondary focus selection (deterministic)
- [x] Rating band gates (<900, 900-1400, 1400-1800, 1800+)
- [x] Personalized opening recommendations from game data
- [x] ECO code to opening name mapping
- [x] Coach note generation (personalized text templates)
- [x] Daily mission with active time tracking (15 min goal)
- [x] Mission sessions with heartbeat events
- [x] Weekly requirements tracking
- [x] Turning points for guided replay
- [x] Full test coverage (15 backend tests passed)

### New Focus Page UI - COMPLETE ✅ (Dec 2025)
- [x] Coach Note (personalized from metrics)
- [x] Primary Focus card with 2 actionable rules
- [x] Opening Pack (white, vs e4, vs d4)
- [x] Guided Replay (turning points)
- [x] Weekly Requirements (3 progress bars)
- [x] Daily Mission with active timer
- [x] Interactive chessboard that updates on position clicks

### Previous Features - DEPRECATED & CLEANED UP (Feb 2026)
The following files were deleted during code cleanup:
- `FocusPage.jsx` - DELETED
- `Coach.jsx` - DELETED
- `Focus.jsx` - DELETED
- `BoardFirstCoach.jsx` - DELETED
- `AdaptiveCoach.jsx` - DELETED
- Routes `/coach` and `/focus` now redirect to `/training`

Backend services kept for backwards compatibility (legacy API endpoints):
- `adaptive_coach_service.py` - kept (legacy endpoints)
- `focus_plan_service.py` - kept (legacy endpoints)

---

## Completed Tasks (Feb 2026)

### Training UX Polish ✅ COMPLETE
- [x] Removed curriculum toggle - now pure data-driven training
- [x] Condensed 5-step wizard to 3 steps (Focus → Reflect → Practice)
- [x] Combined Phase Context + Pattern + Rules into single Focus step
- [x] Cleaner step indicator with labels and checkmarks
- [x] Reduced Training.jsx from 2148 lines to ~1100 lines

### Code Cleanup ✅ COMPLETE
- [x] Deleted 5 obsolete frontend pages (190KB+ removed)
- [x] Updated App.js routing to redirect legacy routes to Training
- [x] Cleaned imports

---

## Upcoming Tasks

### P2: Drill Generation Logic
- [ ] Implement contextual drills based on user's active phase and micro-habit
- [ ] Source drills from user's mistakes + similar rating band users
- [ ] Add interactive drill mode with move validation

### P3: Reflection Reinforcement
- [ ] User reflections dynamically adjust pattern weights
- [ ] Analyze accumulated "gold data" for pattern discovery

### P4: Performance
- [ ] Optimize Stockfish analysis depth (18 → 12-14)

---

## What Were You Thinking? (Gold Data Collection) ✅ NEW

### Purpose
Collect user's thoughts at the moment of mistakes for future pattern analysis. This "gold data" captures what the user was thinking when they made an error.

### API Endpoints
- `POST /api/games/{game_id}/thought` - Save user thought
- `GET /api/games/{game_id}/thoughts` - Get all thoughts for a game
- `GET /api/thoughts/all` - Get all user thoughts for pattern analysis

### Data Model (user_thoughts collection)
```json
{
  "thought_id": "thought_xxx",
  "user_id": "user_xxx",
  "game_id": "xxx",
  "move_number": 15,
  "fen": "...",
  "thought_text": "I thought I could win material",
  "move_played": "Nc7+",
  "best_move": "Ne7+",
  "evaluation_type": "blunder",
  "cp_loss": 400,
  "user_rating": 1200,
  "created_at": "2026-02-15T..."
}
```

### Frontend UI ✅ COMPLETE (Feb 2026)
- [x] "What were you thinking?" prompt in Lab.jsx LearningMomentItem component
- [x] Users can enter and save thoughts for each mistake/blunder
- [x] Saved thoughts show checkmark indicator
- [x] Thoughts persist across page reloads
- [x] Test-ids: thought-section-{moveNumber}, thought-input-{moveNumber}, thought-save-{moveNumber}, thought-prompt-{moveNumber}
- [x] **"Play the better line on board"** - Visual variation player for learning moments (Feb 2026)
  - Shows the better move and continuation on the board
  - Step through moves with Next/Back controls
  - Green highlighting shows variation moves
  - Exit button returns to game position

---

## Test Reports
- `/app/test_reports/iteration_53.json` - Contextual Quick-Tags Feature (100% pass - 12 backend, 8 frontend tests)
- `/app/test_reports/iteration_52.json` - Reflect Tab Feature (100% pass - 13 backend, 8 frontend tests)
- `/app/test_reports/iteration_46.json` - "What were you thinking?" Gold Data UI (100% pass, all 7 features verified)
- `/app/test_reports/iteration_45.json` - Focus Plan V2 (Example cycling, Last Game Audit, User Thoughts API - 100% pass)
- `/app/test_reports/iteration_44.json` - Deterministic Focus Plan (100% pass, 15 tests)
- `/app/test_reports/iteration_43.json` - Focus Page 3-Section Redesign (100% pass)
- `/app/backend/tests/test_focus_plan.py` - Focus plan backend tests
- `/app/backend/tests/test_focus_plan_v2.py` - Focus plan v2 tests (example positions, audit, thoughts)
- `/app/backend/tests/test_reflect_feature.py` - Reflect feature tests
- `/app/backend/tests/test_contextual_tags.py` - Contextual tags tests

---

## NEW FEATURE: Reflect Tab ✅ COMPLETE (Feb 2026)

### Core Purpose
Time-sensitive reflection tab that prompts users to reflect on critical moments from their most recent games **immediately after analysis** while memory is fresh.

### Key Features
1. **Urgent Reflection Prompts**: Shows games needing reflection with time indicators (e.g., "1d ago - Memory fading")
2. **Critical Moments**: Displays positions where user made blunders/mistakes
3. **Interactive Board**: Users can play moves on the board to show their thinking
4. **Awareness Gap Detection**: LLM compares user's thought with actual position analysis
5. **Navigation Badge**: Red badge in nav shows count of games needing reflection
6. **Contextual Quick-Tags** ✅ NEW (Feb 2026): Position-aware tags generated from chess analysis

### Contextual Quick-Tags Feature ✅ NEW (Feb 2026)
Instead of generic tags like "I was rushing" or "I miscalculated", the system now generates position-aware options:
- **Quality over quantity**: Only generates tags that can genuinely be inferred from the position
- **Chess-aware analysis**: Uses position_analysis_service.py to understand what moves do
- **Examples of tags generated**:
  - "I wanted to attack the knight on c6" (for Bb5 in Ruy Lopez)
  - "I was attacking the weak f7/f2 square" (for Qh5 Scholar's mate attempts)
  - "I wanted to capture the pawn" (for capture moves)
  - "I was trying to give check" (for check-giving moves)
  - "I was defending my bishop on d3" (for defensive moves)
- **Honest fallback**: If intent cannot be inferred, tells user honestly and prompts them to describe in their own words

### Verified Awareness Gap Analysis ✅ FIXED (Feb 2026)
The awareness gap detection now uses verified chess analysis to prevent LLM hallucinations:
- Uses `generate_verified_insight()` to compute actual move effects
- Provides explicit attacks/defends/captures to the LLM
- LLM is strictly instructed to ONLY use provided facts
- Graceful handling when move parsing fails

### API Endpoints
- `GET /api/reflect/pending` - Get games needing reflection
- `GET /api/reflect/pending/count` - Get count for badge
- `GET /api/reflect/game/{game_id}/moments` - Get critical moments
- `POST /api/reflect/submit` - Submit reflection (triggers awareness gap analysis)
- `POST /api/reflect/game/{game_id}/complete` - Mark game as fully reflected
- `POST /api/reflect/moment/contextual-tags` ✅ NEW - Get position-aware quick-tags

### Key Files
- `backend/reflect_service.py` - Core reflection service (500+ lines) - includes generate_contextual_tags()
- `frontend/src/pages/Reflect.jsx` - Reflect page UI (800+ lines) - fetches and displays contextual tags
- `frontend/src/components/Layout.jsx` - Navigation with badge
- `frontend/src/components/CoachBoard.jsx` - Chess board component

### Technical Details
- Uses Stockfish analysis data for position evaluation
- LLM (GPT-4o-mini) analyzes user reflections for awareness gaps
- Badge polls every 60 seconds for count updates
- Moments sorted by severity (blunders first, then mistakes)
- Contextual tags use position_analysis_service.py for move analysis (no LLM guessing)
- Reflected moments tracked by move_number to prevent reappearing

---

## Bug Fixes (Feb 2026)

### P0: Fixed Re-appearing Reflected Moments ✅
- **Problem:** After submitting a reflection, the moment could reappear in the list
- **Root cause:** Frontend was calling undefined `fetchMoments` (should be `fetchGameMoments`) and not properly tracking move_number
- **Fix:** 
  1. Fixed function name in Reflect.jsx (line 355)
  2. Added move_number to reflection submission (line 323)
  3. Backend now stores and filters by move_number
  4. fetchGameMoments returns the new moments for immediate state check

### P0: Fixed Lab Milestone Chronological Order ✅
- **Problem:** Learning moments in Lab page were sorted by severity (cp_loss) instead of chronologically
- **User request:** "I need to fix up the sequence as what was my first mistake to my last mistake"
- **Fix:** Changed Lab.jsx line 578 from `sort((a, b) => b.cp_loss - a.cp_loss)` to `sort((a, b) => a.move_number - b.move_number)`

### P0: Verified "What I Can Learn" Content ✅
- **User concern:** Content might be hallucinated by LLM
- **Verification:** The core lesson system uses `BEHAVIORAL_PATTERNS` dictionary + Stockfish data (data-driven)
- **Contextual tags:** Generated by `position_analysis_service.py` analyzing actual move effects (captures, checks, attacks)
- **Awareness gap:** Uses `generate_verified_insight()` to provide only verified chess facts to LLM

### P0: Fixed "What Can I Learn Here?" Checkmate Detection ✅ (Feb 19, 2026)
- **Problem:** Explanation for Move 21 Qf3 said generic "queen vulnerable, knight forks" nonsense when it actually allowed **MATE IN 1**
- **Root cause:** `mistake_explanation_service.py` had ZERO checkmate detection - only checked for forks, pins, hanging pieces
- **Fix:** Added Priority 0 checkmate detection in `analyze_mistake_position()`:
  1. Check if move allows mate in 1 (iterate opponent's legal moves, check if any is checkmate)
  2. Check if user missed mate in 1 (if best_move would have been checkmate)
  3. Check for mate in 2 (for high cp_loss blunders)
  4. Added `MISTAKE_TEMPLATES` for: `allowed_mate_in_1`, `allowed_mate_in_2`, `missed_mate_in_1`, `missed_mate_in_2`
  5. Updated `build_explanation_prompt()` and `get_quick_explanation()` for checkmate cases
- **Result:** Now correctly shows "This move allowed Qxh2# which is checkmate!" instead of generic garbage

---

## Key Files
- `backend/focus_plan_service.py` - Core deterministic coaching service (1300+ lines) - includes audit_last_game()
- `backend/reflect_service.py` - Reflect tab service (300+ lines) - time-sensitive reflection
- `frontend/src/pages/FocusPage.jsx` - Focus Page UI with Last Game Audit and Example Position cycling
- `frontend/src/pages/Reflect.jsx` - Reflect Tab UI - critical moment reflection with awareness gaps
- `frontend/src/pages/Lab.jsx` - Game Analysis (Lab) page with "What were you thinking?" Gold Data collection
- `backend/server.py` - API endpoints for /api/focus-plan/*, /api/games/{game_id}/thought*, /api/reflect/*
- **`backend/chess_verification_layer.py`** - UNIFIED verification layer for ALL position analysis (NEW)

## Chess Verification Layer Architecture (Feb 19, 2026)

### Problem Solved
Multiple services were creating their own `chess.Board` instances with inconsistent analysis:
- `position_analysis_service.py` - didn't check for checkmate
- `position_analyzer.py` - had its own tactical detection
- `mistake_explanation_service.py` - had its own pattern detection
- Result: Move 21 Qf3 (mate in 1) was explained as "queen vulnerable, knight forks" - WRONG!

### Solution: Single Source of Truth
Created `chess_verification_layer.py` that:
1. **Safe FEN parsing** - Consistent error handling
2. **Priority-ordered analysis** - Checkmate > Tactics > Positional (checkmate ALWAYS first)
3. **Unified API** - All services use the same functions:
   - `verify_position(fen)` - Get all facts about a position
   - `verify_move(fen, move, best_move, cp_loss)` - Analyze what a move does
   - `get_critical_facts(fen, move, best_move, cp_loss)` - LLM-ready context

### Services Now Using This Layer
- `mistake_explanation_service.py` - Uses unified checkmate detection
- `position_analysis_service.py` - Uses `get_critical_facts()` for verified insights
- `reflect_service.py` - Uses `generate_verified_insight()` which now uses the layer

### Critical Pattern Priority Order
1. `allows_mate_in_1` - Move allowed checkmate
2. `allows_mate_in_2` - Move allowed forced mate
3. `misses_mate_in_1` - Missed checkmate
4. `misses_mate_in_2` - Missed forced mate
5. `hangs_queen` - Queen left undefended
6. `hangs_rook` - Rook left undefended
7. `hangs_piece` - Minor piece undefended
8. `walks_into_fork` - Move walked into fork
9. `positional_error` - Default for non-tactical issues

## Credentials
- Test user: session_token=test_session_356539ff12b1 (user with 30+ analyzed games)
- Dev Login available on landing page

---

## Phase 1 Complete: Interactive Training (Feb 20, 2026)

### What Was Built
- **New `interactive_training_service.py`** - Core service for personalized puzzles
- **New `TrainingNew.jsx`** - Interactive puzzle-solving frontend
- **API Endpoints:**
  - `GET /training/puzzles` - Returns positions from user's mistakes
  - `POST /training/puzzle/validate` - Validates user's answer, provides feedback
  - `GET /training/weakness-patterns` - Identifies weakest game phase
  - `GET /training/openings` - Lists user's most-played openings
  - `GET /training/progress` - Training statistics

### Features
1. **Puzzles from your own games** - Not random positions, YOUR mistakes
2. **Interactive solving** - Make a move on the board, get immediate feedback
3. **Principle teaching** - Each puzzle teaches a chess principle (Knight Forks, Hanging Pieces, etc.)
4. **Weakness detection** - Shows your weakest phase (opening/middlegame/endgame)
5. **Progress tracking** - Stats on puzzles solved and accuracy

### Chess Principles Database
- Knight Fork, Back Rank Mate, Hanging Pieces, Pins, Discovered Attacks, Skewers, Trapped Pieces, Checkmate Awareness
- Piece Activity, Pawn Structure, King Safety, Center Control
- Development, Queen Safety, Castle Early

### Next Phases
- **Phase 2:** Opening Trainer (variations for your most-played openings)
- **Phase 3:** Community Learning (learn from other users' mistakes)
- **Phase 4:** Trick Library (curated tactical patterns)

---

## Completed Tasks (Feb 19, 2026)

### ✅ P0: Fixed Insightful Analysis in Reflections
- **Problem:** LLM was hallucinating nonsense like "Nh4 defends the pawn on g2" when that wasn't happening
- **Root cause:** `analyze_move()` was listing EVERY attack/defense, not just meaningful ones
- **Fix:**
  1. Updated `analyze_move()` in `position_analysis_service.py` to only include:
     - Attacks on **hanging (undefended)** pieces
     - Attacks on **high-value** pieces (queen, rook)
     - Defenses of pieces that were **actually under attack**
  2. Integrated `chess_verification_layer` for critical issues (checkmate, hanging pieces)
  3. If no meaningful tactical content, honestly say "repositions the piece"
- **Result:** Accurate, insightful analysis based on verified position data

### ✅ P0: Fixed Accuracy to Match Chess.com (CAPS2)
- Implemented CAPS2-style scoring based on move classifications
- Your 71.7% game now calculates to ~82.6% (vs Chess.com 84%)

### ✅ P0: Fixed "Stability" Bug in Training Page
- Fixed eval_after calculation that was defaulting to 0

### ✅ P1: Pre-filter Games with Pending Reflections 
- Only returns games with qualifying moments

---

## Upcoming Tasks (Feb 2026)

### P1: Build Training Page (New Design)
- Rating Intelligence Model (400-800, 800-1400, 1400-2000 ELO bands)
- Personal mistake clustering from last 20 games
- Targeted drills linked to reflections and awareness gaps
- Replaces/refactors current Training.jsx

### P1: Code Cleanup
- Delete obsolete files: FocusPage.jsx, Coach.jsx, focus_service.py, adaptive_coaching_service.py
- Refactor/dismantle monolithic Training.jsx (~1500 lines)

### P2: Advanced Player DNA Profile
- After 30+ games: Generate profile of user's chess personality
- Risk tolerance, calculation depth, time management style
- Use for personalized training recommendations

### P3: Track Improvement Metrics
- Blunder frequency reduction over time
- Reflection accuracy (did awareness gaps decrease?)
- Pattern recognition speed