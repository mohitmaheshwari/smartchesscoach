# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach with Socratic-style, contextual feedback tailored to the user's playstyle.

## What's Been Implemented

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
        │   │   ├── InlineOpeningLesson.jsx  # NEW
        │   │   ├── InlineTrapLesson.jsx     # NEW
        │   │   ├── EvalBar.jsx
        │   │   ├── MoveFeedbackPanel.jsx
        │   │   ├── GuardianWarning.jsx
        │   │   ├── CoachChat.jsx
        │   │   ├── GameSetupPanel.jsx
        │   │   └── index.js
        │   └── ...
        └── pages/
            ├── CoachPlay.jsx    # Updated with inline lessons
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

### P1 - Remaining (User Verification Pending)
- [ ] Verify "Inline Mini-Lesson" panel UX for opening/trap teaching
- [ ] Verify "UI Flicker" in practice mode is resolved
- [ ] Test fresh game opening detection flow
- [ ] Migrate remaining backend endpoints (/start, /move)

### P2 - Frontend Polish
- [ ] Integrate extracted components fully into CoachPlay.jsx (CoachChat, GameSetupPanel, GuardianWarning)
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
