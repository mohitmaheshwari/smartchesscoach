# Chess Coach AI - Product Requirements Document

## Original Problem Statement
Build an AI coach based chess app that understands context and trains mistakes like a human coach.

## Platforms
- **Web App**: React + TailwindCSS + Shadcn UI (Complete)
- **Mobile App**: React Native + Expo (In Development)

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB)
- **Database**: MongoDB
- **AI**: GPT-5.2 via Emergent integrations
- **Voice**: OpenAI TTS
- **Email**: SendGrid

## Completed Features

### Core Features ✅
- Game import from Chess.com/Lichess
- AI analysis with coach persona
- RAG-based memory system
- PlayerProfile with habit tracking
- Interactive chessboard (web)
- Voice coaching (TTS)
- Coach Quality Score (internal)

### Auto-Analysis System ✅
- Background sync (every 6 hours)
- Auto AI analysis on import
- Best move suggestions
- Strength validation

### Premium UI (Web) ✅
- Redesigned Journey + Dashboard
- Framer-motion animations
- Dark-first theme

### Mobile App (In Progress) 🚧
Files created in `/app/mobile`:
- Dashboard screen
- Journey screen with progress tracking
- Games list with import modal
- Game analysis screen
- Settings with email notifications
- Google OAuth login flow
- Dark/light theme support

## Mobile App Structure
```
/app/mobile/
├── app/                    # Expo Router screens
│   ├── (tabs)/             # Tab navigator
│   │   ├── dashboard.js
│   │   ├── journey.js
│   │   ├── games.js
│   │   └── settings.js
│   ├── game/[id].js        # Game analysis
│   └── login.js
├── src/
│   ├── context/            # Auth + Theme providers
│   ├── services/api.js     # Backend API calls
│   └── constants/config.js
└── package.json
```

## To Run Mobile App
```bash
cd /app/mobile
npm install
npm start
# Scan QR code with Expo Go app
```

## Next Steps for Mobile
1. Add interactive chessboard component
2. Implement push notifications
3. Add offline caching
4. Build and deploy to app stores

## Key Files
- Web: `/app/frontend/src/`
- Mobile: `/app/mobile/`
- Backend: `/app/backend/server.py`
- DB Init: `/app/backend/init_db.py`
- Migration: `/app/MIGRATION_GUIDE.md`
