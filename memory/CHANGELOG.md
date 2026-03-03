# Chess Coach - Changelog

## Mar 3, 2026

### Step 9.1: Micro Reinforcement ✅

Added minimal Focus Lock indicators to reinforce habit formation without gamification.

**Lab Page (Game Analysis):**
- Focus Lock badge in header (top right, subtle)
  - Color: Green (≥80%), Yellow (60-79%), Red (<60%)
  - Shows lock icon + "Focus Lock" text
- One-line reinforcement in Coach's Take section:
  - Compliant: "Good. You followed the rule."
  - Failed: "You skipped the rule here."

**Design Philosophy:**
- Minimal reinforcement, not analytics dashboards
- User internalizes "I followed the rule" vs "I didn't"
- No cp numbers, move lists, or detailed breakdowns
- Detailed analysis belongs in Deep Session only

---

### Step 9: Focus Lock Mode Integration ✅

Completed the full integration of Focus Lock Mode - a behavioral enforcement layer that locks a single coaching rule for a set number of games and measures compliance.

**Backend Integration:**
- `analysis_worker.py` - Compliance calculation after each game analysis
  - Checks for active focus lock
  - Calculates compliance using same move_evaluations (no re-analysis)
  - Updates lock state immediately (games_completed, compliance_score)
  - Handles strict mode activation and deep session triggers

**API Endpoints:**
- `GET /api/coach/focus-lock` - Get current focus lock state (read-only)
- `POST /api/coach/focus-lock/activate` - Activate focus lock with guardrails
  - Rejects if lock already active
  - Rejects if < 10 games analyzed
  - Valid lesson_keys: FORCING_BLIND, STOPPED_CALCULATION_EARLY, THREAT_VERIFICATION
- `POST /api/coach/focus-lock/deactivate` - Force-deactivate lock

**Frontend:**
- `FocusLockCard.jsx` - New component for focus lock display
  - Shows rule description, progress bar, compliance score
  - Different colors for ACTIVE/EXTENDED/STRICT/COMPLETED states
  - CTA navigates to /games or /deep-session based on state
- `Dashboard.jsx` - Updated to show FocusLockCard when lock active
  - **Focus Lock OVERRIDES Weekly Signal card** (reinforces authority)

**New Service Functions:**
- `calculate_compliance_trend()` - Detect improving/stable/declining
- `focus_lock_to_db()` / `focus_lock_from_db()` - DB serialization
- `should_trigger_deep_session()` - Check if 2+ failed cycles

**Data Model Updates:**
- Added `failed_cycles` field to FocusLock dataclass
- Strict mode rule: `if failed_cycles >= 1 and declining_trend`
- Deep review rule: `if failed_cycles >= 2`

**Tests:**
- 29/29 unit tests passing for focus_lock_service
- 24/24 integration tests (15 backend + 9 frontend)

---

## Feb 24, 2026

### Mission Engine & Reward System - Phase 2A/2B Complete ✅

Built the Dopamine Engine with mission generation and reward tracking.

**New Backend Modules:**
- `mission_generation_service.py` - Deterministic mission generation
  - Pattern priority scoring formula
  - Rating-band difficulty presets
  - Rotation rules to prevent repetition

**New API Endpoints:**
- `GET /api/missions/today` - Get/generate daily mission
- `POST /api/missions/:id/start` - Start mission session
- `POST /api/missions/:id/step` - Record step + emit rewards
- `POST /api/missions/:id/complete` - Complete mission
- `GET /api/missions/history` - Mission history
- `GET /api/missions/focus-mastery` - Focus mastery levels
- `GET /api/rewards/feed` - Reward event feed
- `POST /api/rewards/mark-seen` - Mark rewards seen
- `GET /api/rewards/stats` - Reflection statistics
- `GET /api/weekly-proof` - Weekly proof card

**Reward Event Types:**
- process_recognition (threat scan used)
- pattern_recognition (2+ correct)
- recovery_moment (wrong→correct→correct)
- mission_complete_pass/fail

**Collections Created:**
- `behavioral_missions` - Mission records
- `mission_sessions` - Session tracking with steps
- `focus_mastery` - Pattern mastery scores
- `reward_events` - Reward audit trail

---

### Reflection Engine V1 - Phase 1B/1C Complete ✅ (Frontend + Timing)

Updated Reflect.jsx to use the V1 deterministic engine with progressive 2-tap flow.

**New UX Flow:**
- Step 0: Intent selection (8 options, 1 tap)
- Step 1: Confidence selection (3 options, 1 tap)
- Step 2: Quick tags (optional, multi-select)
- Submit → Awareness insight + coach reward

**Key Features:**
- Ego-safe framing: "No judgment — we're capturing what you saw"
- Progress indicator (3-step bar)
- Context tracking (shows selected intent/confidence with "change" link)
- Auto-advance on selection
- Tip hints for each step
- Rating-adaptive tags from V1 engine

**Data Stored:**
```json
{
  "intent": "attack",
  "intent_confidence": "very_sure",
  "selected_quick_tags": ["missed_threat"],
  "awareness_gap_type": "partial_alignment",
  "rule_version": "v1"
}
```

---

## Feb 23, 2026

### Reflection Engine V1 - Phase 1A Complete ✅

Built deterministic reflection engine with rating-adaptive behavior.

**New Backend Modules:**
- `reflect_constants.py` - Enums, rating bands, adaptive defaults
- `reflect_predicates.py` - Board fact detection (predicate registry)
- `quick_tag_registry.py` - Config-driven tag generation
- `awareness_gap_rules.py` - Deterministic gap detection (8 rules)
- `adaptive_profile_engine.py` - User profile generator
- `reward_message_service.py` - Template-based coach messages

**New API Endpoints:**
- `GET /api/reflect/v1/profile`
- `POST /api/reflect/v1/quick-tags`
- `POST /api/reflect/v1/submit`
- `GET /api/reflect/v1/post-loss/{game_id}`

**Key Features:**
- Rating bands: A(500-799), B(800-1099), C(1100-1399), D(1400-1699), E(1700+)
- 3 reward tones: encouragement, pattern_progress, precision
- 8 awareness gap rules (confidence_gap, panic_pattern, aligned, etc.)
- Versioned rules (v1) for future A/B testing

---

### Move Arrow Implementation ✅

- Fixed arrow format in Lab.jsx: `[[from, to, color]]`
- Verified on Lab page (orange) and Reflect page (red/green)

### Account Linking Security Fix ✅

- Validation prevents importing from wrong accounts
- Added `/api/journey/unlink-account` endpoint
- Standardized field names (`chess_com_username`)

### Reflection Bug Fixes ✅

- Fixed "I saw X was undefended" when user clearly missed it
- Fixed "I didn't notice" for pieces giving check
- Added check-aware contextual tags
