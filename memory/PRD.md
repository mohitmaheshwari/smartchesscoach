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
- **Database**: MongoDB with RAG embeddings
- **AI**: GPT-5.2 via Emergent integrations

## Core Requirements (Static)
1. Import games from Chess.com/Lichess by username
2. AI-powered game analysis with human-like commentary
3. Pattern recognition for recurring mistakes
4. Memory system (RAG) for contextual coaching
5. Dark/Light theme support
6. Google OAuth authentication

## What's Been Implemented (Feb 2, 2026)
- [x] Landing page with hero section
- [x] Google OAuth authentication flow
- [x] Dashboard with stats overview
- [x] Import games from Chess.com API
- [x] Import games from Lichess API
- [x] AI game analysis with GPT-5.2
- [x] Mistake pattern tracking
- [x] Weakness tracker page
- [x] Training recommendations
- [x] Settings page with theme toggle
- [x] **RAG Pipeline Implementation**:
  - Game chunking (opening/middlegame/endgame/summary)
  - Vector embeddings for semantic search
  - Pattern embeddings for weakness matching
  - Contextual AI coaching with historical awareness

## Database Collections (8 total)
1. users - User profiles
2. user_sessions - Auth sessions
3. games - Imported chess games
4. game_analyses - AI analysis results
5. mistake_patterns - Recurring weaknesses
6. game_embeddings - RAG vectors for games
7. pattern_embeddings - RAG vectors for patterns
8. analysis_embeddings - RAG vectors for analyses

## P0 Features (Done)
- Game import from both platforms
- AI analysis with context
- RAG-based memory system

## P1 Features (Backlog)
- Interactive chess board visualization
- Move-by-move replay with AI commentary
- Spaced repetition for weakness training
- Rating progress tracking

## P2 Features (Future)
- Real-time game analysis
- Opening repertoire builder
- Endgame trainer
- Community features

## Next Tasks
1. Add interactive chess board component
2. Implement move replay with highlighting
3. Add more detailed pattern categorization
4. Performance optimizations for large game libraries
