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
| CoachPlay | 90/100 | ✅ Hallucination fix, position-specific advice |

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

## Recent Changes (Mar 6, 2026)

### 1. Play with Coach - LLM Hallucination Fix ✅ (Critical)
**Problem:** Coach was giving incorrect opening claims (e.g., "h3 is Italian Game") and generic nonsensical advice.

**Root Causes Fixed:**
1. Missing `logger` import in `coach_commentary.py` - caused silent failures
2. Fast path in `generate_response_to_user()` was bypassing move analysis when user asked about specific moves
3. Phrase patterns for move detection were incomplete
4. **Opening attribution bug:** Coach was saying "I played d5. This is the Sicilian Defense" when d5 was just a continuation move, not the defining move (c5 defines Sicilian)

**Solution:**
- Added `import logging` and `logger = logging.getLogger(__name__)` to `coach_commentary.py`
- Modified fast path to skip when `asking_about_last_move` is true
- Added phrase patterns: `"i played"`, `"why did i"`, `"was h"`, `"was my h"`, `"was my move"`
- Fixed `generate_opening_plan_question()` to only say "This is the X" for identifying moves; uses "We're in the X" for continuation moves
- Now correctly routes to `position_strategy_analyzer.py` for Stockfish-based analysis

**Tests Created:**
- `/app/backend/tests/test_coach_chat_hallucinations.py` - 20 tests for no hallucinations
- `/app/tests/e2e/coach-chat.spec.ts` - Frontend integration tests

### 2. Frontend Bug Fix - Chat Send Button & Feedback Button
- Fixed `onClick={sendChatMessage}` passing event object instead of null
- Changed to `onClick={() => sendChatMessage()}`
- **Fixed feedback button not showing**: `pollCoachMessages()` was stripping the `id` field when mapping messages
- Now preserves `id`, `question`, and `context` fields for feedback button to work
- Chat responses now generate client-side IDs for feedback

### 5. Opening Teaching Database ✅
**Built our own curated knowledge base - no Lichess dependency!**

Created `/app/backend/coach_engine/opening_teaching_db.py`:
- 12 key positions seeded with rich teaching content
- Covers: Starting position, e4 responses (e5, c5, e6, c6), Italian, Sicilian, French, Caro-Kann, Queen's Gambit, London
- Each move has:
  - Teaching message (conversational, question-based)
  - Explanation (the "why")
- Uses MongoDB for fast lookups
- Falls back to `opening_plans.py` if position not in DB

**Example Teaching:**
- "1...c5 - The Sicilian Defense! The most popular and aggressive response. You fight for the d4 square from the side. Combative!"
- "3.Bc4 - The Italian Game! Your bishop aims at f7 - the weakest point in Black's camp."

**Why our own DB instead of Lichess:**
- No rate limits for concurrent users
- Higher quality, curated teaching (pedagogically designed)
- Works offline
- Can expand over time

### 3. Merged Progress & Journey Pages (Dec 5, 2025)
- Created `UnifiedProgress.jsx`
- Combined quick stats, main weakness, three tabs (Now/Journey/Trend)
- `/journey` now redirects to `/progress`

### 4. Position-Specific Reflection Fix
- Cognitive gap analysis now detects mate-level blunders
- Shows specific explanations instead of generic advice

### 5. Auto-Correction System Sync
- FeedbackModal on Lab, Reflect, CoachPlay
- Messages now have IDs for feedback button

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

*Last Updated: March 6, 2026*
