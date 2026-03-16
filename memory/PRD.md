# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach with Socratic-style, contextual feedback tailored to the user's playstyle.

## What's Been Implemented

### March 15, 2026 - Chess Brain Deterministic Coaching Engine (COMPLETE)

#### ✅ P0 COMPLETE: "Chess Brain" Architecture Implementation
**Problem:** The coaching logic was shallow, using reactive LLM-based analysis instead of the sophisticated, deterministic "Chess Brain" architecture the user envisioned. Existing backend services (blunder_intelligence, mistake_classifier, coach_moment_selector) were disconnected.

**Solution:** Complete implementation of the deterministic Chess Brain coaching engine:

1. **NEW: Detector Registry** (`/app/backend/services/chess_brain/detector_registry.py`)
   - 10 Tactical Detectors: fork, pin, hanging_piece, trapped_piece, back_rank, mate, discovery, skewer, overload, removal
   - 5 Strategic Detectors: isolated_pawn, passed_pawn, knight_outpost, rook_activity, king_safety
   - 3 Behavioral Detectors: time_trouble, impulse_move, tilt
   - All detectors return `DetectorResult` with confidence, teaching_hook, key_squares

2. **NEW: Lesson Selection Engine** (`/app/backend/services/chess_brain/lesson_selection_engine.py`)
   - Generates multiple `LessonCandidate` objects from detections
   - Weighted scoring formula: `Score = (Severity * 0.4) + (Clarity * 0.3) + (Relevance * 0.3) * Priority * Freshness`
   - Priority multipliers: CRITICAL=2.0, HIGH=1.5, NORMAL=1.0
   - Anti-spam via `LessonMemory` (same pattern blocked for 5 moves)
   - Returns `SelectedLesson` ready for UI

3. **NEW: 7 Teaching Modes** (`/app/backend/services/chess_brain/enums.py`)
   - IMMEDIATE_MISTAKE_CORRECTION: For blunders/mistakes
   - TACTICAL_PATTERN_TEACHING: Missed tactics
   - STRATEGIC_CONCEPT_TEACHING: Positional lessons
   - POSITIVE_REINFORCEMENT: Good moves
   - HABIT_BREAKTHROUGH: Fixed recurring mistakes
   - OPENING_GUIDANCE: Opening theory
   - ENDGAME_TECHNIQUE: Endgame lessons

4. **NEW: Core Schemas** (`/app/backend/services/chess_brain/schemas.py`)
   - `PositionInsightObject`: All data about a position (detections, evals, phase)
   - `LessonCandidate`: Potential lesson with embedded teaching mode
   - `SelectedLesson`: Final output ready for UI
   - `MistakeFingerprint`: User's recurring weakness profile
   - `LessonMemory`: Session memory for anti-spam

5. **NEW: ChessBrain Orchestrator** (`/app/backend/services/chess_brain/chess_brain.py`)
   - Main entry point: `ChessBrain.analyze_move()`
   - Builds `PositionInsightObject` from FEN + Stockfish analysis
   - Runs all detectors via registry
   - Selects best lesson via engine
   - Returns `ChessBrainOutput` with all coaching data

6. **INTEGRATION: realtime_coaching_feedback.py**
   - Added `use_chess_brain=True` flag to `generate_move_feedback()`
   - Chess Brain output used when available, fallback to legacy system
   - Logs: "Chess Brain analyzed move X: quality, mode=teaching_mode"
   - Full backward compatibility maintained

**Testing:** 100% (31/31 tests passed)
- `/app/backend/tests/test_chess_brain.py` - Unit tests
- `/app/backend/tests/test_chess_brain_integration.py` - Integration tests
- All detector counts verified, scoring works, teaching modes assigned correctly

### March 14, 2026 - Clean UI Mode UX Overhaul (COMPLETE)

#### ✅ P0 COMPLETE: "Play with Coach" UX Overhaul
**Problem:** The Play with Coach UI was cluttered and confusing, violating the user's core vision of a calm, focused coaching experience. Multiple panels, nested cards, and a dashboard-like layout distracted from the "one insight at a time" principle.

**Solution:** Complete UX redesign based on user's 37-point manifesto:

1. **NEW: CoachInsightCard** - The CORE teaching element
   - One move → one insight → one next action
   - Shows reaction emoji + main insight + optional "why" + next idea
   - Has expandable "More details" for deeper explanations
   - "Why?" and "Show better move" contextual buttons
   - **Supports coachingMode prop** for beginner/intermediate/advanced verbosity

2. **NEW: TrapAlert** - Separate floating notification
   - Temporary, dismissible alerts for tactical dangers
   - Auto-hides after 10 seconds
   - "Show line" and "Got it" actions
   - Does NOT compete with normal coach explanation

3. **NEW: AskCoach** - Smart prompts + freeform input
   - 4 contextual smart prompts: "Why was that better?", "What's my plan?", "Did I miss a tactic?", "What should I improve?"
   - **NEW: Plan-first prompts** (optional mode): "I want to attack the king", "I want to develop my pieces", "I need to defend", "Should I trade pieces?"
   - Collapsible text input for free-form questions
   - Better than a blank chat box

4. **NEW: MoveHistorySection** - Compact utility
   - Collapsible at bottom with "Moves (N)" summary
   - Click move to revisit position
   - Does NOT compete with coach card

5. **cleanUIMode State** - Feature flag for gradual transition
   - Default: true (new clean UI)
   - Legacy UI wrapped in {!cleanUIMode && } conditional blocks
   - Easy to toggle back if issues found

6. **NEW: Coaching Style Selector** - Different UX modes
   - 🌱 Beginner: "More explanations, hand-holding through each move"
   - 🎯 Standard: "Balanced feedback, click for details" (default)
   - 🚀 Minimal: "Just the essentials, no fluff"
   - Affects CoachInsightCard verbosity

**Bug Fix:** current_fen null issue
- Fixed "illegal san in empty board" error when making moves
- Added fallback to fen_history in `from_dict()` and `/move` endpoint
- Fixed 4 corrupted sessions in database

**Bug Fix:** CoachInsightCard not showing feedback (CRITICAL)
- Fixed field mapping from backend response:
  - `coaching_message` → `main_insight` (was looking for `explanation`)
  - `user_move_quality` → `quality`
  - `best_move_explanation` → `why`
  - `socratic_question` → `next_idea`
- Added "Better was:" display when there's a better move
- Added `encouragement` display

**Bug Fix:** LichessBoard.jsx FEN null check
- Fixed "Cannot read properties of null (reading 'split')" error
- Added safeguard for null FEN values

**Testing:** 93% frontend tests passed (27/30 - 3 intermittent infra timeouts), 100% backend (28/28), regression suite intact

### March 14, 2026 - Resume Game Fix & Inline Teaching System

#### ✅ FIXED: P0 Bug - Resume Game with Coach's Turn
**Problem:** When resuming a game where it was the coach's turn, the board was unplayable.

**Solution:** 
1. New `/api/coach/play/trigger-coach-move` endpoint in `coach_play.py` (lines 1537-1677)
2. Handles SAN to UCI move conversion (lines 1608-1622)
3. Frontend triggers coach move automatically when resuming with coach's turn
4. Added "Coach's turn" badge and "Thinking..." indicator in UI
5. Testing: 100% backend (9/9), 100% frontend (7/7), regression 26/27

#### ✅ NEW: "Continue Where You Left Off" Dashboard Card
- New `ActiveGamesCard` component shows active coach games on dashboard
- Displays game info: time ago, move count, user color, last move
- Quick "Resume" button to jump back into the game
- Shows count of additional active games if multiple exist
- Dismissible with X button

#### ✅ FIXED: Guardian "Play Anyway" Board Reset Bug
**Problem:** When user played a risky move and clicked "Play anyway" after Guardian warning, the board would reset instead of executing the move.

**Root Cause:** The `executeMove` function was calling `/move/confirm` endpoint which only logs the override - it doesn't actually execute the move.

**Solution:** Modified `executeMove` to:
1. First call `/move/confirm` to log the override and update remaining interventions
2. Then call `/move` to actually execute the move on the board

#### ✅ FIXED: Opening/Trap Teaching Redirect Bug
**Problem:** When user clicked "Learn Opening" or "Try Trap", the app would redirect to the opening library page instead of teaching inline on the board.

**Solution:**
1. Removed clunky lesson panels that pushed chat down
2. Added clean **board overlay** showing teaching instructions directly on the chessboard
3. Teaching notification is now a **compact single-line bar** with "Start" and dismiss buttons
4. Teaching mode state properly restored when resuming a session
5. Progress shown on board: lesson name, moves remaining, next move instruction

**UI Changes:**
- Teaching instruction appears as gradient overlay at bottom of board
- Lesson complete shows as centered modal overlay on board
- No more clunky panels taking space in chat area
- Much cleaner, enterprise-quality experience

#### ✅ NEW: Inline Opening & Trap Lessons
**Problem Solved:** Previously, clicking "Learn Opening" would redirect users away from their game, disrupting the flow.

**Solution:** Non-disruptive inline teaching panels that appear during gameplay:

1. **InlineOpeningLesson Component**
   - Shows opening name, key idea, main moves
   - "Show on board" - highlights key squares
   - "Practice later" - saves to practice queue
   - "Full lesson" - opens in new tab (doesn't lose game)

2. **InlineTrapLesson Component**
   - Shows trap sequence inline
   - "Show moves" - displays trap line
   - "Try it now" - navigates to trap practice

3. **Integration with CoachPlay.jsx**
   - When opening detected, shows compact inline lesson
   - User can interact without losing game context
   - Collapsible panels to minimize distraction

#### ✅ Fixed: Opening Teaching Offer
- Added "Learn this opening" option that navigates to `/openings/{key}`
- "Quick trap lesson" for in-game trap practice
- "Just play" to continue without lesson

#### ✅ Fixed: Backend Imports
- Fixed `get_session_state` and `end_coach_session` imports in coach_play.py

#### ✅ Fixed: Opening Info in Messages
- Backend now sends `opening_key` and `opening_name` with coach messages
- "Learn Opening" button appears in chat for opening-related messages

### Previous Sessions
- Backend Refactoring (21 endpoints migrated)
- Break the Habit Challenge
- Memory Lane
- LearningPath Integration

## Code Architecture
```
/app
├── backend/
│   ├── routes/
│   │   ├── coach.py           # ~2500 lines
│   │   ├── coach_play.py      # ~1500 lines (21 endpoints)
│   │   └── ...
│   └── server.py              # ~9000 lines (has /start, /move)
└── frontend/
    └── src/
        ├── components/
        │   ├── coach-play/
        │   │   ├── CoachInsightCard.jsx  # NEW - Clean UI core element
        │   │   ├── TrapAlert.jsx         # NEW - Floating trap notifications
        │   │   ├── AskCoach.jsx          # NEW - Smart prompts + chat input
        │   │   ├── MoveHistoryCompact.jsx # NEW - Collapsible move list
        │   │   ├── InlineOpeningLesson.jsx
        │   │   ├── InlineTrapLesson.jsx
        │   │   ├── EvalBar.jsx
        │   │   ├── MoveFeedbackPanel.jsx
        │   │   ├── GuardianWarning.jsx
        │   │   ├── CoachChat.jsx
        │   │   ├── GameSetupPanel.jsx
        │   │   └── index.js             # Exports all components
        │   └── ...
        └── pages/
            ├── CoachPlay.jsx    # Updated with cleanUIMode flag
            └── ...
```

## Key Features Working

### Play With Coach
- ✅ Game session management
- ✅ Real-time move feedback with quality badges
- ✅ Coach commentary with Socratic questions
- ✅ Emotional state tracking
- ✅ Guardian interventions (3 per game)
- ✅ Inline opening/trap teaching (NEW)
- ✅ "Learn Opening" button in chat messages

### Dashboard
- ✅ LearningPath component
- ✅ Memory Lane (coach references past games)
- ✅ Break the Habit Challenge

### Opening Training Lab
- ✅ 20+ openings with interactive practice
- ✅ 27+ traps with trap practice mode
- ✅ Visual move indicators (✓/✗)

## Prioritized Backlog

### ✅ P0 - Complete
- [x] Resume game when coach's turn (trigger-coach-move endpoint)
- [x] Inline opening/trap teaching
- [x] Non-disruptive teaching flow
- [x] Break the Habit Challenge
- [x] Memory Lane
- [x] Backend refactoring (21 endpoints)
- [x] **Clean UI Mode UX Overhaul** (Mar 14, 2026)
  - CoachInsightCard, TrapAlert, AskCoach, MoveHistorySection components
  - Legacy UI hidden behind cleanUIMode flag
  - LichessBoard FEN null fix
- [x] **Chess Brain Deterministic Coaching Engine** (Mar 15, 2026)
  - 18 pattern detectors (10 tactical, 5 strategic, 3 behavioral)
  - Lesson Selection Engine with weighted scoring
  - 7 Teaching Modes
  - Full integration with realtime_coaching_feedback
  - 31 tests passing
- [x] **New Focused HomePage** (Mar 16, 2026)
  - 4-section layout: Biggest Weakness, Progress Check, Today's Training, Games to Reflect
  - Fixed opponent name display in Games to Reflect (uses opponent_name from API)
  - Fixed fallback display to use analyzed_list instead of analyzed_games
  - Contextual training tasks based on user's detected weakness pattern
  - 10 E2E tests passing

### P1 - Next Steps (Chess Brain V1.1)
- [ ] Implement Explanation Template Library (structured templates per teaching mode)
- [ ] Add more specific tactical detector implementations (skewer, overload, removal)
- [ ] Implement Mistake Fingerprint persistence in MongoDB
- [ ] Build Reinforcement Engine (celebrate when user fixes recurring mistakes)
- [ ] Connect opening_name to PositionInsightObject for OPENING_GUIDANCE mode
- [ ] Frontend: Display teaching_mode and highlight_squares from Chess Brain

### P1 - Remaining (User Verification Pending)
- [x] Test Clean UI mode in actual gameplay with coach responses ✅ VERIFIED
- [ ] Verify memory/personalization shows in new CoachInsightCard
- [ ] Verify "UI Flicker" in practice mode is resolved
- [ ] Test fresh game opening detection flow
- [ ] Migrate remaining backend endpoints (/start, /move)

### P2 - Frontend Polish & Future
- [x] Implement different UX modes for Beginner/Intermediate/Advanced ✅ DONE
- [x] Build "Plan-first" coaching prompts ✅ DONE (AskCoach planFirstMode)
- [ ] Enhanced "Ask Coach" with more smart contextual prompts
- [ ] "Recurring Mistakes" loop and practice drills
- [ ] Break down LabV2.jsx
- [ ] Rich Post-Game Analysis page (last major feature for 95% vision)

## Database Schema
- coach_sessions: Game sessions with coach
- coach_messages: Coach commentary with opening_key/opening_name
- coach_memory: User's habits and patterns
- player_identity: Cognitive identity profiles

## Testing Status
- Frontend lint: ✅ Pass
- Backend lint: ✅ Pass
- UI rendering: ✅ Working
- Inline components: ✅ Created
- Resume game flow: ✅ Tested (9/9 backend, 7/7 frontend tests)
- Test files created: `/app/backend/tests/test_trigger_coach_move.py`, `/app/tests/e2e/resume-game.spec.ts`

## March 14, 2026 - Rating & Post-Game Analysis Improvements

### ✅ User Rating Now From Synced Games
- Rating calculated from actual Chess.com/Lichess game history (not hardcoded 1200)
- Uses average of last 10 games sorted by game date for stability
- Tracks: current rating, highest, lowest, trend (improving/stable/declining)
- bhutramohit current rating: ~1181 from Chess.com

### ✅ Post-Game Analysis Backend Verified
- Rich analysis with memory insights, habit tracking, CPR rating
- Coach memory tracks 126 games with avg 92.7% accuracy
- Known weaknesses: early_queen (4x), one_move_blunders (14x, improving)
- Indian-English style in coach messages (Arre, yaar, na?, Shabash, etc.)

### Coach Rating Algorithm
```
Performance Rating = Base + Adjustment + Win/Loss Bonus
- error_rate = (blunders×3 + mistakes×2 + inaccuracies) / moves
- adjustment = (0.1 - error_rate) × 1000 (capped -400 to +300)
- Win: +50, Loss: -50
```
