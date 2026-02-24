# Chess Coach - Comprehensive Application Documentation

## Overview
A full-featured adaptive chess coaching application that analyzes games, identifies cognitive weaknesses, and provides personalized behavioral training.

**Philosophy:** Transform from analytics dashboard to behavioral shaping coach. Users should instantly understand "what I'm fixing and how to think differently."

---

## Tech Stack
- **Frontend:** React 18 (port 3000)
- **Backend:** FastAPI/Python (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish 16 (depth 18)
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)
- **Chess Libraries:** 
  - Backend: `python-chess`
  - Frontend: `chessground` (Lichess board), `react-chessboard`, `chess.js`

---

## Pages & Features

### 1. Landing Page (`/`)
- Marketing page with "Start Training Free" CTA
- "Dev Login" button for testing
- Google OAuth integration

### 2. Onboarding (`/onboarding`)
- **Step 1:** Link Chess.com/Lichess account (mandatory)
- **Step 2:** Skill calibration (FIDE rating, self-rating, focus intent)
- Validates accounts against Chess.com/Lichess APIs
- Auto-imports and analyzes recent games

### 3. Dashboard (`/dashboard`)
- Welcome message with user's name
- Stats cards: Total Games, Analyzed, Blunders, Best Moves
- Recent games list with ratings and results
- Focus Areas panel showing primary weakness
- "View Journey" CTA to cognitive journey page
- Auto-sync timer for new games

### 4. Lab - Game Analysis (`/game/:gameId`)
- **Full game replay** with move-by-move navigation
- **Coach Mode / Engine Mode toggle:**
  - Coach Mode: Shows only human-improvable errors
  - Engine Mode: Shows all engine disagreements
- **Move arrows:** Orange arrow shows current move being analyzed
- **Tabs:**
  - Summary: Game overview, brilliant moves
  - Strategy: Opening, key moments
  - Milestones: Learning moments with "What Can I Learn" explanations
- **Focus Mode Banner:** Shows active training focus
- **Micro-Protocol Card:** 3-step behavioral checklist
- **"From Journey" Banner:** Context when navigating from Journey page
- **Deep-link support:** `/lab/game/:gameId?move=X&src=journey`

### 5. Training (`/training`)
**Two main sections via tabs:**

#### A. Puzzles Tab
- Puzzles from YOUR games (not random positions)
- Interactive solving with Stockfish validation
- **Puzzle Rating System:**
  - Elo-based rating (starts at 1200)
  - 6 levels: Beginner → Master
  - Streak tracking
  - Achievements system
- **Source filter:** All Puzzles, My Games Only, Community Puzzles
- Shows solve rate, difficulty, and source attribution

#### B. Opening Trainer Tab
- **Your Repertoire:** Openings from your games with mastery levels
- **Opening Library:** 6 curated openings (Italian, Sicilian, Caro-Kann, etc.)
- **Community Comparison:** Compare accuracy to players at your rating
- **Trick Library:** 18 traps with 3 practice modes:
  - Execution Mode: Find the winning move
  - Avoidance Mode: Find safe defensive move
  - Recognition Mode: Spot if trap exists

### 6. Reflect (`/reflect`)
- **Time-sensitive reflection** on recent games
- Shows critical moments (blunders/mistakes) with urgency indicators
- **Interactive board** to show your thinking
- **Contextual Quick-Tags:** Position-aware options like "I wanted to attack the knight on c6"
- **Awareness Gap Detection:** LLM compares your thought vs actual position
- **View modes:** Your Move (red arrow), Better Move (green arrow), Both
- Red badge in nav shows games needing reflection

### 7. Journey - Cognitive Evolution (`/journey`)
**3-Tab Structure:**

#### Tab A: Now (Snapshot)
- Decision Stability band (Stable/Moderate/Unstable/Volatile)
- Main issue (top weakness)
- When ahead behavior (risk band)
- Weakest phase
- "Do this next" directive

#### Tab B: Journey (Then vs Now)
- Voice headline with badge for major improvements
- 4 stat rows: Accuracy, Blunders/Game, Mistakes/Game, Win Rate
- 4 cognitive rows: Decision Stability, Primary Driver, Advantage Risk, Weakest Phase
- Shows deltas only when meaningful changes detected

#### Tab C: Trend (5 vs 5)
- Rolling trend analysis
- Up to 2 meaningful shifts
- Top issues with evidence links
- Links to Lab page at specific positions

### 8. Progress (`/progress`)
- Weakness tracking over time
- Pattern frequency analysis
- TSI (Thinking Stability Index) trend chart

### 9. Settings (`/settings`)
- Profile settings
- Linked accounts management
- Notification preferences

---

## Core Backend Services

### 1. Game Analysis Pipeline
```
Import → Parse PGN → Stockfish Analysis → Mistake Classification → Cognitive Categorization → Store
```

### 2. Mistake Classification (`mistake_classifier.py`)
Categories:
- `missed_forcing_move` - Missed check/capture/threat
- `ignored_opponent_forcing` - Didn't respond to threat
- `structural_misjudgment` - Bad pawn structure decision
- `critical_moment_drift` - Lost focus at key moment
- `advantage_mismanagement` - Threw away winning position
- `phantom_threat` - Defended non-existent threat

### 3. TSI (Thinking Stability Index)
- Score 0-100 measuring decision consistency
- Weighted rolling window (recent games weighted 3x)
- Bands: 85-100 Stable, 70-84 Moderate, 55-69 Frequent lapses, <55 Volatile

### 4. Journey Engine (`journey_engine.py`)
- `StatInterpretationEngine`: Threshold-based signal detection
- `CoachVoiceGenerator`: Deterministic Indian-English text generation
- Reuses `baseline_service.py` for weakness detection

### 5. Reflect Service (`reflect_service.py`)
- Contextual tag generation based on position analysis
- Awareness gap detection
- Check detection to prevent absurd suggestions

### 6. Training Profile Service (`training_profile_service.py`)
- 4-layer cost scoring: Stability, Conversion, Structure, Precision
- Pattern weight management
- Phase-filtered example positions

---

## Key API Endpoints

### Authentication
- `GET /api/auth/google/login` - Google OAuth initiation
- `GET /api/auth/google/callback` - OAuth callback
- `GET /api/auth/dev-login` - Dev login for testing
- `GET /api/auth/me` - Get current user

### Games
- `GET /api/games` - List user's games
- `GET /api/games/:id` - Get specific game
- `POST /api/import-games` - Import from Chess.com/Lichess
- `POST /api/analyze-game` - Trigger analysis

### Training
- `GET /api/training/puzzles` - Get puzzles from user's mistakes
- `POST /api/training/puzzle/validate` - Validate puzzle answer
- `GET /api/training/puzzle-progress` - Puzzle rating and stats
- `GET /api/training/openings/stats` - User's opening statistics
- `GET /api/training/tricks` - Trick library
- `POST /api/training/tricks/validate-avoidance` - Validate avoidance mode
- `POST /api/training/tricks/validate-recognition` - Validate recognition mode

### Reflect
- `GET /api/reflect/pending` - Games needing reflection
- `GET /api/reflect/game/:id/moments` - Critical moments
- `POST /api/reflect/submit` - Submit reflection
- `POST /api/reflect/moment/contextual-tags` - Get position-aware tags

### Journey
- `GET /api/journey/evolution` - 3-tab journey data
- `GET /api/journey/linked-accounts` - Linked Chess.com/Lichess
- `POST /api/journey/link-account` - Link new account
- `POST /api/journey/unlink-account` - Unlink account
- `POST /api/journey/sync-now` - Manual sync trigger

### Cognitive Analysis
- `GET /api/cognitive/patterns` - TSI and patterns
- `GET /api/cognitive/trend` - TSI over time
- `GET /api/cognitive/tsi` - Current TSI score
- `GET /api/cognitive/blunder-context` - Position distribution

### Lab
- `GET /api/lab/:gameId` - Full lab data for game
- `POST /api/explain-mistake` - LLM explanation for mistake

### Evaluation (Stockfish)
- `GET /api/eval/position?fen=...` - Position analysis
- `GET /api/eval/best-move?fen=...` - Best move
- `POST /api/eval/move` - Analyze specific move

---

## Database Collections

### Core Collections
- `users` - User profiles, linked accounts, settings
- `games` - Imported games with PGN
- `game_analyses` - Stockfish analysis results per game
- `user_thoughts` - "What were you thinking?" gold data

### Training Collections
- `training_profiles` - User's training focus and phase
- `puzzle_attempts` - Puzzle solving history
- `puzzle_ratings` - Elo-based puzzle ratings
- `reflection_impacts` - How reflections affected training
- `trap_attempts` - Trick library practice attempts

### Coaching Collections
- `focus_plans` - Deterministic coaching plans
- `coaching_sessions` - Active coaching sessions
- `mistake_cards` - Spaced repetition cards

---

## Key Features Summary

| Feature | Status | Description |
|---------|--------|-------------|
| Game Import | ✅ | Chess.com & Lichess integration |
| Stockfish Analysis | ✅ | Depth 18 with caching |
| Move Arrows | ✅ | Visual indicators on boards |
| TSI Scoring | ✅ | Thinking Stability Index |
| Puzzle Trainer | ✅ | From your mistakes + community |
| Opening Trainer | ✅ | Your repertoire + curated openings |
| Trick Library | ✅ | 18 traps, 3 practice modes |
| Reflect System | ✅ | Time-sensitive with contextual tags |
| Journey 3-Tab | ✅ | Now/Journey/Trend views |
| Account Linking | ✅ | Single account per platform |
| Coach/Engine Mode | ✅ | Toggle human-improvable vs all errors |
| LLM Explanations | ✅ | GPT-4o-mini with verification layer |

---

## Known Issues / Technical Debt

1. **Stuck Analysis Screen** - 45-second timeout workaround in place, root cause not diagnosed
2. **LLM Hallucination Risk** - Light guardrail in place, may need strengthening
3. **Old Training.jsx** - Contains 3-step wizard code not currently routed

---

## Current Status

**Phase:** Validation - All new feature development PAUSED

**Next Action:** Observe 3-5 real users to validate:
- Emotional fairness of feedback
- Behavioral awareness of patterns
- Improvement speed on focus areas

---

## Credentials for Testing

- **Dev Login:** Click "Dev Login" on landing page
- **Test User:** Mohit (bhutramohit@gmail.com)
- **Linked Account:** Chess.com - killerknightroyalrook (1200-1400 rating)

---

## File Structure

```
/app
├── backend/
│   ├── server.py                    # Main FastAPI app (8500+ lines)
│   ├── services/
│   │   ├── baseline_service.py      # Weakness detection
│   │   ├── journey_engine.py        # 3-tab journey logic
│   │   ├── reflect_service.py       # Reflect page logic
│   │   ├── training_profile_service.py  # Training engine
│   │   ├── mistake_classifier.py    # Cognitive categorization
│   │   ├── mistake_explanation_service.py  # LLM explanations
│   │   ├── interactive_training_service.py  # Puzzle validation
│   │   ├── opening_trainer_service.py  # Opening trainer
│   │   ├── trick_library_service.py # Trick library
│   │   ├── puzzle_progression_service.py  # Elo ratings
│   │   ├── position_analysis_service.py  # Position analysis
│   │   └── chess_verification_layer.py  # Unified verification
│   └── tests/
│       └── *.py                     # Test files
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Lab.jsx              # Game analysis (118KB)
│   │   │   ├── TrainingNew.jsx      # Puzzles & Openings
│   │   │   ├── Reflect.jsx          # Reflection page
│   │   │   ├── JourneyCognitive.jsx # Journey 3-tab
│   │   │   ├── Onboarding.jsx
│   │   │   └── Landing.jsx
│   │   └── components/
│   │       ├── CoachBoard.jsx       # Reusable chess board
│   │       ├── LichessBoard.jsx     # Chessground wrapper
│   │       ├── OpeningTrainer.jsx   # Opening trainer UI
│   │       └── Layout.jsx           # App layout with nav
│   └── package.json
└── memory/
    └── PRD.md                       # Product requirements
```

---

## Integration Points

1. **Chess.com API** - Game import, account validation
2. **Lichess API** - Game import, opening explorer
3. **Stockfish** - Position analysis (via python-chess)
4. **OpenAI GPT-4o-mini** - Mistake explanations, awareness gaps
5. **Emergent LLM Key** - Universal API key for LLM services

---

## What Makes This App Unique

1. **Behavioral Focus** - Not just analytics, but cognitive pattern identification
2. **Your Mistakes** - Puzzles come from YOUR games, not random positions
3. **Deterministic Coaching** - Rule-based, no LLM randomness in core logic
4. **Indian-English Tone** - Plain, direct, supportive language
5. **Time-Sensitive Reflection** - Captures thoughts while memory is fresh
6. **TSI Scoring** - Novel metric for decision consistency
7. **Coach Mode** - Filters out "engine preferences", shows human-improvable errors only

---

## Recent Bug Fixes (Feb 23, 2026)

1. **Move Arrows** - Fixed arrow format for react-chessboard (`[[from, to, color]]`)
2. **Account Linking** - Added validation to prevent importing from wrong accounts
3. **Onboarding Loop** - Fixed field name inconsistency (`chess_com_username` vs `chesscom_username`)
4. **Contextual Tags** - Fixed "I saw X was undefended" when user clearly missed it
5. **Check Detection** - Don't suggest "I didn't notice" for pieces giving check
