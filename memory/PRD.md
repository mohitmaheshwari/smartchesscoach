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
**Issue 3:** Fixed puzzle board showing starting position - added `puzzles.length` to useEffect dependency array in `TrainingNew.jsx` so board updates when puzzles load.
**Issue 4:** Hide "0 → 0" metrics in `JourneyIntelligence.jsx` and `CoachFocusCard.jsx`.
**Issue 5:** Added HelpCircle tooltips for rating metrics on `/progress` page.

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
