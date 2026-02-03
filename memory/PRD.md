# Chess Coach AI - Product Requirements Document

## Original Problem Statement
Build an AI coach based chess app that understands context and trains mistakes like a human coach. It remembers mistakes, guides accordingly in human-based language. Integrates with Chess.com and Lichess, imports games, understands playing style, and trains accordingly.

## User Choices
- AI: Emergent LLM key (GPT-5.2)
- Integrations: Chess.com + Lichess
- Auth: Google social login (Emergent OAuth)
- Theme: Dark/Light toggle

## Architecture
- **Frontend**: React + TailwindCSS + Shadcn UI
- **Backend**: FastAPI + Motor (async MongoDB)
- **Database**: MongoDB with RAG embeddings + PlayerProfile
- **AI**: GPT-5.2 via Emergent integrations

## Core Requirements (Static)
1. Import games from Chess.com/Lichess by username
2. AI-powered game analysis with human-like commentary
3. Pattern recognition for recurring mistakes
4. Memory system (RAG) for contextual coaching
5. Dark/Light theme support
6. Google OAuth authentication
7. **PlayerProfile** - First-class coaching profile per user
8. **Strict Explanation Contract** - No engine language, human-only advice
9. **Deterministic Habit Tracking** - Rule-based with 30-day time decay

## Database Collections (9 total)
1. users - User profiles
2. user_sessions - Auth sessions
3. games - Imported chess games
4. game_analyses - AI analysis results with explanation contract
5. mistake_patterns - Recurring weaknesses (legacy, RAG support)
6. game_embeddings - RAG vectors for games
7. pattern_embeddings - RAG vectors for patterns
8. analysis_embeddings - RAG vectors for analyses
9. **player_profiles** - First-class coaching profiles (NEW)

## Phase 1 Implementation (Dec 2025) ✅
### PlayerProfile Collection
- Stores estimated level, ranked weaknesses with decay, strengths
- Learning style (concise/detailed), coaching tone (firm/encouraging/balanced)
- Improvement trend tracking (improving/stuck/regressing)
- Challenge mode success tracking for weakness resolution

### Coaching Explanation Contract
Every mistake explanation follows strict schema:
- `thinking_error`: What mental mistake occurred
- `why_it_happened`: Root cause
- `what_to_focus_on_next_time`: Actionable focus
- `one_repeatable_rule`: Simple rule to remember
- **FORBIDDEN**: Move lists, engine language, centipawn scores

### Deterministic Habit Tracking
- 30-day decay window: `score = count × e^(-days/30)`
- Predefined categories only (tactical, strategic, king_safety, opening_principles, endgame_fundamentals, psychological)
- Weakness auto-resolves when challenge success > 70%

### New API Endpoints
- GET `/api/profile` - Full coaching profile
- GET `/api/profile/weaknesses` - Top weaknesses with decay
- GET `/api/profile/strengths` - Identified strengths
- PATCH `/api/profile/preferences` - Update learning/tone preferences
- POST `/api/profile/challenge-result` - Record puzzle result
- GET `/api/weakness-categories` - All predefined categories

## P0 Features (Done)
- Game import from both platforms
- AI analysis with context
- RAG-based memory system
- **PlayerProfile system with habit tracking**
- **Strict coaching explanation contract**

## P1 Features (In Progress)
- Interactive chess board visualization (has bug - awaiting verification)
- Challenge mode feedback loop
- Progress & reinforcement summaries
- Voice-ready explanation fields

## P2 Features (Future)
- Daily challenge mode (3 personalized puzzles)
- Keyboard shortcuts for move navigation
- Opening name detection
- Move sound effects

## Key Files
- `/app/backend/server.py` - Main API with all endpoints
- `/app/backend/rag_service.py` - RAG pipeline
- `/app/backend/player_profile_service.py` - PlayerProfile & habit tracking (NEW)
- `/app/memory/PHASE1_SCHEMA_REVIEW.md` - Schema documentation for review
