# Chess Coach AI - Product Requirements Document

## Original Problem Statement
Build an AI coach based chess app that understands context and trains mistakes like a human coach. It remembers mistakes, guides accordingly in human-based language. Integrates with Chess.com and Lichess, imports games, understands playing style, and trains accordingly.

## User Choices
- AI: Emergent LLM key (GPT-5.2)
- Integrations: Chess.com + Lichess
- Auth: Google social login (Emergent OAuth)
- Theme: Dark/Light toggle
- Voice: OpenAI TTS for coaching
- Email: SendGrid (API key to be added by user)

## Architecture
- **Frontend**: React + TailwindCSS + Shadcn UI
- **Backend**: FastAPI + Motor (async MongoDB)
- **Database**: MongoDB with RAG embeddings + PlayerProfile
- **AI**: GPT-5.2 via Emergent integrations
- **Voice**: OpenAI TTS via Emergent LLM key
- **Email**: SendGrid for notifications

## Core Requirements (Static)
1. Import games from Chess.com/Lichess by username
2. AI-powered game analysis with human-like commentary
3. Pattern recognition for recurring mistakes
4. Memory system (RAG) for contextual coaching
5. Dark/Light theme support
6. Google OAuth authentication
7. PlayerProfile - First-class coaching profile per user
8. Strict Explanation Contract - No engine language, human-only advice
9. Deterministic Habit Tracking - Rule-based with 30-day time decay
10. Coach Quality Score (CQS) - Internal quality gate for explanations
11. Voice coaching with OpenAI TTS
12. Journey Dashboard - Track learning progress over time
13. Background Game Sync - Automatic polling for new games
14. Email Notifications - Game analyzed, weekly summary, weakness alerts

## Database Collections (9 total)
1. users - User profiles + linked chess accounts + email preferences
2. user_sessions - Auth sessions
3. games - Imported chess games
4. game_analyses - AI analysis results with explanation contract
5. mistake_patterns - Recurring weaknesses (legacy, RAG support)
6. game_embeddings - RAG vectors for games
7. pattern_embeddings - RAG vectors for patterns
8. analysis_embeddings - RAG vectors for analyses
9. player_profiles - First-class coaching profiles

## Completed Features (Dec 2025)

### P0 Features ✅
- Game import from Chess.com and Lichess
- AI analysis with Indian coach persona
- RAG-based memory system
- PlayerProfile system with habit tracking
- Strict coaching explanation contract
- Interactive chessboard for game review
- Voice coaching with OpenAI TTS
- Coach Quality Score (CQS) internal gate

### P1 Features ✅
- **Journey Dashboard** - Shows weekly assessment, focus areas, weakness trends
- **Background Game Sync** - Automatic polling every 6 hours
- **Manual Sync** - "Sync Now" button for immediate sync
- Account linking UI for Chess.com/Lichess
- **Email Notifications** - Game analyzed, weekly summary, weakness alerts
- **Email Settings UI** - Toggle notifications in Settings page
- **Test Email** - Send test email to verify configuration

### Key API Endpoints
- `/api/journey` - Journey Dashboard data
- `/api/journey/linked-accounts` - Get linked accounts
- `/api/journey/link-account` - Link Chess.com/Lichess account
- `/api/journey/sync-now` - Trigger manual game sync
- `/api/analyze-game` - AI game analysis
- `/api/profile` - Player coaching profile
- `/api/tts/generate` - Voice generation
- `/api/settings/email-notifications` - GET/PUT email preferences
- `/api/settings/test-email` - POST send test email

## P2 Features (Future)
- Daily Challenge Mode (3 personalized puzzles daily)
- Keyboard shortcuts for move navigation
- Opening name detection
- Move sound effects

## Key Files
- `/app/backend/server.py` - Main API with all endpoints
- `/app/backend/rag_service.py` - RAG pipeline
- `/app/backend/player_profile_service.py` - PlayerProfile & habit tracking
- `/app/backend/cqs_service.py` - Coach Quality Score system
- `/app/backend/journey_service.py` - Journey Dashboard & sync logic
- `/app/backend/email_service.py` - Email notification service (SendGrid)
- `/app/frontend/src/pages/Journey.jsx` - Journey Dashboard UI
- `/app/frontend/src/pages/GameAnalysis.jsx` - Game analysis UI
- `/app/frontend/src/pages/Settings.jsx` - Settings with email notifications
- `/app/frontend/src/components/Layout.jsx` - Navigation layout

## Technical Notes
- Babel visual-edits plugin disabled (was causing compilation errors)
- Background sync runs every 6 hours automatically
- CQS system is internal only, not exposed to users
- react-chessboard version locked at 4.6.0
- SendGrid API key must be added by user for email notifications

## Email Configuration (PENDING USER ACTION)
To enable email notifications, add your SendGrid API key to `/app/backend/.env`:
```
SENDGRID_API_KEY=your_sendgrid_api_key_here
SENDER_EMAIL=your_verified_sender@yourdomain.com
```

Get your API key from: https://app.sendgrid.com/settings/api_keys
