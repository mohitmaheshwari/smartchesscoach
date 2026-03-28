# ChessGuru System Map - Complete Architecture
**Generated:** 2025-01-XX  
**Purpose:** Complete mapping of existing systems before optimization

---

## ✅ SYSTEMS THAT ALREADY EXIST

### 1. **PLAYER IDENTITY SYSTEM** (Complete - 1,209 lines)

**Files:**
- `/backend/player_identity_engine.py` (523 lines) - Main identity computation
- `/backend/services/identity_formation_service.py` (686 lines) - Temporal tracking
- `/backend/coach_play/identity_engine.py` - Real-time identity

**What It Does:**
- ✅ Computes player identity from games (Primary archetype, traits, summary)
- ✅ **4 Identity Dimensions:**
  1. **Decision Stability:** Stable / Mixed / Volatile
  2. **Primary Leak:** Calculation depth, threat blindness, hanging pieces, tactical oversight, time pressure, etc.
  3. **Phase Vulnerability:** Opening / Middlegame / Endgame
  4. **Risk Style:** Low (cautious) / Medium (balanced) / High (aggressive)

- ✅ **Identity Labels:** "Stopping Calculation Too Early", "Tactical Opportunist", etc.
- ✅ **Collapsed Summary:** 2-3 line powerful summary
- ✅ **Expanded Sections:** 4 detailed breakdowns (Consistency, Main Leak, Phase, Style)
- ✅ **Confidence Scoring:** Based on games analyzed
- ✅ **Temporal Snapshots:** Tracks identity evolution over time
- ✅ **Change Detection:** Breakthrough, style_shift, leak_change, phase_mastery, regression
- ✅ **Archetypes:** "The Calculating Attacker", "The Impulsive Tactician", etc.

**API Endpoints:**
```
GET /coach/identity - Current identity
GET /coach/identity/evolution - Identity changes over time
GET /coach/identity/snapshots - Historical snapshots
GET /coach/identity/trajectory - Long-term trend
GET /coach/identity/insight - Identity insights
GET /coach/identity/summary - Summary view
GET /coach/play/identity - Identity for coach-play mode
```

**Status:** ✅ COMPLETE - No rebuild needed

---

### 2. **WEAKNESS TRACKING SYSTEM** (Complete - Multiple Components)

**Files:**
- `/backend/coach_memory_service.py` (640 lines) - Persistent memory
- `/backend/services/coach_memory.py` - Pattern tracking
- `/backend/services/chess_brain/fingerprint_service.py` (NEW - we added)
- `/backend/routes/cognitive.py` - Weakness API

**What It Does:**
- ✅ Tracks recurring mistakes across games
- ✅ Pattern frequency counting
- ✅ **Decay scoring** (recent mistakes weighted higher)
- ✅ Top weaknesses ranking
- ✅ Lesson memory (cooldown to avoid repetition)
- ✅ Milestone tracking (first clean game, 3-game streak)
- ✅ Progress over 20 games
- ✅ Pattern learning from corrections

**API Endpoints:**
```
GET /cognitive/prioritized-weaknesses - Top weaknesses
GET /journey/weakness-trends - Weakness changes over time
```

**Status:** ✅ COMPLETE - Has decay scoring and ranking

---

### 3. **BREAKTHROUGH DETECTION SYSTEM** (Complete - 639 lines)

**File:** `/backend/coach_state/breakthrough_service.py`

**What It Does:**
- ✅ Detects 6 states:
  1. **BREAKTHROUGH** - Real improvement (blunders down 30%)
  2. **PLATEAU** - Stuck despite effort
  3. **CONFIDENCE_ILLUSION** - Same core mistakes repeating
  4. **TILT_RISK** - Performance swings (blunders up 40%)
  5. **STABLE_GROWTH** - Low volatility, consistent
  6. **NORMAL** - No special state

- ✅ **Deterministic rules** (no LLM)
- ✅ **Rolling windows:** Last 5 / 10 / 20 games
- ✅ **Metrics tracked:** Blunders, mistakes, cp_loss, volatility, lesson repeat rate
- ✅ **Coach messages** (tier-aware: Novice / Developing / Disciplined / Advanced)
- ✅ **Recommended actions:** Recovery mode, Level up, Focus lock, Deep session
- ✅ **Evidence tracking** for debugging

**API Endpoints:**
```
GET /coach/breakthrough-signal - Current breakthrough state
```

**Status:** ✅ COMPLETE - Sophisticated breakthrough detection

---

### 4. **HABIT CHALLENGE SYSTEM** (Complete)

**File:** `/backend/routes/coach.py` (habit-challenge endpoints)

**What It Does:**
- ✅ Extracts positions from user's past mistakes
- ✅ Creates practice challenges ("Find the right move")
- ✅ Validates user answers
- ✅ Tracks progress
- ✅ Personalized to user's exact weaknesses

**API Endpoints:**
```
GET /coach/habit-challenge - Get challenge positions
POST /coach/habit-challenge/check - Validate answer
```

**Status:** ✅ COMPLETE - This IS the "Demon Challenge" system

---

### 5. **CHESS BRAIN - PATTERN DETECTION** (Complete - 18 Detectors)

**Files:**
- `/backend/services/chess_brain/detector_registry.py` (1,356 lines)
- `/backend/services/chess_brain/chess_brain.py`
- `/backend/services/chess_brain/integration.py`

**What It Does:**
- ✅ **10 Tactical Detectors:**
  - Fork, Pin, Skewer, Hanging Piece, Trapped Piece
  - Back Rank, Mate, Discovery, Overload, Removal

- ✅ **5 Strategic Detectors:**
  - Isolated Pawn, Passed Pawn, Knight Outpost
  - Rook Activity, King Safety

- ✅ **3 Behavioral Detectors:**
  - Time Trouble, Impulse Move, Tilt Detection

- ✅ **Confidence scores** for each detection
- ✅ **Teaching hooks** for explanations
- ✅ **Key squares** for board highlighting

**Status:** ✅ COMPLETE - All detectors working

---

### 6. **LESSON SELECTION ENGINE** (Complete)

**File:** `/backend/services/chess_brain/lesson_selection_engine.py`

**What It Does:**
- ✅ Weighted scoring formula
- ✅ 7 Teaching modes:
  1. TACTICAL_PATTERN_TEACHING
  2. STRATEGIC_CONCEPT_TEACHING
  3. IMMEDIATE_MISTAKE_CORRECTION
  4. POSITIVE_REINFORCEMENT
  5. HABIT_BREAKTHROUGH
  6. OPENING_GUIDANCE
  7. ENDGAME_TECHNIQUE

- ✅ **Anti-spam:** LessonMemory with 5-move cooldown
- ✅ **Priority levels:** HIGH, MEDIUM, LOW
- ✅ **Freshness tracking**
- ✅ **Player relevance scoring**

**Status:** ✅ COMPLETE - Sophisticated lesson selection

---

### 7. **EXPLANATION TEMPLATE SYSTEM** (Complete - NEW)

**Files:**
- `/backend/services/explanation_templates.py` (318 lines) - NEW
- `/backend/services/chess_brain/templates/` (6 modules, 2,000+ lines)

**What It Does:**
- ✅ Deterministic templates (NO LLM)
- ✅ 40+ template variations
- ✅ Rating-adaptive language (beginner/intermediate/advanced)
- ✅ Multiple variations per pattern
- ✅ Covers all teaching modes

**Status:** ✅ COMPLETE - Just added

---

### 8. **COACHING FEEDBACK LOOP** (Complete)

**Files:**
- `/backend/services/pattern_learning/` (4,827 lines total)
  - auto_correction_service.py (500 lines)
  - feedback_collector.py (248 lines)
  - pattern_learner.py (495 lines)
  - smart_pattern_matcher.py (555 lines)

**What It Does:**
- ✅ User submits correction
- ✅ System auto-generates corrected explanation
- ✅ Learns new classification rules
- ✅ Creates smart_patterns
- ✅ Applies to future positions
- ✅ Cross-user learning

**API Endpoints:**
```
POST /coach/pattern-learning/feedback - Submit correction
GET /coach/pattern-learning/stats - Learning statistics
POST /coach/pattern-learning/quick-rating - Simple thumbs up/down
GET /coach/pattern-learning/template-performance - Template stats
```

**Status:** ✅ COMPLETE - Self-learning system operational

---

### 9. **TRAINING RECOMMENDATIONS** (Complete)

**Files:**
- `/backend/routes/training.py`
- `/backend/services/active_teaching_engine.py`
- `/backend/services/teaching_move_selector.py`

**What It Does:**
- ✅ Personalized training based on weaknesses
- ✅ Puzzle selection
- ✅ Opening training
- ✅ Endgame training
- ✅ Tactical drills

**Status:** ✅ COMPLETE

---

### 10. **GAMIFICATION SYSTEM** (Complete)

**Files:**
- `/backend/routes/missions.py`
- `/backend/services/gamification/` (multiple files)

**What It Does:**
- ✅ XP system
- ✅ Level progression
- ✅ Daily rewards
- ✅ Streak tracking
- ✅ Milestone celebrations
- ✅ Animated UI

**API Endpoints:**
```
GET /gamification/progress
POST /gamification/daily-reward
GET /missions/focus-mastery
```

**Status:** ✅ COMPLETE

---

### 11. **COACH STATE MACHINE** (Complete)

**Files:**
- `/backend/coach_state/` (5 files)
  - breakthrough_service.py
  - focus_lock_service.py
  - module_trigger_service.py
  - teaching_style_service.py
  - theory_modules.py

**What It Does:**
- ✅ Weekly coach signals
- ✅ Focus lock (lock on one pattern)
- ✅ Recovery mode
- ✅ Deep session triggers
- ✅ Teaching style adaptation

**Status:** ✅ COMPLETE

---

## ❌ WHAT'S MISSING

### 1. **SHAREABLE IDENTITY CARDS** ❌
- No "Share My Chess DNA" feature
- No image export
- No viral sharing mechanism

**What's needed:**
- Generate PNG image of identity card
- Share buttons (Twitter, Reddit)
- Referral tracking

### 2. **FAST ONBOARDING** ⚠️
- Current: Link account → Wait → Analyze → See value (10+ min)
- Needed: PGN paste → 30 sec analysis → Identity reveal

### 3. **IDENTITY ON LANDING PAGE** ❌
- Identity buried in Journey → Intelligence
- Needed: Identity reveal on homepage/onboarding

### 4. **COACHING DEBUG DASHBOARD** ❌
- No internal tool to see:
  - Detected patterns
  - Candidate lessons
  - Scoring breakdown
  - Selected lesson
  - Template used

**What's needed:**
- Admin panel at `/debug/coaching`
- Shows full coaching pipeline per move

---

## 📊 SYSTEM INTERACTION MAP

```
User Plays Game
  ↓
[Chess Analysis] (Stockfish + position_analysis_service.py)
  ↓
[Pattern Detection] (detector_registry.py - 18 detectors)
  ↓
[Position Insight] (chess_brain.py - PositionInsightObject)
  ↓
[Lesson Candidates] (lesson_selection_engine.py)
  ↓
[Lesson Scoring] (weighted formula)
  ↓
[Lesson Selection] (top lesson chosen)
  ↓
[Teaching Mode] (one of 7 modes)
  ↓
[Explanation Generation] (explanation_templates.py OR LLM fallback)
  ↓
[User Display] (CoachInsightCard.jsx)
  ↓
[Feedback Collection] (Quick rating OR detailed correction)
  ↓
[Pattern Learning] (auto_correction_service.py learns)
  ↓
[Weakness Update] (coach_memory_service.py)
  ↓
[Fingerprint Update] (fingerprint_service.py)
  ↓
[Breakthrough Check] (breakthrough_service.py)
  ↓
[Identity Update] (player_identity_engine.py)
  ↓
[Identity Snapshot] (identity_formation_service.py)
```

**Status:** ✅ Pipeline EXISTS and is connected

---

## 🎯 OPTIMIZATION PRIORITIES

### Priority 1: Add Viral Sharing (2 days)
- Generate shareable identity cards
- Add share buttons
- Track referrals

### Priority 2: Fast Onboarding (1 day)
- Quick PGN analysis
- Identity reveal in 30 seconds

### Priority 3: Debug Dashboard (1 day)
- Internal tool to see coaching decisions
- Helps tune lesson scoring

### Priority 4: Frontend Polish (1 day)
- Identity card on dashboard top
- Breakthrough celebrations
- Challenge progress visible

---

## ✅ CONCLUSION

**What EXISTS:** 90% of the coaching engine
**What's MISSING:** 10% user experience polish + viral mechanisms

**DO NOT REBUILD:**
- Player Identity ✅
- Weakness Tracking ✅
- Breakthrough Detection ✅
- Habit Challenge ✅
- Pattern Detection ✅
- Lesson Selection ✅
- Templates ✅
- Feedback Loop ✅
- Gamification ✅

**DO BUILD:**
- Shareable identity cards
- Fast onboarding flow
- Debug dashboard
- Frontend polish

**The hard work is done. Now make it visible and shareable.**
