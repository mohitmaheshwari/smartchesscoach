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

### Session Update: March 6, 2026 (Continued - Session 2)

#### COMPLETED IN THIS SESSION ✅

1. **Rolling Evolution System** (Replaces baseline-based progress)
   - Created `/app/backend/services/rolling_evolution_service.py`
   - Three comparison windows:
     - Macro: 25 vs 25 games (monthly trend)
     - Medium: 10 vs 10 games (bi-weekly trend)
     - Micro: 5 vs 5 games (weekly trend)
   - Automatic trend detection (improving/declining/stable)
   - API endpoint: `GET /api/progress/evolution`

2. **Opening Evolution Tracking**
   - Created `/app/backend/services/opening_evolution_service.py`
   - Tracks: "Openings improving" vs "Openings not working"
   - Extracts openings from PGN when not stored in DB
   - Generates actionable recommendations
   - API endpoint: `GET /api/progress/openings`

3. **Game Tagging System (Foundation)**
   - Created `/app/backend/services/game_tagging_service.py`
   - 40+ tag definitions: one_move_blunder, hung_piece, captured_in_fork, missed_back_rank_mate, etc.
   - Rating-appropriate filtering (beginners see different tags than experts)
   - Phase detection (opening/middlegame/endgame)
   - Theory linking for each tag type
   - Integrated into critical moment generation in server.py

4. **Server.py Refactoring (6% complete)**
   - Auth routes: `/app/backend/routes/auth.py`
   - Feedback routes: `/app/backend/routes/feedback.py`

5. **GuidedAnalysis Enhanced to 9.5/10**
   - 50+ coach personality phrases
   - Pattern-specific tips
   - Session completion celebration
   - Feedback integration

### Core Features ✅

#### 1. COMPLETE Auto-Correction System ✅ (100% Done)
**Three-Layer Architecture:**
1. **Deep Position Analyzer** (`deep_position_analyzer.py`) - Real chess analysis using python-chess
2. **Smart Pattern Matcher** (`smart_pattern_matcher.py`) - Queries DB, matches new positions  
3. **Match History** (`pattern_match_history` collection) - Records every successful match

**Complete Flow:**
```
User feedback → Deep analysis → Store pattern → 
New position → Query DB → Match → Return explanation → Record history
```

**Collections:**
- `smart_patterns` - Deep chess analysis patterns with match criteria
- `pattern_match_history` - Every match recorded for analytics
- `pattern_feedback` - User feedback storage
- `learned_rules` - AI-generated classification rules

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

### 1. COMPLETE AUTO-CORRECTION SYSTEM ✅ (CRITICAL - Finally Done!)

**The auto-correction loop is now 100% complete:**

```
BEFORE (Broken):
User feedback → Store pattern → ❌ Never used again

AFTER (Working):
User feedback → Deep position analysis → Store smart pattern → 
New position → Query DB → Match criteria → Return learned explanation ✅
```

**How it works:**
1. User clicks "Not helpful" and says "knight forks my king and rook"
2. `deep_position_analyzer.py` analyzes the ACTUAL position:
   - Finds knight on c7
   - Finds king on e8, rook on a8
   - Understands geometry: "knight on c7 attacks king and rook simultaneously"
3. Stores in `smart_patterns` collection with match criteria
4. Future position comes in → `_check_learned_patterns_sync()` queries DB
5. If pattern matches → Return learned explanation

**Key Files:**
- `deep_position_analyzer.py` - Real chess analysis (python-chess, NOT LLM)
- `smart_pattern_matcher.py` - Queries DB and matches new positions
- `cognitive_gap_service.py` - Calls learned pattern check FIRST

**Database Collections:**
- `smart_patterns` - Learned patterns with match criteria
- Match criteria examples:
  - Fork: `{attacker_piece: "knight", min_targets: 2, target_pieces: ["king", "rook"]}`
  - King trapped: `{king_on_back_rank: true, max_escape_squares: 0, blocked_by_own_pieces: true}`

**Verified Working:**
- Submitted feedback on position A (knight fork on c7)
- Tested on position B (knight fork on d6, different pieces)
- System correctly matched the pattern and returned learned explanation

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

### P0 - Continue Refactoring server.py (IN PROGRESS - 6% done)
- `server.py` is over 14,000 lines - only ~18 endpoints extracted so far
- Next priority route files to create:
  - `/routes/games.py` - Game import, listing, analysis (~40 endpoints)
  - `/routes/coach.py` - Coach state, memory, play with coach (~50 endpoints)
  - `/routes/lab.py` - Lab analysis endpoints (~20 endpoints)
  - `/routes/training.py` - Training and puzzle endpoints (~20 endpoints)
  - `/routes/reflect.py` - Reflection engine endpoints (~15 endpoints)

### P1 - Enhance Other Pages to 9.5/10
- **Reflect Page**: Add coach encouragement, progress animations
- **Prescribed Training**: Add "Why this puzzle?" messaging, celebrations
- **Play with Coach**: Memory of past games, visual move hints

### P2 - Production Hardening
- Pattern validation layer (require 2-3 similar feedbacks before rule creation)
- Human review queue for low-confidence patterns
- Confidence decay for unused rules

### P3 - B2B Coaching Model
- Coach portal with student dashboard
- Add/invite students
- Assign prescribed training

### P4 - Weekly Progress Report
- "Last week: 5 missed threats. This week: 3."
- Email/WhatsApp notification

---

## Code Architecture (Updated)

```
/app/backend/
├── routes/
│   ├── __init__.py       # Module documentation
│   ├── auth.py           # NEW: Auth endpoints (10 endpoints)
│   └── feedback.py       # NEW: Pattern learning endpoints (8 endpoints)
├── server.py             # MONOLITH: Still 14,400+ lines, ~295 endpoints
├── services/
│   ├── blunder_intelligence/
│   │   ├── cognitive_gap_service.py
│   │   └── deep_position_analyzer.py
│   ├── pattern_learning/
│   │   ├── auto_correction_service.py
│   │   └── smart_pattern_matcher.py
│   └── coach_engine/
│       └── coach_personality.py
└── tests/
    └── test_auth_and_feedback_routes.py  # NEW

/app/frontend/
├── src/
│   ├── components/
│   │   ├── GuidedAnalysis.jsx    # ENHANCED: Coach personality, tips, feedback
│   │   └── InlineFeedbackButton.jsx
│   └── pages/
│       └── Lab.jsx               # Integrated GuidedAnalysis mode
└── tests/e2e/
    └── guided-analysis.spec.ts   # NEW: 9 E2E tests
```

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
