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

#### 1. COMPLETE Self-Learning Pattern Recognition System ✅ (Mar 6, 2026)
**The auto-correction system is now FULLY implemented with generalizable rule learning:**

**Two-Layer Rule System:**
1. **`pattern_rules` collection** - Stores generalizable position-based rules (king safety, back rank, forks)
2. **`learned_rules` collection** - Stores AI-generated classification rules from GPT-4o

**How it works:**
1. User clicks "Not helpful" on Lab, Reflect, or CoachPlay
2. System immediately generates corrected explanation
3. `pattern_rule_extractor.py` analyzes position features (king on back rank, escape squares, etc.)
4. Creates a GENERALIZABLE rule that applies to similar future positions
5. `cognitive_gap_service.py` checks these rules FIRST before own analysis
6. AI-powered learner also creates classification rules for complex patterns

**Key Files:**
- `backend/services/pattern_learning/pattern_rule_extractor.py` - Feature-based rule extraction
- `backend/services/pattern_learning/auto_correction_service.py` - Main orchestrator
- `backend/cognitive_gap_service.py` - Uses learned rules in analysis

**Collections:**
- `pattern_rules` - Position-feature based rules
- `learned_rules` - AI-generated classification rules
- `pattern_feedback` - User feedback storage
- `verified_corrections` - Validated corrections cache

**API Endpoints:**
- `POST /api/coach/pattern-learning/feedback` - Submit feedback
- `GET /api/coach/pattern-learning/my-feedback` - View user's feedback history
- `GET /api/coach/pattern-learning/stats` - System statistics
- `POST /api/coach/pattern-learning/classify` - Classify using learned rules

#### 2. Home Page "95/100" ✅
- Personal greeting with specific patterns ("28x missed threats this week")
- "Start Training" button - Auto-routes to Prescribed Training
- Games to Reflect queue

#### 3. Lab Page "Human Coach" Vision ✅
- Position-specific strategic analysis (e.g., "Re1+ was checkmate")
- "Not helpful / Wrong explanation?" feedback button on ALL commentary
- "Play the better line" and "Show why it's bad" buttons
- "My Feedback" button to view submission history

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
| Lab | 95/100 | ✅ Position-specific, full feedback system |
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

### 1. COMPLETE Self-Learning System Integration ✅ (Critical)
**Problem:** Previous "auto-correction" system only fixed one position but didn't learn generalizable rules.

**Solution - Two Systems Now Working Together:**
1. **Pattern Rule Extractor** - Analyzes position features and creates rules like `KING_SAFETY_LUFT`
2. **AI Pattern Learner** - Uses GPT-4o to generate complex classification rules

**Integration Points:**
- `auto_correction_service.py` now calls `pattern_rule_extractor.py` when feedback is submitted
- `cognitive_gap_service.py` checks `pattern_rules` collection FIRST before analysis
- Position features (king_on_back_rank, escape_squares, etc.) are analyzed synchronously

**Test Coverage:**
- `/app/backend/tests/test_pattern_learning_system.py` - 8 tests covering:
  - Position feature extraction
  - User insight classification
  - End-to-end feedback → rule creation
  - Cognitive gap integration

### 2. Play with Coach - LLM Hallucination Fix ✅
**Problem:** Coach was giving incorrect opening claims (e.g., "h3 is Italian Game") and generic nonsensical advice.

**Root Causes Fixed:**
1. Missing `logger` import in `coach_commentary.py` - caused silent failures
2. Fast path in `generate_response_to_user()` was bypassing move analysis
3. Opening attribution bug fixed

### 3. Opening Teaching Database ✅
**Built our own curated knowledge base - no Lichess dependency!**
- 12 key positions seeded with rich teaching content
- Uses MongoDB for fast lookups

### 4. Frontend Bug Fix - Chat Send Button & Feedback Button
- Fixed `onClick={sendChatMessage}` passing event object instead of null
- Fixed feedback button not showing on chat messages

---

## Upcoming Tasks

### P0 - Refactor Monolithic server.py (CRITICAL)
- `server.py` is over 14,000 lines and handles nearly all backend logic
- Break down into domain-specific route files:
  - `/routes/coach.py`
  - `/routes/lab.py`
  - `/routes/feedback.py`
  - `/routes/games.py`

### P1 - B2B Coaching Model
- Coach portal with student dashboard
- Add/invite students
- Assign prescribed training

### P2 - Weekly Progress Report
- "Last week: 5 missed threats. This week: 3."
- Email/WhatsApp notification

---

## Key Principles

1. **NO HALLUCINATION**: Stockfish is source of truth
2. **POSITION-SPECIFIC**: Say exactly what threat was missed
3. **COACHING NARRATIVE**: Tell a story, not show a dashboard
4. **AUTO-CORRECTION**: User feedback improves system FOR ALL USERS
5. **GENERALIZABLE LEARNING**: Don't just fix one position - learn patterns
6. **SINGLE SOURCE OF TRUTH**: One page for progress, not two

---

*Last Updated: March 6, 2026*
