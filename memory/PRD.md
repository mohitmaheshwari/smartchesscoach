# Chess Coaching Application - Product Requirements Document

## Original Problem Statement
Create a hyper-personalized, data-driven chess coaching application that functions as a human-like AI coach with Socratic-style, contextual feedback tailored to the user's playstyle.

**Vision**: The first chess app that teaches you HOW to think, not just WHAT to play.

**Target Market**: Indian chess players (5M+ active), 600-2000 ELO rating range.

## Latest Updates (March 2026)

### Game Decryption Feature - V1 Implementation (March 23, 2026)
**"Every move explained in plain English" — Decrypting the game for human understanding**

**Philosophy:** Stop showing engine lines. Make the entire game story understandable like a coach would explain it.

**Backend Service (`/app/backend/services/game_decryption_service.py`):**
- Generates move-by-move coaching narratives during analysis (Phase 9)
- For EACH move explains: what happened, move idea, opponent's idea, what to think about
- Detects game phase (opening/middlegame/endgame)
- For mistakes: what you missed, better move idea, principle to remember
- For good moves: praise

**JSON Knowledge Base (`/app/backend/data/coaching/`):**
- `move_ideas.json`: Piece intentions, move types, common mistakes
- `opponent_threats.json`: Tactical and positional threats, common plans
- `phase_principles.json`: Opening/middlegame/endgame goals and principles

**API Endpoints:**
- `GET /api/coach/decryption/{gameId}` - Full move-by-move coaching data
- `POST /api/coach/decryption/feedback` - Submit "not helpful" with user correction
- `GET /api/coach/decryption/feedback/{gameId}` - Get feedback for a game

**On-Demand Generation:**
- For games analyzed before feature added, decryption is generated on first request
- Cached in `game_analyses.decryption_data` for instant subsequent loads

**Frontend (`/app/frontend/src/components/GameDecryption.jsx`):**
- Coach/Decrypt toggle on `/game/{gameId}` page
- Game Overview card at start: total moves, good moves, mistakes, key moments
- Move Coaching cards with all sections (what happened, idea, opponent idea, focus)
- Navigation: ← → ↑ ↓ keyboard and button controls
- "Not Helpful" button with feedback textarea

**Testing:** 100% (11/11 backend + frontend verified - iteration 144)

### Pattern Memory Feature - V1 Implementation (March 21, 2026)
**"Evidence-based self-awareness" — Confrontation, not information**

**Backend Service (`/app/backend/services/pattern_memory_service.py`):**
- Aggregates cognitive gaps from `game_analyses` (Stockfish-verified mistakes)
- Also aggregates thinking patterns from `question_insights` (Q&A revealed patterns)
- Normalizes pattern types (e.g., "threat_oversight" → "ignore_threat")
- Calculates severity based on recent + total counts
- Returns: `total_count`, `recent_count`, `recent_games` (20), `severity`, `sample_games`

**API Endpoints:**
- `GET /api/coach/patterns/summary` - Full aggregated pattern summary
- `GET /api/coach/patterns/top?limit=3` - Top N worst patterns for dashboard
- `GET /api/coach/patterns/for-mistake/{cognitive_gap}` - Pattern data with confrontation message

**Dashboard "Your Patterns" Section (`/app/frontend/src/components/patterns/YourPatterns.jsx`):**
- Shows top 3 recurring blind spots
- Sharp, minimal design (no progress bars, no analytics-style UI)
- Each card shows: label, recent count ("13 times in last 20 games"), overall count if different
- "Fix This" CTA on each pattern → navigates to Plateau Breaker

**Review Page Integration (`/plateau-breaker/review/:gameId`):**
- Step 2 (The Pattern) now shows confrontational message from Pattern Memory API
- Format: "You've had {label} {recent_count} times in your last {recent_games} games."
- Shows "Overall: {total_count} times" when lifetime > recent
- Falls back to old count display when pattern not found

**Cleanup:**
- Removed deprecated `/app/frontend/src/pages/PlateauBreakerTraining.jsx`
- Removed `/plateau-breaker/training` route from `App.js`

**Testing:** 100% (10/10 backend + frontend verified - iteration 143)

### Enterprise Theory Knowledge Base Refactoring (March 21, 2026)
**From 19 patterns in 1 file → 82 patterns in 4 files, zero duplication**

**Architecture Overhaul:**
- Split monolithic `chess_theory.json` into `/data/theory/` directory:
  - `opening_mistakes.json`: 28 opening-specific mistake patterns with FEN matching
  - `endgame_principles.json`: 17 endgame patterns matched by material configuration
  - `tactical_patterns.json`: 17 tactical motifs with prevention tips
  - `positional_rules.json`: 20 golden rules for PV line classification fallback
  - `index.json`: Metadata and data flow documentation
- Rewrote `chess_theory_service.py` to load from new directory structure (with legacy fallback)
- Cleaned `line_parser.py`: removed hardcoded `GOLDEN_RULES` and `OPENING_PATTERNS` dicts — now loads from theory service
- Deleted deprecated `llm_chess_explainer.py`
- Added `GET /api/coach/theory/rules` admin endpoint

**Testing:** 100% (17/17 backend tests passed - iteration 140)

### Coaching-Quality Q&A Engine (March 21, 2026)
**From chess.com eval dumps → real coaching that reads the student's mind**

**Coaching Answer Generator (`coaching_answer.py`):**
- Acknowledges what the user was thinking ("You're looking at capturing that pawn...")
- Traces material consequences through the PV line
- Detects "piece gets immediately recaptured" pattern
- Explains WHY the better move is better ("attacks the bishop, forcing a reaction")
- Provides a principle/takeaway ("Before moving, check: can opponent just take it?")

**Thinking Pattern Detection:**
- `short_calculation`: User calculates 1 ply but misses the reply
- `pawn_grabbing`: User sees a "free" pawn that isn't free
- `check_first`: User wants to give check that wastes time
- `capture_instinct`: User is drawn to captures over better quiet moves
- `positional_misread`: User plays a natural-looking move that misses tactics
- `material_awareness` (positive): User spots a good capture
- `positional_sense` (positive): User considers good quiet moves

**Question Insights Logging:**
- All Q&A questions stored in `question_insights` MongoDB collection
- Logs: fen, question, parsed_move, thinking_pattern, coaching_signal, severity
- This data reveals the student's blind spots for future personalization

**Improved Illegal Move Diagnostics:**
- Instead of "not legal", explains WHY: "your own pawn is on e5" or "Knight on f6 can't reach e1"

**Testing:** 100% (8/8 backend + frontend verified - iteration 141, 7/7 + frontend iteration 142)

### "Try a Move" Board Q&A (March 21, 2026)
**No more notation confusion — play the move on the board**

- Users click "Try a move on board" → board becomes interactive
- Drag/click the proposed alternative → auto-submits Q&A with "why not {SAN}?"
- Board shows blue "Play your move" header, loading overlay during analysis
- Cancel button to exit board mode
- Text input still available as fallback ("Or type: why not Nxd5?")

### Bug Fixes (March 21, 2026)
- **Fixed duplicate `board.push()` bug** in `move_qa_service.py` — move was being pushed twice, causing Stockfish PV analysis to crash
- **Fixed pawn exchange detection** — "d5 exd5" correctly identified as exchange ("material is even, but position is worse") instead of "you lose a pawn for nothing"
- **Added engine best-move comparison** — when user asks "why not X?" without specifying what was played, system compares against engine's best to compute meaningful eval_diff
- **Added PV pseudo-legality validation** — prevents crashes from invalid PV moves

**Testing:** 100% (7/7 backend + frontend verified - iteration 142)

### UI Consistency Fix - Streak vs Blocker Display (March 21, 2026)
**Issue**: Dashboard showed conflicting messages - "No Weakness Detected Yet" in the streak component while also showing "Your Current Blocker: You miss opponent's threats" in the blocker card.

**Root Cause**: Two independent data sources were not synchronized:
1. `MistakeFreeStreak` component fetched `/api/streak/status` which returns `needs_detection: true` when `streak_data.current_focus_mistake` is null
2. `PlateauBreakerDashboard` fetched `/api/coach/deep-memory` and found blunder data in `identity.blunder_taxonomy.by_type`

**Fix**: 
- Modified `PlateauBreakerDashboard.jsx` to pass `blockerDetected` and `blockerInfo` props to `MistakeFreeStreak`
- Modified `MistakeFreeStreak.jsx` to accept these props and use blocker info as fallback when streak API says `needs_detection` but parent has detected a blocker
- Now shows consistent "Start Your Streak - Tracking: Threat Awareness" with the blocker data

**Testing**: Screenshot verified - both components now show consistent "Threat Awareness" / "You miss opponent's threats" data

### Final 2 Gaps Closed - Ready for User Testing (March 21, 2026)
**"Until the user is forced to pause and reflect, nothing changes."**

**GAP 1: EnforcementCheckboxModal (Point of No Escape)**
- Created `/app/frontend/src/components/coach-play/EnforcementCheckboxModal.jsx`
- At Level 3 enforcement: Board blocked, modal unavoidable
- No close button, no skip, no escape
- Checkbox: "I checked what my opponent is threatening"
- Continue button disabled until checked + 400ms delay (prevents spam)
- Micro-copy: "You are repeating your mistake. Slow down."

**GAP 2: Improvement Proof (Belief Engine)**
- Updated `_enhance_postgame_messaging()` to compare this game vs last game
- Shows: "You missed 4 threats (last: 6)" with verdict
- Verdicts: `improving` (green), `slipping` (red), `same` (neutral)
- Messages: "Good. You're improving." / "You're slipping. Focus." / "You're not improving yet. Fix this."

**Testing**: 100% (10/10 backend, frontend verified)

### Backend Truth + Enforcement Ladder + Emotional Messaging (March 21, 2026)
**"Users don't change because of insight. They change because the system doesn't let them repeat mistakes easily."**

**Phase 8: Backend Streak Update (SOURCE OF TRUTH)**
- Added Phase 8 to `analysis_worker.py` (line 1103+) - calls `update_streak_from_analysis()` after Stockfish analysis
- Frontend NO LONGER updates streak - backend is authoritative
- Stores metadata: `{ source: "engine_verified", analysis_version: "v1.3" }`
- Finds and stores critical moment (highest cp_loss move)

**Enforcement Ladder (Progressive Strictness)**
- Added `EnforcementLadder` class to `pre_move_guardian.py` (line 801+)
- 5 escalation levels based on repeat count + risk severity:
  1. WARNING: "Check opponent threat"
  2. STRONG_WARNING: "You are repeating your mistake"
  3. CHECKBOX_REQUIRED: Forces acknowledgment before proceeding
  4. SOFT_BLOCK: "Try a different move"
  5. ALLOW_WITH_PENALTY: "Warning ignored. Streak broken."
- Combines `risk_level` (CRITICAL/HIGH/MEDIUM) with `repeat_count` for smart escalation

**Emotional Messaging (Retention Engine)**
- Upgraded `PostGameStreakResult.jsx`: 
  - Broken: "You broke your streak by ignoring threats again. This is exactly why you're stuck."
  - New Best: "This is real progress. Keep building."
  - Critical moment hint: "Move 17 was your turning point."
- Upgraded `PreGameStreakPopup.jsx`:
  - Failed last game: "You ignored threat awareness and lost. Fix it now."
  - On best streak: "You've never gone this long. Protect it."
  - Urgency messages that create psychological pressure

**Testing**: 100% success (16/16 backend tests, frontend verified)

### P0: Mistake-Free Streak + Carry-Forward Engine (March 21, 2026)
**This is NOT gamification - it's proof of behavior change.**

Implemented the core behavioral improvement system that tracks games without the user's specific focus mistake:
- **Backend Service**: `/app/backend/services/mistake_streak_service.py`
  - Strict Stockfish-based detection (eval_loss >= 200cp)
  - Compensation check (recovery within 2 plies = ignore)
  - Game validity filters (min 15 moves OR tactical opportunity)
  - Focus mistake types: THREAT_VERIFICATION, FORCING_BLIND, STOPPED_CALCULATION_EARLY, HANGING_PIECE, TACTICAL_MISS
- **API Endpoints**: `/app/backend/routes/streak.py`
  - GET `/api/streak/status` - Pre-game carry-forward data
  - GET `/api/streak/focus-types` - Available focus mistake types
  - POST `/api/streak/set-focus` - Set user's focus mistake
  - POST `/api/streak/update` - Update streak after game analysis
  - GET `/api/streak/history` - Last 5 games with streak data
- **Frontend Components**: `/app/frontend/src/components/streak/`
  - `MistakeFreeStreak.jsx` - Dashboard display with streak, rule, trend
  - `PreGameStreakPopup.jsx` - "You're on a 3-game streak. Don't break it."
  - `PostGameStreakResult.jsx` - Celebrate or break message
- **Database Schema**: `user.streak_data`
  ```json
  {
    "current_focus_mistake": "THREAT_VERIFICATION",
    "mistake_streak": { "current": 3, "best": 7, "last_game_had_mistake": false },
    "mistake_trend": { "before_avg": 6.2, "recent_avg": 2.1, "improvement_pct": 66 },
    "last_5_games": [...]
  }
  ```
- **Testing**: 100% success rate (backend 12/12 tests, frontend verified)

### V1 Plateau Breaker Mode - LichessBoard Refactoring Fix (March 21, 2026)
- **Fixed Critical Board Rendering Bug**: All V1 Plateau Breaker pages were using direct `Chessground` initialization instead of the app's existing `LichessBoard.jsx` wrapper component, causing boards not to render
- **Refactored Components**:
  - `PlateauBreakerTraining.jsx` - Now uses LichessBoard for puzzle training
  - `PlateauBreakerReview.jsx` - Now uses LichessBoard for game review
  - `GuidedOpeningLesson.jsx` - Now uses LichessBoard for opening walkthrough
  - `ApplyMode.jsx` - Was already using LichessBoard (verified working)
- **Testing**: All V1 pages tested with 100% success rate. Boards render correctly, pieces are interactive, move validation works
- **Routes**:
  - `/plateau-breaker` - Dashboard showing user's blocker and rule
  - `/plateau-breaker/training` - Forced puzzle training with fail state
  - `/plateau-breaker/apply` - Mini-game with enforced rule check before each move

### Interactive Guided Opening Lessons
- **GuidedOpeningLesson component**: Transformed static text dumps into interactive video-style walkthroughs
- Coach auto-plays through moves with narration ("Now watch this...", "Pay attention here...")
- Progress bar showing lesson completion (e.g., "5 / 12")
- Playback controls: Pause, Previous, Next, Reset, Speed slider
- "Why this move?" button for AI-powered deeper explanations
- Key Ideas Reference panel with collapsible summary

### Opening Library Overview Page
- New `/openings-overview` page for admin verification
- Shows all 23 openings with source badges (library, mastery, plans)
- Expandable cards with full content preview (key ideas, main line, traps, common mistakes)
- Data completeness warnings for missing content
- Quick links to lesson pages and admin editor

### Comprehensive Documentation
- Created `/app/APP.md` - Complete investor-ready product & technical documentation
- Covers: Vision, Problem, Features, User Flows, Technical Architecture, AI Engine, Data Models, API Reference, Competitive Analysis, Monetization, Roadmap

## What's Been Implemented

### Core Features
- **Play with Coach**: Move-by-move coaching during opening phase (every move gets commentary)
- **Intelligent Position Coaching**: Position-based coaching for middlegame and endgame phases using pawn structure classification, strategic plan database, and tactical detectors
- **Human Coach Layer (NEW - 9/10 Experience)**: Lab page now provides human-coach-like insights including:
  - **"WHY THIS HAPPENED"**: Behavioral tags (impatience, hope_chess, laziness, overconfidence, tunnel_vision, etc.) explaining the psychology behind mistakes
  - **Reflection Questions**: Coach-like questions ("What did this move do to your pawn structure?")
  - **Cross-Game Pattern Detection**: "This is the 3rd time you've made this type of mistake"
  - **Coach Voice Summaries**: Natural language game narratives with actionable takeaways
  - **Enriched Memory Tab**: Real aggregated data showing playing style, worst phase, most common mistakes
- **Unified Opening Detection**: Now detects 22+ openings (up from 9) including Vienna, Scotch, Petrov, King's Indian, Slav, Dutch, Nimzo-Indian, Benoni, Budapest, etc.
- **Opening Detection After Coach's Move**: Opening teaching now triggers immediately after the coach plays the defining move (e.g., French Defense detected after 1.e4 e6, not delayed)
- **"Explain My Position" Feature**: On-demand position analysis via POST /api/coach/play/explain-position - users can ask the coach to explain their current position at any time
- **Dynamic Coaching in Practice Mode**: Opening Practice mode now uses the Behavioral Coaching Layer and Intelligent Position Coach for personalized feedback
- **Deep Opening Context Engine**: Live coach now merges direct opening plans with family-level variation trees so sub-lines like QGD / Slav can inherit richer teaching
- **Expanded Deep Opening Coverage**: Added deeper variation trees for Italian, London, Sicilian, French, Caro-Kann, and King's Indian coaching
- **Game Analysis Lab**: 5-tab structure (Summary, Moments, Ideas, Habits, Memory)
- **Moments Tab**: Interactive training loop (Intro → Thinking → Try Move → Reveal → Reflection → Lesson)
- **Turning Point Detection**: v4 logic, correctly handles user-only move evaluations
- **Blind Spots**: Homepage widget showing recurring mistake patterns
- **Explain Move**: Expandable explanations for turning points and biggest blunders
- **Opening Teaching**: Rich teaching moments for Queen's Gambit, Italian, London, etc.
- **Deviation Guidance**: If a user leaves the main line, the coach now keeps teaching by naming the expected move and explaining the idea instead of going generic/silent
- **Trap Awareness**: QGD family trap warnings (including Elephant Trap context) now surface from the live coaching engine
- **Color-Aware Plans**: Variation teaching now returns side-aware plan suggestions for both White and Black openings
- **Safer Redirect Flow**: Protected route auth/onboarding flow now preserves intended destination and supports demo-mode bypass from onboarding without redirect loops
- **Frontend Runtime Stability**: Disabled cross-origin iframe recording in analytics to prevent the `PerformanceServerTiming` `DataCloneError` on page load
- **Typed Opening Schema Foundation**: Added a structured opening catalog layer for families, variations, rating-aware teaching nodes, traps, deviation rules, and coverage metadata
- **Duplicate SAN Support**: Opening teaching now supports move-index-aware teaching nodes so repeated SAN moves in the same line can still teach correctly
- **Undo Move in Play with Coach**: Added an `Undo Move` control near the board that rewinds the user's last move in normal play and rewinds the student's last move in lesson mode
- **Self-Healing Analysis Queue**: Added stuck-job retry metadata, fallback queue processing, and Lab-page queue/failure status messaging so analysis jobs do not silently sit forever
- **Verified Trap Source-of-Truth**: Added a canonical trap registry for live coaching so traps are only offered and taught when the exact opening line matches a verified legal sequence
- **Opening/Trap Correction Loop**: Users can now submit corrected PGN or SAN directly from Play with Coach and /openings, with current moves auto-filled and live overwrite behavior via DB-backed corrections
- **Admin Opening Feedback Manager**: Added `/admin/openings` with Monaco JSON editor, schema validation, MongoDB save/fetch, version history, and rating-bucket preview panels

## Code Architecture
```
/app
├── backend/
│   ├── data/
│   │   ├── theory/                      # Enterprise knowledge base (admin-editable)
│   │   │   ├── index.json               # Metadata and data flow docs
│   │   │   ├── opening_mistakes.json    # 28 FEN-based opening patterns
│   │   │   ├── endgame_principles.json  # 17 material-based endgame patterns
│   │   │   ├── tactical_patterns.json   # 17 tactical motif patterns
│   │   │   └── positional_rules.json    # 20 golden rules for PV fallback
│   │   ├── eco_openings.json            # ECO reference data (static)
│   │   └── chess_theory.json            # Legacy (kept for backwards compat)
│   ├── routes/
│   │   ├── coach.py                     # Theory/explain-mistake/Q&A endpoints
│   │   └── ...
│   └── services/
│       ├── chess_theory_service.py      # Single source of truth - loads /data/theory/
│       ├── line_parser.py               # PV line parsing (no hardcoded data)
│       ├── move_qa_service.py           # "Why not move X?" feature
│       └── ...
└── frontend/
    └── src/
        ├── pages/
        │   └── PlateauBreakerReview.jsx # Interactive review with theory + Q&A
        └── components/
            └── ClickableLine.jsx        # Interactive move sequences
```

## Prioritized Backlog

### P0 - Critical Issues
All P0 issues resolved in this session.

### Improvement Engine - Phase 1 (Completed March 19, 2026)
- [x] **Opening Fundamentals Checker**: Backend service (`opening_fundamentals_checker.py`) that analyzes player adherence to basic opening principles (castling early, center control, piece development, etc.)
- [x] **Opening Fundamentals API**: `GET /api/analysis/{game_id}/opening-fundamentals` returns score (0-100), violations list, adherences list, and summary
- [x] **Opening Fundamentals UI**: `OpeningFundamentals.jsx` component renders in Lab page Habits tab - shows score, principles followed, principles violated (with expandable thinking prompts), and coach advice

### Improvement Engine - Phase 2 (Completed March 19, 2026)
- [x] **Pre-Move Checklist UI**: `PreMoveChecklist.jsx` component in Play with Coach page - shows contextual prompts based on move number, castling status, and player weaknesses. Items are checkable, expandable/collapsible, dismissible.
- [x] **Thinking Coach Service**: Backend service (`thinking_coach.py`) that teaches players HOW to think:
  - `POST /api/thinking-coach/walkthrough` - Step-by-step thought process for any position
  - `POST /api/thinking-coach/principle-feedback` - Connects mistakes to fundamental principles
  - `POST /api/thinking-coach/behavioral-intervention` - Specific interventions for patterns like hope_chess, tunnel_vision
  - `POST /api/thinking-coach/mindset-prompt` - Position-specific questions based on characteristics
  - `GET /api/thinking-coach/pre-move-checklist` - Contextual checklist items for game state

### Improvement Engine - Phase 3 (Completed March 19, 2026)
- [x] **ThoughtProcessWalkthrough UI**: `ThoughtProcessWalkthrough.jsx` component in Lab page Moments tab - shows step-by-step thinking process in REVEAL stage with "How Should I Have Thought Here?" button. Displays phases (Check Threats, King Safety, Find Targets, etc.), questions, observations, and key takeaways.
- [x] **PrincipleFeedback UI**: `PrincipleFeedback.jsx` component in Lab page Summary tab - connects biggest mistakes to fundamental principles. Shows principle name, explanation, applied context, thinking habit, and what to do instead.
- [x] **BehavioralIntervention UI**: `BehavioralIntervention.jsx` component in Lab page Summary tab - appears when cross-game patterns detected. Shows diagnosed pattern, intervention habit, and practice rule with commitment button.
- [x] **Enhanced PreMoveChecklist**: Added player-specific weakness mapping (hope_chess -> response_check, impulsive_play -> verify_check, tunnel_vision -> whole_board_check, etc.) for personalized prompts.

### Thinking Score System (Completed March 19, 2026)
- [x] **Thinking Score Service**: Backend service (`thinking_score.py`) calculates scores from REAL game data - not random numbers. Tracks 5 habits: threat_awareness, tactical_vision, move_verification, king_safety, patience.
- [x] **Thinking Score APIs**: 
  - `GET /api/thinking-score` - Returns overall score + progress trends
  - `POST /api/thinking-score/calculate/{game_id}` - Calculate score for one game
  - `GET /api/thinking-score/history` - Score history across games
  - `GET /api/thinking-score/recommendations` - Personalized advice based on weakest habits
- [x] **ThinkingScoreCard UI**: `ThinkingScoreCard.jsx` component added to both HomePage and Dashboard. Shows circular progress ring, habit breakdown with scores, trend indicators, and personalized recommendations.
- [x] **Automatic Score Calculation**: Integrated into analysis_worker.py - thinking scores calculated automatically when games are analyzed.

### Data Freshness System (Completed March 20, 2026)
- [x] **Data Freshness Service**: Backend service (`data_freshness.py`) ensures all aggregated data is recalculated when games are analyzed. Fixes stale data issues across all pages.
- [x] **Collections Updated on Analysis**:
  - `player_identities` - Recalculated from ALL games (Memory tab, coaching context)
  - `player_profiles` - Dashboard stats (biggest weakness, errors/game)
  - `journey_stats` - Journey page stats
  - `thinking_scores` - Calculated for any games missing scores
- [x] **Data Freshness APIs**:
  - `POST /api/data/refresh` - Manual trigger to refresh all data
  - `GET /api/data/status` - Check freshness status of all collections
- [x] **Fixed Issues**:
  - Duplicate player_identities cleaned up automatically
  - Stale consecutive losses now recalculated correctly
  - Games processed in chronological order for correct streak state
- [x] **Integration**: Runs automatically after every game analysis (PHASE 7 in analysis_worker.py)
- [x] **Documentation**: Created `/app/memory/DATA_SOURCES.md` mapping all pages to their data sources

### P1 - Next
- [ ] **Enrich Game Decryption Knowledge Base**: Add more patterns to `opponent_threats.json`, `move_ideas.json` for richer explanations
- [ ] **Review Feedback Dashboard**: Admin page to view and analyze "Not Helpful" feedback submissions
- [ ] **Admin UI for Theory Database**: Web interface to view/edit theory JSON files via browser (CRUD without code deployment)
- [ ] **Inject Pattern Memory into Guided Play**: Show confrontational pattern messages at critical moments during coached games
- [ ] **Opening-based Categorization**: Group mistakes by opening type for targeted training
- [ ] Fully verify onboarding/navigation reliability with a fresh un-onboarded test user
- [ ] Add automatic profile creation during game sync if it doesn't exist (currently relies on analysis worker)
- [ ] Add "What You Did Well" section to Summary (celebrate good moves)
- [ ] Expand deep variation trees to the remaining repertoire gaps (Ruy Lopez, Scotch, Vienna, Nimzo, Scandinavian, Philidor, Petrov)
- [ ] Add richer trap setup / trap-avoidance coaching for the newly covered openings in `move_by_move_coach.py`
- [ ] Add multi-plan candidate suggestions directly in live coach messages
- [ ] Start consuming the typed opening schema more directly at runtime instead of only exporting it through catalog helpers
- [ ] Add move-preview + undo/redo design polish for coaching mode
- [ ] Surface queue status consistently across the newer LabV2 flow too, not just the legacy Lab page
- [ ] Audit the remaining trap libraries and migrate them fully onto the verified trap registry
- [ ] Apply correction overrides more broadly across all legacy opening/trap training endpoints, not just the lesson and coach-trap flows
- [ ] Connect live coach runtime directly to the new admin-managed opening feedback collection where appropriate

### P2 - Backlog
- [ ] Lesson flow bug verification (Fried Liver Attack)
- [ ] Integrate MistakeFingerprint + ReinforcementEngine
- [ ] Positive pattern tracking on homepage (strengths alongside blind spots)
- [ ] Shareable "Chess DNA" report
- [ ] Enhanced "Ask Coach" prompts

## Testing Status
- **Game Decryption Feature**: iteration 144 (11/11 backend + frontend verified) - verifies decryption API, feedback API, on-demand generation, Coach/Decrypt toggle, navigation, move coaching cards
- **Pattern Memory Feature**: iteration 143 (10/10 backend + frontend verified) - verifies pattern aggregation APIs, dashboard YourPatterns, review page confrontation messages
- All features tested: iterations 120, 121, 122 (all passed)
- Deep opening teaching fix tested: iteration 123 (30/30 backend tests passed)
- Expanded opening coverage self-tested + unit-tested (`test_play_with_coach_opening_context.py`, `test_expanded_opening_variations.py` → 10/10 passed)
- Frontend routing/demo-mode smoke tested and checked with frontend testing agent (critical flows working; fresh-user onboarding still needs one final verification)
- PostHog `PerformanceServerTiming` DataCloneError fix verified by frontend testing agent (console clean after page load and interaction)
- Typed opening schema/catalog phase verified in iteration 124 (48/48 backend tests passed)
- Undo Move feature verified with live API checks and frontend testing agent after service restart
- Analysis queue recovery verified by backend and frontend testing agents, including Lab-page failed/processing status messaging
- Verified trap registry and exact-line trap selection tested (registry legality + Siberian/QGD selection integration)
- Opening/trap correction loop verified by frontend testing agent, including immediate lesson overwrite from submitted SAN/PGN
- Admin Opening Feedback Manager MVP verified by frontend testing agent (fetch, validate, save, preview, reload persistence all working)
- **Intelligent Position Coaching**: iteration 125-126 (19/19 backend tests passed, 7/7 frontend tests passed)
- **Unified Opening Detection & Features**: iteration 127-128 (30/30 backend tests passed) - verifies 22+ openings, explain-position endpoint, dynamic coaching
- **Human Coach Layer**: iteration 129 (28/28 tests passed, 13/13 backend, 15/15 frontend) - verifies behavioral insights, coach voice summaries, enriched memory tab
- **Opening Fundamentals Bug Fix**: iteration 130 (19/19 tests passed, 13/13 backend, 6/6 frontend) - verifies OpeningFundamentals component renders correctly in Habits tab
- **Thinking Coach/Improvement Engine Phase 2**: iteration 131 (32/32 tests passed, 15/15 backend, 17/17 frontend) - verifies Pre-Move Checklist, all Thinking Coach APIs, regression tests
- **Improvement Engine Phase 3**: iteration 132 (42/42 tests passed, 15/15 backend, 27/27 frontend) - verifies ThoughtProcessWalkthrough in Moments tab, PrincipleFeedback/BehavioralIntervention in Summary tab, enhanced PreMoveChecklist with weakness mapping
- **Thinking Score System**: iteration 133 (33/33 tests passed, 16/16 backend, 17/17 frontend) - verifies all thinking score APIs, calculation from real game data, ThinkingScoreCard component
- **Enterprise Theory Knowledge Base Refactoring**: iteration 140 (17/17 backend tests passed) - verifies split theory loading, all admin endpoints, FEN matching, PV fallback, Q&A
- Test files: `/app/backend/tests/test_*.py`, `/app/tests/e2e/*.spec.ts`

## New Files Created
- `/app/backend/services/human_coach_layer.py`: Behavioral tagging system with 11 psychological tags, cross-game pattern detection, coach voice generation
- `/app/backend/tests/test_human_coach_layer_api.py`: API tests for enriched analysis
- `/app/tests/e2e/lab-human-coach-layer.spec.ts`: Frontend tests for behavioral insights UI
- `/app/backend/services/opening_fundamentals_checker.py`: Checks player adherence to basic opening principles (castle early, center control, piece development, etc.)
- `/app/frontend/src/components/lab/OpeningFundamentals.jsx`: UI component showing opening principles score, violations, adherences, and coach advice
- `/app/tests/e2e/opening-fundamentals.spec.ts`: Frontend tests for OpeningFundamentals component
- `/app/backend/tests/test_opening_fundamentals_api.py`: API tests for opening fundamentals endpoint
- `/app/backend/services/thinking_coach.py`: Teaches players HOW to think - thought process walkthroughs, principle-based feedback, behavioral interventions, mindset prompts
- `/app/frontend/src/components/coach/PreMoveChecklist.jsx`: UI component showing contextual pre-move prompts in Play with Coach
- `/app/tests/e2e/pre-move-checklist.spec.ts`: Frontend tests for PreMoveChecklist component
- `/app/backend/tests/test_thinking_coach_api.py`: API tests for all Thinking Coach endpoints
- `/app/frontend/src/components/lab/ThoughtProcessWalkthrough.jsx`: UI component showing step-by-step thinking process in Moments tab
- `/app/frontend/src/components/lab/PrincipleFeedback.jsx`: UI component connecting mistakes to fundamental principles
- `/app/frontend/src/components/lab/BehavioralIntervention.jsx`: UI component for behavioral pattern interventions
- `/app/tests/e2e/improvement-engine.spec.ts`: Frontend tests for ThoughtProcessWalkthrough, PrincipleFeedback, BehavioralIntervention
- `/app/backend/services/thinking_score.py`: Calculates thinking scores from real game data - 5 habits tracked
- `/app/frontend/src/components/coach/ThinkingScoreCard.jsx`: Dashboard component showing overall score, habit breakdown, trends, recommendations
- `/app/backend/tests/test_thinking_score_api.py`: API tests for thinking score endpoints
- `/app/tests/e2e/thinking-score.spec.ts`: Frontend tests for ThinkingScoreCard component

## Key Technical Notes
- `move_evaluations` only contains USER's moves (not both sides)
- `get_opening_by_moves` returns `OpeningPlan` dataclass, use `getattr()` not `.get()`
- User data in `test_database`, DEV_USER_ID=user_4dad2b14e380
- Coach messages stored in `coach_messages` collection with trigger="opening_teaching"
- Live opening coaching now uses `build_opening_coaching_context(moves)` to merge direct openings with family variation trees before calling `generate_move_commentary(...)`
- `get_variation_teaching(...)` now supports main-line guidance even when the player deviates from the expected move
- `get_variation_teaching(...)` now also returns `plans_for_user` so Black and White get side-aware plan suggestions from the same opening tree
- Frontend protected routes now store `post_auth_redirect` in session storage and allow `demo=true` onboarding bypass for demo exploration
- Frontend analytics config now keeps `recordCrossOriginIframes: false` to avoid non-cloneable `PerformanceServerTiming` objects during `postMessage`
- `get_opening_family_catalog()` and `get_opening_catalog_validation_report()` now provide typed family-level coverage data for the opening library
- Ruy Lopez now includes structured Steinitz Exchange Queenless and Berlin variations, and repeated SAN teaching is handled through `teaching_nodes` with `move_index`
- `/api/coach/play/undo` now rewinds the latest user move in normal play and the latest student move in teaching mode, with stale lesson-state fallback and action-revision protection against late async coach writes
- Analysis queue now tracks `retry_count`, `retrying`, `last_error`, `last_error_at`, `started_at`, and `failed_at`; only stale `processing` jobs older than 10 minutes are retried, up to 3 times
- `server.py` now runs a fallback queue processor loop so pending jobs can still be analyzed even when a separate analysis worker process is absent
- Live opening coaching now prefers the verified trap registry over loose per-opening trap lists, which prevents trap-name hallucinations like mismatched Siberian lines
- `/api/openings/corrections` now accepts corrected PGN or SAN plus current moves/FEN and stores DB-backed live overrides that the /openings lesson flow and coach trap flow can consume immediately
- `/api/admin/openings` now supports list/fetch, `/validate` performs schema validation, and `/save` stores MongoDB-backed opening feedback with version history in `opening_feedback_versions`
- **Intelligent Position Coaching**: `/app/backend/services/intelligent_position_coach.py` orchestrates `PawnStructureClassifier`, `StructurePlanDatabase`, `DetectorRegistry`, and `position_strategy_analyzer` to provide contextual coaching for any position. Triggers after 12+ moves when no opening teaching is active. Frontend component: `PositionCoachingPanel.jsx`
- **V1 Plateau Breaker Mode**: Enforced learning system that identifies the user's single biggest mistake ("blocker"), provides psychological messaging, and forces completion of puzzle training + apply mode before unlocking next game analysis. Uses `LichessBoard.jsx` wrapper for consistent board rendering across all pages.
- **P0 Mistake-Free Streak**: Tracks games without user's focus mistake. Displays on dashboard with current/best streak, rule reminder, and improvement trend. Pre-game popup applies psychological pressure. Post-game shows celebration or break message.
- **V1 Guided Play Mode Integration**: CoachPlay page (`/play-with-coach`) now integrated with Plateau Breaker streak system:
  - Streak data fetched on page load via `/api/streak/status`
  - Focus mistake mapped to player weaknesses in PreMoveChecklist (e.g., THREAT_VERIFICATION → "What will my opponent do after this move?")
  - Pre-game streak popup shows rule reminder before game starts
  - Post-game streak result shows whether streak continued or broke

## Next Tasks (Prioritized)
1. **(P1) Admin UI for Theory Database**: Build a simple web interface for an admin to perform CRUD operations on the JSON files in `/app/backend/data/theory/`
2. **(P1) Connect Streak to Real Game Analysis**: Call POST /api/streak/update from backend analysis worker (not frontend) after Stockfish analysis completes with real move_evaluations
3. **(P1) Enhance Apply Mode**: Make it a real 10-15 move mini-game against engine that tracks if user commits focus-mistake
4. **(P2) Inject Pattern Memory into Guided Play**: Show confrontational pattern messages at critical moments during coached games
5. **(P2) Opening-based Categorization**: Group mistakes by opening type for targeted training
6. **(P2) Server-Side Training Lock**: Migrate lock state from localStorage to backend (add `is_training_locked`, `current_mistake_focus` to user model)
7. **(P2) Multi-Game Focus**: Lock user into fixing same mistake for 3 consecutive games before introducing new blocker

## Future/Backlog Tasks
- "Trajectory Coaching" rating growth plan (V3 - carefully)
- Monetization (Razorpay integration)
- Content population for opening lessons
- Positive reinforcement features ("What You Did Well")
- Mistake Replay Trainer and Spaced Repetition Queue
- Shareable "Chess DNA Report"
- Native mobile app (React Native)
- Localization (Hindi)
