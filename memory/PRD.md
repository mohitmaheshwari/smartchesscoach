# Chess Coach AI - Product Requirements Document

## Original Problem Statement
Build an AI chess coach app that understands the context of a user's games, remembers their mistakes like a human coach, and provides guidance in natural language. The goal is to replace human coaches. The app needs to integrate with Chess.com and Lichess, allowing users to import their games. The AI should understand the user's playing style and level, providing tailored training.

## User Persona
Chess players (beginners to intermediate) who want personalized coaching without expensive human coaches. Target market: India (high chess popularity, price-sensitive market).

## Platforms
- **Web App**: React + TailwindCSS + Shadcn UI ✅ Complete
- **Mobile App**: React Native + Expo ✅ Core features implemented

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB)
- **Database**: MongoDB (MongoDB Atlas Vector Search recommended for production RAG)
- **AI**: GPT-5.2 via Emergent integrations (Emergent LLM Key)
- **Voice**: OpenAI TTS
- **Email**: SendGrid
- **Auth**: Emergent-managed Google OAuth (web), expo-auth-session (mobile)

---

## COMPLETED FEATURES (December 2025)

### Core Features ✅
- Game import from Chess.com/Lichess
- AI analysis with Indian chess coach persona (firm but supportive)
- RAG-based memory system (hash-based embeddings in MongoDB)
- PlayerProfile with habit tracking and weakness detection
- Interactive chessboard (web and mobile)
- Voice coaching (TTS)
- Coach Quality Score (CQS) - internal quality evaluation
- Best move suggestions for mistakes/blunders

### Auto-Analysis System ✅
- Background sync (every 6 hours)
- Automatic AI analysis on import
- Email notifications after sync (SendGrid)
- Push notifications (mobile) for new analysis

### Premium UI (Web) ✅
- Redesigned Journey + Dashboard pages
- Framer-motion animations
- Dark-first theme (Linear/Stripe inspired)

### Mobile App (React Native/Expo) ✅
- Interactive chessboard with WebView (chess.js for logic)
- Google OAuth authentication (expo-auth-session)
- Push notification service (expo-notifications)
- Dashboard, Journey, Games, Settings screens
- Dark/light theme support (system-aware)

### 🆕 Rating Trajectory & Training System ✅ (NEW)
**Backend Endpoints:**
- `GET /api/rating/trajectory` - Fetches platform ratings, projected ratings, time to milestone
- `GET /api/training/time-management` - Analyzes clock usage from games
- `GET /api/training/fast-thinking` - Calculation speed analysis with tips
- `GET /api/training/puzzles` - Personalized puzzles based on weaknesses
- `POST /api/training/puzzles/{index}/solve` - Track puzzle attempts

**Features:**
1. **Rating Trajectory Card**
   - Current platform rating (Chess.com/Lichess Rapid/Blitz/Bullet)
   - Projected ratings (1 month, 3 months, 6 months)
   - Time to next milestone (1200 → 1400 → 1600, etc.)
   - Rating potential from fixing specific weaknesses
   - Improvement velocity tracking

2. **Time Management Analysis**
   - Clock usage breakdown by game phase (opening/middlegame/endgame)
   - Time trouble detection
   - Personalized recommendations

3. **Fast Thinking / Calculation Training**
   - Pattern recognition analysis
   - Speed issue identification
   - Targeted tips based on weaknesses
   - Personalized puzzle trainer with weakness-based puzzles

---

## API Endpoints Reference

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/session` | POST | Web OAuth session exchange |
| `/api/auth/google/mobile` | POST | Mobile OAuth with Google access token |
| `/api/auth/me` | GET | Get current user |
| `/api/auth/logout` | POST | Sign out |

### Rating & Training (NEW)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rating/trajectory` | GET | Rating predictions & milestones |
| `/api/training/time-management` | GET | Clock usage analysis |
| `/api/training/fast-thinking` | GET | Calculation speed analysis |
| `/api/training/puzzles` | GET | Personalized puzzles |
| `/api/training/puzzles/{index}/solve` | POST | Track puzzle attempt |

### Games & Analysis
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/games` | GET | User's games list |
| `/api/games/:id` | GET | Single game details |
| `/api/analysis/:id` | GET | AI analysis for game |
| `/api/analyze-game` | POST | Trigger AI analysis |
| `/api/import-games` | POST | Import from Chess.com/Lichess |

### Journey & Dashboard
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard-stats` | GET | Dashboard statistics |
| `/api/journey` | GET | Journey dashboard data |
| `/api/journey/sync-now` | POST | Manual sync trigger |

---

## File Structure

```
/app/
├── backend/
│   ├── server.py            # Main FastAPI app, all API endpoints
│   ├── rating_service.py    # NEW: Rating prediction, time analysis, puzzles
│   ├── player_profile_service.py
│   ├── journey_service.py
│   ├── email_service.py
│   ├── cqs_service.py
│   └── rag_service.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Journey.jsx  # Includes Rating Trajectory components
│   │   │   ├── Dashboard.jsx
│   │   │   └── GameAnalysis.jsx
│   │   └── components/
│   │       └── RatingTrajectory.jsx  # NEW: Web rating components
└── mobile/
    ├── app/
    │   ├── (tabs)/
    │   │   ├── journey.js   # Includes Rating Trajectory components
    │   │   └── ...
    │   └── game/[id].js
    └── src/
        └── components/
            ├── ChessBoard.js
            └── RatingTrajectory.js   # NEW: Mobile rating components
```

---

## Testing Status
- Backend tests: 18/18 passed (iteration_7.json)
- All new endpoints properly require authentication
- Response structures verified via code review

---

## Upcoming Tasks (P0 - High Priority)
1. **Parent Dashboard**: Simplified view for parents with WhatsApp-sharable weekly reports
2. **Hindi/Hinglish Coaching**: AI coach commentary in Hindi for Indian market

## Upcoming Tasks (P1 - Medium Priority)
1. **Opening Repertoire Builder**: Build and practice personalized opening tree
2. **Offline Caching**: Cache games and analysis for offline viewing (mobile)

## Future Tasks (P2 - Lower Priority)
1. **Freemium Model**: 5 free analyses/month, subscription for unlimited
2. **"Coach Call"**: AI-generated weekly video summary
3. **"Prepare for Opponent"**: Analyze opponent's games
4. **Social Features**: Leaderboards, achievement sharing
5. **B2B Academy Dashboard**: School/academy management

---

## 3rd Party Integrations

| Integration | Status | Key Source |
|-------------|--------|------------|
| OpenAI GPT-5.2 | ✅ Active | Emergent LLM Key |
| OpenAI TTS | ✅ Active | Emergent LLM Key |
| Chess.com API | ✅ Active | Public API |
| Lichess API | ✅ Active | Public API |
| Google OAuth (Web) | ✅ Active | Emergent-managed |
| Google OAuth (Mobile) | ✅ Active | expo-auth-session |
| SendGrid Email | ⚠️ Needs key | Placeholder in .env |
| Expo Push | ✅ Active | expo-notifications |

---

Last Updated: December 2025
