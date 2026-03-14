# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach with Socratic-style, contextual feedback tailored to the user's playstyle.

## What's Been Implemented

### March 14, 2026 - Inline Teaching System

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
- [x] Inline opening/trap teaching
- [x] Non-disruptive teaching flow
- [x] Break the Habit Challenge
- [x] Memory Lane
- [x] Backend refactoring (21 endpoints)

### P1 - Remaining
- [ ] Test fresh game opening detection flow
- [ ] Migrate remaining backend endpoints (/start, /move)
- [ ] Clean up old sessions feature

### P2 - Frontend Polish
- [ ] Integrate extracted components fully into CoachPlay.jsx
- [ ] Break down LabV2.jsx

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
