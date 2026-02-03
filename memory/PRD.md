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

## Design System (Dec 2025)
- **Typography**: Outfit (headings), Manrope (body)
- **Theme**: Dark-first, warm paper light mode
- **Animations**: Subtle micro-interactions via framer-motion
- **Philosophy**: "Calm, disciplined, warm authority" - like a coach sitting next to you
- **Colors**: Muted greens/ambers for status, no red panic colors
- **Inspiration**: Linear, Stripe, Apple Fitness

## Completed Features

### Core Features ✅
- Game import from Chess.com/Lichess
- AI analysis with Indian coach persona
- RAG-based memory system
- PlayerProfile system with habit tracking
- Interactive chessboard
- Voice coaching (TTS)
- Coach Quality Score (internal)

### Journey & Dashboard ✅
- Journey Dashboard with progress tracking
- Status badges (Improving/Stable/Focus)
- Trend indicators with arrows
- Background game sync (6 hours)
- Manual sync button

### Email Notifications ✅
- Game analyzed notifications
- Weekly summary emails
- Weakness alert emails
- Settings UI for preferences

### Premium UI (Phase 1) ✅
- Redesigned Journey page
- Redesigned Dashboard page
- New Layout with premium navigation
- Framer-motion animations
- Premium components (ProgressRing, StatusBadge, TrendIndicator)
- Dark/light theme with proper typography

## P2 Features (Future)
- Daily Challenge Mode
- Keyboard shortcuts for moves
- Sound effects
- Landing page redesign (Phase 3)
- Game Analysis page cleanup (Phase 2)

## Key Files
- `/app/frontend/src/pages/Journey.jsx` - Premium Journey Dashboard
- `/app/frontend/src/pages/Dashboard.jsx` - Premium Dashboard
- `/app/frontend/src/components/Layout.jsx` - Navigation
- `/app/frontend/src/components/ui/premium.jsx` - Premium components
- `/app/frontend/src/index.css` - Design system CSS
- `/app/frontend/tailwind.config.js` - Tailwind config
- `/app/backend/server.py` - API endpoints
- `/app/backend/email_service.py` - Email notifications

## API Endpoints
- `/api/journey` - Journey Dashboard data
- `/api/journey/sync-now` - Manual sync
- `/api/settings/email-notifications` - Email preferences
- `/api/dashboard-stats` - Dashboard stats
- `/api/analyze-game` - AI analysis

## Technical Notes
- Babel visual-edits plugin disabled
- react-chessboard locked at 4.6.0
- SendGrid API key needed for emails
- Framer-motion for animations
