# Chess Coach AI - Product Requirements Document

## Original Problem Statement
Build a full-stack AI chess coach application that integrates with Chess.com and Lichess to import user games, understand playing style, remember mistakes, and provide human-like coaching commentary in the persona of a firm but supportive Indian chess coach.

## Target Audience
- Kids (8-16) learning chess with parent oversight
- Competitive adults looking to improve
- Chess academies and schools (B2B)

## Core Features

### ✅ Implemented
1. **User Authentication**
   - Emergent-managed Google Auth (Web)
   - Demo Login for mobile testing
   - JWT session management

2. **Game Import & Analysis**
   - Chess.com and Lichess integration
   - Stockfish engine for accurate move evaluation
   - GPT-powered coaching commentary
   - Background auto-sync every 6 hours

3. **Journey Dashboard**
   - Progress tracking
   - Weakness pattern detection
   - Strength identification
   - Focus recommendations

4. **Gamification System** (NEW - Dec 2025)
   - XP & Level System (20 levels: Pawn → Grandmaster)
   - 25+ Achievements across 7 categories
   - Daily streak tracking with bonuses
   - Daily reward claims
   - Leaderboard
   - Auto XP for: game import (+5), analysis (+25), 90%+ accuracy (+30), no blunders (+20)

5. **Mobile App** (React Native/Expo)
   - Tab navigation: Journey → Games → Badges → Settings
   - Game analysis with redesigned UX
   - Gamification components
   - Demo login flow

6. **Rating & Training Backend**
   - Rating trajectory prediction
   - Time management analysis
   - Fast thinking trainer
   - Puzzle generation

### 🔄 In Progress
- Parent Dashboard
- Mobile Game Analysis UX refinements

### ✅ Recently Completed (Feb 2025)
- **Interactive Chessboard in Opening Lessons** - Opening repertoire coaching modal now displays moves on an interactive chessboard with:
  - Navigation controls (back, forward, play/pause, skip)
  - Clickable move list to jump to any position
  - Board flipping for black piece lessons
  - Auto-play mode to watch moves automatically
  - 13 openings with hardcoded move sequences

### 📋 Planned (P1)
- Puzzle Rush / Challenge Mode
- Rating Prediction UI (frontend)
- Time Management UI
- Opening Repertoire Builder (extend existing analysis into full builder)
- Push notifications for streak reminders

### 📋 Future (P2)
- Freemium Model
- "Coach Call" - AI-generated weekly video summary
- "Prepare for Opponent" mode
- Voice coaching on mobile
- WhatsApp weekly reports
- B2B Academy Dashboard
- Hindi/Vernacular language support

## Technical Architecture

```
/app/
├── backend/                 # FastAPI + MongoDB
│   ├── server.py           # Main API routes
│   ├── gamification_service.py  # XP, achievements, streaks
│   ├── stockfish_service.py     # Chess engine
│   ├── rating_service.py        # Rating predictions
│   ├── journey_service.py       # Dashboard logic
│   └── player_profile_service.py
├── frontend/               # React + Tailwind
│   └── src/
│       ├── components/
│       │   ├── Gamification.jsx        # XP bar, achievements, etc.
│       │   ├── OpeningRepertoire.jsx   # Opening analysis & coaching
│       │   └── InteractiveChessBoard.jsx # Visual move display
│       └── pages/
│           └── Journey.jsx
└── mobile/                 # React Native + Expo
    ├── app/
    │   ├── (tabs)/
    │   │   ├── journey.js
    │   │   ├── games.js
    │   │   ├── achievements.js   # NEW
    │   │   └── settings.js
    │   └── game/[id].js
    └── src/components/
        └── Gamification.js
```

## Key API Endpoints

### Gamification
- `GET /api/gamification/progress` - User XP, level, streak, stats
- `GET /api/gamification/achievements` - All achievements with unlock status
- `POST /api/gamification/daily-reward` - Claim daily login reward
- `GET /api/gamification/leaderboard` - Top users by XP

### Analysis
- `POST /api/games/{id}/analyze` - Analyze game with Stockfish + GPT
- `GET /api/analysis/{game_id}` - Get analysis results

### Journey
- `GET /api/journey` - Dashboard data
- `POST /api/journey/sync-now` - Manual game sync

## 3rd Party Integrations
- **Stockfish** - Chess engine (local binary)
- **OpenAI GPT-5.2** - Coaching commentary (via Emergent LLM Key)
- **Chess.com API** - Game imports
- **Lichess API** - Game imports
- **Emergent Google Auth** - Web authentication

## Database Collections
- `users` - User accounts
- `games` - Imported chess games
- `game_analyses` - Analysis results with Stockfish data
- `user_progress` - XP, level, streak, stats
- `user_achievements` - Unlocked achievements
- `mistake_patterns` - Detected weakness patterns
- `player_profiles` - Player style and preferences

## Level System
| Level | Name | XP Required |
|-------|------|-------------|
| 1-3 | Pawn I-III | 0-250 |
| 4-6 | Knight I-III | 500-1200 |
| 7-9 | Bishop I-III | 1700-3000 |
| 10-12 | Rook I-III | 4000-6500 |
| 13-15 | Queen I-III | 8000-12500 |
| 16-18 | King I-III | 15500-23000 |
| 19 | Master | 28000 |
| 20 | Grandmaster | 35000 |

## Achievement Categories
1. **Beginner** - First steps, curious mind, puzzle starter
2. **Streak** - On fire (3d), Dedicated student (7d), Vishy's Apprentice (14d), Chess Warrior (30d)
3. **Analysis** - Analyst (5), Deep thinker (25), Game scholar (100)
4. **Accuracy** - Sharp player (80%), Precision master (90%), Computer-like (95%)
5. **Quality** - Careful player, Blunder-free warrior, Fortress
6. **Puzzles** - Tactical eye, Tactical tiger, Puzzle master, Speed demon
7. **Level** - Rising star, Climbing ranks, Elite player, Grandmaster material

---
*Last Updated: December 2025*
