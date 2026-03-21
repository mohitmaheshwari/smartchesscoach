# Chess Coach AI - Comprehensive Product & Technical Documentation

> **"The first chess app that teaches you HOW to think, not just WHAT to play."**

---

## Table of Contents

1. [Vision & Mission](#vision--mission)
2. [The Problem We Solve](#the-problem-we-solve)
3. [Our Unique Approach](#our-unique-approach)
4. [Core Features](#core-features)
5. [User Journey & Flows](#user-journey--flows)
6. [Technical Architecture](#technical-architecture)
7. [AI Coaching Engine](#ai-coaching-engine)
8. [Data Models & Schema](#data-models--schema)
9. [API Reference](#api-reference)
10. [Competitive Differentiation](#competitive-differentiation)
11. [Monetization Strategy](#monetization-strategy)
12. [Roadmap](#roadmap)

---

## Vision & Mission

### Vision
To democratize access to high-quality chess coaching by building an AI that thinks and teaches like a human grandmaster coach - understanding each player's unique psychology, weaknesses, and learning patterns.

### Mission
Replace the ₹5,000-50,000/month human coach with an AI that:
- **Remembers everything** about your playing style and mistakes
- **Adapts explanations** to your exact rating level
- **Teaches thinking processes**, not just moves
- **Provides real-time coaching** during practice games
- **Creates personalized training** from your actual game mistakes

### Target Market
- **Primary**: Indian chess players (5M+ active players post-Praggnanandhaa/Gukesh era)
- **Rating Range**: 600-2000 ELO (amateur to club level)
- **Demographics**: Ages 10-35, mobile-first, price-sensitive
- **Market Size**: ₹2,000 Cr+ addressable market in India alone

---

## The Problem We Solve

### What Existing Apps Do Wrong

| Platform | What They Offer | The Problem |
|----------|----------------|-------------|
| Chess.com | Game analysis, puzzles | Shows "best move" but not WHY or HOW to find it |
| Lichess | Free analysis, studies | No personalization, no coaching context |
| Chessable | Opening courses | Passive memorization, doesn't fix thinking errors |
| Human Coach | Personalized feedback | Expensive (₹2-5k/hour), inconsistent, not scalable |

### The Real Issue
**Players repeat the same mistakes because no one teaches them the THINKING PROCESS.**

A 1200-rated player who blunders a piece doesn't need to see "Qxd4 was better." They need to learn:
1. "Before every move, ask: What is my opponent threatening?"
2. "You've made this same tactical error in 7 of your last 15 games"
3. "Here's how a stronger player would analyze this position step-by-step"

---

## Our Unique Approach

### The "Improvement Engine" Philosophy

We don't just analyze games. We build a **cognitive model** of each player and teach them to think differently.

```
Traditional App:                    Chess Coach AI:
                                    
[Game] → [Engine Analysis]          [Game] → [Cognitive Analysis]
      → "Qxd4 was best"                   → "You missed a tactic"
                                          → "This is your 8th tactical miss"
                                          → "Your pattern: You don't check threats"
                                          → "Before moving, ask: Can opponent capture?"
                                          → "Practice drill: Threat detection puzzles"
                                          → [Tracks if you improve]
```

### Three Pillars of Learning

1. **REFLECT** - Understand what went wrong and why
2. **LEARN** - Acquire the correct thinking process
3. **PRACTICE** - Apply knowledge in coached games

---

## Core Features

### 1. Game Analysis Lab (Reflect)

**Purpose**: Deep-dive into any game with AI coaching

**Five Analysis Tabs**:

| Tab | What It Shows | Unique Value |
|-----|--------------|--------------|
| **Summary** | Game story, accuracy, turning point, biggest blunder | Narrative format, not just numbers |
| **Moments** | Critical positions where game changed | Socratic questioning ("What was your plan?") |
| **Ideas** | Strategic themes with rating-adaptive explanations | "How to think here" walkthrough button |
| **Habits** | Opening fundamentals score, training rules | Checks if you followed principles |
| **Memory** | Player style, blunder history, streaks | Deep personalization data |

**Key Innovation**: The "How to Think Here" button generates a step-by-step thought process:
```
Step 1: Check for immediate threats
Step 2: Look for tactical opportunities (checks, captures, threats)
Step 3: Evaluate pawn structure
Step 4: Consider piece activity
Step 5: Form a plan based on imbalances
```

### 2. Opening Training Lab (Learn)

**Purpose**: Interactive, guided opening lessons

**User Flow**:
```
[Browse Openings] → [Select Opening] → [Guided Walkthrough]
                                              ↓
                    [Auto-play with coach narrating each move]
                                              ↓
                    [Click "Why this move?" for deeper insight]
                                              ↓
                    [Practice Mode - play against AI]
                                              ↓
                    [Trap Practice - learn common traps]
```

**Guided Lesson Features**:
- Auto-plays moves with explanations
- Coach personality ("Now watch this...", "Pay attention here...")
- Progress bar showing lesson completion
- Playback controls (pause, skip, speed)
- "Why this move?" AI-powered deeper explanations
- Key ideas reference panel

**Content Structure** (per opening):
```json
{
  "opening_key": "caro-kann",
  "opening_name": "Caro-Kann Defense",
  "description": "A solid, reliable defense...",
  "key_ideas": [
    "Develop light-squared bishop BEFORE playing e6",
    "Play for ...c5 break to challenge center"
  ],
  "main_line": [
    {"move": "e4", "explanation": "White takes the center."},
    {"move": "c6", "explanation": "The Caro-Kann! Preparing d5 with support."}
  ],
  "traps": [...],
  "common_mistakes": [...],
  "what_if": [...]
}
```

### 3. Play with Coach (Practice)

**Purpose**: Real-time coaching during practice games

**Features**:
- Play against Stockfish (adjustable levels 1-20)
- **Pre-Move Checklist**: Contextual reminders based on YOUR weaknesses
- **Coach Chat**: Ask questions like "What's my plan?", "Did I miss a tactic?"
- **Opening Guidance**: Real-time opening theory help
- **Post-Move Analysis**: Immediate feedback on each move

**Pre-Move Checklist Logic**:
```python
def generate_checklist(player_weaknesses, game_phase, position):
    items = []
    
    if game_phase == "opening":
        items.append("Is there a piece I haven't developed yet?")
        items.append("Have I castled or is my king safe?")
    
    if "tactical_error" in player_weaknesses:
        items.append("What is my opponent threatening?")
        items.append("Are any of my pieces undefended?")
    
    if "time_trouble" in player_weaknesses:
        items.append("Am I playing too fast/slow?")
    
    return items
```

### 4. Thinking Score System

**Purpose**: Quantify improvement in thinking habits, not just rating

**Five Thinking Dimensions**:

| Dimension | What It Measures | How It's Scored |
|-----------|-----------------|-----------------|
| Threat Awareness | Ability to see opponent's threats | Missed hanging pieces, checks |
| Tactical Vision | Finding tactics in own games | Missed winning tactics vs found |
| Positional Understanding | Strategic decisions | Pawn structure, piece placement |
| Time Management | Clock usage patterns | Blunders in time trouble |
| Opening Preparation | Opening principle adherence | Fundamentals score |

**Score Calculation**:
```python
def calculate_thinking_score(game_analysis):
    scores = {
        "threat_awareness": 100 - (blundered_pieces * 15),
        "tactical_vision": min(100, found_tactics * 20),
        "positional": accuracy_score,
        "time_mgmt": 100 - (time_trouble_blunders * 10),
        "opening_prep": opening_fundamentals_score
    }
    return weighted_average(scores)
```

### 5. Dashboard & Progress Tracking

**Displays**:
- Biggest weakness with improvement trend
- Blind spots (error patterns across games)
- Games to reflect (unanalyzed games)
- Thinking Score with trend arrow
- Training recommendations
- Win/loss streaks

### 6. Admin Content Pipeline

**Purpose**: Scalable content management for opening library

**Features**:
- Monaco JSON editor for opening data
- Validate/Save/Preview workflow
- Static + Admin override system
- Community correction submissions

---

## User Journey & Flows

### New User Onboarding

```
[Landing Page] → [Chess.com Username Input]
                        ↓
              [Fetch Recent Games via API]
                        ↓
              [Auto-Analyze 5 Games]
                        ↓
              [Generate Initial Profile]
                        ↓
              [Show Dashboard with Insights]
```

### Daily Active User Flow

```
[Login] → [Dashboard]
              ↓
    ┌────────┴────────┐
    ↓                 ↓
[Review Game]    [Practice]
    ↓                 ↓
[Lab Analysis]   [Play with Coach]
    ↓                 ↓
[Key Insights]   [Real-time Tips]
    ↓                 ↓
[Training]       [Post-Game Review]
    ↓                 ↓
    └────────┬────────┘
             ↓
      [Progress Updated]
             ↓
      [Next Recommendation]
```

### Game Analysis Flow

```
[Select Game] → [Summary Tab]
                     ↓
              "You played well until move 23..."
                     ↓
              [Moments Tab] → [Critical Position]
                                    ↓
                            "What was your plan here?"
                                    ↓
                            [Reveal Analysis]
                                    ↓
              [Ideas Tab] → [Strategic Theme]
                                    ↓
                            [Rating-Adaptive Explanation]
                                    ↓
                            [How to Think Walkthrough]
                                    ↓
              [Habits Tab] → [Opening Fundamentals: 85%]
                                    ↓
                            [Principles Followed/Violated]
                                    ↓
              [Memory Tab] → [Your Pattern History]
                                    ↓
                            [Clickable Mistake List]
```

---

## Technical Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  React 18 + Tailwind CSS + Shadcn/UI + Framer Motion            │
│  Chessground (board) + Chess.js (logic)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                  │
│  FastAPI (Python 3.11+) + Async/Await                           │
│  Pydantic Models + Motor (async MongoDB)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    MongoDB      │  │   Stockfish     │  │   LLM APIs      │
│  (Primary DB)   │  │  (Chess Engine) │  │ (GPT/Claude)    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Directory Structure

```
/app
├── backend/
│   ├── server.py                 # FastAPI main app
│   ├── routes/
│   │   ├── auth.py              # Authentication
│   │   ├── games.py             # Game CRUD
│   │   ├── analysis.py          # Game analysis
│   │   ├── openings.py          # Opening lessons
│   │   ├── training.py          # Training features
│   │   ├── coach.py             # AI coaching
│   │   └── reflect.py           # Reflection features
│   ├── services/
│   │   ├── chess_com_service.py # Chess.com API integration
│   │   ├── stockfish_service.py # Engine analysis
│   │   ├── llm_service.py       # LLM integration
│   │   ├── thinking_coach.py    # Thought process generation
│   │   ├── thinking_score.py    # Score calculation
│   │   ├── player_identity.py   # Player profiling
│   │   ├── data_freshness.py    # Data sync service
│   │   └── opening_feedback_admin_service.py
│   ├── models/                  # Pydantic models
│   └── tests/                   # Pytest test files
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── HomePage.jsx     # Dashboard
│   │   │   ├── LabV2.jsx        # Game analysis lab
│   │   │   ├── CoachPlay.jsx    # Play with coach
│   │   │   ├── OpeningLesson.jsx # Interactive lessons
│   │   │   ├── Training.jsx     # Training page
│   │   │   └── ...
│   │   ├── components/
│   │   │   ├── lab/             # Lab components
│   │   │   ├── coach/           # Coach components
│   │   │   ├── openings/        # Opening components
│   │   │   └── ui/              # Shadcn components
│   │   └── utils/
│   └── public/
│
└── memory/
    └── PRD.md                   # Product requirements
```

### Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend Framework | React 18 | Industry standard, large talent pool |
| UI Components | Shadcn/UI | High quality, customizable, accessible |
| Chess Board | Chessground | Same as Lichess, battle-tested |
| Chess Logic | Chess.js | Comprehensive move validation |
| Backend | FastAPI | Async, fast, auto-docs, Python ecosystem |
| Database | MongoDB | Flexible schema for game data, fast queries |
| Chess Engine | Stockfish 16 | Best engine, WASM support possible |
| LLM | GPT-4/Claude | Natural language coaching |

### Frontend Component Architecture

```
App.js
├── Layout (sidebar, header)
├── Routes
│   ├── HomePage (Dashboard)
│   │   ├── WeaknessCard
│   │   ├── BlindSpotsCard
│   │   ├── ThinkingScoreCard
│   │   ├── GamesToReflect
│   │   └── TrainingRecommendations
│   │
│   ├── LabV2 (Game Analysis)
│   │   ├── GameSummary
│   │   ├── CriticalMoments
│   │   ├── StrategicThemes (Ideas)
│   │   │   └── ThoughtProcessWalkthrough
│   │   ├── OpeningFundamentals (Habits)
│   │   └── DeepMemoryPanel (Memory)
│   │
│   ├── CoachPlay
│   │   ├── ChessBoard
│   │   ├── CoachChat
│   │   ├── PreMoveChecklist
│   │   ├── EvalBar
│   │   └── OpeningGuidePanel
│   │
│   └── OpeningLesson
│       ├── GuidedOpeningLesson
│       ├── InteractivePractice
│       └── TrapPractice
```

### Backend Service Architecture

```
server.py (FastAPI)
     │
     ├── routes/
     │   └── [HTTP endpoints]
     │
     └── services/
         │
         ├── Analysis Pipeline
         │   ├── chess_com_service.py    # Fetch games
         │   ├── stockfish_service.py    # Engine eval
         │   ├── analysis_service.py     # Mistake detection
         │   └── llm_service.py          # Natural language
         │
         ├── Coaching Engine
         │   ├── thinking_coach.py       # Thought walkthroughs
         │   ├── thinking_score.py       # Score calculation
         │   └── coach_response.py       # Chat responses
         │
         ├── Player Profiling
         │   ├── player_identity.py      # Style, patterns
         │   ├── weakness_tracker.py     # Weakness detection
         │   └── data_freshness.py       # Data sync
         │
         └── Content
             ├── opening_feedback_admin_service.py
             └── static_openings.py
```

---

## AI Coaching Engine

### LLM Integration

We use LLMs for:
1. **Game Summaries** - Natural language game narratives
2. **Move Explanations** - Why a move is good/bad
3. **Thought Process Walkthroughs** - Step-by-step analysis
4. **Coach Chat** - Interactive Q&A during games
5. **Rating-Adaptive Content** - Explanations for different levels

**Prompt Engineering Example** (Thought Process):
```python
def generate_thought_process_prompt(fen, move, player_rating):
    return f"""
    You are a chess coach teaching a {player_rating}-rated player.
    
    Position (FEN): {fen}
    Move played: {move}
    
    Generate a step-by-step thought process showing how to analyze
    this position. Use simple language appropriate for their level.
    
    Format:
    Step 1: [What to look for first]
    Step 2: [Next consideration]
    ...
    
    Key insight: [Main takeaway]
    """
```

### Stockfish Integration

```python
class StockfishService:
    def __init__(self):
        self.engine = chess.engine.SimpleEngine.popen_uci("stockfish")
    
    async def analyze_position(self, fen: str, depth: int = 20):
        board = chess.Board(fen)
        info = await self.engine.analyse(board, chess.engine.Limit(depth=depth))
        return {
            "best_move": info["pv"][0].uci(),
            "evaluation": info["score"].relative.score(mate_score=10000),
            "principal_variation": [m.uci() for m in info["pv"][:5]]
        }
    
    async def get_move_classification(self, fen, move, prev_eval, curr_eval):
        diff = curr_eval - prev_eval
        if diff < -300: return "blunder"
        if diff < -100: return "mistake"
        if diff < -50: return "inaccuracy"
        return "good"
```

### Player Identity Algorithm

```python
def calculate_player_identity(games: List[Game]) -> PlayerIdentity:
    """
    Analyzes all games to build a comprehensive player profile.
    """
    metrics = {
        "total_games": len(games),
        "accuracy_scores": [],
        "mistake_types": defaultdict(int),
        "phase_performance": {"opening": [], "middlegame": [], "endgame": []},
        "time_trouble_blunders": 0,
        "tactical_patterns": [],
    }
    
    for game in games:
        # Aggregate accuracy
        metrics["accuracy_scores"].append(game.accuracy)
        
        # Categorize mistakes
        for mistake in game.mistakes:
            metrics["mistake_types"][mistake.type] += 1
            metrics["phase_performance"][mistake.phase].append(mistake.eval_loss)
    
    # Determine playing style
    style = determine_style(metrics)  # "tactical", "positional", "universal"
    
    # Find blind spots
    blind_spots = find_patterns(metrics["mistake_types"])
    
    return PlayerIdentity(
        style=style,
        blind_spots=blind_spots,
        strongest_phase=max(metrics["phase_performance"], key=avg),
        weakest_phase=min(metrics["phase_performance"], key=avg),
        improvement_trend=calculate_trend(metrics["accuracy_scores"])
    )
```

---

## Data Models & Schema

### MongoDB Collections

#### `users`
```javascript
{
  _id: ObjectId,
  user_id: "user_abc123",
  email: "player@example.com",
  chess_com_username: "player123",
  created_at: ISODate,
  preferences: {
    theme: "dark",
    board_style: "brown",
    sound: true
  },
  onboarding_completed: true
}
```

#### `games`
```javascript
{
  _id: ObjectId,
  game_id: "uuid",
  user_id: "user_abc123",
  pgn: "1. e4 e5 2. Nf3...",
  source: "chess.com",
  result: "win",
  opponent_username: "opponent456",
  opponent_rating: 1250,
  user_color: "white",
  time_control: "600",
  is_analyzed: true,
  analysis: {
    accuracy: 78.5,
    mistakes: [...],
    summary: "An interesting battle...",
    turning_point: {...},
    opening_name: "Italian Game"
  },
  created_at: ISODate
}
```

#### `player_identities`
```javascript
{
  _id: ObjectId,
  user_id: "user_abc123",
  games_analyzed: 47,
  style: {
    type: "positional",
    confidence: 0.85
  },
  blunder_taxonomy: {
    tactical_error: 30,
    positional_mistake: 12,
    time_trouble: 5
  },
  weakest_phase: "middlegame",
  strongest_phase: "endgame",
  pattern_history: [
    {
      type: "missed_fork",
      game_id: "...",
      move_number: 23,
      date: ISODate
    }
  ],
  streaks: {
    current_wins: 3,
    current_losses: 0,
    best_streak: 7
  },
  updated_at: ISODate
}
```

#### `thinking_scores`
```javascript
{
  _id: ObjectId,
  user_id: "user_abc123",
  game_id: "uuid",
  overall_score: 78,
  dimensions: {
    threat_awareness: 85,
    tactical_vision: 70,
    positional_understanding: 75,
    time_management: 90,
    opening_preparation: 65
  },
  calculated_at: ISODate
}
```

#### `opening_feedback`
```javascript
{
  _id: ObjectId,
  opening_key: "caro-kann",
  opening_name: "Caro-Kann Defense",
  description: "...",
  key_ideas: ["..."],
  main_line: [
    { move: "e4", explanation: "..." }
  ],
  traps: [...],
  common_mistakes: [...],
  updated_at: ISODate,
  updated_by: "admin"
}
```

---

## API Reference

### Authentication
```
POST /api/auth/register     - Create account
POST /api/auth/login        - Login (returns JWT)
GET  /api/auth/me           - Get current user
```

### Games
```
GET  /api/games                    - List user's games
POST /api/games/fetch              - Fetch from Chess.com
POST /api/games/{id}/analyze       - Trigger analysis
GET  /api/games/{id}/analysis      - Get analysis results
```

### Coaching
```
POST /api/coach/chat               - Chat with coach
POST /api/coach/thought-process    - Get thinking walkthrough
GET  /api/coach/deep-memory        - Get player profile
POST /api/coach/pre-move-checklist - Get contextual checklist
```

### Analysis
```
GET  /api/analysis/summary/{game_id}     - Game summary
GET  /api/analysis/moments/{game_id}     - Critical moments
GET  /api/analysis/ideas/{game_id}       - Strategic themes
GET  /api/analysis/habits/{game_id}      - Opening fundamentals
```

### Thinking Score
```
GET  /api/thinking-score/latest          - Latest score
GET  /api/thinking-score/history         - Score trend
POST /api/game/{id}/calculate-thinking-score - Calculate for game
```

### Openings
```
GET  /api/openings                       - List all openings
GET  /api/openings/{key}                 - Get opening details
GET  /api/admin/openings                 - Admin: list all
PUT  /api/admin/openings/{key}           - Admin: update opening
```

### Data Sync
```
POST /api/data/refresh                   - Recalculate user data
```

---

## Competitive Differentiation

### Feature Comparison Matrix

| Feature | Chess.com | Lichess | Chessable | Chess Coach AI |
|---------|-----------|---------|-----------|----------------|
| Game Analysis | ✓ | ✓ | ✗ | ✓ |
| Shows Best Move | ✓ | ✓ | ✗ | ✓ |
| **Explains WHY** | ✗ | ✗ | Partial | **✓** |
| **Teaches Thinking Process** | ✗ | ✗ | ✗ | **✓** |
| **Personalized Coaching** | ✗ | ✗ | ✗ | **✓** |
| **Tracks Patterns Over Time** | Basic | ✗ | ✗ | **✓ Deep** |
| **Rating-Adaptive Explanations** | ✗ | ✗ | ✗ | **✓** |
| **Pre-Move Checklist** | ✗ | ✗ | ✗ | **✓** |
| Opening Lessons | ✓ | ✓ | ✓ | ✓ |
| **Interactive Guided Lessons** | ✗ | ✗ | ✗ | **✓** |
| Puzzles from Own Games | ✗ | ✗ | ✗ | **✓** |
| Price (Monthly) | ₹300-900 | Free | ₹500-2000 | ₹99-299 |

### Unique Value Propositions

1. **"How to Think" vs "What to Play"**
   - Others: "Qxd4 was best move"
   - Us: "Step 1: Check for threats. Step 2: Look for tactics..."

2. **Deep Player Memory**
   - Others: Basic stats (accuracy, rating)
   - Us: "You've made this same tactical pattern 8 times in 15 games"

3. **Contextual Real-Time Coaching**
   - Others: Post-game analysis only
   - Us: Pre-move checklist, live opening guidance

4. **Personalized Training Loop**
   - Others: Generic puzzles
   - Us: Puzzles generated from YOUR mistakes

---

## Monetization Strategy

### Pricing Tiers (India-Focused)

| Tier | Price | Features |
|------|-------|----------|
| **Free** | ₹0 | 5 game analyses/month, basic insights |
| **Student** | ₹99/month | Unlimited analysis, opening lessons |
| **Pro** | ₹199/month | Everything + Play with Coach, Thinking Score |
| **Family** | ₹299/month | Pro for 3 users |

### Payment Integration
- **Primary**: Razorpay (UPI, cards, net banking)
- **Secondary**: Google Pay, PhonePe direct
- **Freemium Model**: 5 free analyses, then paywall

### Revenue Projections (Year 1)

| Quarter | Users | Paid % | ARPU | MRR |
|---------|-------|--------|------|-----|
| Q1 | 10,000 | 3% | ₹150 | ₹45,000 |
| Q2 | 50,000 | 5% | ₹160 | ₹4,00,000 |
| Q3 | 150,000 | 7% | ₹170 | ₹17,85,000 |
| Q4 | 300,000 | 10% | ₹180 | ₹54,00,000 |

---

## Roadmap

### Phase 1: MVP (Current) ✅
- [x] Game analysis with 5-tab Lab
- [x] Opening lessons with guided walkthrough
- [x] Play with Coach (real-time coaching)
- [x] Thinking Score system
- [x] Player identity tracking
- [x] Admin content pipeline

### Phase 2: Monetization (Next 4 weeks)
- [ ] Razorpay integration
- [ ] Freemium paywall logic
- [ ] Subscription management
- [ ] Payment analytics

### Phase 3: Retention (Next 8 weeks)
- [ ] Daily streak counter
- [ ] XP and leveling system
- [ ] Email/push notifications
- [ ] "What You Did Well" positive feedback

### Phase 4: Growth (Next 12 weeks)
- [ ] Mobile app (React Native)
- [ ] Social sharing ("Chess DNA Report")
- [ ] Referral program
- [ ] Hindi localization

### Phase 5: Scale (6+ months)
- [ ] Spaced repetition mistake trainer
- [ ] Video lesson integration
- [ ] Tournament preparation mode
- [ ] Regional language support
- [ ] B2B for chess academies

---

## Getting Started (For Developers)

### Prerequisites
- Node.js 18+
- Python 3.11+
- MongoDB
- Stockfish binary

### Local Setup
```bash
# Clone
git clone [repo-url]
cd chess-coach

# Backend
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# Frontend
cd frontend
yarn install
yarn start
```

### Environment Variables
```
# backend/.env
MONGO_URL=mongodb://localhost:27017
DB_NAME=chess_coach
EMERGENT_MODEL_API_KEY=your_key
STOCKFISH_PATH=/usr/local/bin/stockfish

# frontend/.env
REACT_APP_BACKEND_URL=http://localhost:8001/api
```

---

## Screenshots Gallery

### Dashboard
The main command center showing player's biggest weakness, blind spots, thinking score, and recommended actions.

### Game Analysis Lab
Five-tab analysis system: Summary (narrative), Moments (critical positions), Ideas (strategic themes with "How to Think"), Habits (opening fundamentals), Memory (player profile).

### Play with Coach
Real-time coaching during practice games with Pre-Move Checklist, Coach Chat, and Opening Guidance.

### Opening Lessons
Interactive guided walkthroughs with auto-playing moves, coach narration, and "Why this move?" AI explanations.

---

## Contact & Links

- **Live Demo**: https://chess-truth-engine.preview.emergentagent.com
- **API Documentation**: /api/docs (FastAPI auto-generated)

---

*Last Updated: March 2026*
*Version: 1.0*
