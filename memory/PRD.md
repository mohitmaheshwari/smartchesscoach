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

## Completed Features

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
**Core Features Implemented:**
- Interactive chessboard with WebView (chess.js for logic)
- Google OAuth authentication (expo-auth-session)
- Push notification service (expo-notifications)
- Dashboard with stats overview
- Journey tracking with linked accounts
- Games list with import modal
- Game analysis with move-by-move review
- Settings with email/push notification preferences
- Dark/light theme support (system-aware)

## Mobile App Structure
```
/app/mobile/
├── app/                    # Expo Router screens
│   ├── (tabs)/             # Tab navigator
│   │   ├── _layout.js      # Tab configuration
│   │   ├── dashboard.js    # Stats overview
│   │   ├── journey.js      # Progress tracking
│   │   ├── games.js        # Games list + import
│   │   └── settings.js     # User preferences
│   ├── game/
│   │   └── [id].js         # Game analysis with chessboard
│   ├── login.js            # Google Sign-In
│   ├── index.js            # Entry/routing
│   └── _layout.js          # Root layout + providers
├── src/
│   ├── components/
│   │   └── ChessBoard.js   # WebView-based interactive board
│   ├── context/
│   │   ├── AuthContext.js  # Authentication state
│   │   └── ThemeContext.js # Theme state
│   ├── services/
│   │   ├── api.js          # Backend API calls (Bearer token auth)
│   │   ├── googleAuth.js   # Google OAuth helpers
│   │   └── notifications.js # Push notification setup
│   └── constants/
│       └── config.js       # API URL, colors, etc.
├── assets/                  # App icons and images
├── app.json                # Expo configuration
└── package.json            # Dependencies
```

## Key API Endpoints

### Authentication
- `POST /api/auth/session` - Web OAuth session exchange
- `POST /api/auth/google/mobile` - Mobile OAuth with Google access token
- `GET /api/auth/me` - Get current user
- `POST /api/auth/logout` - Sign out

### Games & Analysis
- `GET /api/games` - User's games list
- `GET /api/games/:id` - Single game details
- `GET /api/analysis/:id` - AI analysis for game
- `POST /api/analyze-game` - Trigger AI analysis
- `POST /api/import-games` - Import from Chess.com/Lichess

### Journey & Dashboard
- `GET /api/dashboard-stats` - Dashboard statistics
- `GET /api/journey` - Journey dashboard data
- `GET /api/journey/linked-accounts` - Connected platforms
- `POST /api/journey/link-account` - Connect platform
- `POST /api/journey/sync-now` - Manual sync trigger

### Notifications
- `POST /api/notifications/register-device` - Register push token (mobile)
- `DELETE /api/notifications/unregister-device` - Unregister device
- `GET /api/settings/email-notifications` - Email preferences
- `PUT /api/settings/email-notifications` - Update email preferences

## Testing
- Backend tests: `/app/backend/tests/`
- Test reports: `/app/test_reports/`
- Latest iteration: `/app/test_reports/iteration_6.json` (21/21 tests passed)

## Upcoming Tasks (P0 - High Priority)
1. **Parent Dashboard**: Simplified view for parents to track child's progress with sharable weekly reports
2. **Production Deployment**: Set up proper Google OAuth credentials for mobile

## Upcoming Tasks (P1 - Medium Priority)
1. **Opening Repertoire Builder**: Build and practice personalized opening tree
2. **Elo/Rating Prediction**: Projected rating based on improvement trend
3. **Offline Caching**: Cache games and analysis for offline viewing (mobile)

## Future Tasks (P2 - Lower Priority)
1. **Freemium Model**: 5 free analyses/month, subscription for unlimited
2. **Time Management Coaching**: Analyze time usage per move
3. **"Coach Call"**: AI-generated weekly video summary
4. **"Prepare for Opponent"**: Analyze opponent's games
5. **"Live Coach"**: Instant post-game analysis
6. **Social Features**: Leaderboards, achievement sharing
7. **B2B Academy Dashboard**: School/academy management

## Key Files Reference
- Web Frontend: `/app/frontend/src/`
- Mobile App: `/app/mobile/`
- Backend: `/app/backend/server.py`
- Database Init: `/app/backend/init_db.py`
- Migration Guide: `/app/MIGRATION_GUIDE.md`
- Design Guidelines: `/app/design_guidelines.json`

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

## Running the Apps

### Web App
```bash
# Already running via supervisor
# Access at: https://chesssage.preview.emergentagent.com
```

### Mobile App
```bash
cd /app/mobile
npm install
npx expo start
# Scan QR code with Expo Go app
```

### Backend
```bash
# Already running via supervisor on port 8001
# API available at: https://chesssage.preview.emergentagent.com/api
```

---
Last Updated: December 2025
