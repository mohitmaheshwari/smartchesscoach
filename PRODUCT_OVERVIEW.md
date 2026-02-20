# Chess Coach - Complete Product Overview
## For LLM Review & Product Assessment

---

# 1. PRODUCT VISION & GOALS

## Core Mission
Build an **AI-powered chess coaching application** that:
1. Analyzes user's games using Stockfish engine
2. Identifies personalized weaknesses and patterns
3. Provides adaptive training focused on one weakness at a time
4. Creates a "GM-coach" style experience with actionable feedback

## Target Users
- Chess players rated 400-2200+ on Chess.com/Lichess
- Players who want to improve but don't know what to work on
- Self-learners who need structure and accountability

## Key Differentiators
1. **Data-Driven Coaching**: Uses YOUR game data, not generic advice
2. **One Weakness at a Time**: Focuses training on your biggest leak
3. **Interactive Learning**: Puzzles from your own mistakes
4. **Real Statistics**: Integrates Lichess Opening Explorer (300M+ games)
5. **Reflection System**: Captures your thought process for pattern analysis

---

# 2. TECHNICAL ARCHITECTURE

## Stack
```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  React 18 + Vite + TailwindCSS + Shadcn/UI                  │
│  Port: 3000                                                  │
│  Chessboard: Lichess Chessground Library                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        BACKEND                               │
│  FastAPI (Python 3.11) + Async                              │
│  Port: 8001 (proxied via /api)                              │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    MongoDB      │  │   Stockfish     │  │  OpenAI GPT     │
│  (All data)     │  │  (Analysis)     │  │  (Explanations) │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                                                    │
                                          ┌────────┴────────┐
                                          │ Emergent LLM Key│
                                          │ (Universal Key) │
                                          └─────────────────┘
```

## External Integrations
1. **Stockfish**: Deep game analysis (18-depth)
2. **OpenAI GPT-4o-mini**: Natural language explanations (via Emergent LLM Key)
3. **Lichess Opening Explorer API**: Real opening statistics from 300M+ games
4. **Chess.com API**: Game import
5. **Lichess API**: Game import

---

# 3. DATABASE SCHEMA (MongoDB)

## Collections

### `users`
```json
{
  "user_id": "user_xxx",
  "email": "user@example.com",
  "username": "chessplayer123",
  "rating": 1200,
  "platform": "chess.com",
  "created_at": "2026-01-01T..."
}
```

### `games`
```json
{
  "game_id": "game_xxx",
  "user_id": "user_xxx",
  "pgn": "1. e4 e5 2. Nf3...",
  "platform": "chess.com",
  "result": "win",
  "user_color": "white",
  "opponent": "opponent123",
  "opening_name": "Italian Game",
  "is_analyzed": true,
  "accuracy": 78.5,
  "imported_at": "2026-01-01T..."
}
```

### `game_analyses`
```json
{
  "game_id": "game_xxx",
  "user_id": "user_xxx",
  "stockfish_analysis": {
    "accuracy": 78.9,
    "move_evaluations": [
      {
        "move_number": 15,
        "evaluation": "blunder",
        "played_move": "Qh5",
        "best_move": "Nf3",
        "cp_loss": 450,
        "fen": "rnbqkbnr/..."
      }
    ]
  },
  "commentary": [...],
  "blunders": 3,
  "mistakes": 5
}
```

### `reflections`
```json
{
  "reflection_id": "ref_xxx",
  "user_id": "user_xxx",
  "game_id": "game_xxx",
  "move_number": 15,
  "moment_fen": "rnbqkbnr/...",
  "user_thought": "I thought I could win the queen",
  "awareness_gap": "You missed that Nxe5 wins the knight",
  "tags": ["missed_tactic", "calculation_error"],
  "created_at": "2026-02-15T..."
}
```

### `training_profiles`
```json
{
  "user_id": "user_xxx",
  "active_phase": "opening_principles",
  "current_tier": 3,
  "phase_progress": {
    "clean_games": 2,
    "target": 3,
    "mistakes_per_game": 1.8
  },
  "pattern_weights": {
    "threat_blindness": 0.46,
    "hanging_pieces": 0.32
  },
  "updated_at": "2026-02-15T..."
}
```

### `user_thoughts` (Gold Data)
```json
{
  "thought_id": "thought_xxx",
  "user_id": "user_xxx",
  "game_id": "game_xxx",
  "move_number": 15,
  "thought_text": "I thought I could win material",
  "move_played": "Nc7+",
  "best_move": "Ne7+",
  "evaluation_type": "blunder",
  "cp_loss": 400
}
```

---

# 4. CORE FEATURES

## 4.1 Game Import & Analysis

### Flow
1. User connects Chess.com or Lichess account
2. System imports last 50-100 games
3. Background worker analyzes each game with Stockfish
4. Stores move-by-move evaluation data
5. Calculates accuracy using CAPS2-style algorithm (matches Chess.com)

### API Endpoints
- `POST /api/connect-platform` - Link chess account
- `POST /api/import-games` - Import games
- `POST /api/analyze-game` - Trigger analysis
- `GET /api/games` - List user's games
- `GET /api/games/{game_id}` - Get game details
- `GET /api/analysis/{game_id}` - Get Stockfish analysis

---

## 4.2 Lab (Game Analysis Page)

### Purpose
Deep-dive into individual games with move-by-move analysis.

### Features
- Interactive chessboard with move navigation
- "Learning Moments" - list of mistakes/blunders
- "What were you thinking?" - capture user's thought process
- "Play the better line" - visualize the correct continuation
- AI-generated explanations for each mistake

### Key Files
- `frontend/src/pages/Lab.jsx`
- `frontend/src/pages/GameAnalysis.jsx`
- `backend/mistake_explanation_service.py`

---

## 4.3 Reflect Page (Time-Sensitive Reflection)

### Purpose
Prompt users to reflect on mistakes while memory is fresh.

### Features
- Shows games needing reflection with urgency indicators
- Critical moments with board position
- **Contextual Quick-Tags**: Position-aware options like:
  - "I was attacking the weak f7 square"
  - "I wanted to capture the pawn"
  - "I was trying to give check"
- **Awareness Gap Detection**: LLM analyzes what user missed
- Badge in navigation shows count of pending reflections

### API Endpoints
- `GET /api/reflect/pending` - Games needing reflection
- `GET /api/reflect/pending/count` - Count for badge
- `GET /api/reflect/game/{game_id}/moments` - Critical positions
- `POST /api/reflect/submit` - Submit reflection
- `POST /api/reflect/moment/contextual-tags` - Get position-aware tags

### Key Files
- `frontend/src/pages/Reflect.jsx`
- `backend/reflect_service.py`

---

## 4.4 Training Page (Personalized Training)

### Purpose
Adaptive training system that focuses on ONE weakness at a time.

### Two Modes (Tabs)

#### Tab 1: Puzzles (Interactive Problem Solving)
- Puzzles sourced from YOUR OWN mistakes
- Find the better move interactively
- Immediate feedback with explanations
- Tracks solved count and accuracy

#### Tab 2: Opening Trainer (Phase 2)
- Tree view of user's opening repertoire
- **Lichess Statistics**: Win/draw/loss from 300M+ games
- Key variations and move orders
- Traps to know (and avoid)
- Practice mode with step-through controls

### Training Philosophy: "Data-Driven, One Leak at a Time"

**6 Training Tiers (based on rating):**
1. **Fundamentals** (0-600): Piece Safety, Check Awareness
2. **Stability** (600-1000): Blunder Reduction, Threat Detection
3. **Structure** (1000-1400): Opening Principles, Pawn Structure
4. **Conversion** (1400-1800): Advantage Maintenance, Endgames
5. **Precision** (1800-2200): Calculation Depth, Complex Tactics
6. **Mastery** (2200+): Deep Preparation, Psychology

### API Endpoints
- `GET /api/training/puzzles` - Personalized puzzles
- `POST /api/training/puzzle/validate` - Check answer
- `GET /api/training/openings/stats` - User's opening repertoire
- `GET /api/training/openings/{key}` - Opening training content
- `GET /api/training/lichess/opening?moves=e4,e5` - Lichess stats

### Key Files
- `frontend/src/pages/TrainingNew.jsx`
- `frontend/src/components/OpeningTrainer.jsx`
- `backend/interactive_training_service.py`
- `backend/opening_trainer_service.py`
- `backend/lichess_opening_service.py`

---

## 4.5 Journey Page (Progress Dashboard)

### Purpose
Track improvement over time.

### Features
- Rating trajectory chart
- Games played statistics
- Weakness trends over time
- Badge/achievement system
- Linked accounts management

### Key Files
- `frontend/src/pages/Journey.jsx`
- `backend/chess_journey_service.py`

---

# 5. BACKEND SERVICES

## Core Analysis Services
| Service | Purpose |
|---------|---------|
| `stockfish_service.py` | Stockfish engine wrapper for deep analysis |
| `chess_verification_layer.py` | **CRITICAL**: Single source of truth for position analysis |
| `mistake_explanation_service.py` | Generate explanations for mistakes |
| `position_analysis_service.py` | Analyze what moves do (attacks, defends, captures) |
| `mistake_classifier.py` | Classify mistakes (blunder, mistake, inaccuracy) |

## Training Services
| Service | Purpose |
|---------|---------|
| `training_profile_service.py` | User's training state and progress |
| `interactive_training_service.py` | Puzzle generation from user's mistakes |
| `opening_trainer_service.py` | Opening database with variations/traps |
| `lichess_opening_service.py` | Lichess Opening Explorer API integration |

## Reflection Services
| Service | Purpose |
|---------|---------|
| `reflect_service.py` | Time-sensitive reflection prompts |

## Legacy Services (Deprecated but kept)
| Service | Purpose |
|---------|---------|
| `focus_plan_service.py` | Old deterministic coaching |
| `adaptive_coach_service.py` | Old adaptive coach v1 |

---

# 6. FRONTEND PAGES

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | `Landing.jsx` | Landing page with auth |
| `/training` | `TrainingNew.jsx` | Puzzles + Opening Trainer |
| `/reflect` | `Reflect.jsx` | Time-sensitive reflection |
| `/lab` | `Lab.jsx` | Deep game analysis |
| `/journey` | `Journey.jsx` | Progress dashboard |
| `/import` | `ImportGames.jsx` | Game import wizard |
| `/settings` | `Settings.jsx` | User settings |

---

# 7. KEY TECHNICAL DECISIONS

## Chess Verification Layer
**Problem**: Multiple services had inconsistent analysis (e.g., missed checkmates)
**Solution**: Created `chess_verification_layer.py` as single source of truth
- All position analysis goes through this layer
- Priority order: Checkmate > Tactics > Positional
- Prevents LLM hallucinations by providing verified facts

## CAPS2-Style Accuracy
**Problem**: Our accuracy didn't match Chess.com
**Solution**: Implemented CAPS2 algorithm
- Classifies each move (blunder, mistake, inaccuracy, good, excellent, best)
- Weighted scoring that matches Chess.com methodology

## Lichess Chessground Migration
**Problem**: `react-chessboard` had UX issues
**Solution**: Migrated to Lichess Chessground library
- Professional animations and styling
- Arrow rendering for showing moves
- Better interactive experience

## ECO Opening Mapping
**Problem**: Games stored ECO codes (B01, C50) not names
**Solution**: Created `eco_openings.json` with 500+ mappings
- B01 → "Scandinavian Defense"
- C50 → "Italian Game"

---

# 8. THIRD-PARTY INTEGRATIONS

| Integration | Purpose | Status |
|-------------|---------|--------|
| **Stockfish** | Game analysis engine | ✅ Active |
| **OpenAI GPT-4o-mini** | Natural language explanations | ✅ Active (via Emergent Key) |
| **Lichess Opening Explorer** | Opening statistics (300M+ games) | ✅ Active |
| **Chess.com API** | Game import | ✅ Active |
| **Lichess API** | Game import | ✅ Active |

---

# 9. WHAT'S WORKING (Production Ready)

✅ **Game Import**: Chess.com and Lichess integration
✅ **Game Analysis**: Stockfish-powered move-by-move analysis
✅ **Lab Page**: Deep analysis with explanations
✅ **Reflect Page**: Time-sensitive reflection with awareness gaps
✅ **Training Puzzles**: Interactive puzzles from user's mistakes
✅ **Opening Trainer**: Tree view + Lichess statistics
✅ **Journey Dashboard**: Progress tracking
✅ **Auth**: Google OAuth + Dev login

---

# 10. UPCOMING FEATURES

## Phase 3: Community Learning
- Shared puzzle pool from all users
- Categorize by theme and rating band
- Learn from community's mistakes

## Phase 4: Trick Library
- Curated tactical patterns (Noah's Ark Trap, Legal's Mate, etc.)
- Practice positions with explanations

## Future
- Player DNA Profile (after 30+ games)
- Advanced pattern analysis from gold data
- Mobile app

---

# 11. API ENDPOINT SUMMARY

## Authentication
- `GET /api/auth/google/login` - Google OAuth
- `GET /api/auth/dev-login` - Dev login
- `GET /api/auth/me` - Current user
- `POST /api/auth/logout` - Logout

## Games
- `POST /api/connect-platform` - Link account
- `POST /api/import-games` - Import games
- `GET /api/games` - List games
- `GET /api/games/{id}` - Get game
- `POST /api/analyze-game` - Analyze game
- `GET /api/analysis/{id}` - Get analysis

## Reflection
- `GET /api/reflect/pending` - Pending reflections
- `GET /api/reflect/pending/count` - Badge count
- `POST /api/reflect/submit` - Submit reflection
- `POST /api/reflect/moment/contextual-tags` - Get tags

## Training
- `GET /api/training/puzzles` - Get puzzles
- `POST /api/training/puzzle/validate` - Check answer
- `GET /api/training/openings/stats` - User's openings
- `GET /api/training/openings/{key}` - Opening content
- `GET /api/training/lichess/opening` - Lichess stats

## Journey
- `GET /api/journey` - Dashboard data
- `GET /api/journey/weakness-trends` - Trends

---

# 12. CREDENTIALS FOR TESTING

- **Dev Login**: Button on landing page (creates test user)
- **Session Token**: `test_session_356539ff12b1` (for API testing)
- **Test User**: Has 30+ analyzed games with reflections

---

# 13. FILE STRUCTURE

```
/app
├── backend/
│   ├── server.py                    # Main FastAPI app (6000+ lines)
│   ├── stockfish_service.py         # Stockfish wrapper
│   ├── chess_verification_layer.py  # Position analysis (critical)
│   ├── interactive_training_service.py
│   ├── opening_trainer_service.py   # Opening database
│   ├── lichess_opening_service.py   # Lichess API
│   ├── reflect_service.py
│   ├── mistake_explanation_service.py
│   ├── position_analysis_service.py
│   ├── training_profile_service.py
│   └── data/
│       └── eco_openings.json        # ECO code mappings
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── TrainingNew.jsx      # Training page
│       │   ├── Reflect.jsx          # Reflection page
│       │   ├── Lab.jsx              # Game analysis
│       │   └── Journey.jsx          # Dashboard
│       └── components/
│           ├── OpeningTrainer.jsx   # Opening trainer
│           ├── CoachBoard.jsx       # Chess board wrapper
│           └── LichessBoard.jsx     # Chessground wrapper
└── memory/
    └── PRD.md                       # Product requirements
```

---

# 14. KNOWN LIMITATIONS

1. **Opening Content**: Only 12 openings have curated traps/key ideas
2. **Lichess-only Stats**: No Chess.com opening stats (API limitations)
3. **Single User Focus**: No multiplayer or social features yet
4. **English Only**: No internationalization

---

# 15. METRICS TO TRACK

- Games analyzed per user
- Reflections submitted
- Puzzles solved accuracy
- Time in training sessions
- User retention (weekly active)
- Rating improvement correlation

---

*Document generated: February 20, 2026*
*For LLM review and product assessment*
