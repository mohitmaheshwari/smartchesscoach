# Chess Coach AI - Product Requirements Document

## Original Problem Statement
Build an AI chess coach app that understands the context of a user's games, remembers their mistakes like a human coach, and provides guidance in natural language. The goal is to replace human coaches with accurate analysis and personalized coaching.

## User Persona
Chess players (beginners to intermediate) who want personalized coaching without expensive human coaches. Target market: India (high chess popularity, price-sensitive market).

## Platforms
- **Web App**: React + TailwindCSS + Shadcn UI ✅ Complete
- **Mobile App**: React Native + Expo ✅ Core features implemented

---

## 🆕 MAJOR UPDATE: Stockfish Integration (February 2025)

### The Problem
Previously, the app relied on GPT to evaluate chess moves, which led to inaccurate analysis:
- Moves rated "best" by Chess.com were sometimes flagged as mistakes
- Blunder/mistake counts didn't match chess platform evaluations
- Best move suggestions were sometimes incorrect

### The Solution
**Integrated Stockfish 15** - the world's strongest open-source chess engine (~3500 Elo):

1. **Accurate Move Evaluation**: Every move is now evaluated by Stockfish at depth 18
2. **Centipawn-Based Classification**: Moves are classified using industry-standard thresholds:
   - Best: 0 cp loss
   - Excellent: < 10 cp loss
   - Good: 10-30 cp loss
   - Inaccuracy: 30-100 cp loss
   - Mistake: 100-300 cp loss
   - Blunder: > 300 cp loss
3. **Accurate Best Move Suggestions**: Stockfish provides the actual best moves
4. **Accuracy Score**: Chess.com-style accuracy percentage (0-100%)
5. **GPT for Coaching**: Stockfish provides the WHAT, GPT explains the WHY

### New Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze-position` | POST | Analyze a single FEN position |
| `/api/best-moves` | POST | Get top N best moves for a position |

### Architecture Change
```
BEFORE: PGN → GPT → (inaccurate) blunder/mistake counts

AFTER:  PGN → Stockfish Engine → Accurate move evaluations
               ↓
             GPT Coach → Explains WHY mistakes happen
                        → Provides habit-based coaching
```

---

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB) + **Stockfish 15**
- **Database**: MongoDB 
- **AI**: GPT-5.2 via Emergent integrations (for coaching commentary)
- **Chess Engine**: Stockfish 15 (for accurate move evaluation)
- **Voice**: OpenAI TTS
- **Email**: SendGrid
- **Auth**: Emergent-managed Google OAuth (web), expo-auth-session (mobile)

---

## COMPLETED FEATURES

### Core Features ✅
- Game import from Chess.com/Lichess
- **Stockfish-powered move analysis** (accurate to Chess.com/Lichess)
- AI coaching with Indian chess coach persona
- RAG-based memory system
- PlayerProfile with habit tracking
- Interactive chessboard (web and mobile)
- Voice coaching (TTS)
- Coach Quality Score (CQS)
- **Accurate best move suggestions** (from Stockfish)

### Rating & Training System ✅
- Rating trajectory with projections
- Time management analysis
- Fast thinking/calculation training
- Personalized puzzle trainer

### Auto-Analysis System ✅
- Background sync every 6 hours
- Email notifications (SendGrid)
- Push notifications (mobile)

### Mobile App ✅
- Google OAuth (expo-auth-session)
- Interactive chessboard (WebView)
- Push notifications
- Full feature parity with web

---

## Key API Endpoints

### Game Analysis
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze-game` | POST | Full game analysis with Stockfish + GPT |
| `/api/analyze-position` | POST | Single position evaluation |
| `/api/best-moves` | POST | Top N moves for a position |

### Rating & Training
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rating/trajectory` | GET | Rating predictions & milestones |
| `/api/training/time-management` | GET | Clock usage analysis |
| `/api/training/fast-thinking` | GET | Calculation speed analysis |
| `/api/training/puzzles` | GET | Personalized puzzles |

---

## File Structure

```
/app/
├── backend/
│   ├── server.py              # Main FastAPI app
│   ├── stockfish_service.py   # NEW: Stockfish engine integration
│   ├── rating_service.py      # Rating prediction
│   ├── player_profile_service.py
│   └── ...
├── frontend/
│   └── src/
│       ├── pages/
│       └── components/
│           └── RatingTrajectory.jsx
└── mobile/
    └── src/
        └── components/
            ├── ChessBoard.js
            └── RatingTrajectory.js
```

---

## Upcoming Tasks

### P0 - High Priority
1. **Parent Dashboard**: WhatsApp-sharable weekly reports
2. **Hindi/Hinglish Coaching**: AI commentary in Hindi

### P1 - Medium Priority
1. **Opening Repertoire Builder**
2. **Offline Caching** (mobile)

### P2 - Lower Priority
1. Freemium model
2. "Coach Call" video summaries
3. Social features

---

## 3rd Party Integrations

| Integration | Status | Purpose |
|-------------|--------|---------|
| **Stockfish 15** | ✅ Active | Chess engine (move evaluation) |
| OpenAI GPT-5.2 | ✅ Active | Coaching commentary |
| OpenAI TTS | ✅ Active | Voice coaching |
| Chess.com API | ✅ Active | Game imports |
| Lichess API | ✅ Active | Game imports |
| Google OAuth | ✅ Active | Authentication |
| SendGrid | ⚠️ Needs key | Email notifications |
| Expo Push | ✅ Active | Mobile notifications |

---

## Stockfish Configuration

- **Binary**: `/usr/games/stockfish`
- **Version**: 15.1
- **Default Depth**: 18 (good balance of speed/accuracy)
- **Quick Depth**: 12 (for rapid analysis)
- **Deep Depth**: 22 (for critical positions)
- **Threads**: 1 (can increase for faster analysis)
- **Hash**: 128 MB

---

Last Updated: February 2025
