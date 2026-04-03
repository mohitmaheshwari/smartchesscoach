# ChessGuru — Complete Codebase Documentation for Claude Code

## What is ChessGuru?

ChessGuru is a personalized chess coaching platform that watches how you play, remembers your mistake patterns, and builds training programs around your specific weaknesses. It's not a puzzle app — it's a closed-loop coaching system where your mistakes become your training material, and the system knows when you've stopped making them.

Target audience: 600-1500 rated players stuck on a plateau.

---

## Tech Stack

- **Frontend**: React 18 (CRA), Tailwind CSS, Shadcn/UI components, Framer Motion, react-chessboard
- **Backend**: FastAPI (Python 3.11), motor (async MongoDB driver), python-chess, Stockfish
- **Database**: MongoDB (single DB: `test_database`)
- **LLM**: OpenAI GPT-4o-mini via Emergent LLM Key (emergentintegrations library)
- **Auth**: JWT + dev mode (DEV_MODE=true auto-authenticates as dev_user_local)

### Environment Variables

**Backend (`/app/backend/.env`):**
```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"
EMERGENT_LLM_KEY=<key>
DEV_MODE=true
```

**Frontend (`/app/frontend/.env`):**
```
REACT_APP_BACKEND_URL=https://coaching-board.preview.emergentagent.com
```

---

## Architecture Overview

```
/app/
├── backend/
│   ├── server.py                          # Main FastAPI app, api_router, lab-coach-pick, pattern-puzzles, extract-puzzles endpoints
│   ├── routes/                            # Modular route files (all prefixed /api)
│   │   ├── auth.py          (/auth)       # Login, register, dev-login, Google OAuth
│   │   ├── coach.py         (/coach)      # Coach home-intelligence, coaching endpoints
│   │   ├── coach_play.py    (/coach/play) # Play with Coach: start, move, teaching/*, escape-squares/*
│   │   ├── training.py      (/training)   # Training plans, puzzle attempts, prescribed training
│   │   ├── reflect.py       (/reflect)    # Game reflection/review
│   │   ├── games.py         (/games)      # Game import, sync, analysis
│   │   ├── journey.py                     # Player journey tracking
│   │   ├── lab.py                         # Lab page data
│   │   ├── openings.py                    # Opening repertoire
│   │   ├── missions.py      (/missions)   # Behavioral missions
│   │   ├── streak.py        (/streak)     # Streak tracking
│   │   ├── behavioral.py    (/behavioral) # Behavioral analysis
│   │   ├── cognitive.py                   # Cognitive gap analysis
│   │   ├── feedback.py      (/coach/pattern-learning) # Pattern learning feedback
│   │   ├── notifications.py (/notifications)
│   │   ├── settings.py                    # User settings
│   │   └── admin_openings.py (/admin/openings)
│   │
│   ├── services/                          # Business logic services
│   │   ├── realtime_coaching_feedback.py  # ★ RATING-AWARE move-by-move coaching feedback
│   │   ├── teaching_engine.py             # Generic lesson dispatcher (traps, endgames)
│   │   ├── escape_squares_service.py      # Count escape squares quiz
│   │   ├── pattern_decay_service.py       # ★ Recency-weighted mistake scoring
│   │   ├── puzzle_extraction_service.py   # ★ Auto-extract puzzles from analyzed games
│   │   ├── postgame_analysis.py           # Postgame analysis pipeline
│   │   ├── position_reader.py             # Position analysis
│   │   ├── coach_memory.py                # Persistent coach memory across sessions
│   │   ├── coach_personality.py           # Coach personality/voice
│   │   ├── coach_move_pipeline.py         # Coach move selection
│   │   ├── opening_curriculum_engine.py   # Opening teaching curriculum
│   │   ├── trap_library.py                # Verified chess traps (18)
│   │   ├── endgame_teaching.py            # Endgame lessons (10)
│   │   └── ... (100+ service files)
│   │
│   ├── coach_play/                        # Play with Coach subsystem
│   │   ├── coach_game_session.py          # Session management (CoachGameSession dataclass)
│   │   ├── coach_opponent.py              # Engine opponent with adjustable strength
│   │   ├── coach_commentary.py            # Move commentary generation
│   │   ├── pre_move_guardian.py           # Pre-move safety check ("Are you sure?")
│   │   ├── teaching_integration.py        # Teaching mode integration
│   │   └── ...
│   │
│   ├── deterministic_coach_service.py     # ★ RATING_BANDS definition, coaching plan generation
│   ├── home_intelligence_service.py       # Dashboard data with win streak + mood override
│   ├── community_learning_service.py      # Community puzzle sharing
│   ├── cognitive_gap_service.py           # Cognitive gap detection
│   ├── journey_service.py                 # Game import from Chess.com/Lichess
│   ├── analysis_worker.py                 # Background Stockfish analysis worker
│   ├── stockfish_service.py               # Stockfish wrapper
│   ├── llm_service.py                     # LLM integration (OpenAI via emergentintegrations)
│   │
│   ├── data/
│   │   ├── opening_curriculum.json        # Opening teaching data
│   │   ├── traps.json                     # 18 trap definitions (FEN, moves, explanations)
│   │   └── endgames.json                  # 10 endgame lesson definitions
│   │
│   └── tests/
│       ├── test_all_flows.py              # ★ Core test suite (38 tests) — RUN AFTER ANY BACKEND CHANGE
│       ├── test_rating_aware_feedback.py  # Rating-aware feedback tests (19 tests)
│       └── ... (150+ test files)
│
├── frontend/
│   ├── src/
│   │   ├── App.js                         # Router, all routes defined here
│   │   ├── pages/
│   │   │   ├── Landing.jsx                # Landing page (unauthenticated)
│   │   │   ├── HomePage.jsx               # ★ Main dashboard after login (/home)
│   │   │   ├── CoachHome.jsx              # Coaching-focused dashboard (not routed, imported but unused)
│   │   │   ├── CoachPlay.jsx              # ★ Play with Coach orchestrator (/play-with-coach)
│   │   │   ├── Dashboard.jsx              # ★ Lab page (/lab) — Coach's Pick with decay model
│   │   │   ├── PatternTraining.jsx        # ★ Pattern-specific puzzle training (/training/pattern/:pattern)
│   │   │   ├── Reflect.jsx                # Game reflection (/reflect)
│   │   │   ├── GameAnalysis.jsx           # Single game analysis (/game/:gameId)
│   │   │   ├── Progress.jsx               # Progress tracking
│   │   │   ├── OpeningsOverview.jsx        # Openings page
│   │   │   ├── PrescribedTraining.jsx     # Coached puzzles
│   │   │   ├── Training.jsx / TrainingNew.jsx / ThinkingTraining.jsx
│   │   │   └── ... (30+ page files)
│   │   │
│   │   ├── components/
│   │   │   ├── coach/
│   │   │   │   ├── CoachPlaySidebar.jsx   # ★ Main coaching sidebar (1163 lines)
│   │   │   │   ├── CoachPlayBoard.jsx     # Chessboard wrapper
│   │   │   │   ├── CoachPlaySetup.jsx     # Game setup (color, time control)
│   │   │   │   ├── LessonPicker.jsx       # Trap/Endgame lesson browser
│   │   │   │   ├── EscapeSquaresQuiz.jsx  # Escape squares interactive quiz
│   │   │   │   └── TrainingDashboard.jsx
│   │   │   ├── ui/                        # Shadcn/UI components
│   │   │   ├── Layout.jsx                 # App layout with nav
│   │   │   └── ...
│   │   │
│   │   ├── hooks/
│   │   │   ├── useTeachingMode.js         # ★ Teaching mode state (traps, endgames, lesson transitions)
│   │   │   ├── useGuardian.js             # Pre-move guardian ("Are you sure?")
│   │   │   ├── usePlayerData.js           # Player data fetching
│   │   │   └── useCoachSession.js / useCoachGame.js
│   │   │
│   │   └── context/
│   │       └── ThemeContext.jsx            # Dark/light theme
│   │
│   └── package.json
```

---

## Key Features & How They Work

### 1. Play with Coach (`/play-with-coach`)

**Flow:** User picks color → Starts game → Plays against Stockfish at adjusted strength → Gets real-time coaching feedback after each move → Game ends → Auto-analysis runs.

**Backend pipeline:**
1. `POST /api/coach/play/start` → Creates `CoachGameSession`, initializes board
2. `POST /api/coach/play/move` → User makes a move, Stockfish evaluates, coach responds
3. Background: `generate_move_feedback()` in `realtime_coaching_feedback.py` → Classifies move quality using **rating-aware thresholds** → Generates coaching message
4. `GET /api/coach/play/move-feedback/{session_id}` → Frontend polls for coach response
5. On game end: Auto-triggers `analyze_postgame()` to attach review data to profile immediately

**Rating-Aware Feedback (★ KEY DIFFERENTIATOR):**
```
800 player:  -120cp loss → "inaccuracy" → "Nf3 is fine for now. Let's keep going!" (suppressed)
1600 player: -120cp loss → "mistake"    → "Hmm, Nf3 is okay but Nd5 was better here."
1900 player: -120cp loss → "blunder"    → Socratic: "Wait, what did you see here?"
```

Thresholds in `_classify_move_quality()`:
| Rating | Inaccuracy | Mistake | Blunder |
|--------|-----------|---------|---------|
| <1000  | -150cp    | -300cp  | -300cp+ |
| 1000-1399 | -75cp  | -200cp  | -200cp+ |
| 1400-1799 | -50cp  | -150cp  | -150cp+ |
| 1800+  | -30cp     | -100cp  | -100cp+ |

### 2. Teaching Modes (Traps & Endgames)

**Generic Teaching Engine** (`services/teaching_engine.py`):
- Dispatches lesson events regardless of lesson type
- `POST /api/coach/play/teaching/start` → Loads lesson JSON, sets initial FEN
- `POST /api/coach/play/teaching/move` → Validates user's move against expected moves
- `POST /api/coach/play/teaching/exit` → Returns to regular game
- `GET /api/coach/play/teaching/catalog` → Returns 18 traps + 10 endgames

**Frontend:** `LessonPicker.jsx` renders in sidebar, `useTeachingMode.js` manages state transitions.

### 3. Escape Squares Quiz

During tactical moments (check, restricted king, back-rank threat), the coach prompts:
"How many escape squares does the opponent's king have?"

- `POST /api/coach/play/escape-squares/check` → Backend detects if it's a teaching moment
- `POST /api/coach/play/escape-squares/answer` → Validates answer, gives detailed feedback
- Frontend: `EscapeSquaresQuiz.jsx` renders in coaching sidebar

### 4. Pattern Decay Model (★ KEY DIFFERENTIATOR)

Instead of raw mistake counts ("you made this mistake 102 times"), uses exponential decay:

```python
DECAY_RATE = 0.85    # Each game back multiplies by this
RECOVERY_CREDIT = 0.3 # Each consecutive clean game subtracts this

# States:
# ACTIVE:   score > 2, clean streak < 2  → "X times recently. Let's fix it."
# DECLINING: score 1-2, streak >= 3       → "Was a problem, but clean for Y games."
# FADING:   score < 1                     → Don't prioritize anymore.
```

Lives in `services/pattern_decay_service.py`. Used by `GET /api/lab-coach-pick` (Lab page).

### 5. Community Puzzle System

**Auto-extraction pipeline** (`services/puzzle_extraction_service.py`):
1. When a game is analyzed, blunder positions are auto-extracted as puzzles
2. Tagged with cognitive gap (piece_safety, calculation_depth, tactical_oversight, etc.)
3. Rating-aware extraction: 800 player → only 200cp+ blunders extracted, 1800+ → 75cp+ included
4. Stored in `community_puzzles` collection
5. Auto-backfill triggers on first visit to pattern training page

**Training flow:**
- `GET /api/training/pattern-puzzles/{pattern}` → Returns user's own puzzles first, then community puzzles
- `POST /api/training/puzzle-attempt` → Records solve attempt
- Solved puzzles never shown again (`puzzle_attempts` collection)
- Frontend: `PatternTraining.jsx` at `/training/pattern/:pattern`

### 6. Dashboard Intelligence

**HomePage** (`/home`):
- Fetches from `GET /api/home/dashboard-v2` (main dashboard data) + `GET /api/coach/home-intelligence` (coaching intel)
- Shows: Coach message, last game with board preview, Chess DNA, patterns, action grid
- **Win streak banner**: If 3+ consecutive wins, shows positive momentum banner
- **Progress trend**: "2 fewer blunders than last week" / "Steady progress"
- **Mood suppression**: When on a streak, negative pattern alerts are hidden

**Lab page** (`/lab`, rendered by `Dashboard.jsx`):
- Coach's Pick: Best unreviewed game to study, selected by decay model
- "Practice [pattern] puzzles" button → links to `/training/pattern/{pattern}`
- Game list with cognitive gaps, results, review status

### 7. Game Import & Analysis

**Import pipeline** (`journey_service.py`):
1. User connects Chess.com / Lichess username
2. `GET /api/journey/sync` → Fetches games via external APIs
3. Games stored in `games` collection
4. `analysis_worker.py` processes queue → Stockfish analysis → `game_analyses` collection
5. After analysis: Auto-extracts puzzles from blunders

### 8. Opening Curriculum

- `data/opening_curriculum.json` — Structured opening trees
- `services/opening_curriculum_engine.py` — Progression tracking
- During Play with Coach: Detects opening being played, provides move-by-move teaching
- Separate pages: Opening overview, individual opening lessons, quizzes

---

## MongoDB Collections (test_database)

| Collection | Docs | Purpose |
|-----------|------|---------|
| `users` | 2 | User accounts (user_id, email, rating, chess_com_username) |
| `games` | 69 | Imported games (game_id, pgn, platform, user_color, is_analyzed) |
| `game_analyses` | 38 | Stockfish analysis (move_evaluations with cp_loss, best_move, cognitive_gap) |
| `coach_sessions` | 78 | Play with Coach sessions (session_id, fen_history, move_history, result) |
| `coach_messages` | 118 | Coaching messages per session |
| `coach_memory` | 2 | Persistent coach memory (weaknesses, strengths, patterns per user) |
| `community_puzzles` | 161 | Extracted training puzzles (fen, best_move_san, issue_type, difficulty) |
| `puzzle_attempts` | 4 | User puzzle solve tracking (user_id, puzzle_id, correct) |
| `postgame_analyses` | 29 | Coach play postgame analysis |
| `player_profiles` | 2 | Player statistics (accuracy, blunders, mistakes per game) |
| `player_identities` | 2 | Player style profile (style_profile, blunder_taxonomy) |
| `analysis_queue` | 32 | Stockfish analysis job queue |
| `behavioral_missions` | 2 | Coaching missions (focus patterns, goals) |
| `notifications` | 15 | User notifications |
| `thinking_scores` | 31 | Habit scores per game |
| `community_training_positions` | 42 | Community training positions |

---

## Key API Endpoints

### Authentication
```
GET  /api/auth/dev-login          # Dev mode login (sets cookie)
POST /api/auth/login              # Email/password login
POST /api/auth/register           # Register new user
GET  /api/auth/google             # Google OAuth redirect
```

### Play with Coach
```
POST /api/coach/play/start                    # Start new game
POST /api/coach/play/move                     # Make a move
GET  /api/coach/play/move-feedback/{id}       # Poll for coach response
GET  /api/coach/play/session/{id}             # Get session state
POST /api/coach/play/teaching/start           # Start trap/endgame lesson
POST /api/coach/play/teaching/move            # Make move in lesson
POST /api/coach/play/teaching/exit            # Exit lesson
GET  /api/coach/play/teaching/catalog         # Get all lessons (18 traps, 10 endgames)
POST /api/coach/play/escape-squares/check     # Check for escape squares quiz moment
POST /api/coach/play/escape-squares/answer    # Validate quiz answer
```

### Dashboard & Intelligence
```
GET  /api/home/dashboard-v2                   # Main dashboard data
GET  /api/coach/home-intelligence             # Win streak, mood override, progress trend
GET  /api/lab-coach-pick                      # Lab page with decay-model Coach's Pick
POST /api/lab-mark-reviewed/{game_id}         # Mark game as reviewed
```

### Training & Puzzles
```
GET  /api/training/pattern-puzzles/{pattern}  # Pattern-specific puzzles (auto-backfills)
POST /api/training/extract-puzzles            # Manual backfill trigger
POST /api/training/puzzle-attempt             # Record puzzle solve
GET  /api/training/prescribed                 # Prescribed training plan
```

### Game Import
```
POST /api/journey/connect                     # Connect Chess.com/Lichess
GET  /api/journey/sync                        # Sync games
GET  /api/journey/stats                       # Journey statistics
```

---

## Frontend Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/` | Landing.jsx | Landing page |
| `/home` | HomePage.jsx | Main dashboard (win streak, progress trend, coach message) |
| `/play-with-coach` | CoachPlay.jsx | Interactive coaching board |
| `/lab` | Dashboard.jsx | Lab page with Coach's Pick |
| `/game/:gameId` | GameAnalysis.jsx | Single game analysis |
| `/training/pattern/:pattern` | PatternTraining.jsx | Pattern-specific puzzle training |
| `/training/prescribed` | PrescribedTraining.jsx | Prescribed training |
| `/training` | ThinkingTraining.jsx | Thinking training |
| `/reflect` | Reflect.jsx | Game reflection |
| `/openings` | OpeningsOverview.jsx | Opening overview |
| `/openings/:openingKey` | OpeningLesson.jsx | Individual opening lesson |
| `/progress` | Progress.jsx | Progress tracking |
| `/journey` | JourneyIntelligence.jsx | Journey page |
| `/import` | ImportGames.jsx | Import games |
| `/settings` | Settings.jsx | User settings |
| `/endgames/:categoryKey/:lessonKey` | EndgameLesson.jsx | Endgame lessons |

---

## Testing

### Backend Tests
```bash
cd /app/backend
python3 tests/test_all_flows.py          # Core suite: 38 tests (RUN AFTER EVERY CHANGE)
python3 -m pytest tests/test_rating_aware_feedback.py  # Rating-aware: 19 tests
```

### Test Credentials
- Dev mode: `DEV_MODE=true` in backend/.env
- Dev user: `dev_user_local` (auto-authenticated via cookie `dev_mode=true`)
- Real user: `user_1e2b7b2777bc` (has 62 games, 31 analyzed)

### API Testing
```bash
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
curl -s "$API_URL/api/lab-coach-pick" -b "dev_mode=true" | python3 -m json.tool
```

---

## Rating Band System (★ Critical Architecture)

Defined in `deterministic_coach_service.py`:

```python
RATING_BANDS = {
    "beginner_low": {"min": 0, "max": 999, ...},
    "beginner_high": {"min": 1000, "max": 1399, ...},
    "intermediate": {"min": 1400, "max": 1799, ...},
    "advanced": {"min": 1800, "max": 9999, ...},
}
```

Used in:
- **realtime_coaching_feedback.py** — Move classification thresholds, message style
- **puzzle_extraction_service.py** — Minimum cp_loss for extraction
- **deterministic_coach_service.py** — Training plans, coaching intensity
- **reflect.py** — Review prioritization
- **adaptive_profile_engine.py** — Adaptive profiling
- **awareness_gap_rules.py** — Gap detection
- **mission_generation_service.py** — Mission difficulty

---

## Cognitive Gap Types

These are the weakness patterns tracked throughout the system:

| Gap | Description | Typical Rating |
|-----|-------------|---------------|
| `piece_safety` | Hanging pieces, unprotected material | 600-1200 |
| `missed_tactic` | Missing forks, pins, skewers | 800-1400 |
| `tactical_oversight` | Seeing 1 move ahead but missing 2nd | 1000-1600 |
| `calculation_depth` | Shallow calculation, missing deeper lines | 1200-1800 |
| `king_safety` | Weak king position, ignoring threats | 800-1600 |
| `pawn_structure` | Weak pawns, bad pawn breaks | 1400-1800 |
| `piece_activity` | Passive pieces, poor piece coordination | 1400-1800 |
| `time_pressure` | Blunders in time trouble | All ratings |
| `opening_knowledge` | Deviating from theory early | 800-1400 |
| `endgame_technique` | Poor endgame conversion | 1200+ |

---

## Hook Architecture (Frontend)

### useTeachingMode.js
Manages trap/endgame lesson state inside Play with Coach. Handles:
- `handleStartLesson(lessonType, lessonKey)` — Starts a lesson
- `handleTeachingMove(move)` — Validates moves in lesson
- `handleExitLesson()` — Returns to regular game
- Consumes backend response: `correct`, `complete`, `teaching_fen`, `auto_played_moves`

### useGuardian.js
Pre-move safety check. When enabled, asks "Are you sure?" before risky moves.

### usePlayerData.js
Fetches and caches player profile data for the coaching sidebar.

---

## LLM Integration

Uses OpenAI GPT-4o-mini via Emergent LLM Key. The key is in `EMERGENT_LLM_KEY` env var.

```python
# In llm_service.py
from emergentintegrations.llm.chat import chat_completion, ChatMessage, ChatRole

response = await chat_completion(
    api_key=os.environ.get("EMERGENT_LLM_KEY"),
    model="gpt-4o-mini",
    messages=[ChatMessage(role=ChatRole.USER, content=prompt)],
)
```

Used for: Game decryption narratives, coaching messages, opening explanations.

---

## Stockfish Integration

Binary at `/usr/games/stockfish`. Wrapped by `stockfish_service.py`.

Used for:
- Move evaluation during Play with Coach
- Game analysis (analysis_worker.py processes queue)
- Position assessment

---

## Known Issues / Things to Watch

1. **CoachHome.jsx** is imported in App.js but NOT routed. Contains good coaching intelligence UI (state-based REFLECT→TRAIN→PLAY flow). HomePage.jsx is the actual `/home` page.

2. **Game import** depends on Chess.com / Lichess API availability. Games sync in background.

3. **LLM calls** can fail silently — many services have try/except around LLM calls with fallback to deterministic responses.

4. **Puzzle extraction auto-backfill** triggers on first visit to pattern training page. If a user has many games, this can take a few seconds.

5. **The `_id` field** from MongoDB is not JSON serializable. Every response returning MongoDB data must exclude `_id` in projections or convert to string.

---

## Prioritized Backlog

### P2
- Puzzle solve rate feeding back into decay model as recovery credit
- Difficulty progression (easier puzzles first, scaling up)
- Rating-aware puzzle matching

### Future
- Add "Tactics" pluggable lesson mode to teaching_engine.py
- Add "Short Wins" pluggable lesson mode
- Deeper opening variation trees
- Daily puzzle streak / challenge system
- Streak leaderboard

---

## How to Run

```bash
# Backend (runs on port 8001 via supervisor)
sudo supervisorctl restart backend

# Frontend (runs on port 3000 via supervisor)
sudo supervisorctl restart frontend

# Check logs
tail -f /var/log/supervisor/backend.err.log
tail -f /var/log/supervisor/frontend.out.log

# Run tests
cd /app/backend && python3 tests/test_all_flows.py
```

---

*Last updated: April 3, 2026*
