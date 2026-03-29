# Thinking Simulator — Complete Product & Technical Specification

> A hyper-personalized chess coaching platform that trains players to *think* like stronger players, not just memorize moves.

---

## 1. Product Vision

**The Problem:** Chess improvement tools (Lichess puzzles, Chess.com lessons, YouTube videos) teach *what* to play but never *how to think*. Players plateau at 1000–1400 because they lack a structured thinking process — they can't evaluate positions, form plans, or learn from their own mistakes in a personalized way.

**The Solution:** The Thinking Simulator is a coaching AI that:
1. **Coaches every single move** — not just mistakes, but explains *why* good moves are good and what the opponent's plan was
2. **Teaches plans, not moves** — every explanation includes the strategic *why*, making knowledge transferable
3. **Tracks behavioral patterns** — detects tilt, impulse moves, time management issues, and provides behavioral coaching
4. **Provides deep opening theory** — 24 openings, 49 variations, 12–26 moves deep, with interactive step-by-step lessons
5. **Adapts to the player** — remembers what concepts the player has acknowledged understanding, what mistakes recur, and adjusts coaching accordingly

**Core Design Principle:** The LLM is a *language translator only*. All chess logic (evaluation, candidate moves, plans, consequences) comes from Stockfish + deterministic rule engines. The LLM converts structured coaching data into natural, engaging prose. This ensures correctness — no hallucinated chess analysis.

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                       │
│  Landing → Onboarding → Home → Lab → Play with Coach → ...   │
│  Tailwind CSS + Shadcn/UI + react-chessboard                 │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTPS (via Kubernetes Ingress)
                       │ All routes prefixed /api
┌──────────────────────▼───────────────────────────────────────┐
│                      BACKEND (FastAPI)                        │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Routes (18) │  │ Services(50+)│  │  Coach Engine       │  │
│  │  auth, coach │  │ V5 coaching  │  │  Opening plans      │  │
│  │  games, lab  │  │ Habits engine│  │  Piece metrics      │  │
│  │  openings    │  │ Opening tree │  │  Rule validator     │  │
│  │  training    │  │ LLM narrator │  │  Teaching engine     │  │
│  │  missions    │  │ Pattern mem  │  │  Wisdom library     │  │
│  │  ...         │  │ ...          │  │  ...                │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                │                      │             │
│  ┌──────▼──────────────▼──────────────────────▼──────────┐  │
│  │                   Core Analysis Layer                    │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌────────────────┐  │  │
│  │  │ Stockfish   │  │ python-chess │  │ GPT-4o-mini    │  │  │
│  │  │ Depth 18    │  │ Board logic  │  │ (via Emergent) │  │  │
│  │  │ Multi-PV    │  │ FEN/PGN/SAN  │  │ Narrative only │  │  │
│  │  └────────────┘  └──────────────┘  └────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│                              │                                │
│  ┌───────────────────────────▼──────────────────────────────┐│
│  │                    MongoDB (Motor async)                   ││
│  │  users, games, coach_sessions, user_opening_progress,     ││
│  │  feedback, notifications, missions, streaks, ...          ││
│  └───────────────────────────────────────────────────────────┘│
│                                                               │
│  ┌───────────────────────────────────────────────────────────┐│
│  │            Static Data (JSON/Python)                       ││
│  │  opening_theory_tree.json (24 openings, 49 variations)    ││
│  │  verified_opening_traps.py (curated trap database)        ││
│  │  eco_openings.json, chess_theory.json                     ││
│  └───────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### Tech Stack
| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | React 18 + Tailwind CSS + Shadcn/UI | Single-page app, dark theme |
| Backend | FastAPI (Python 3.11) | Async throughout, Motor for MongoDB |
| Database | MongoDB | Document store, async via Motor |
| Chess Engine | Stockfish (depth 18, multi-PV) | All position evaluation |
| Chess Logic | python-chess | Board representation, move validation, FEN/PGN |
| LLM | GPT-4o-mini via `emergentintegrations` | Narrative generation only — never for chess analysis |
| Auth | Google OAuth (Emergent-managed) + session cookies | 7-day sessions |
| Hosting | Kubernetes (Emergent Cloud) | Preview + production deployments |

---

## 3. User Flow & Pages

### 3.1 Authentication & Onboarding
| Route | Page | Purpose |
|-------|------|---------|
| `/` | Landing | Marketing page, Google OAuth login |
| `/onboarding` | Onboarding | Collect chess.com/lichess username, rating, playing style preferences |

### 3.2 Core Experience (Main Navigation)
| Route | Page | Purpose |
|-------|------|---------|
| `/home` | HomePage | Dashboard hub — recent games, active missions, coaching tips, quick actions |
| `/lab` | Dashboard | Game library — browse analyzed games, trigger analysis, see stats |
| `/game/:gameId` | LabV2 | **The Lab** — deep move-by-move game analysis with V5 coaching engine |
| `/play-with-coach` | CoachPlay | **Play with Coach** — play a game against the engine with real-time coaching on every move |
| `/openings-overview` | OpeningsOverview | **Opening Theory Tree** — browse all 24 openings, variations, plans, and critical positions |
| `/openings/:openingKey` | OpeningLesson | Individual opening lesson with interactive board |
| `/training` | Training | Training hub — prescribed puzzles, drills, weakness-targeted exercises |
| `/progress` | UnifiedProgress | Progress tracking — rating trajectory, weakness trends, concept mastery |
| `/reflect` | Reflect | Post-game reflection — guided review of key moments, tagging, and self-assessment |

### 3.3 Secondary Features
| Route | Page | Purpose |
|-------|------|---------|
| `/import` | ImportGames | Import games from chess.com/lichess via username |
| `/training/prescribed` | PrescribedTraining | Weakness-targeted puzzle sets |
| `/training/quiz/:openingKey` | OpeningQuizPage | Opening knowledge quiz |
| `/mission/:missionId` | MissionRunner | Daily mission execution (positions to solve) |
| `/recover/:gameId` | PostLossRecovery | Post-loss emotional recovery + lesson extraction |
| `/plateau-breaker` | PlateauBreakerDashboard | Enforced learning mode for stuck players |
| `/weaknesses` | WeaknessTracker | Detailed weakness breakdown |
| `/settings` | Settings | Profile, linked accounts, email preferences |

---

## 4. Core Features — Deep Dive

### 4.1 The Lab (Post-Game Analysis)

**What it does:** Takes any completed game and produces a move-by-move "decryption" — explaining what happened, why, and what the player should have been thinking.

**Pipeline:**
```
PGN/Game → Stockfish Multi-PV Analysis → V5 Coaching Layer → LLM Narrative → UI
```

**V5 Coaching Layer** (`shared_coaching_v5.py`):
- `generate_move_coaching()` — Main entry point for every move
- Produces structured coaching data for each move:
  - **Eval delta** — How much the position changed
  - **Move classification** — Brilliant / Best / Good / Inaccuracy / Mistake / Blunder
  - **Candidate moves** — Top 3 alternatives from Stockfish multi-PV with eval scores
  - **Consequence description** — What this move specifically enables (e.g., "allows Nf5 fork on e7 and g7")
  - **Strategic plan** — What each side should be doing in this position
  - **Concept tag** — The underlying chess principle (e.g., "piece activity", "pawn structure", "king safety")

**LLM Narrator** (`v5_llm_narrator.py`):
- Takes the structured V5 coaching data and converts it into natural language
- Constrained prompt: "You are NOT analyzing chess. You are translating pre-computed analysis into engaging prose."
- Output validated by `chess_verification_layer.py` to ensure no hallucinated moves/evaluations

**Habits Report** (`player_habits_service.py`):
- After analysis, generates a behavioral report detecting:
  - **Impulse moves** — Moves made in < 3 seconds after opponent's move
  - **Tilt detection** — Cascading errors after a blunder (error rate increase)
  - **Overthinking** — Spending > 2 minutes on low-complexity positions
  - **Time pressure patterns** — Quality degradation in last 30 seconds
  - **Calculation depth** — Inferred from move timing patterns

**API Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/coach/decryption/v5/{game_id}` | Full V5 decryption with habits report |
| POST | `/api/coach/decryption/acknowledge` | Mark a coaching concept as "understood" |
| POST | `/api/coach/decryption/feedback` | Rate coaching quality |

---

### 4.2 Play with Coach (Live Coaching)

**What it does:** The user plays a game against Stockfish while receiving real-time coaching on every move — both their own moves and the engine's responses.

**Two-Moment Feedback Architecture:**
```
User plays move → MOMENT 1: Immediate feedback on user's move
                 ↓
Coach plays response → MOMENT 2: Explanation of coach's counter-move
```

**Phase 1 (User Move Feedback):**
- Stockfish evaluates the user's move
- V5 coaching layer generates structured analysis
- If blunder detected: **Guardian Intervention** — inline warning with undo option
- Behavioral coaching: "You spent 2s on this move. Was this calculated or reactive?"

**Phase 2 (Coach Move Explanation):**
- Coach selects a move (Stockfish-guided, difficulty-adaptive)
- V5 coaching layer explains the coach's move and its plan
- "I played Nf5 to target your weak e7 and g7 squares. This is a classic outpost maneuver."

**Opening Teaching System (JSON-driven):**
When an opening is detected during play, the system offers interactive lessons:
1. **Detection** — `detect_opening_from_moves()` identifies the opening after 2-6 moves
2. **Offer** — Shows teaching offer card with options: "Learn the {Variation}" or "Just play"
3. **Lesson** — Step-by-step guided play through 12-26 deep theory moves
   - Resumes from current board position (doesn't restart)
   - Auto-plays coach's moves, waits for user's moves
   - Critical position enrichment: explains key decisions at important junctures
   - Wrong move feedback: "Not quite! c3 is passive here because... The correct move is e5."
4. **Completion** — Updates user progress, offers to continue game or start fresh

**Coaching Panel (Right Side):**
- V5 coaching card with move classification, candidate moves, and plans
- Behavioral coaching alerts (tilt, rushing, etc.)
- Opening suggestion / lesson offer
- Clickable candidate moves that preview on the board

**API Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/coach/play/v5/interactive-feedback` | Two-phase coaching (user_move / coach_move) |
| POST | `/api/coach/play/teaching/start` | Start opening lesson |
| POST | `/api/coach/play/teaching/move` | Process teaching move |
| POST | `/api/coach/play/teaching/exit` | Exit lesson mode |
| POST | `/api/coach/play/move/confirm` | Confirm a move after Guardian intervention |
| GET | `/api/coach/play/state/{session_id}` | Get session state |
| GET | `/api/coach/play/active` | Get active session |
| POST | `/api/coach/play/end` | End session |

---

### 4.3 Opening Theory System

**Architecture:**
```
opening_theory_tree.json (Single Source of Truth)
         │
         ├── opening_theory_json_service.py (Loader + Query API)
         │
         ├── opening_teaching_integration.py (Lesson flow for Play with Coach)
         │      └── Resumes from board position, auto-plays, enriches instructions
         │
         ├── opening_mastery.py (Detection + Progress tracking)
         │      ├── detect_opening_from_moves() — Hardcoded priority detection
         │      ├── OPENING_DATABASE — Populated from JSON at startup
         │      └── get_user_opening_progress() / update_user_opening_progress()
         │
         ├── verified_opening_traps.py (Curated trap database)
         │      └── Used for trap lessons within Play with Coach
         │
         └── OpeningsOverview.jsx (Theory Tree Browser UI)
                └── Expandable cards with plans, variations, critical positions
```

**Coverage:**
| Opening | Variations | Max Depth |
|---------|-----------|-----------|
| Italian Game | Giuoco Piano, Two Knights | 15 moves |
| French Defense | Advance, Classical, Winawer, Tarrasch, Exchange | 16 moves |
| Queen's Gambit | QGD Orthodox, QGA, Slav | 18 moves |
| Sicilian Najdorf | English Attack | 24 moves |
| Ruy Lopez | Morphy Defense, Closed | 20 moves |
| King's Indian | Classical, Samisch | 16 moves |
| Grunfeld Defense | Exchange, Russian | 17 moves |
| ... +17 more | Total: 49 variations | 12–26 moves |

Each variation includes:
- Full move sequence with `python-chess` validated legality
- White plan / Black plan descriptions
- Critical positions with best moves, mistake moves, and explanations
- Common learnings (transferable principles)

---

### 4.4 Player Habits Engine

**What it does:** Analyzes behavioral patterns beyond chess quality — time management, emotional state, calculation habits.

**Detection Model** (`player_habits_service.py`):

| Pattern | Detection Method | Trigger |
|---------|-----------------|---------|
| Impulse move | Move time < 3s after opponent | Time delta analysis |
| Tilt cascade | 3+ errors in 5-move window after blunder | Error rate spike |
| Overthinking | > 120s on position with eval delta < 0.3 | Time vs complexity |
| Time trouble | Quality drops in final 30s of time control | Time pressure correlation |
| Calculation depth | Inferred from avg think time on complex positions | Position complexity vs time |
| Rushing after advantage | Speed increase when ahead | Eval + time correlation |

**Integration Points:**
- **Play with Coach** — Real-time behavioral alerts during the game
- **The Lab** — Post-game habits report appended to V5 decryption
- **Progress page** — Behavioral trend tracking over time

---

### 4.5 Training & Missions

**Training Hub** (`/training`):
- Prescribed puzzles based on detected weaknesses
- Spaced repetition system for pattern recognition
- Data-driven drill recommendations

**Daily Missions** (`/mission/:missionId`):
- Generated from the player's weakness profile
- Position-based challenges: "Find the correct plan in 3 positions where you tend to miss knight outposts"
- Completion tracking with streak system

**Plateau Breaker** (`/plateau-breaker`):
- Enforced learning mode for players stuck at a rating
- Structured review → lesson → application cycle
- Must demonstrate understanding before proceeding

---

### 4.6 Reflection System

**What it does:** Guided post-game self-assessment that builds metacognitive skills.

**Flow:**
```
Game completed → Key moments extracted → User tags each moment →
User explains their thinking → System compares with engine evaluation →
Learning points generated → Progress updated
```

**Why it matters:** Research shows that *self-assessment after performance* is the #1 factor in skill improvement. The reflection system forces players to actively engage with their decisions rather than passively consuming analysis.

---

## 5. Service Dependency Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        REQUEST FLOW                              │
│                                                                  │
│  User clicks "Analyze"                                          │
│    → routes/coach.py (decryption/v5/{game_id})                  │
│      → game_decryption_v5_service.py                            │
│        → stockfish_service.py (multi-PV analysis, depth 18)     │
│        → shared_coaching_v5.py (V5 coaching for each move)      │
│          → coach_engine/opening_plans.py (strategic plans)      │
│          → services/pawn_structure_service.py                   │
│          → services/game_phase_service.py                       │
│        → v5_llm_narrator.py (GPT-4o-mini narrative)             │
│        → player_habits_service.py (behavioral analysis)         │
│      → MongoDB: store decryption result                         │
│    ← Return full decryption with habits report                  │
│                                                                  │
│  User plays move in Coach                                        │
│    → routes/coach_play.py (v5/interactive-feedback)             │
│      → coach_play/coach_game_session.py (game state)            │
│      → shared_coaching_v5.py (evaluate user's move)             │
│      → coach_play/pre_move_guardian.py (blunder check)          │
│      → player_habits_service.py (behavioral coaching)           │
│      → opening_mastery.py (opening detection)                   │
│        → opening_teaching_integration.py (lesson offers)        │
│          → opening_theory_json_service.py (JSON theory data)    │
│      → v5_llm_narrator.py (narrative)                           │
│    ← Return phased feedback (user_move or coach_move)           │
│                                                                  │
│  User starts opening lesson                                      │
│    → routes/coach_play.py (teaching/start)                      │
│      → opening_teaching_integration.py                          │
│        → opening_theory_json_service.py (load lesson data)      │
│        → Match played moves, resume from current position       │
│        → Auto-play coach moves, wait for user moves             │
│      → MongoDB: update session teaching state                   │
│    ← Return lesson with current_move_index and teaching_fen     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Model (Key Collections)

### `users`
```json
{
  "user_id": "google_12345",
  "email": "player@example.com",
  "display_name": "ChessKnight",
  "chess_com_username": "knight1200",
  "lichess_username": null,
  "rating": 1200,
  "playing_style": "aggressive",
  "created_at": "2025-03-01T...",
  "onboarding_complete": true
}
```

### `games`
```json
{
  "game_id": "uuid-v4",
  "user_id": "google_12345",
  "platform": "chess.com",
  "pgn": "1. e4 e5 2. Nf3 ...",
  "white_username": "knight1200",
  "black_username": "opponent",
  "result": "1-0",
  "user_color": "white",
  "time_control": "600",
  "opening_name": "Italian Game",
  "analysis_status": "complete",
  "stockfish_analysis": { ... },
  "v5_decryption": { ... },
  "habits_report": { ... },
  "imported_at": "2025-03-15T..."
}
```

### `coach_sessions` (Play with Coach)
```json
{
  "session_id": "uuid-v4",
  "user_id": "google_12345",
  "user_color": "white",
  "current_fen": "rnbqkb1r/pppp1ppp/...",
  "move_history": [
    {"move": "e4", "color": "white", "time_spent": 2.1, "eval": 0.3},
    {"move": "e5", "color": "black", "time_spent": 1.5, "eval": 0.2}
  ],
  "behavior_events": [
    {"type": "impulse_move", "move_number": 12, "time_spent": 1.2}
  ],
  "detected_opening": "italian_game",
  "teaching_mode": "main_line",
  "teaching_data": {
    "variation_name": "Giuoco Piano",
    "variation_key": "giuoco_piano",
    "main_line_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", ...],
    "current_move_index": 7,
    "critical_positions": { ... },
    "user_plays_white": true,
    "teaching_fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2P2N2/PP1P1PPP/..."
  },
  "status": "active",
  "created_at": "2025-03-20T..."
}
```

### `user_opening_progress`
```json
{
  "user_id": "google_12345",
  "opening_name": "French Defense",
  "mastery_level": "learning",
  "times_practiced": 5,
  "traps_learned": ["Winawer Poisoned Pawn"],
  "variations_learned": ["Advance Variation", "Classical"],
  "last_practiced_at": "2025-03-20T..."
}
```

### `user_concept_understanding`
```json
{
  "user_id": "google_12345",
  "concept_id": "piece_activity_outpost",
  "concept_type": "strategic",
  "concept_text": "Knights are strongest on outpost squares...",
  "shown_count": 4,
  "acknowledged": true,
  "acknowledged_at": "2025-03-18T...",
  "applied_correctly_count": 2,
  "failed_to_apply_count": 1
}
```

---

## 7. External Integrations

| Service | Purpose | Integration Method |
|---------|---------|-------------------|
| **Stockfish** | All chess position evaluation | Binary executed via subprocess, UCI protocol |
| **python-chess** | Board representation, move validation, FEN/PGN parsing | Python library |
| **GPT-4o-mini** | Narrative generation (coaching prose) | Via `emergentintegrations` library (Emergent Universal Key) |
| **Chess.com API** | Game import, rating sync | REST API (public) |
| **Lichess API** | Game import, rating sync | REST API (public) |
| **Google OAuth** | Authentication | Emergent-managed OAuth flow |
| **MongoDB** | Primary data store | Motor async driver |

---

## 8. Key Design Decisions

### Why Stockfish + LLM (not pure LLM)?
LLMs hallucinate chess analysis. GPT-4o frequently suggests illegal moves and miscalculates evaluations. Our approach: Stockfish computes all analysis (evals, candidate moves, consequences), and the LLM is *only* used to convert structured data into natural language. This gives us 100% accurate analysis with engaging presentation.

### Why JSON-based opening theory (not a database)?
- **Accuracy**: Opening theory must be verified move-by-move. A JSON file with `python-chess` validation ensures every line is legal.
- **Expandability**: Adding a new opening is a JSON object, not a database migration.
- **Performance**: Loaded once at startup, cached in memory. Zero DB queries for theory data.
- **Portability**: The entire theory database is a single file that can be reviewed, versioned, and contributed to.

### Why two-moment feedback (not immediate)?
Players need time to process. Showing the coach's move explanation *simultaneously* with feedback on the user's move creates cognitive overload. The two-moment architecture (1: feedback on your move → pause → 2: explanation of coach's response) creates a dialogue rhythm that mimics a real coaching session.

### Why behavioral coaching alongside tactical?
A player who knows the right move but plays impulsively under time pressure doesn't need more tactics — they need behavioral awareness. The Habits Engine addresses the 50% of chess improvement that isn't chess knowledge: emotional regulation, time management, and calculation discipline.

---

## 9. Backend Service Inventory

### Route Modules (18)
| Module | Prefix | Endpoints | Purpose |
|--------|--------|-----------|---------|
| `auth.py` | `/auth` | 11 | Authentication, Google OAuth, session management |
| `coach.py` | `/coach` | 14 | Lab decryption, V5 coaching, concept tracking, patterns |
| `coach_play.py` | `/coach/play` | 18 | Live coaching game, teaching, Guardian, chat |
| `openings.py` | `/openings` | 14 | Opening lessons, practice, traps, corrections |
| `admin_openings.py` | `/admin/openings` | 4 | Opening theory tree API |
| `games.py` | `/games` | 7 | Game library, analysis status, reanalysis |
| `lab.py` | `/lab` | 5 | Deep game analysis, mistake context, strategy |
| `training.py` | `/training` | 14 | Spaced repetition, puzzles, habits, weekly plan |
| `missions.py` | `/missions` | 8 | Daily missions, focus mastery |
| `journey.py` | `/journey` | 10 | Progress dashboard, weakness trends, intelligence |
| `cognitive.py` | `/cognitive` | 14 | Cognitive gap analysis, TSI, focus system |
| `behavioral.py` | `/behavioral` | 9 | Behavioral analysis, missions, reanalysis |
| `reflect.py` | `/reflect` | 10 | Post-game reflection, moment tagging |
| `feedback.py` | `/feedback` | 16 | Coaching quality feedback, tag system |
| `notifications.py` | `/notifications` | 7 | Push notifications, read/dismiss |
| `settings.py` | `/settings` | 6 | Profile, email prefs, account linking |
| `streak.py` | `/streak` | 6 | Daily streak, focus types |
| `server.py` (api_router) | Various | 30+ | Import, analysis, TTS, thinking score, etc. |

### Core Services
| Service | File | Purpose |
|---------|------|---------|
| V5 Coaching | `shared_coaching_v5.py` | Heart of all coaching — generates structured move analysis |
| Game Decryption | `game_decryption_v5_service.py` | Full game analysis pipeline |
| LLM Narrator | `v5_llm_narrator.py` | Converts structured coaching into natural prose |
| Opening Theory | `opening_theory_json_service.py` | Loads and queries the JSON theory tree |
| Opening Detection | `opening_mastery.py` | Identifies openings from move sequences |
| Opening Teaching | `opening_teaching_integration.py` | Interactive lesson flow for Play with Coach |
| Player Habits | `player_habits_service.py` | Behavioral pattern detection |
| Stockfish | `stockfish_service.py` | Chess engine wrapper, multi-PV analysis |
| LLM Service | `llm_service.py` | GPT-4o-mini via emergentintegrations |
| Coach Game Session | `coach_play/coach_game_session.py` | Manages live coaching game state |
| Pre-Move Guardian | `coach_play/pre_move_guardian.py` | Blunder detection before move confirmation |
| Opening Traps | `verified_opening_traps.py` | Curated opening trap database |
| Pattern Memory | `services/pattern_memory_service.py` | Long-term pattern tracking |
| Learning Tracker | `services/v5_learning_tracker.py` | Concept understanding tracking |
| Journey Service | `journey_service.py` | Progress dashboard data, background sync |
| Rating Service | `rating_service.py` | Rating prediction, time analysis, training generation |
| Player Profile | `player_profile_service.py` | Adaptive player modeling |
| Reflect Service | `reflect_service.py` | Post-game reflection engine |
| Coach Quality Score | `cqs_service.py` | Internal quality scoring for coaching output |
| Chess Verification | `chess_verification_layer.py` | Validates LLM output against legal chess |

---

## 10. Frontend Component Architecture

### Page Components (37)
Core pages listed in Section 3 above. Each page is a standalone route component receiving the `user` object from `ProtectedRoute`.

### Shared Components
| Component | Purpose |
|-----------|---------|
| `Layout.jsx` | Sidebar navigation, responsive, dark theme |
| `V5CoachingCard.jsx` | Reusable V5 coaching display (used in Lab + Coach Play) |
| `GameDecryptionV5.jsx` | Full game decryption viewer with habits report |
| `InteractiveChessBoard.jsx` | Chess board component with move highlighting |
| `CoachBoard.jsx` | Board component for Play with Coach |
| `OpeningTeachingPanel.jsx` | Opening lesson UI in coaching panel |
| `NotificationBell.jsx` | Real-time notification component |
| `Gamification.jsx` | Streaks, badges, progress indicators |

### UI Component Library
Shadcn/UI components at `/components/ui/`: Button, Card, Badge, Input, Dialog, DropdownMenu, Tabs, Tooltip, Toast (sonner), Calendar, etc.

---

## 11. File Structure Summary

```
/app
├── frontend/
│   ├── src/
│   │   ├── App.js                    # Routes, auth, protected routes
│   │   ├── pages/                    # 37 page components
│   │   │   ├── CoachPlay.jsx         # Play with Coach (3500+ lines)
│   │   │   ├── Dashboard.jsx         # Game library + Lab entry
│   │   │   ├── OpeningsOverview.jsx  # Theory tree browser
│   │   │   ├── HomePage.jsx          # Dashboard hub
│   │   │   ├── Landing.jsx           # Marketing + login
│   │   │   └── ...
│   │   ├── components/
│   │   │   ├── Layout.jsx            # Navigation sidebar
│   │   │   ├── GameDecryptionV5.jsx  # V5 decryption viewer
│   │   │   ├── shared/
│   │   │   │   └── V5CoachingCard.jsx
│   │   │   ├── ui/                   # Shadcn components
│   │   │   └── ...
│   │   └── context/
│   │       └── ThemeContext.jsx
│   └── package.json
│
├── backend/
│   ├── server.py                     # FastAPI app, 30+ inline endpoints
│   ├── config.py                     # Centralized configuration
│   ├── routes/                       # 18 route modules
│   │   ├── coach_play.py             # Live coaching endpoints
│   │   ├── coach.py                  # Lab + decryption endpoints
│   │   ├── openings.py               # Opening system endpoints
│   │   └── ...
│   ├── services/                     # 50+ service modules
│   │   ├── shared_coaching_v5.py     # Core V5 coaching engine
│   │   ├── opening_theory_json_service.py  # JSON theory loader
│   │   ├── opening_teaching_integration.py # Lesson flow
│   │   ├── opening_mastery.py        # Detection + progress
│   │   ├── player_habits_service.py  # Behavioral analysis
│   │   ├── v5_llm_narrator.py        # LLM narrative layer
│   │   └── ...
│   ├── coach_engine/                 # Chess knowledge engine
│   │   ├── opening_plans.py          # Strategic plans per opening
│   │   ├── piece_metrics.py          # Piece activity scoring
│   │   ├── teaching_engine.py        # Teaching logic
│   │   └── ...
│   ├── coach_play/                   # Live game services
│   │   ├── coach_game_session.py     # Game session management
│   │   ├── pre_move_guardian.py      # Blunder prevention
│   │   └── ...
│   ├── data/
│   │   └── coaching/
│   │       └── opening_theory_tree.json  # 24 openings, 49 variations
│   ├── stockfish_service.py          # Engine wrapper
│   ├── llm_service.py                # LLM integration
│   └── requirements.txt
│
└── memory/
    └── PRD.md                        # Product requirements doc
```

---

## 12. What Makes This Different

| Feature | Chess.com / Lichess | Typical AI Coach | Thinking Simulator |
|---------|-------------------|-----------------|-------------------|
| Move-by-move coaching | Basic eval bar | LLM-generated (hallucination risk) | Stockfish analysis + LLM narrative (verified) |
| Opening lessons | Static video/text | Generic lines | 24 openings, 49 variations, 12-26 moves, interactive on-board |
| Behavioral coaching | None | None | Real-time tilt/impulse/time detection |
| Concept tracking | None | None | Tracks what user "understands" per concept |
| Live coaching during play | None | Post-game only | Every move, both sides, with plans |
| Lesson resume from position | N/A | N/A | Detects played moves, continues from board state |
| Blunder prevention | None | None | Guardian system warns before confirming blunder |
| Post-loss recovery | None | None | Guided emotional + tactical recovery session |

---

## 13. Current Status & Metrics

- **24 openings** with deep theory (12-26 moves per variation)
- **49 opening variations** with critical position data
- **18 route modules** with 200+ API endpoints
- **50+ backend services**
- **37 frontend pages**
- **All opening theory `python-chess` validated** (zero illegal moves)
- **Backend test suite**: 150+ test files
- **LLM usage**: Narrative only — zero chess analysis via LLM (100% Stockfish)

---

*Document generated March 2025. For questions: refer to `/app/memory/PRD.md` for product requirements and `/app/backend/DATA_MODEL.md` for extended data model documentation.*
