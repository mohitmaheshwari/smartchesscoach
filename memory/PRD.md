# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized, data-driven chess coaching application. The coach should feel like a calm, direct, Indian mentor - not a simple move-suggester.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)
- **Engine Version:** P2.8 (Step 10 Complete)

---

## What's Been Implemented

### Core Features ✅

#### 1. Self-Learning Pattern Recognition System
A self-correcting AI system that learns from user feedback to improve mistake classification accuracy.
- Stockfish = Source of Truth (WHAT happened)
- AI = Translator (HOW to explain it)
- Cross-user learning: corrections propagate to all users with similar patterns

#### 2. "95/100" Home Page ✅ (Mar 6, 2026)
- Personal greeting with specific behavioral patterns ("28x you missed opponent's threats this week")
- Progress trends and session continuity
- Games to Reflect queue with opponent names and blunder counts
- Active Focus card

#### 3. Lab Page "Human Coach" Vision ✅ (Mar 6, 2026)
- "Where It Went Wrong" section with specific move comparisons
- Position-specific strategic analysis (not generic advice)
- Decision Protocol checklist
- Alternate Timeline with "Practice this" button
- "What can I learn here?" expandable sections

#### 4. Prescribed Training (Improvement Engine) ✅ (Mar 6, 2026)
The core "Improvement Loop" connecting diagnosis to training:
- Diagnoses user's primary weakness (e.g., "missed_threat")
- Fetches puzzles from user's OWN games
- Shows coaching context: what was played vs. what was better
- "FROM YOUR GAME" badges with threat information
- Progress tracking (solved count, accuracy)

#### 5. Reflect Page ✅ (Mar 6, 2026)
- Moment-by-moment game reflection
- Quick select options for user thinking
- "Show on board" feature
- Free text input for custom explanations

#### 6. Play with Coach Mode ✅
- Live coaching during games
- Opening teaching (first 12 moves)
- Socratic questions with clickable answers
- Practice mode from Alternate Timeline positions

---

## Key API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/home-intelligence/v2` | Powers Home page with patterns |
| `GET /api/lab/{game_id}` | Lab page with biggest_blunder data |
| `GET /api/lab/deep-strategy-analysis` | Position-specific insights |
| `GET /api/training/prescribed/{weakness}` | Prescribed training puzzles |
| `POST /api/training/puzzle-attempt` | Record puzzle attempt |
| `GET /api/reflect/pending` | Games needing reflection |

---

## Pending User Verification

1. **Reflect Page Flow** - Test completing a moment and progressing to the next
2. **Puzzle Display Bug** - If "piece not on board" issue occurs, report specific puzzle
3. **Prescribed Training** - Verify puzzles from own games are helpful

---

## Upcoming Tasks

### P0 - Phase 2: Full "Play with Coach" UI/UX
- Socratic questions with visual cues (arrows on board)
- More interactive response options
- Better coaching message formatting

### P1 - Weekly Progress Report
- View or notification showing progress over time
- "Last week: 5 missed threats. This week: 3. You're improving."
- Email/WhatsApp notification option

### P2 - Lab Integration for Coach Events
- Replay CoachEvent log from "Play with Coach" sessions
- Interactive post-game review of live coaching moments

---

## Future Tasks (Backlog)

### B2B Coaching Model (Researched, Not Started)
- Coach portal with student dashboard
- Add/invite students
- View all students' weaknesses and progress
- Assign prescribed training to students
- Revenue model: $19-49/month coach subscription

### Other Future Items
- Data Observation & Tuning for WisdomLibrary
- Identity Formation Layer (long-term playstyle feedback)
- Mobile App
- Proactive "Game Plan" before games

---

## Technical Architecture

```
/app
├── backend/
│   ├── coach_engine/
│   │   ├── wisdom_library.py (16 V1 rules)
│   │   ├── piece_metrics.py
│   │   ├── rule_validator.py
│   │   └── teaching_engine.py
│   ├── services/
│   │   ├── pattern_learning/
│   │   ├── home/ (home_intelligence_service_v2.py)
│   │   ├── blunder_intelligence/
│   │   │   ├── blunder_intelligence_service.py
│   │   │   └── deep_strategy_analyzer.py
│   │   └── coaching_puzzle_service.py
│   └── server.py
└── frontend/
    └── src/
        ├── components/
        │   └── lab/
        │       └── AlternateTimeline.jsx
        └── pages/
            ├── CoachHome.jsx
            ├── Lab.jsx
            ├── CoachPlay.jsx
            ├── Reflect.jsx
            └── PrescribedTraining.jsx
```

---

## 3rd Party Integrations

| Service | Purpose |
|---------|---------|
| Stockfish | Core chess analysis |
| OpenAI GPT-4o | Pattern Learner AI, Deep Strategy Analyzer |
| Lichess Public API | Opening names, puzzle database |

---

## Testing Status

- Latest test report: `/app/test_reports/iteration_96.json`
- Backend: 100% passing
- Frontend: 100% passing
- All core features tested via testing_agent_fork

---

## Key Principles

1. **NO HALLUCINATION**: Stockfish is source of truth. AI explains, doesn't invent.
2. **IMPROVEMENT LOOP**: Connect diagnosis to training (don't just identify weaknesses, fix them)
3. **POSITION-SPECIFIC**: No generic advice like "trade pieces when ahead"
4. **HUMAN COACH FEEL**: Conversational, personal, remembers patterns

---

*Last Updated: December 5, 2025*
