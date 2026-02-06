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
   - Stockfish engine for accurate move evaluation
   - GPT-powered coaching commentary
   - Background auto-sync every 6 hours
   - Auto-analysis (15 on first sync, 3/day ongoing)

3. **Coach Mode** (NEW - Feb 2025)
   - One active habit at a time
   - Clear rule for each habit
   - "Go Play. I'll review." CTA
   - Minimal, discipline-first design

4. **Progress Dashboard** (NEW - Feb 2025)
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
- **Stockfish** - Chess engine (local binary)
- **OpenAI GPT** - Coaching commentary (via Emergent LLM Key)
- **Chess.com API** - Game imports
- **Lichess API** - Game imports
- **Emergent Google Auth** - Web authentication

## Database Collections
- `users` - User accounts + linked platforms
- `games` - Imported chess games
- `game_analyses` - Analysis results
- `player_profiles` - Weaknesses, strengths, habits
- `notifications` - Refined notification system

---
*Last Updated: February 2025*
*Philosophy: Hide intelligence, don't remove it. The system watches. It speaks when it matters.*
