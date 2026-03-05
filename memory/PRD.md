# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized, data-driven chess coaching application. The coach should feel like a calm, direct, Indian mentor - not a simple move-suggester.

## Core Architecture
- **Frontend:** React (port 3000)
- **Backend:** FastAPI (port 8001)
- **Database:** MongoDB
- **Analysis Engine:** Stockfish
- **AI Coaching:** OpenAI GPT-4o-mini (via Emergent LLM Key)

---

## What's Been Implemented

### Core Features ✅

#### 1. Self-Learning Pattern Recognition System (Auto-Correction)
A self-correcting AI system that learns from user feedback to improve mistake classification accuracy.
- Stockfish = Source of Truth (WHAT happened)
- AI = Translator (HOW to explain it)
- Cross-user learning: corrections propagate to all users with similar patterns
- **"Not helpful" feedback buttons** now on Lab, Reflect, and CoachPlay pages

#### 2. "95/100" Home Page ✅
- Personal greeting with specific behavioral patterns ("28x you missed opponent's threats this week")
- **"Start Training" button** - Auto-routes to Prescribed Training based on dominant weakness
- Progress trends and session continuity
- Games to Reflect queue with opponent names and blunder counts

#### 3. Lab Page "Human Coach" Vision ✅
- "Where It Went Wrong" section with specific move comparisons
- **Position-specific strategic analysis** (e.g., "Playing Nf5 was a mistake because it allowed your opponent to deliver a forced checkmate starting with Re1+")
- **"Not helpful / Wrong explanation?" feedback button** - enables auto-correction
- Decision Protocol checklist
- "Play the better line on board" and "Show why it's bad" buttons

#### 4. Prescribed Training (Improvement Engine) ✅
The core "Improvement Loop" connecting diagnosis to training:
- Diagnoses user's primary weakness (e.g., "missed_threat")
- Fetches puzzles from user's OWN games
- Shows coaching context: what was played vs. what was better
- Progress tracking (solved count, accuracy)

#### 5. Position-Specific Reflection Feedback ✅
- Detects mate-level blunders (cp_loss >= 9000) even when threat doesn't say "mate"
- Shows specific explanations: "You missed checkmate! After your move, opponent had Re1+ leading to checkmate."
- **"Not helpful / Wrong explanation?" feedback button** - enables auto-correction

#### 6. Play with Coach Mode ✅
- Live coaching during games with pre-move guardian
- Opening teaching (first 12 moves)
- Socratic questions with clickable answers
- "Not helpful" feedback button for pattern learning

---

## Key Components

### FeedbackModal (NEW)
Reusable feedback modal component for auto-correction system.
- Located at: `/app/frontend/src/components/FeedbackModal.jsx`
- Used in: Lab, Reflect, CoachPlay pages
- Submits to: `/api/coach/pattern-learning/feedback`

### System Sync Status (VERIFIED)
| Page | Cognitive Gap | Position-Specific | Auto-Correction |
|------|---------------|-------------------|-----------------|
| **Lab** | ✅ | ✅ | ✅ |
| **Reflect** | ✅ | ✅ | ✅ |
| **CoachPlay** | ✅ | ✅ | ✅ |

---

## Key API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/coach/home-intelligence` | Powers Home page with patterns |
| `GET /api/lab/{game_id}` | Lab page with biggest_blunder data |
| `GET /api/lab/{game_id}/deep-strategy` | Position-specific insights for Lab |
| `GET /api/training/prescribed/{weakness}` | Prescribed training puzzles |
| `POST /api/coach/pattern-learning/feedback` | Auto-correction feedback |
| `POST /api/games/{game_id}/move/{move_number}/analyze-gap` | Cognitive gap analysis |

---

## Recent Changes (Dec 5, 2025)

### Change 1: Auto-Correction System Sync
- Added `FeedbackModal` component
- Integrated "Not helpful / Wrong explanation?" button to Lab page
- Integrated same button to Reflect page
- All three pages (Lab, Reflect, CoachPlay) now use consistent feedback system

### Change 2: Position-Specific Insights Verification
- Verified Lab page shows specific threats (e.g., "Re1+ checkmate")
- Verified cognitive gap analysis uses enhanced detection for mate-level blunders
- All explanations now tied to actual board position, not generic advice

---

## Pending User Verification

1. **Feedback Modal Flow** - Test clicking "Not helpful" on Lab page
2. **Reflect Flow** - Complete a reflection and verify feedback button appears
3. **Prescribed Training** - Verify puzzles from own games are helpful

---

## Upcoming Tasks

### P0 - B2B Coaching Model (Researched)
- Coach portal with student dashboard
- Add/invite students
- View all students' weaknesses and progress
- Assign prescribed training to students

### P1 - Weekly Progress Report
- "Last week: 5 missed threats. This week: 3. You're improving."
- Email/WhatsApp notification option

### P2 - Full "Play with Coach" UI/UX
- Socratic questions with visual cues (arrows on board)
- More interactive response options

---

## Key Principles

1. **NO HALLUCINATION**: Stockfish is source of truth. AI explains, doesn't invent.
2. **POSITION-SPECIFIC**: No generic advice - say exactly what threat was missed
3. **IMPROVEMENT LOOP**: Connect diagnosis to training
4. **AUTO-CORRECTION**: User feedback improves system for everyone

---

*Last Updated: December 5, 2025*
