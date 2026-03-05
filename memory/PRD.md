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
- "Not helpful" feedback buttons on Lab, Reflect, and CoachPlay pages
- Cross-user learning: corrections propagate to all users with similar patterns
- Stockfish = Source of Truth, AI = Translator

#### 2. Home Page "95/100" ✅
- Personal greeting with specific patterns ("28x missed threats this week")
- **"Start Training" button** - Auto-routes to Prescribed Training
- Games to Reflect queue

#### 3. Lab Page "Human Coach" Vision ✅
- Position-specific strategic analysis (e.g., "Re1+ was checkmate")
- "Not helpful / Wrong explanation?" feedback button
- "Play the better line" and "Show why it's bad" buttons

#### 4. Prescribed Training (Improvement Engine) ✅
- Diagnoses primary weakness
- Fetches puzzles from user's OWN games
- Progress tracking

#### 5. Position-Specific Reflection Feedback ✅
- Detects mate-level blunders (cp_loss >= 9000)
- Shows specific explanations with auto-correction feedback

#### 6. Journey Page - Redesigned! ✅ (Dec 5, 2025)
**Now Tab - Human Coach Style:**
- "YOUR MAIN ISSUE: Piece safety issues" with "Train This" button
- Consistency with context: "You're swinging between clean games and blunder-fests"
- Weakest phase with coaching: "The chaos of the middlegame gets you"
- Coach's Focus directive

**Journey Tab:**
- Voice headline with emotional tone
- Before → After stat comparison
- Cognitive growth tracking

**Trend Tab:**
- Momentum headline with badges
- What's changing (improving/declining)
- Evidence links to specific games

---

## Page Quality Ratings

| Page | Rating | Status |
|------|--------|--------|
| Home | 95/100 | ✅ Human coach feel |
| Lab | 90/100 | ✅ Position-specific, feedback enabled |
| Reflect | 85/100 | ✅ Specific explanations, feedback enabled |
| Journey | 85-90/100 | ✅ Redesigned with coaching narrative |
| Progress | 70/100 | ⚠️ Needs redesign (different route) |
| CoachPlay | 80/100 | ✅ Guardian + feedback |

---

## Recent Changes (Dec 5, 2025)

### 1. Journey Page Redesign
- Transformed cold stats into coaching narrative
- Added contextual explanations for each metric
- Integrated "Train This" action buttons
- Human-readable phase advice

### 2. Auto-Correction System Sync
- FeedbackModal component on all coaching pages
- Consistent feedback submission to pattern-learning API

### 3. Position-Specific Insights
- All pages now use same insight system
- Mate-level blunder detection enhanced

---

## Routing Reference

| Route | Component |
|-------|-----------|
| `/home` | CoachHome.jsx |
| `/lab/game/:id` | Lab.jsx |
| `/reflect` | Reflect.jsx |
| `/journey` | JourneyCognitive.jsx (redesigned) |
| `/progress` | JourneyIntelligence.jsx (old) |
| `/training/prescribed` | PrescribedTraining.jsx |
| `/play-with-coach` | CoachPlay.jsx |

---

## Upcoming Tasks

### P0 - B2B Coaching Model
- Coach portal with student dashboard
- Add/invite students
- Assign prescribed training

### P1 - Weekly Progress Report
- "Last week: 5 missed threats. This week: 3."
- Email/WhatsApp notification

### P2 - Route `/progress` to redesigned Progress.jsx
- Currently renders old JourneyIntelligence.jsx

---

## Key Principles

1. **NO HALLUCINATION**: Stockfish is source of truth
2. **POSITION-SPECIFIC**: Say exactly what threat was missed
3. **COACHING NARRATIVE**: Tell a story, not show a dashboard
4. **AUTO-CORRECTION**: User feedback improves system

---

*Last Updated: December 5, 2025*
