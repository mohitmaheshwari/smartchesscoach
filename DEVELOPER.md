# Chess Coach AI - Developer Guide

A comprehensive AI-powered chess coaching application that analyzes games, identifies patterns, and provides personalized coaching feedback.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Getting Started](#getting-started)
5. [Backend Services](#backend-services)
6. [Frontend Components](#frontend-components)
7. [API Reference](#api-reference)
8. [Database Schema](#database-schema)
9. [Key Features](#key-features)
10. [Configuration](#configuration)
11. [Deployment](#deployment)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│  React Frontend (SPA)          │  React Native Mobile App       │
│  - Shadcn/UI Components        │  - Expo Framework              │
│  - React Router                │  - Native Chess Board          │
│  - Chess.js for board logic    │                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI Backend                                                │
│  ├── Authentication (Google OAuth + JWT)                        │
│  ├── Game Import (Chess.com, Lichess APIs)                      │
│  ├── Game Analysis (Stockfish + LLM)                            │
│  ├── Player Profile & Pattern Tracking                          │
│  └── Coaching & Training Services                               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SERVICE LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│  Stockfish Engine     │  LLM Integration    │  MongoDB          │
│  - Move evaluation    │  - GPT/Claude       │  - User data      │
│  - Position analysis  │  - Coaching text    │  - Game storage   │
│  - Best move calc     │  - Voice scripts    │  - Analysis cache │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **FastAPI** | REST API framework |
| **Python 3.11** | Backend language |
| **MongoDB** | Primary database |
| **Motor** | Async MongoDB driver |
| **Stockfish 15** | Chess engine for move analysis |
| **Emergent Integrations** | LLM API integration (OpenAI, Claude, Gemini) |
| **Pydantic** | Data validation |

### Frontend
| Technology | Purpose |
|------------|---------|
| **React 18** | UI framework |
| **Shadcn/UI** | Component library |
| **Tailwind CSS** | Styling |
| **Chess.js** | Chess logic |
| **react-chessboard** | Board rendering |
| **React Router** | Navigation |
| **Sonner** | Toast notifications |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| **Docker** | Containerization |
| **Nginx** | Reverse proxy |
| **Supervisor** | Process management |

---

## Project Structure

```
/app
├── backend/                    # FastAPI Backend
│   ├── server.py              # Main API routes & entry point
│   ├── config.py              # Configuration constants
│   ├── stockfish_service.py   # Chess engine integration
│   ├── player_profile_service.py  # User profile management
│   ├── mistake_card_service.py    # Spaced repetition system
│   ├── phase_theory_service.py    # Opening/Middle/Endgame theory
│   ├── journey_service.py     # Progress tracking
│   ├── rating_service.py      # Rating calculations
│   ├── rag_service.py         # RAG for personalized coaching
│   ├── cqs_service.py         # Coach Quality Score (internal)
│   ├── gamification_service.py    # XP, achievements, streaks
│   └── requirements.txt       # Python dependencies
│
├── frontend/                   # React Frontend
│   ├── src/
│   │   ├── App.jsx            # Main app component
│   │   ├── components/        # Reusable components
│   │   │   ├── ui/            # Shadcn/UI components
│   │   │   ├── ChessBoardViewer.jsx  # Interactive chess board
│   │   │   └── Layout.jsx     # App layout wrapper
│   │   └── pages/             # Page components
│   │       ├── Landing.jsx    # Home page
│   │       ├── Dashboard.jsx  # User dashboard
│   │       ├── GameAnalysis.jsx   # Game analysis view
│   │       ├── Import.jsx     # Game import
│   │       └── Training.jsx   # Training features
│   ├── package.json           # Node dependencies
│   └── tailwind.config.js     # Tailwind configuration
│
├── docker/                     # Docker configuration
│   ├── nginx.conf             # Nginx reverse proxy config
│   └── supervisord.conf       # Process manager config
│
├── Dockerfile                  # Production multi-stage build
├── Dockerfile.backend          # Backend-only container
├── Dockerfile.frontend         # Frontend-only container
├── docker-compose.yml          # Development orchestration
└── DEVELOPER.md               # This file
```

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for local development)
- Python 3.11+ (for local development)
- MongoDB (or use Docker)

### Quick Start with Docker

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd chess-coach

# 2. Create environment file
cp .env.example .env
# Edit .env with your credentials

# 3. Start all services
docker-compose up -d

# 4. Access the app
# Frontend: http://localhost:3000
# Backend:  http://localhost:8001/docs
```

### Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# Frontend (new terminal)
cd frontend
yarn install
yarn start
```

### Environment Variables

Create a `.env` file in the root directory:

```env
# Database
MONGO_URL=mongodb://localhost:27017
DB_NAME=chess_coach

# LLM Integration (Required)
EMERGENT_LLM_KEY=your_emergent_llm_key

# OAuth (Optional - for Google login)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Frontend
REACT_APP_BACKEND_URL=http://localhost:8001
```

---

## Backend Services

### Core Services

#### `server.py` - Main API
The central FastAPI application containing all routes:
- **Auth**: `/api/auth/*` - Session management, OAuth
- **Games**: `/api/games/*` - Game CRUD, import
- **Analysis**: `/api/analyze-game` - AI analysis
- **Ask**: `/api/game/{id}/ask` - Interactive Q&A about positions

#### `stockfish_service.py` - Chess Engine
Interfaces with Stockfish chess engine:
```python
# Key functions
analyze_game_with_stockfish(pgn, user_color, depth=18)
get_position_evaluation(fen, depth=18)
get_best_moves_for_position(fen, num_moves=3)
```

#### `player_profile_service.py` - User Profiles
Manages player profiles and weakness tracking:
```python
# Key functions
get_or_create_profile(db, user_id, name)
update_profile_after_analysis(db, user_id, game_id, ...)
categorize_weakness(category, subcategory)
```

#### `phase_theory_service.py` - Strategic Coaching
Provides phase-specific chess theory:
```python
# Key functions
analyze_game_phases(pgn, user_color, rating)
get_phase_theory(phase, rating_bracket)
detect_game_phase(board, move_number)
```

### Analysis Pipeline

```
1. User submits game (PGN)
           │
           ▼
2. Stockfish analyzes all moves
   - Calculates accuracy
   - Identifies blunders/mistakes
   - Finds best moves
           │
           ▼
3. LLM generates coaching commentary
   - Uses Stockfish data as context
   - Applies player profile
   - Generates personalized feedback
           │
           ▼
4. Results stored & returned
   - Analysis cached in MongoDB
   - Mistake cards created
   - Profile updated
```

---

## Frontend Components

### Key Components

#### `ChessBoardViewer.jsx`
Interactive chess board with move navigation:
```jsx
// Props
pgn: string           // PGN game notation
userColor: string     // "white" or "black"
onMoveChange: func    // Callback when move changes
commentary: array     // Move comments to display

// Ref methods
boardRef.current.goToMove(index)
boardRef.current.getCurrentFen()
boardRef.current.getFenBeforeMove()
boardRef.current.playVariation(fen, moves)
```

#### `GameAnalysis.jsx`
Main game analysis page:
- Displays interactive board
- Shows analysis summary (accuracy, blunders)
- "Ask About This Move" feature
- Phase-based strategic lessons

### UI Components (Shadcn/UI)
Located in `frontend/src/components/ui/`:
- `button.jsx` - Styled buttons
- `card.jsx` - Card containers
- `dialog.jsx` - Modal dialogs
- `tabs.jsx` - Tab navigation
- `toast.jsx` / `sonner.tsx` - Notifications

---

## API Reference

### Authentication

```http
POST /api/auth/session
Content-Type: application/json
{"session_id": "oauth_session_id"}

Response: {user object + sets session_token cookie}
```

### Game Import

```http
POST /api/import-games
Content-Type: application/json
{"platform": "chess.com", "username": "player123"}

Response: {"imported": 15, "total_found": 30}
```

### Game Analysis

```http
POST /api/analyze-game
Content-Type: application/json
{"game_id": "game_abc123", "force": false}

Response: {
  "accuracy": 85.5,
  "blunders": 1,
  "mistakes": 2,
  "commentary": [...],
  "stockfish_analysis": {...}
}
```

### Ask About Position

```http
POST /api/game/{game_id}/ask
Content-Type: application/json
{
  "fen": "position_fen",
  "fen_before": "position_before_move",
  "question": "Why was d6 a mistake?",
  "played_move": "d6",
  "user_color": "black"
}

Response: {
  "answer": "Coach's explanation...",
  "stockfish": {
    "best_move": "opponent_best",
    "user_best_move": "what_you_should_have_played"
  }
}
```

---

## Database Schema

### Collections

#### `users`
```javascript
{
  user_id: "user_abc123",
  email: "user@example.com",
  name: "John Doe",
  picture: "url",
  chess_com_username: "johndoe",
  lichess_username: null,
  created_at: ISODate
}
```

#### `games`
```javascript
{
  game_id: "game_abc123",
  user_id: "user_abc123",
  platform: "chess.com",
  pgn: "1. e4 e5 2. Nf3...",
  white_player: "johndoe",
  black_player: "opponent",
  result: "1-0",
  user_color: "white",
  is_analyzed: true,
  imported_at: ISODate
}
```

#### `game_analyses`
```javascript
{
  analysis_id: "analysis_abc123",
  game_id: "game_abc123",
  user_id: "user_abc123",
  accuracy: 85.5,
  blunders: 1,
  mistakes: 2,
  commentary: [{
    move_number: 15,
    move: "Bxf7",
    evaluation: "blunder",
    feedback: "This loses material...",
    details: {...}
  }],
  stockfish_analysis: {
    accuracy: 85.5,
    move_evaluations: [...]
  }
}
```

#### `player_profiles`
```javascript
{
  user_id: "user_abc123",
  games_analyzed_count: 25,
  top_weaknesses: [{
    category: "tactical",
    subcategory: "pin_blindness",
    occurrence_count: 5
  }],
  improvement_trend: "improving",
  current_rating: 1200
}
```

---

## Key Features

### 1. Game Analysis
- Import games from Chess.com and Lichess
- Stockfish-powered move evaluation
- AI-generated coaching commentary
- Accuracy calculation

### 2. Ask About This Move
- Interactive Q&A about any position
- Analyzes position BEFORE and AFTER the move
- Correctly identifies user's best move vs opponent's
- Supports follow-up questions

### 3. Phase-Aware Coaching
- Detects opening/middlegame/endgame
- Provides phase-specific theory
- Rating-adaptive content

### 4. Player Profile
- Tracks recurring mistakes
- Identifies improvement patterns
- Personalizes coaching based on history

### 5. Gamification
- XP system
- Achievements
- Daily streaks

---

## Deployment

### Docker Production Build

```bash
# Build production image
docker build -t chess-coach:latest .

# Run with environment variables
docker run -d \
  -p 80:80 \
  -e MONGO_URL=mongodb://your-mongo:27017 \
  -e DB_NAME=chess_coach \
  -e EMERGENT_LLM_KEY=your_key \
  chess-coach:latest
```

### Docker Compose Production

```bash
# Create production .env
MONGO_URL=mongodb://mongodb:27017
DB_NAME=chess_coach
EMERGENT_LLM_KEY=your_production_key

# Deploy
docker-compose up -d
```

### Health Checks
- Backend: `GET /api/health`
- Frontend: `GET /health`
- MongoDB: `mongosh --eval "db.adminCommand('ping')"`

---

## Troubleshooting

### Common Issues

**1. Stockfish not found**
```bash
# Install Stockfish
sudo apt-get install stockfish

# Or verify path
which stockfish  # Should be /usr/games/stockfish
```

**2. MongoDB connection failed**
```bash
# Check MongoDB is running
docker-compose ps mongodb

# Check logs
docker-compose logs mongodb
```

**3. LLM API errors**
- Verify `EMERGENT_LLM_KEY` is set
- Check API quota/balance
- Review backend logs: `tail -f /var/log/supervisor/backend.err.log`

---

## Contributing

1. Create a feature branch
2. Make changes
3. Run tests: `pytest backend/tests/`
4. Submit pull request

## License

[Your License Here]
