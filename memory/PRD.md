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

#### 1. Self-Learning Pattern Recognition (Auto-Correction)
- "Not helpful" feedback buttons on Lab, Reflect, and CoachPlay pages
- Cross-user learning: corrections propagate to all users
- Stockfish = Source of Truth, AI = Translator

#### 2. Home Page "95/100" ✅
- Personal greeting with specific patterns ("28x missed threats this week")
- "Start Training" button - Auto-routes to Prescribed Training
- Games to Reflect queue

#### 3. Lab Page "Human Coach" Vision ✅
- Position-specific strategic analysis (e.g., "Re1+ was checkmate")
- "Not helpful / Wrong explanation?" feedback button
- "Play the better line" and "Show why it's bad" buttons

#### 4. Prescribed Training (Improvement Engine) ✅
- Diagnoses primary weakness
- Fetches puzzles from user's OWN games
- Progress tracking

#### 5. Unified Progress Page ✅ (Dec 5, 2025)
**Merged /progress and /journey into one unified page:**
- `/progress` → Shows unified page
- `/journey` → Redirects to `/progress`

**Structure:**
- Header with coaching vibe ("Steady progress")
- Quick Stats: Accuracy + Blunders/Game
- Main Leak: "28x missed threat" + "Train This Now"
- Three Tabs:
  - **Now:** Consistency, When winning, Weakest phase, Habits, Coach's Focus
  - **Journey:** Voice headline, Before→After stats, Next Milestone
  - **Trend:** Momentum, What's Changing, Evidence links
- Playing Identity (expandable)
- Quick Actions: Reflect, Today's Focus

---

## Page Quality Ratings

| Page | Rating | Status |
|------|--------|--------|
| Home | 95/100 | ✅ Human coach feel |
| Lab | 90/100 | ✅ Position-specific, feedback enabled |
| Reflect | 85/100 | ✅ Specific explanations, feedback enabled |
| Progress | 90/100 | ✅ Unified, coaching narrative |
| CoachPlay | 80/100 | ✅ Guardian + feedback |

---

## Routing Reference

| Route | Component |
|-------|-----------|
| `/home` | CoachHome.jsx |
| `/lab/game/:id` | Lab.jsx |
| `/reflect` | Reflect.jsx |
| `/progress` | UnifiedProgress.jsx |
| `/journey` | Redirects to `/progress` |
| `/training/prescribed` | PrescribedTraining.jsx |
| `/play-with-coach` | CoachPlay.jsx |

---

## Recent Changes (Dec 5, 2025)

### 1. Merged Progress & Journey Pages
- Created `UnifiedProgress.jsx`
- Combined quick stats, main weakness, three tabs (Now/Journey/Trend)
- `/journey` now redirects to `/progress`

### 2. Position-Specific Reflection Fix
- Cognitive gap analysis now detects mate-level blunders
- Shows specific explanations instead of generic advice

### 3. Auto-Correction System Sync
- FeedbackModal on Lab, Reflect, CoachPlay
- Consistent feedback submission

---

## Upcoming Tasks

### P0 - B2B Coaching Model (Researched)
- Coach portal with student dashboard
- Add/invite students
- Assign prescribed training

### P1 - Weekly Progress Report
- "Last week: 5 missed threats. This week: 3."
- Email/WhatsApp notification

---

## Key Principles

1. **NO HALLUCINATION**: Stockfish is source of truth
2. **POSITION-SPECIFIC**: Say exactly what threat was missed
3. **COACHING NARRATIVE**: Tell a story, not show a dashboard
4. **AUTO-CORRECTION**: User feedback improves system
5. **SINGLE SOURCE OF TRUTH**: One page for progress, not two

---

*Last Updated: December 5, 2025*
