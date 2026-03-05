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

## Implementation Status

### Step 0-4: CoachState Foundation ✅
### Step 5: Memory Continuity Layer ✅
### Step 6: Intent Recognition Layer ✅
### Step 7: Adaptive Teaching Style ✅
### Step 8: Breakthrough & Plateau Detection ✅
### Step 9: Focus Lock Mode ✅ (Mar 3, 2026)
### Step 10: Pattern Injection Engine ✅ (Mar 3, 2026)

**Core Service:** `focus_lock_service.py`

**Compliance Heuristics:**
| Lesson Key | Rule | Metric |
|------------|------|--------|
| FORCING_BLIND | Check forcing moves first | 1 - (missed_forcing / total_forcing_opportunities) |
| STOPPED_CALCULATION_EARLY | Calculate deeper at critical moments | 1 - (early_stop / total_critical_moments) |
| THREAT_VERIFICATION | Verify opponent threats | 1 - (missed_threat / total_threat_opportunities) |

**Lock States:**
- ACTIVE → In progress
- EXTENDED → Compliance < 75%, first failure
- STRICT → Declining trend or second failure
- COMPLETED → Success (avg ≥ 75%)
- FAILED → 2 failures → Deep Review required

**Thresholds:**
- Strong: ≥80% | Partial: 60-79% | Failed: <60%
- Completion: 75%
- Default games: 5 | Extension: +3

---

## ChessGuru Capabilities (P2.8)

1. Deterministic chess truth
2. Behavioral tagging + Context-aware moment selection
3. Intent interpretation + Timing calibration
4. Memory continuity
5. Adaptive teaching style (tier-appropriate)
6. Breakthrough & Plateau Detection (phase awareness)
7. **Focus Lock Mode** (behavioral enforcement)
8. **Pattern Injection Engine** (theory + auto-lock)

---

## Key Files

### Step 10 - Pattern Injection
- `/app/backend/coach_state/theory_modules.py` (30 modules)
- `/app/backend/coach_state/module_trigger_service.py`
- `/app/frontend/src/components/Lab/OneThingFix.jsx`
- `/app/frontend/src/components/Lab/ConceptCard.jsx`

### Step 9 - Focus Lock
- `/app/backend/coach_state/focus_lock_service.py`
- `/app/backend/coach_state/tests/test_focus_lock_service.py`

### Step 8 - Breakthrough Detection
- `/app/backend/coach_state/breakthrough_service.py`

### Step 7 - Adaptive Teaching
- `/app/backend/coach_state/teaching_style_service.py`

---

## Testing
- 128/128 unit tests passing
- 3 simulated lock runs validated

---

## Recent Updates

### P0 - "95/100" Home Page Redesign ✅ COMPLETED (Mar 6, 2026)
Upgraded home page to feel like a personal coaching session:

**What Changed:**
- Updated `CoachHome.jsx` to use V2 API data (`specific_patterns`, `progress_trend`, `last_session`)
- Displays specific behavioral patterns: "27x you missed opponent's threats this week"
- Shows progress trends: "Steady progress. Stay focused on your habits."
- Celebrates wins with trophy icon and "Clean win! Let's see what worked."
- Shows session continuity for returning users

**Key Files Modified:**
- `/app/frontend/src/pages/CoachHome.jsx` - Frontend component
- `/app/backend/home_intelligence_service.py` - Already had V2 functions

**Test Status:** 100% passing (67/67 tests)
- Frontend: 35/35 specs passed
- Backend: 32/32 tests passed
- New specs: `/app/tests/e2e/coach-home-v2.spec.ts`, `/app/backend/tests/test_home_intelligence_v2.py`

### P0 - Lab Page "Human Coach" Improvements ✅ COMPLETED (Mar 6, 2026)
Upgraded Lab page from 72/100 to ~85/100 on "human coach" feel:

**What Changed:**
1. **Coaching Intro** - Added conversational opener that connects to user's recurring patterns
   - Example: "Tough game. But here's the thing — this is the same pattern we've seen before. You've missed opponent's threats 27 times recently. Let's fix this once and for all."
2. **Milestones Reordering** - For LOSS games, shows "Where It Went Wrong" FIRST, then "What Worked"
   - Previously showed Brilliant Moves first regardless of result
3. **Encouragement Section** - Added actionable encouragement at bottom of Summary tab
   - Example: "One habit change: after every move, scan for hanging pieces. Do this for 10 games and watch your wins climb."
4. **Pattern Connection** - Lab page now fetches recurring patterns from home-intelligence API

**Key Files Modified:**
- `/app/frontend/src/pages/Lab.jsx` - Frontend component with all improvements

**Test Status:** 100% passing (22/22 new tests)
- Frontend: 11/11 specs passed  
- Backend: 11/11 tests passed
- New specs: `/app/tests/e2e/lab-coaching-features.spec.ts`, `/app/backend/tests/test_lab_coaching_api.py`

---

## Next Steps

### P0 - Step 9 Integration ✅ COMPLETED (Mar 3, 2026)
- ✅ Wire compliance calculation into analysis_worker
- ✅ API endpoint: `GET/POST /api/coach/focus-lock`
- ✅ UI: Focus Lock card on Dashboard (overrides Weekly Signal)
- ✅ **Step 9.1: Micro Reinforcement** - Minimal badge on Lab page + one-line coach feedback
- ✅ **Internal Analytics** - Silent logging to `focus_lock_analytics` collection

### P0 - Step 10 UI Redesign ✅ COMPLETED (Mar 4, 2026)
- ✅ Simplified Lab page Summary tab: Main Lesson + Supporting Lessons + Coach Notice
- ✅ Simplified Lab page Strategy tab: 3 blocks only (Position Type, What required, What happened)
- ✅ Created `/app/frontend/src/components/Lab/` components: LessonCard, CoachNotice, FocusLockStatus
- ✅ **Strategy Tab Coach Language** (Mar 4, 2026):
  - Never show "Unknown Opening" → describe position characteristics
  - Numbered step-by-step plan (not arrow-separated)
  - Specific mistake explanation (not vague "went poorly")
  - Clickable "Key Moment" with descriptive text
- ✅ **Game Termination Context** (Mar 4, 2026):
  - Header badge shows how game ended (abandoned, timeout, resigned, checkmate)
  - Strategy tab shows notice for incomplete games
- ✅ **Enhanced Lesson Structure** (Mar 4, 2026):
  - Full coaching format: Concept → What happened → Better idea → Rule → Coach Insight
  - Shows "Played: X → Better: Y" comparison
  - Memorable coach quotes from principles library
- ✅ **Tab Interconnection** (Mar 4, 2026):
  - Summary → Strategy via "See Strategy" button
  - Strategy → Milestones via "See all learning moments" link
  - 30 theory modules in `/app/backend/coach_state/theory_modules.py`

### 🛑 OBSERVATION PHASE (Do Not Add Features)
Wait for real user data before Step 10:
- Need: 10+ completed locks, 5+ extended locks, 3+ strict-mode triggers, 2+ deep-sessions
- Track: Completion rate, compliance distribution, quit patterns

### P1 - Smart Coach Engine - Phase 1 ✅ COMPLETED (Mar 4, 2026)
Built Stockfish-validated teaching engine with strict no-hallucination policy:

**Core Components Created:**
- `/app/backend/coach_engine/` - New module with:
  - `wisdom_library.py` - 16 V1 rules (high-frequency, verifiable)
  - `piece_metrics.py` - Deterministic piece analysis (mobility, blocking, etc.)
  - `rule_validator.py` - Two-gate validation (Gate A: evidence, Gate B: SF proof)
  - `teaching_engine.py` - Main orchestrator with de-duplication
  - `telemetry.py` - User interaction logging
  - `models.py` - Strict output contracts

**V1 Rules (16):**
1. DELAYED_CASTLING
2. EARLY_QUEEN_REPEATS
3. MOVE_SAME_PIECE_REPEAT
4. MISSED_FORCING_MOVES
5. HANGING_PIECE
6. SIMPLE_FORK_ALLOWED
7. OPEN_FILE_ROOK_UNUSED
8. ROOKS_NOT_CONNECTED
9. BLOCKED_BISHOP_BY_OWN_PAWN
10. BAD_TRADE_ACTIVE_FOR_PASSIVE
11. BISHOP_PAIR_GIVEN_UP_OPEN_POS
12. IGNORE_WORST_PIECE
13. ADVANTAGE_CONVERSION_SIMPLIFY
14. WHEN_WORSE_AVOID_TRADES
15. KING_SAFETY_PAWN_SHIELD_WEAKEN
16. CENTER_TENSION_IGNORED

**Key Constraints Implemented:**
- Coaching output contract: 1 diagnosis + move comparison + 1 reason + 1 rule
- 8 allowed reasons: threat, pin, open_file, hanging_piece, king_safety, development_tempo, piece_activity, pawn_structure
- De-duplication: max 1 same rule/game, max 3 same rule in last 10 games
- Teach vs Observe distinction
- Confidence + soft language policy
- Telemetry from day 1

**Tests:** 17/17 passing in `/app/backend/tests/test_coach_engine.py`

### P1 - Smart Coach Engine - Phase 2 Integration ✅ COMPLETED (Mar 5, 2026)
Integrated teaching engine with existing Play with Coach system:

- Created `/app/backend/coach_play/teaching_integration.py`:
  - `enhance_coaching_message()` - Adds wisdom-based explanations to coaching moments
  - `get_wisdom_for_position()` - Proactive hints based on position features
  - `reset_engine_for_new_game()` - De-duplication state management
- Exports added to `coach_play/__init__.py`
- All 17 coach_engine tests passing

### P1 - Smart Coach Engine - Phase 3 Lab Integration ✅ COMPLETED (Mar 5, 2026)
Integrated teaching engine with Lab game analysis:

- Added `wisdom_lessons` to `/api/lab/{game_id}` response
- Lab now shows "Chess Principles Applied" section with:
  - Clickable move references
  - Board-grounded diagnosis
  - Memorable rule from wisdom library
- Play with Coach `/coach/play/move` endpoint now uses wisdom-based explanations
  - Falls back to LLM if no rule matches
  - Stores `rule_id`, `memorable_rule`, `highlights` in coach_messages

### P1 - Bug Fixes ✅ COMPLETED (Mar 5, 2026)
**Issue 2:** Updated `reflect_service.py` to check `stockfish_analysis.blunders/mistakes`. Fixed critical UnboundLocalError.
**Issue 3:** Fixed puzzle board showing starting position - added `puzzles.length` to useEffect dependency array. Also fixed red arrow not showing by adding `user_move_uci` and `best_move_uci` to puzzle data in `interactive_training_service.py`.
**Issue 4:** Hide "0 → 0" metrics in `JourneyIntelligence.jsx` and `CoachFocusCard.jsx`.
**Issue 5:** Added HelpCircle tooltips for rating metrics on `/progress` page.

### P1 - Play with Coach Enhancements 🟡 IN PROGRESS (Mar 5, 2026)
**Goal:** Transform from "playing an engine" to "learning from an Indian coach mentor"

**Completed:**
- ✅ Created `opening_plans.py` - Database of 20 common openings with plans, teaching moments, key squares
- ✅ Created `lichess_explorer.py` - Integration with Lichess Opening Explorer API
- ✅ Created `question_system.py` - Question generation, fuzzy response understanding, consequence detection
- ✅ Added `/api/coach/play/feedback` endpoint for beta user feedback collection
- ✅ Added `/api/coach/play/opening-plan` endpoint to get current opening plan
- ✅ Added feedback button ("Not helpful") on each coach message with modal
- ✅ Added opening teaching in background processing (coach explains its moves)
- ✅ Added proactive teaching for good moves (praise + "why is this good?")
- ✅ Added long-term consequence detection (blocked bishop, lost castling)
- ✅ Added question options UI (clickable buttons to answer)
- ✅ Added pattern-matched response understanding (no LLM for simple intents)

**What the coach now does:**
1. **Opening Teaching** - Explains moves in first 12 moves, names opening, describes plans
2. **Asks Questions** - "What do you think I'm planning?" with clickable answer options
3. **Praises Good Moves** - "Good move! Why do you think this is strong?"
4. **Warns About Consequences** - "That pawn restricts your bishop" (only verifiable facts)
5. **Understands Fuzzy Input** - "idk", "help", "what should I do?" → contextual responses
6. **Collects Feedback** - Beta users can flag unhelpful messages

**Remaining for V1:**
1. Test with a fresh game to verify opening teaching flow
2. Tune question frequency (not too many!)
3. Add more opening plans based on user feedback

### P2 - Step 10: Identity Formation Layer
- Long-term, identity-level feedback (e.g., "You are becoming a tactical player")
- Only starts after 10+ users complete full Focus Lock cycle
- Need real compliance distributions first

### P2 - Future Tasks
- Escalation psychology tuning
- UI for Memory/Intent display
- B2B features for human coaches
- Analytics dashboards
- RAG/LLM-based commentary

### P3 - Proactive Coaching (Future Vision)
- **Game Plan Before Play**: Show position-type specific guidance before middlegame begins
- Example: "Your main goal here is activating the rooks"
- Would make the coach feel proactive, not just reactive
- Requires: Opening classification → Position-type → Suggested plan mapping

---

## API Reference (Step 9)

### Focus Lock Endpoints
```
GET  /api/coach/focus-lock
POST /api/coach/focus-lock/activate  {lesson_key: string, games?: number}
POST /api/coach/focus-lock/deactivate
```

### Response: GET /api/coach/focus-lock (when active)
```json
{
  "active": true,
  "lesson_key": "FORCING_BLIND",
  "rule_description": "Forcing moves before every decision.",
  "state": "ACTIVE",
  "headline": "Rule locked for 5 games.",
  "message": "...",
  "progress": {"completed": 2, "required": 5, "text": "2 of 5 games"},
  "compliance": {"average": 75, "color": "yellow", "text": "..."},
  "strict_mode": false,
  "should_trigger_deep_session": false,
  "failed_cycles": 0
}
```

---

## Self-Learning Pattern Recognition System (NEW - Mar 5, 2026)

### Overview
A self-correcting AI system that learns from user feedback to improve mistake classification accuracy. When users flag a wrong explanation, the system:
1. Generates an immediate corrected explanation
2. Learns a new classification rule
3. Propagates the fix to ALL users with similar patterns

### Key Principle: NO HALLUCINATION
- Stockfish = Source of Truth (WHAT happened)
- AI = Translator (HOW to explain it)
- LLM never invents chess facts, only interprets Stockfish data

### Architecture
```
/app/backend/services/pattern_learning/
├── __init__.py
├── auto_correction_service.py   # Main orchestrator
├── feedback_collector.py        # Collects user feedback
├── pattern_learner.py           # GPT-4o generates rules from feedback
├── rule_validator.py            # Validates rules before activation
├── rule_executor.py             # Runs learned rules at classification time
└── learning_db.py               # Database operations
```

### API Endpoints
```
POST /api/coach/pattern-learning/feedback    # Submit correction feedback
GET  /api/coach/pattern-learning/stats       # System statistics
GET  /api/coach/pattern-learning/pending-rules  # Rules needing review
POST /api/coach/pattern-learning/approve-rule   # Approve a rule
POST /api/coach/pattern-learning/reject-rule    # Reject a rule
POST /api/coach/pattern-learning/classify       # Test classification
POST /api/coach/pattern-learning/track-accuracy # Track rule accuracy
```

### Frontend Integration
- Enhanced feedback modal in CoachPlay.jsx
- When user selects "Wrong/Incorrect", shows pattern correction dropdown
- Options: Fork, Pin, Skewer, Hanging Piece, Missed Tactic, etc.
- User explanation helps AI learn the pattern

### Auto-Approval Threshold: 0.85
Rules with confidence >= 85% are auto-approved and activated immediately.

### Database Collections
- `pattern_feedback` - User feedback on wrong explanations
- `learned_rules` - AI-generated classification rules
- `verified_corrections` - Cached corrections for fast lookup

### Cross-User Learning Flow
1. User A flags: "This wasn't a trap, it was a pawn fork"
2. AI analyzes position + Stockfish PV
3. Generates rule: "When PV shows sequential pawn captures, classify as FORK"
4. Rule validated against Stockfish
5. Rule activated (if confidence >= 85%)
6. User B encounters similar pattern → Correct classification automatically!

### Integration with Lab Page (NEW - Mar 5, 2026)
- Created `get_lab_data_async()` in `blunder_intelligence_service.py`
- Uses `classify_mistake_enhanced()` from `enhanced_classifier.py`
- Checks for corrections BEFORE hardcoded classification
- Lab endpoint updated to use async version with fallback

### Correction Matching Logic
Corrections are matched by PV characteristics:
- `attacker_piece`: The piece making the first PV move (e.g., "pawn")
- `is_sequential`: Whether PV has multiple moves (>1)

This ensures corrections propagate to similar tactical patterns across ALL positions, not just exact FEN matches.

