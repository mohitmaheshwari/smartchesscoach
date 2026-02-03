# Chess Coach AI - Product Requirements Document

## Original Problem Statement
Build an AI coach based chess app that understands context and trains mistakes like a human coach. It remembers mistakes, guides accordingly in human-based language.

## User Choices
- AI: Emergent LLM key (GPT-5.2)
- Integrations: Chess.com + Lichess
- Auth: Google social login (Emergent OAuth)
- Theme: Dark-first (Dynamic dark/light)
- Voice: OpenAI TTS for coaching
- Email: SendGrid (API key pending)
- Design: Premium UI (Linear/Stripe inspired)

## Architecture
- **Frontend**: React + TailwindCSS + Shadcn UI + Framer Motion
- **Backend**: FastAPI + Motor (async MongoDB)
- **Database**: MongoDB with RAG embeddings
- **AI**: GPT-5.2 via Emergent integrations
- **Voice**: OpenAI TTS
- **Email**: SendGrid

## Completed Features (Dec 2025)

### Core Features ✅
- Game import from Chess.com/Lichess
- AI analysis with coach persona
- RAG-based memory system
- PlayerProfile with habit tracking
- Interactive chessboard
- Voice coaching (TTS)
- Coach Quality Score (internal)

### Auto-Analysis System ✅
- **Background Sync**: Every 6 hours, automatically fetches new games
- **Auto AI Analysis**: Games are automatically analyzed with GPT-5.2 when imported
- **Best Move Suggestions**: AI suggests better moves for blunders/mistakes
- **Profile Updates**: Player profile automatically updated with weaknesses

### Bug Fixes (This Session) ✅
- **Fixed Strengths Bug**: Added validation to filter out weakness patterns being incorrectly stored as strengths
- **Cleared Bad Data**: Removed incorrectly classified "strengths" from profiles

### New Features (This Session) ✅
- **Best Move Display**: Move analysis now shows suggested better moves for mistakes
- **Strength Validation**: AI prompt and backend validation ensure only positive patterns are stored as strengths

### Premium UI (Phase 1) ✅
- Redesigned Journey + Dashboard pages
- Framer-motion animations
- Premium components (ProgressRing, StatusBadge, TrendIndicator)

## Key API Endpoints
- `/api/journey` - Journey Dashboard data
- `/api/journey/sync-now` - Manual sync + auto-analysis
- `/api/analyze-game` - Manual AI analysis with best move suggestions
- `/api/settings/email-notifications` - Email preferences

## P2 Features (Future)
- Daily Challenge Mode
- Phase 2: Game Analysis page redesign
- Phase 3: Landing page redesign

## Technical Notes
- `auto_analyze_game()` function in journey_service.py handles automatic analysis
- Strength validation filters out patterns containing: blunder, miss, poor, weak, not_, ignore, etc.
- Best move suggestions stored in `best_move_suggestions` array in analysis document
- Background sync runs every 6 hours with MAX_GAMES_PER_DAY = 2

## Key Files
- `/app/backend/journey_service.py` - Auto-sync + auto-analysis logic
- `/app/backend/player_profile_service.py` - Strength validation
- `/app/backend/server.py` - API endpoints, AI prompts
- `/app/frontend/src/pages/GameAnalysis.jsx` - Best move display
