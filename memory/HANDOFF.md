# ChessGuru - Complete Development Handoff Document

## Original Problem Statement
Hyper-personalized chess coaching application "ChessGuru" (formerly "Thinking Simulator"). Focuses on deep, insightful coaching for every move with a "One screen = one job" UX principle. The app tracks player identity (Chess DNA), patterns across games, and provides brutal truth coaching — not generic chess analysis.

## Tech Stack
- **Frontend**: React 18 + Tailwind CSS + Shadcn/UI + Framer Motion
- **Backend**: FastAPI (Python 3.11) + Motor (async MongoDB)
- **Database**: MongoDB
- **Chess Engine**: Stockfish (local binary at `/usr/games/stockfish`)
- **LLM**: OpenAI GPT-4o-mini via emergentintegrations library (uses Emergent LLM Key)
- **Auth**: Emergent-managed Google OAuth
- **Fonts**: Playfair Display (headings), DM Sans (body), JetBrains Mono (labels/mono)
- **Color Theme**: Light mode — warm off-white `#F5F3F0` bg, white `#FFFFFF` cards, Wine Red `#722F37` primary, Gold `#CBA135`/`#8B6F1F` accents

## Architecture Overview

### Backend (`/app/backend/`)
```
server.py              # 14,600+ lines — main FastAPI app (needs refactoring into routes/)
analysis_worker.py     # Background game analysis processor
routes/
  auth.py              # Google OAuth + dev login
  coach.py             # V5 coaching endpoints, decryption
  coach_play.py        # Live "Play with Coach" sessions  
  lab.py               # Lab page data + coach-insight endpoint
  games.py             # Game CRUD + import
  training.py          # Training/drill endpoints
  feedback.py          # Flag/feedback system
  openings.py          # Opening repertoire
  admin_openings.py    # Admin opening management
  journey.py           # Player journey tracking
  behavioral.py        # Behavioral analysis
  cognitive.py         # Cognitive gap analysis
  missions.py          # Missions/challenges
  notifications.py     # Push notifications
  settings.py          # User settings
  streak.py            # Win/loss streak tracking
  reflect.py           # Reflection/review
services/
  game_decryption_v5_service.py  # Core V5 coaching engine (2800+ lines)
  shared_coaching_v5.py          # Shared coaching logic for live play + lab
  v5_llm_narrator.py             # LLM-enhanced coaching narratives
  game_coach_summary.py          # 3-tab coach insight (summary/habits/memory)
  player_identity.py             # Chess DNA / player identity tracking
  community_training_service.py  # Training position extraction + community feed
  pattern_memory_service.py      # Pattern tracking across games
  player_profile_service.py      # Player profile management
```

### Frontend (`/app/frontend/src/`)
```
pages/
  Landing.jsx           # Premium landing page (coach-first design)
  HomePage.jsx          # Home dashboard V4 (coach message + board + actions)
  Dashboard.jsx         # Lab page (coach's review queue)
  LabV2.jsx             # Game review (board + decrypt/coach toggle)
  UnifiedProgress.jsx   # Progress page (trajectory + danger zones)
  CoachPlay.jsx         # Play with Coach (3500+ lines, needs refactoring)
  ThinkingTraining.jsx  # Training puzzles from real games
  AdminDashboard.jsx    # Admin panel
  ImportGames.jsx       # Game import from Chess.com/Lichess
  OpeningsOverview.jsx  # Opening study
components/
  Layout.jsx            # Sidebar + main layout
  LichessBoard.jsx      # Chess board (Chessground wrapper)
  GameDecryptionV5.jsx  # Move-by-move coaching cards
  Lab/
    CoachInsightPanel.jsx  # 3-tab coach panel (Summary/Habits/Memory)
  shared/
    V5CoachingCard.jsx     # Shared coaching card component
    FlagMoveDialog.jsx     # Feedback flag dialog
  coach/
    PreMoveChecklist.jsx   # Pre-move thinking checklist
  ui/                      # Shadcn components
```

## Key Features Implemented

### 1. Adaptive Game Decryption (V5 Engine)
- **V5_COACHING_VERSION = 7** — auto-regenerates cached coaching when logic changes
- **Rating-based filtering**: 1100 player only sees mistakes/blunders, not inaccuracies
- **Known weakness matching**: Moves matching player_identity patterns get "Known pattern" badge
- **PV-based consequence analysis**: Walks Stockfish PV to explain captures, checks, forcing sequences
- **Teaching-focused language**: Standard chess terms (knight, bishop, not "Horsey", "Slicey Boi")
- **Opponent plan reading**: `_extract_opponent_plan_from_pv()` detects kingside attacks, pawn storms, exchanges
- **Minor inaccuracy softening**: cp_loss < 50 gets gentler language ("fine, but X was slightly stronger")

### 2. Coach Insight Panel (3-Tab System)
- **Summary**: One brutal truth diagnosis (MATE_BLIND, THROW, SLOW_BLEED, etc.)
- **Habits**: Pass/fail checklist (5 habits with smart thresholds — mate blunders excluded from "hanging pieces")
- **Memory**: Chess DNA (before/after identity lines, archetype) + "If You Fixed This One Thing" (rating projection)

### 3. Smart Lab (Coach's Review Queue)
- **Smart game picker**: Priority = recurring pattern > thrown game > decisive blunder
- **3-state review**: not_started → in_progress (opened) → reviewed (reached last move)
- **Auto-mark reviewed**: When user navigates to last move in decrypt view
- **Coach prompt**: Sticky bar at bottom after finishing decrypt: "Open Coach View" button
- **Verdict strip**: "7W 8L — 5 games thrown from winning positions"

### 4. Home Page (Coach-First)
- **Dynamic coach message**: Based on streak/patterns/last game
- **Contextual primary action**: "Train Calculation Depth" / "Review This Loss" / "Play Another"
- **Two-column layout**: Board + actions on left/right, patterns + DNA below

### 5. Progress Page (Trajectory Dashboard)
- **Accuracy journey chart**: SVG line chart with gold gradient, green/red dots
- **Win Rate + Blunder Rate**: Side-by-side cards, blunders card turns RED when rising
- **Danger Zones**: Top 3 critical patterns linked to training
- **Chess Identity**: Archetype + biggest leak badge
- **Last 10 games strip**: Color-coded bars with accuracy opacity

### 6. Community Training
- **Auto-extraction**: Positions extracted from analyzed games via analysis_worker.py
- **Pattern classification**: Uses `cognitive_gap` + `coaching_focus` fields → calculation_depth, tactical_miss, etc.
- **Pattern filtering**: `/api/training/community-feed?pattern=calculation_depth`
- **Solve feedback**: Backend returns candidates with ideas via Stockfish multi-PV
- **Known bug**: Board onMove callback has timing issues with AnimatePresence — fix: removed `mode="wait"`, board stays always interactive

### 7. Play with Coach
- **Live coaching**: Real-time feedback on every move
- **Opponent plan reading**: Same `_explain_opponent_move_with_context()` as Lab
- **Removed**: "Explain my position" buttons + chat input (coach is proactive)
- **Removed**: Opening suggestion card during play

## Key API Endpoints

### Home
- `GET /api/home/dashboard-v2` — Coach message, last battle (FEN + critical position), chess DNA, patterns, streak, one-thing-to-fix

### Lab
- `GET /api/lab-coach-pick` — Smart game picker + verdict + all games with review status
- `POST /api/lab-mark-reviewed/{game_id}?status=in_progress|reviewed`
- `GET /api/lab/{game_id}/coach-insight` — 3-tab coaching data (summary/habits/memory)
- `GET /api/lab/{game_id}` — Full lab data

### Coaching
- `GET /api/coach/decryption/v5/{game_id}` — V5 move-by-move coaching (cached, auto-regenerates on version bump)
- `POST /api/coach/play/start` — Start live game
- `POST /api/coach/play/move` — Submit player move in live game

### Training
- `GET /api/training/community-feed?limit=12&pattern=calculation_depth` — Filtered training positions
- `POST /api/training/solve-attempt` — Submit solve, returns correct/incorrect + candidates
- `POST /api/training/extract-positions/{game_id}` — Extract training positions from a game

### Progress
- `GET /api/progress/journey` — Accuracy journey, win trend, blunder trend, chess DNA, danger zones

### Admin
- `GET /api/admin/feedback` — All user feedback with rich diagnostics
- `POST /api/feedback/flag` — Submit flag with full diagnostic context

## Database Collections (MongoDB)
- `users` — User accounts
- `games` — Imported games (has `reviewed`, `review_status` fields)
- `game_analyses` — Stockfish analysis + V5 coaching data (cached in `decryption_v5_data`)
- `player_identities` — Chess DNA, blunder taxonomy, play style
- `player_profiles` — Estimated ELO, accuracy stats
- `thinking_scores` — Per-game habit scores
- `community_training_positions` — Extracted training positions with pattern_type
- `coach_sessions` — Live play sessions
- `user_concept_understanding` — Acknowledged coaching concepts
- `move_feedback` — Flag/feedback submissions with diagnostics

## CSS Theme (index.css `.dark` class — actually light theme)
```css
--background: 37 16% 96%;     /* #F5F3F0 warm off-white */
--card: 0 0% 100%;            /* #FFFFFF white */
--primary: 353 42% 32%;       /* #722F37 wine red */
--accent: 43 59% 50%;         /* #CBA135 gold */
--border: 35 10% 87%;         /* light warm border */
--muted-foreground: 30 5% 45%; /* gray text */
```

## Known Issues / Bugs
1. **Training solve feedback**: Board `onMove` callback has timing issue with Chessground — AnimatePresence `mode="wait"` was removed, board stays always interactive. User should verify in browser.
2. **server.py 14,600+ lines**: 272 endpoints still in server.py, needs modular refactoring into routes/
3. **CoachPlay.jsx 3500+ lines**: Needs breakdown into smaller components
4. **Feedback #2 unfixed**: Qg6 fork misidentification (coach says "fork king and knight" but it's "king and queen")
5. **LLM Key**: Uses emergentintegrations library with Emergent LLM Key. If deploying independently, replace with direct OpenAI SDK calls — extract `response.choices[0].message.content` (don't return raw response object)

## Deployment Notes
- Backend runs on port 8001, frontend on 3000
- All API routes prefixed with `/api`
- Frontend uses `REACT_APP_BACKEND_URL` env var
- Backend uses `MONGO_URL` and `DB_NAME` env vars
- Stockfish binary at `/usr/games/stockfish`
- V5_COACHING_VERSION = 7 — bump this when coaching logic changes to auto-regenerate

## LLM Integration (CRITICAL for self-hosting)
The app uses `emergentintegrations` library which requires an Emergent LLM Key. For self-hosting:

1. Replace `from emergentintegrations.llm import ...` with direct OpenAI SDK
2. Key files to modify:
   - `services/v5_llm_narrator.py` — coaching narrative enhancement
   - `services/shared_coaching_v5.py` — live coaching LLM calls
   - `services/game_coach_summary.py` — game summary generation
3. IMPORTANT: Extract text from OpenAI response: `response.choices[0].message.content`
4. The "body stream already read" error on Hostinger was likely caused by returning the raw OpenAI response object instead of the extracted text string

## What's Next (Prioritized Backlog)
### P0
- Fix training solve feedback (verify board interaction in browser)
- Fix Qg6 fork misidentification in coaching

### P1
- Admin content management for opening/endgame theory JSONs
- Refactor server.py into modular route files
- Refactor CoachPlay.jsx (3500+ lines → smaller components)

### P2
- Endgame expansion (minor piece endgames)
- Voice coaching mode
- "Theory Applied" celebration streak

## Testing
- Test reports: `/app/test_reports/iteration_165.json` (latest passing)
- Dev login: Click "Dev Login" on landing page (dev user has super_admin role)
- All games belong to user `user_62852a1b64e7` (dev user)
