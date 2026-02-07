# Chess Coach AI - Product Requirements Document

## Original Problem Statement
Build a full-stack AI chess coach application that integrates with Chess.com and Lichess to import user games, understand playing style, remember mistakes, and provide human-like coaching commentary in the persona of a firm but supportive Indian chess coach.

## Product Philosophy (Updated Feb 2025)
**"The app should know many things, but say only ONE thing at a time."**

A real coach:
- Identifies ONE habit to fix
- Repeats it until fixed
- Only then moves on

The system thinks like a coach internally but speaks like a disciplined mentor externally.

## Target Audience
- Indian adult players (4-5 games/week, paid subscription)
- Competitive adults looking to improve
- Chess academies and schools (B2B)

## App Structure

### `/coach` - Default Home (Coach Mode)
The discipline-first surface. Shows ONLY:
- Current Active Habit (ONE)
- One clear rule
- "Go Play. I'll review."

Does NOT show: Rating, Accuracy, Charts, Trends

### `/progress` - Secondary View (Metrics)
Where rating and metrics live:
- Rating chart (30/90 days)
- Accuracy trend
- Blunder trend
- Habit trend (↑ ↓ →)
- Resolved habits

Metrics support the habit narrative, not replace it.

## Core Features

### ✅ Implemented
1. **User Authentication**
   - Emergent-managed Google Auth (Web)
   - JWT session management

2. **Game Import & Analysis**
   - Chess.com and Lichess integration
   - Stockfish engine for accurate move evaluation (with FEN extraction)
   - GPT-powered coaching commentary
   - Background auto-sync every 6 hours
   - Auto-analysis (15 on first sync, 3/day ongoing)
   - Critical moment extraction for reflection training

3. **Coach Mode - Personalized Decision Reconstruction (PDR)** (Feb 2025)
   - **Reflection Moment**: Interactive chessboard showing critical position from recent game
     - Two move choices: User's original (wrong) move vs correct move
     - Random puzzle selection from recent mistakes on each page load
     - Board animations with arrows and highlights
   - **Socratic Method (Correct Move)**: 
     - "Good choice! But tell me — why is this better?"
     - Three reason options (1 correct, 2 plausible but wrong)
     - Shows real reason if wrong answer selected
   - **Idea Chain Explanation (Wrong Move)**:
     - Animated refutation on board
     - 5-step explanation: Your Idea → Why It Felt Right → Opponent's Counter → Why It Works → Better Approach
     - Rule summary at the end
     - "Replay on board" button
   - **Coach's Note**: 2-line emotional framing from mentor
   - **Light Stats**: 2-3 key metrics with trends (blunders/game, rating trend)
   - **Next Game Plan**: 1-2 line mental instruction
   - **Game Context**: Opponent name, platform, link to full analysis
   - **"Go Play. I'll watch this game."** CTA

4. **Progress Dashboard**
   - Rating tracking with weekly change
   - Accuracy trend (last 10 vs previous 10)
   - Blunder trend
   - Active habit highlighting
   - Resolved habits section

5. **Habit Tracking (Backend)**
   - Weakness pattern detection
   - Decay logic
   - Trend analysis
   - All intelligence preserved, selectively surfaced

6. **Opening Repertoire Analysis**
   - Identifies user's openings from games
   - Win/loss rates per opening
   - Interactive chessboard in lessons
   - Coach-like advice

### 🚫 Removed from UI (Backend intact)
- XP system
- Level progression (Pawn → Grandmaster)
- Achievements
- Daily streaks
- Reward-style notifications

### 📋 NOT Building
- Internal playing system
- Leaderboards
- Rating-based competition
- Parent dashboard
- Voice TTS

## Technical Architecture

```
/app/
├── backend/                 # Flask + MongoDB
│   ├── server.py           # Main API routes
│   │   ├── /api/coach/today     # One active habit
│   │   ├── /api/progress        # Metrics dashboard
│   │   ├── /api/journey/*       # Legacy (still works)
│   ├── stockfish_service.py     # Chess engine
│   ├── rating_service.py        # Rating predictions
│   ├── journey_service.py       # Background sync
│   └── player_profile_service.py
├── frontend/               # React + Tailwind
│   └── src/
│       ├── pages/
│       │   ├── Coach.jsx        # NEW - Default home
│       │   ├── Progress.jsx     # NEW - Metrics view
│       │   ├── Dashboard.jsx    # Games list
│       │   └── Landing.jsx
│       └── components/
│           ├── Layout.jsx       # Updated nav
│           └── OpeningRepertoire.jsx
└── mobile/                 # React Native (not updated yet)
```

## Key API Endpoints

### Coach Mode
- `GET /api/coach/today` - Returns ONE active habit + rule
- `GET /api/progress` - Rating, accuracy, blunders, habits

### Analysis
- `POST /api/games/{id}/analyze` - Analyze game
- `GET /api/analysis/{game_id}` - Get results

### Import
- `GET /api/journey/linked-accounts` - Check linked platforms
- `POST /api/journey/link-account` - Link Chess.com/Lichess
- `POST /api/journey/sync-now` - Manual sync

## Notification Rules

### Allowed
- "Your recent game has been reviewed."
- Weekly summary: Habit progress + Rating change (brief)

### NOT Allowed
- XP gain notifications
- Streak notifications
- Achievement unlock
- Engagement pressure messages

## Subscription Structure

### Free Tier
- Limited weekly analysis
- Basic metrics

### Paid Tier
- Full auto-analysis
- Coach Mode
- Habit tracking
- Rating trends
- Weekly summaries

## 3rd Party Integrations
- **Stockfish** - Chess engine (local binary at /usr/games/stockfish)
- **OpenAI GPT-4o-mini** - Idea chain explanations, why options (via Emergent LLM Key)
- **OpenAI GPT-5.2** - Full game analysis coaching commentary (via Emergent LLM Key)
- **Chess.com API** - Game imports
- **Lichess API** - Game imports
- **Emergent Google Auth** - Web authentication

## Database Collections
- `users` - User accounts + linked platforms
- `games` - Imported chess games
- `game_analyses` - Analysis results
- `player_profiles` - Weaknesses, strengths, habits, trends
- `coach_sessions` - Play session tracking (Go Play / Done Playing)
- `analysis_queue` - Priority game analysis queue
- `notifications` - Refined notification system
- `reflection_results` - PDR reflection tracking (move_correct, reason_correct)

---

## Changelog

### February 7, 2025 - Light Stats & Bug Fixes
- **Light Stats Fix**: Fixed Rating (30d) not showing by correcting `fetch_platform_ratings` result parsing
  - Now correctly accesses `ratings['chess_com']['rapid']` instead of `ratings['rapid']`
  - All 3 stats now display: Blunders/game, Rating (30d), Reflection success
- **Most Recent Game Logic Fix**: Fixed recurring bug in `coach_session_service.py`
  - Changed sort field from non-existent `date` to `imported_at`
  - Added opponent extraction from PGN White/Black headers
  - This fixes the fragile "most recent game" identification that caused incorrect game data to be displayed
- **Game Termination Display**: Verified termination reason displays correctly on both:
  - Coach page "Last Game" summary (e.g., "lost on time")
  - Game Analysis page header (e.g., "You lost on time" in amber color)
- **Testing**: 16/16 backend tests passed, all features verified working

### February 6, 2025 (Update 3) - Backlog Features
- **PDR Phase 2: Auto-Rotate Habits**
  - New service: `habit_rotation_service.py`
  - Tracks consecutive correct answers per habit
  - Auto-rotates when user demonstrates mastery (4+ consecutive OR 6/8 total correct)
  - Shows toast notification: "Great progress! You've mastered {habit}. Moving on to new focus area."
  - Endpoints: `GET /api/coach/habits`, `POST /api/coach/check-habit-rotation`
- **Weekly Email Summaries**
  - New service: `weekly_summary_service.py`
  - Generates personalized weekly assessment based on:
    - Games analyzed this week
    - Blunder trend comparison
    - Reflection success rate
    - Top weakness/strength
  - Endpoints: `GET /api/user/weekly-summary`, `POST /api/user/send-weekly-summary`
  - Email requires SendGrid API key in `.env`
- **Progress Page Enhancements**
  - Shows "Reflections: X/Y" for each habit
  - Displays "IMPROVING" badge when habit is progressing
  - Shows mastered habits in "Resolved" section
- **Bug Fix**: Fixed missing `res` variable in Coach.jsx handlePDRResult

### February 6, 2025 (Update 2)
- **Go Play Reminder Modal** - Shows "Before You Play" dialog with:
  - "Remember This" (rule) in purple box
  - "Your Plan" (next game plan) in blue box
  - Cancel/Open Chess.com buttons
- **Reflection Tracking** - POST `/api/coach/track-reflection` endpoint:
  - Saves PDR results to `reflection_results` collection
  - Increments user's `total_reflections` and `correct_reflections` counters
- **Enhanced Light Stats** - Now shows up to 3 stats:
  - Blunders/game with trend arrow
  - Rating (30d) with trend
  - Reflection success rate (e.g., 4/5)
- **Habit-Aligned PDR Selection** - 70% preference for mistakes matching dominant habit
- **Accessibility Fix** - Added aria-describedby to Go Play modal

### February 6, 2025
- **PDR Feature Complete** - Personalized Decision Reconstruction fully implemented
  - Two-move choice interface (user's move vs correct move)
  - Socratic "why is this better?" verification for correct answers
  - 5-step Idea Chain explanation for wrong answers with LLM-generated content
  - Board animations with arrows and highlights for refutations
  - Random puzzle selection from recent analyzed games
- **LLM Integration Fixed** - Updated pdr_service.py to use correct EMERGENT_LLM_KEY and LlmChat pattern
- **Stockfish Installed** - Chess engine available at /usr/games/stockfish for accurate refutation analysis
- **Backend Tests Added** - 14 test cases for PDR feature at /app/backend/tests/test_pdr_coach.py

---
*Last Updated: February 7, 2025*
*Philosophy: Hide intelligence, don't remove it. The system watches. It speaks when it matters.*
