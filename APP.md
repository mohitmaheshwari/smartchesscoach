# ChessGuru - Application Documentation

**Generated:** March 2, 2026  
**Status:** Accurate code-level documentation of what EXISTS

---

## Table of Contents
1. [Application Overview](#application-overview)
2. [Tech Stack](#tech-stack)
3. [Database Collections](#database-collections)
4. [UI Pages & Routes](#ui-pages--routes)
5. [Rating-Based Features](#rating-based-features)
6. [Play With Coach Flow](#play-with-coach-flow)
7. [Game Analysis Flow](#game-analysis-flow)
8. [Training System](#training-system)
9. [Personalization System](#personalization-system)
10. [What's Actually Persisted](#whats-actually-persisted)
11. [API Endpoints Reference](#api-endpoints-reference)

---

## Application Overview

ChessGuru is a chess coaching application that:
- Imports games from Lichess/Chess.com
- Analyzes games with Stockfish
- Provides AI-powered coaching feedback
- Offers a "Play with Coach" mode with live guidance
- Tracks cognitive patterns and weaknesses

### Core Differentiators (Intended)
- Personal pattern recognition from game history
- Socratic coaching (asks "why" before telling)
- Behavioral analysis (not just move quality)

### Reality Check
- Pattern recognition code EXISTS but has NO DATA (0 games in DB)
- Personalization is CODE COMPLETE but FUNCTIONALLY INACTIVE
- LLM coaching works but is currently GENERIC (no personal context)

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + TailwindCSS + Shadcn/UI |
| Backend | FastAPI (Python 3.11) |
| Database | MongoDB |
| Chess Engine | Stockfish (local binary at `/usr/games/stockfish`) |
| LLM | GPT-4o-mini via Emergent LLM Key |
| Chess UI | react-chessboard + chess.js |
| Opening Data | Lichess Opening Explorer API |

### Ports
- Frontend: 3000
- Backend: 8001 (proxied via `/api`)

---

## Database Collections

| Collection | Status | Purpose |
|------------|--------|---------|
| `users` | ACTIVE | User accounts (Google OAuth / Demo) |
| `user_sessions` | ACTIVE | Auth sessions |
| `games` | EMPTY | Imported game metadata |
| `game_analyses` | EMPTY | Stockfish analysis results |
| `coach_sessions` | EMPTY | Play-with-coach game sessions |
| `player_profiles` | EMPTY | Training profiles |
| `player_identity` | EMPTY | Cognitive identity (The Calculator, etc.) |
| `reflection_results` | EMPTY | User reflection submissions |
| `behavioral_reports` | EMPTY | Behavioral analysis per game |
| `mistake_patterns` | EMPTY | Recurring mistake patterns |
| `mission_history` | EMPTY | Completed training missions |
| `puzzle_attempts` | EMPTY | Puzzle solving history |
| `notifications` | EMPTY | User notifications |

### Collections with Data
| Collection | Count | Content |
|------------|-------|---------|
| `mistake_cards` | 2 | Sample mistake data |
| `user_habit_progress` | 1 | Habit tracking |

---

## UI Pages & Routes

### Public Routes
| Route | Page | Component |
|-------|------|-----------|
| `/` | Landing | `Landing.jsx` |

### Protected Routes (Require Auth)
| Route | Page | Component | Description |
|-------|------|-----------|-------------|
| `/onboarding` | Onboarding | `Onboarding.jsx` | Rating selection, platform linking |
| `/home` | Coach Home | `CoachHome.jsx` | Main dashboard after login |
| `/dashboard` | Dashboard | `Dashboard.jsx` | Game list + stats |
| `/lab` | Lab | `Dashboard.jsx` | Alias to dashboard |
| `/game/:gameId` | Game Analysis | `Lab.jsx` | Deep game analysis view |
| `/lab/game/:gameId` | Lab Analysis | `Lab.jsx` | Same as above |
| `/import` | Import Games | `ImportGames.jsx` | Lichess/Chess.com import |
| `/training` | Training | `Training.jsx` | Training hub |
| `/coach` | Coach | `Training.jsx` | Alias to training |
| `/focus` | Focus | `Training.jsx` | Alias to training |
| `/play-with-coach` | Play with Coach | `CoachPlay.jsx` | Interactive coach game |
| `/journey` | Journey | `Journey.jsx` | Progress overview |
| `/progress` | Progress | `JourneyIntelligence.jsx` | Intelligence view |
| `/reflect` | Reflect | `Reflect.jsx` | Review mistakes |
| `/mission/:missionId` | Mission Runner | `MissionRunner.jsx` | Training missions |
| `/settings` | Settings | `Settings.jsx` | User settings |
| `/challenge` | Challenge | `Challenge.jsx` | Puzzle challenges |
| `/recover/:gameId` | Post-Loss | `PostLossRecovery.jsx` | Loss recovery flow |
| `/weaknesses` | Weaknesses | `WeaknessTracker.jsx` | Weakness tracking |

---

## Rating-Based Features

### Onboarding Rating Selection
User selects rating in onboarding. Stored in `users.rating`.

### Stockfish Opponent Difficulty
**File:** `backend/coach_play/coach_opponent.py`

```python
# rating_to_skill_level() mapping
< 800   → Skill 0  (~800 Elo)
800-999 → Skill 3
1000-1199 → Skill 5  (~1200 Elo)
1200-1399 → Skill 8
1400-1599 → Skill 10 (~1600 Elo)
1600-1799 → Skill 12
1800-1999 → Skill 15 (~2000 Elo)
2000-2199 → Skill 17
≥2200     → Skill 20 (Full strength)
```

### Coaching Trigger Thresholds
**File:** `backend/coach_play/coaching_triggers.py`

| Rating Range | Blunder | Mistake | Inaccuracy |
|--------------|---------|---------|------------|
| 0-1200 | ≥3.0 pawns | ≥2.0 | ≥1.5 |
| 1200-1400 | ≥2.5 | ≥1.5 | ≥1.0 |
| 1400-1600 | ≥2.0 | ≥1.2 | ≥0.8 |
| 1600-1800 | ≥1.5 | ≥1.0 | ≥0.5 |
| 1800-2000 | ≥1.2 | ≥0.8 | ≥0.4 |
| 2000-2200 | ≥1.0 | ≥0.6 | ≥0.3 |
| 2200+ | ≥0.8 | ≥0.5 | ≥0.25 |

**What this means:**
- Lower-rated players: Coach only speaks on BIG mistakes (3+ pawn loss)
- Higher-rated players: Coach speaks on subtle inaccuracies (0.25 pawn loss)

---

## Play With Coach Flow

### Entry Point
Route: `/play-with-coach`  
Component: `CoachPlay.jsx`

### Session Lifecycle

1. **Start Session** (`POST /api/coach/play/start`)
   ```json
   Input: { "user_color": "white", "user_rating": 1200 }
   Output: { "session_id": "uuid", "initial_fen": "...", "stockfish_skill": 8 }
   ```
   - Creates `coach_sessions` document
   - Initializes Stockfish at user's skill level

2. **Make Move** (`POST /api/coach/play/move`)
   ```json
   Input: { "session_id": "...", "move": "e4" }
   Output: {
     "success": true,
     "fen_after": "...",
     "coach_move": "e5",
     "coach_move_pending": true,
     "evaluation": 0.3,
     "coach_message": "Good opening move!"
   }
   ```
   - Validates move legality
   - Triggers coaching evaluation
   - Coach responds asynchronously

3. **Chat with Coach** (`POST /api/coach/play/chat`)
   ```json
   Input: { "session_id": "...", "message": "Was my last move good?" }
   Output: {
     "response": "Your move was solid. Better was Nf3...",
     "suggestion_arrow": "g1f3",
     "move_quality": "good",
     "pattern_match": { "matched": false }
   }
   ```
   - LLM generates personalized response
   - Returns suggestion arrow for UI

4. **Get State** (`GET /api/coach/play/state/{session_id}`)
   - Polls for coach move completion
   - Returns current position + messages

5. **End Session** (`POST /api/coach/play/end`)
   - Computes CPR score
   - Updates player identity
   - Stores session summary

### UI Components in CoachPlay.jsx

| Component | Purpose |
|-----------|---------|
| Chessboard | Interactive board with move validation |
| Chat Sidebar | Coach messages + user input |
| Evaluation Bar | Real-time position evaluation (-10 to +10) |
| Move History | PGN-style move list |
| Suggestion Arrow | Green arrow showing best move |
| Pre-Move Guardian | Warning before bad moves |

### Pre-Move Guardian
**File:** `backend/coach_play/pre_move_guardian.py`

Checks user's intended move BEFORE execution:
- Blunder detection (>2 pawns loss)
- Hanging piece detection
- Threat blindness check

Returns warning modal if issues found.

---

## Game Analysis Flow

### Import Flow
1. User goes to `/import`
2. Enters Lichess/Chess.com username
3. Backend fetches games via platform APIs
4. Games stored in `games` collection

### Analysis Flow
1. User clicks "Analyze" on a game
2. `POST /api/analyze-game` queues analysis
3. Background worker runs Stockfish:
   - Depth 18-20 analysis
   - Move-by-move evaluation
   - Best move calculation
4. Results stored in `game_analyses`

### Lab View (`/lab/game/:gameId`)
**Component:** `Lab.jsx` (128KB - largest component)

Features:
- Move-by-move navigation
- Stockfish evaluation graph
- Mistake highlighting
- LLM explanations for blunders
- Opening name detection

---

## Training System

### Training Hub (`/training`)
**Component:** `Training.jsx`

Tabs:
1. **Focus Items** - Priority weaknesses
2. **Drills** - Practice positions
3. **Openings** - Opening trainer
4. **Puzzles** - Tactical puzzles

### Training Profile
**API:** `GET /api/training/profile`

Returns:
- Primary weakness
- Secondary weaknesses
- Recommended drills
- Phase-specific issues (opening/middlegame/endgame)

### Missions System
**API:** `GET /api/missions/today`

Daily training missions based on:
- Recent game analysis
- Identified weaknesses
- User's rating level

---

## Personalization System

### What EXISTS (Code)

#### 1. Pattern Indexer (`pattern_indexer.py`)
```python
# Indexes mistakes by CognitiveGap type
class PatternIndexer:
    async def build_index()      # Scans game_analyses
    async def find_similar_pattern()  # Returns exact game_id
    def detect_current_motif()   # Detects MISSED_FORK, etc.

# Cross-game analysis
class CrossGamePatternIndex:
    async def get_pattern_context_for_coaching()
    # Returns: frequency, trend, similar_game, injection_context
```

**CognitiveGap Types:**
- `MISSED_FORK`
- `KING_SAFETY_NEGLECT`
- `THREAT_BLINDNESS`
- `HANGING_PIECE_BLINDNESS`
- `BACK_RANK_BLINDNESS`
- `MISSED_PIN`
- `TACTICAL_OVERSIGHT`

#### 2. CPR Engine (`cpr_engine.py`)
```python
# Cognitive Performance Rating (0-100)
# Components:
# - Decision Quality (30%)
# - Threat Awareness (25%)
# - Emotional Control (20%)
# - Time Management (15%)
# - Focus Consistency (10%)

def compute_cpr(behavior_events, session_stats) -> CPRResult
```

#### 3. Identity Engine (`identity_engine.py`)
```python
# Player identity based on behavior patterns
# Traits: Aggression, Calculation, Consistency, Resilience, Risk Tolerance

# Labels:
# - "The Calculator" - Analytical, tactical, steady
# - "The Warrior" - Aggressive, intuitive, resilient
# - "The Strategist" - Positional, analytical, steady
# - "The Fortress" - Defensive, consistent
# - "The Phoenix" - Resilient learner
# - "The Improviser" - Intuitive, adaptive
```

#### 4. Personalized Coach (`personalized_coach.py`)
```python
async def get_personalized_coaching():
    # Returns:
    # - personal_context (similar mistakes, tendencies)
    # - position_plan (strategic guidance)
    # - pattern_match (deterministic retrieval result)
```

### What's MISSING (Data)

| Feature | Code Status | Data Status |
|---------|-------------|-------------|
| Pattern matching | ✅ Complete | ❌ No games to match |
| CPR scoring | ✅ Complete | ❌ No sessions scored |
| Identity building | ✅ Complete | ❌ No identity built |
| Personal context | ✅ Complete | ❌ Always returns {} |

**Result:** LLM gets empty `personal_context`, generates GENERIC responses.

---

## What's Actually Persisted

### After User Login
```javascript
// users collection
{
  user_id: "uuid",
  email: "...",
  name: "...",
  lichess_username: "...",  // if linked
  chesscom_username: "...", // if linked
  rating: 1200,
  created_at: "2026-03-02T..."
}
```

### After Game Import
```javascript
// games collection
{
  game_id: "lichess_xxx",
  user_id: "...",
  platform: "lichess",
  pgn: "1.e4 e5...",
  result: "1-0",
  opponent: "username",
  time_control: "600",
  imported_at: "..."
}
```

### After Game Analysis
```javascript
// game_analyses collection
{
  game_id: "...",
  user_id: "...",
  stockfish_analysis: {
    average_centipawn_loss: 45,
    accuracy: 87.5,
    move_evaluations: [
      {
        move_number: 1,
        move: "e4",
        evaluation: "good",
        eval_before: 0.0,
        eval_after: 0.3,
        best_move: "e4",
        cp_loss: 0
      }
    ]
  },
  cognitive_gaps: ["missed_fork", "threat_blindness"],
  analyzed_at: "..."
}
```

### After Play-with-Coach Session
```javascript
// coach_sessions collection
{
  session_id: "uuid",
  user_id: "...",
  user_color: "white",
  user_rating: 1200,
  current_fen: "...",
  move_history: [
    { move: "e4", by: "player", fen_before: "...", fen_after: "..." },
    { move: "e5", by: "coach" }
  ],
  behavior_events: [
    { behavior_type: "impulse_move", severity: "medium", move_number: 5 }
  ],
  messages: [
    { role: "coach", content: "Welcome! Let's play." }
  ],
  status: "active",
  created_at: "..."
}

// player_identity collection (after session ends)
{
  user_id: "...",
  identity_label: "The Calculator",
  trait_snapshot: {
    aggression: -15,
    calculation: 45,
    consistency: 30,
    resilience: 20,
    risk_tolerance: -10
  },
  sessions_analyzed: 1,
  last_updated: "..."
}
```

---

## API Endpoints Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/google/login` | Start Google OAuth |
| GET | `/api/auth/google/callback` | OAuth callback |
| GET | `/api/auth/dev-login` | Dev mode login |
| POST | `/api/auth/demo-login` | Demo account login |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/logout` | Logout |

### Games
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/import-games` | Import from platform |
| GET | `/api/games` | List user's games |
| GET | `/api/games/analyzed` | List analyzed games |
| GET | `/api/games/{game_id}` | Get game details |
| POST | `/api/analyze-game` | Queue analysis |
| GET | `/api/analysis/{game_id}` | Get analysis results |

### Play with Coach
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/coach/play/start` | Start session |
| POST | `/api/coach/play/move` | Make a move |
| POST | `/api/coach/play/chat` | Chat with coach |
| GET | `/api/coach/play/state/{session_id}` | Get session state |
| POST | `/api/coach/play/end` | End session |
| GET | `/api/coach/play/active` | Get active session |
| GET | `/api/coach/play/history` | Get session history |
| GET | `/api/coach/play/identity` | Get player identity |
| GET | `/api/coach/play/cpr/history` | Get CPR history |

### Training
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/training/profile` | Get training profile |
| GET | `/api/training/drills` | Get recommended drills |
| GET | `/api/missions/today` | Get daily missions |
| POST | `/api/missions/{id}/start` | Start mission |
| POST | `/api/missions/{id}/complete` | Complete mission |

### Journey/Progress
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/journey` | Get journey overview |
| GET | `/api/journey/comprehensive` | Full journey data |
| GET | `/api/cognitive/journey` | Cognitive progress |
| GET | `/api/cognitive/patterns` | Pattern analysis |
| GET | `/api/cognitive/weaknesses` | Weakness list |

---

## Current State Summary

### What WORKS
1. ✅ User authentication (Google OAuth + Demo)
2. ✅ Game import from Lichess/Chess.com
3. ✅ Stockfish analysis (when triggered)
4. ✅ Play with Coach - basic flow
5. ✅ LLM chat responses (generic)
6. ✅ Evaluation bar display
7. ✅ Pre-move guardian warnings

### What's CODE COMPLETE but INACTIVE
1. 🟡 Pattern indexer (no data to index)
2. 🟡 CPR scoring (no sessions to score)
3. 🟡 Identity engine (no identity built)
4. 🟡 Personal context in LLM (always empty)
5. 🟡 Cross-game trend analysis (no games)

### What's MISSING
1. ❌ Real user game data
2. ❌ Analyzed games in database
3. ❌ Behavioral reports
4. ❌ Reflection results
5. ❌ Pattern persistence

---

## To Activate Personalization

1. Import games → `games` collection
2. Analyze games → `game_analyses` collection
3. Play with coach → `coach_sessions` + `player_identity`
4. Pattern indexer reads from `game_analyses`
5. LLM receives non-empty `personal_context`
6. Responses become personalized

**The entire system is a pipeline. Without input data, nothing flows through.**
