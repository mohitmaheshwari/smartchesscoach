# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized chess coaching application. The core feature is a "Game Decryption Engine" that provides a move-by-move narrative explaining the strategic story of the game.

## Vision: "Thinking Simulator" (V5)
The system is NOT a "move explanation system" but a **"Thinking Simulator"**. It trains the user's thinking process and helps them see the board like a stronger player, focusing on future consequences rather than just the current move.

### Core Principles
1. **Coach on EVERY move** (user + opponent)
2. **Show PLANS** (transferable knowledge, not just moves)
3. **LLM = Language translator ONLY** (all chess logic from existing layers)
4. **Smart theory** (track what user has acknowledged understanding)
5. **Simple language** (1200-friendly, under 20 words)
6. **Show the future** (next 1-2 moves in the variation)
7. **SPECIFIC consequences** - Never generic "position weakens", always explain WHAT gets weak and WHY

### UX Mental Model
- **Home** = Decision (what to do next)
- **Play** = Experience (learn by doing, with pedagogical opponent)
- **Review (Lab)** = Understand (deep analysis, "Show my plan", cognitive gap)
- **Train** = Cure (community positions + own mistakes)
- **Progress** = Confidence

---

## Community Intelligence Training — NEW (March 2025)

### Concept
Every user's mistake is another user's training material. Training positions are sourced from:
1. **Your own games** — positions where you made significant mistakes
2. **Community** — positions from similar-rated players' games

### How It Works
- When a game is analyzed (V5 decryption), positions with cp_loss >= 150 are auto-extracted into `community_training_positions` collection
- Training feed serves ~40% own positions + ~60% community positions from players within ±200 rating
- Each position shows source attribution: "From a game by **Ravi**, 1180"
- After attempting, shows solve rate and community miss rate at user's level
- Pattern-level tracking: fork 3/5, pin 2/4, etc.

### Backend
- **Service**: `/app/backend/services/community_training_service.py`
  - `extract_training_positions()` — Extracts from V5 decrypted games
  - `get_training_feed()` — Mixed feed of own + community positions
  - `record_solve_attempt()` — Records attempt, returns correct/incorrect + stats
  - `get_user_pattern_stats()` — Pattern-level solve rates

### API Endpoints
- `GET /api/training/community-feed` — Get training positions (mixed feed)
- `POST /api/training/solve-attempt` — Record solve attempt
- `GET /api/training/pattern-stats` — Get user's pattern stats
- `GET /api/training/community-count` — Total positions in pool
- `POST /api/training/extract-positions/{game_id}` — Manual extraction trigger

### Data Model: `community_training_positions`
```javascript
{
  position_id: String,        // "game_id_m{move_number}"
  fen: String,
  best_move_san: String,
  best_move_uci: String,
  user_move_san: String,
  cp_loss: Number,
  pattern_type: String,       // fork, pin, hanging_piece, checkmate_pattern, positional, etc.
  difficulty: String,         // easy (500+ cp_loss), medium (200-499), hard (<200)
  source_game_id: String,
  source_user_id: String,
  source_user_name: String,   // First name only
  source_user_rating: Number,
  user_color: String,
  attempts: Number,
  solves: Number,
  solve_rate: Number,
  created_at: String,
}
```

### Frontend: `ThinkingTraining.jsx`
- Interactive LichessBoard (Chessground)
- "Find the Best Move" prompt with pattern/difficulty badges
- Source attribution: "From a game by **Name**, rating"
- Correct/Incorrect feedback with community stats
- "Your Patterns" sidebar with solve rate bars
- Session progress tracking (solved X of Y)
- Auto-extraction hook in V5 decryption pipeline

---

## V5 Implementation Status: COMPLETE

### What's Been Implemented

#### 1. Shared Coaching Layer (`shared_coaching_v5.py`)
- Single source of truth for V5 coaching used by BOTH Lab and Play with Coach
- `generate_move_coaching()` - Main entry point for all V5 coaching

#### 2. Play with Coach V5 Integration
- Two-part coaching: user move feedback + coach move explanation
- Behavioral coaching (habits engine) integrated

#### 3. Player Habits Engine (`player_habits_service.py`)
- Detects behavioral patterns: impulse moves, tilt, overthinking

#### 4. Opening Theory System - CONSOLIDATED
- **24 openings, 49 variations, all 12-26 moves deep**
- Single source: `/data/coaching/opening_theory_tree.json`

#### 5. Pedagogical Opponent Engine
- Creates targeted opportunities based on user weaknesses
- Phase-based probability (0% opening, 25% middlegame, 30% endgame)

#### 6. Rich Game Summaries
- Extracts specific mistake contexts for Lab Dashboard

#### 7. "Show My Plan" Cognitive Analysis
- Stockfish evaluates user's intended line to find calculation divergence

#### 8. Dynamic Plateau Breaker
- Hidden unless 3+ consecutive losses

---

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI
- **Backend**: FastAPI, MongoDB (Motor async driver)
- **Chess**: python-chess, Stockfish
- **LLM**: GPT-4.1-mini via emergentintegrations (Emergent LLM Key)

---

## Future Enhancements (Backlog)

### P1 - High Priority
- [ ] Interactive Board in Opening Explorer (clickable chessboard to step through lines)
- [ ] Variation Selector for Lessons (choose French: Advance vs Classical)
- [ ] Pattern Memory Injection ("You've made this mistake 3 times...")
- [ ] Refactor `GameDecryptionV5.jsx` to use shared `V5CoachingCard.jsx`

### P2 - Medium Priority
- [ ] Admin UI for theory database management
- [ ] Endgame theory tree (similar structure to openings)
- [ ] Habits Trend Dashboard (show improvement over time)
- [ ] Opening Proficiency in Coach Panel
- [ ] Community position opt-in/opt-out
- [ ] "Did you find it?" stats — "73% of players at your level missed this"
- [ ] Pattern clustering — group community positions by theme

### P3 - Nice to Have
- [ ] Voice coaching mode
- [ ] Weekly learning summary emails
- [ ] Major refactoring of `CoachPlay.jsx` (3500+ lines)
- [ ] Comparative analysis with similar-rated players

---

## Testing Status
- **Community Training (March 2025)**: Backend 10/10 tests passed, Frontend 100% verified
- **Pedagogical Opponent (March 2025)**: Backend 15/15 tests passed, Frontend 100% verified
- **Opening Theory Consolidation (March 2025)**: Backend 21/21 tests passed, Frontend 100% verified

---

*Last Updated: March 2025*
