# Chess Coaching App - Product Requirements Document

## ⛔ DO NOT TOUCH — CRITICAL DEPLOYMENT FILES
**These files must NEVER be modified, overwritten, or have values changed. The owner's production deployment depends on them exactly as they are.**

| File | Why |
|------|-----|
| `backend/.env` | Contains owner's OPENAI_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, MONGO_URL, and all production keys |
| `backend/llm_service.py` | Auto-detects LLM provider (OpenAI on owner's server, Emergent on Emergent platform). Logic must stay as-is |
| `frontend/.env` | Contains REACT_APP_BACKEND_URL — production URL mapping |
| `backend/routes/auth.py` | Google OAuth flow — owner's auth depends on this |
| Any `*_KEY`, `*_SECRET`, `*_ID` env vars | Never add, remove, or modify authentication/API credentials |

**Rule**: If a fix requires touching any of the above, ASK THE OWNER FIRST. No exceptions.

---

## Original Problem Statement
Build a hyper-personalized chess coaching application "Thinking Simulator" focusing on deep, insightful coaching for every move. Core features: "Play with Coach", "The Lab" for post-game analysis, "Community Intelligence Training", personalized Opening & Endgame study. UX principle: "One screen = one job."

---

## What's Been Implemented

### Human Coach Game Review — March 2026
- **THE STORY**: Game narrative arc (opening → tension → climax → resolution), no engine numbers
- **THE MIRROR**: Personality observation ("you play scared when winning", cross-game patterns)
- **THE MOMENT**: 2-3 critical decisions with THINKING ERROR diagnosis (complacency, desperation, tunnel_vision, no_plan, tactical_blindness, fatigue, frustration_spiral)
- **THE TAKEAWAY**: One memorable mantra for next game
- **THE PROOF**: Progress tracking (blunder rate, accuracy, opening quality vs recent history)
- **LLM Narrative Layer**: GPT-4o-mini generates human coaching language on top of deterministic analysis
- Backend: `services/coach_review_service.py`, endpoint: `GET /api/lab/{game_id}/coach-review`
- Frontend: `components/Lab/CoachReview.jsx`, integrated into LabV2.jsx Coach view mode
- Testing: iteration_166 — 100% pass (13/13 backend, all frontend verified)

### Adaptive Game Decryption V5 — March 2026
- Rating-based filtering: ~1100 player only sees mistakes (100+cp) and blunders (250+cp), not inaccuracies
- Known weakness matching: moves matching player_identity patterns get priority boost ("Known pattern" badge)
- Progressive difficulty: as rating increases, more detail surfaces (1200→70cp, 1400→50cp, 1600+→30cp)
- V5_COACHING_VERSION bumped to 4 to auto-regenerate cached data
- Each move now has `priority` field: essential/weakness_match/growth/silent/context
- Backend: `_get_adaptive_config()` in `game_decryption_v5_service.py`

### Coach Insight Panel — March 2026 (The Lab 3-Tab Pivot)
- Replaced old 5-tab analysis (Summary/Moments/Ideas/Habits/Memory) with 3-tab Coach Insight
- **Summary Tab**: One brutal truth diagnosis (THROW, MATE_BLIND, SLOW_BLEED, etc.), critical move, context bullets, coach note
- **Habits Tab**: Pass/fail checklist (6 habits: threat check, opening principles, hanging pieces, plan, critical moments, endgame). Focus habit highlight.
- **Memory Tab**: 
  - "Your Chess DNA": Before/after identity lines, archetype label (The Blind Spot, The Thrower, etc.)
  - "If You Fixed This One Thing": 3-line impact punch (stat → fix → rating difference), rating projection bar
- Backend: `/api/lab/{game_id}/coach-insight` — fully deterministic, no LLM
- Files: `services/game_coach_summary.py`, `components/Lab/CoachInsightPanel.jsx`, integrated into `LabV2.jsx` coach view

### Inline Flagging System - March 2026
- Every coaching text element has its own inline flag icon (appears on hover)
- Sections flagged: narrative, your_plan_now, consequence, better_approach, candidate_moves, transferable_learning, pattern_memory, theory_applied
- Flag dialog auto-captures: game_id, FEN, move, side (user/opponent), severity, CP loss, best move, eval before/after, phase, component, section name
- Admin Dashboard shows full diagnostics in feedback queue
- Backend stores diagnostics in `move_feedback` collection

### Book Opening Move Guard - March 2026
- Known opening responses (d5/Scandinavian, c5/Sicilian, e6/French, etc.) no longer flagged as inaccuracies
- Applied to both live coaching (`shared_coaching_v5.py`) and post-game analysis (`game_decryption_v5_service.py`)
- V5_COACHING_VERSION = 2: old coaching auto-regenerates when game is opened in Lab
- `POST /api/games/{game_id}/regenerate-coaching` endpoint added
- "Refresh Coaching" button in Lab header

### CoachPlay P0 Fixes - March 2026
- **State Sync**: executeMove clears all coaching state immediately, shows "Analyzing your move..." indicator
- **Fork Detection**: Uses `BB_KNIGHT_ATTACKS` bitboard for precise knight-only attack detection (was using `is_attacked_by` which caused false positives). Threshold raised from 5 to 6.
- **Opening Lesson Persistence**: Auto-dismisses after 14 half-moves + rendering condition checks move count
- **Adaptive UX**: Removed Time Control, Coaching Style selectors, "Lvl X" badge. Setup screen: Color + Start Game only.

### Player Profile Narrative (March 2026)
- LLM-generated coaching narrative, Indian Coach persona
- Cached in `player_profiles`, regenerates every 5 games

### Super Admin Dashboard (March 2026)
- Role system: super_admin, admin, user
- Overview, Users, Feedback Queue tabs (now with diagnostics display)

### Endgame Lesson System (March 2026)
- 10 lessons, 30 positions, interactive flow

### Previous Features (All Working)
- Community Intelligence Training, Opening Portrait, Pattern Memory
- V5 Decryption Engine, Pedagogical Opponent, Habit Insights
- Pattern Prescriptions, Theory Applied tracking

---

## Architecture
```
/app/backend/
  services/
    coach_review_service.py            # NEW: 5-section Human Coach Review engine
    shared_coaching_v5.py              # UPDATED: Fork detection + book move guard
    game_decryption_v5_service.py  # UPDATED: Book move guard + V5 versioning
    game_coach_summary.py          # NEW: 3-tab coach insight (summary/habits/memory)
    player_identity.py             # Core memory tracker for Chess DNA
    player_profile_service.py
    endgame_theory_service.py
    v5_llm_narrator.py
  routes/
    games.py                       # UPDATED: regenerate-coaching endpoint
    lab.py                         # UPDATED: /lab/{id}/coach-insight endpoint
    coach.py                       # UPDATED: V5 version check + auto-regeneration
  server.py                        # UPDATED: FlagMoveRequest with diagnostics
/app/frontend/src/
  pages/
    CoachPlay.jsx                  # UPDATED: P0 fixes
    Lab.jsx                        # UPDATED: Refresh Coaching button
    LabV2.jsx                      # UPDATED: Human Coach Review integrated in Coach view mode
    AdminDashboard.jsx             # UPDATED: Diagnostics display
  components/
    Lab/
      CoachInsightPanel.jsx        # 3-tab insight panel (Summary, Habits, Memory) — preserved
      CoachReview.jsx              # NEW: 5-section Human Coach Review (Story, Mirror, Moment, Takeaway, Proof)
    shared/
      FlagMoveDialog.jsx           # REWRITTEN: InlineFlag system
      V5CoachingCard.jsx           # UPDATED: Inline flags on every section
    GameDecryptionV5.jsx           # UPDATED: Inline flags on every section
```

---

## Backlog

### P1 - High Priority
- [ ] Integrate logo into app sidebar/favicon
- [ ] Refactor `GameDecryptionV5.jsx` to use shared `V5CoachingCard.jsx`
- [ ] Admin content management (edit openings/endgames theory)

### P2 - Medium Priority
- [ ] Endgame expansion (minor piece endgames)
- [ ] "Theory Applied" celebration streak indicator
- [ ] Habits Trend Dashboard

### P3 - Nice to Have
- [ ] Voice coaching mode
- [ ] CoachPlay.jsx refactoring (3500+ lines - split into smaller components)
- [ ] Coaching accuracy score (% of flags valid vs dismissed)

---

## Testing Status
- Iteration 166: Human Coach Review — 100% (13/13 backend, all frontend verified)
- Iteration 160: Endgame Lessons -- 100%
- Iteration 161: Super Admin Dashboard -- 100%
- Iteration 162: Player Profile Narrative -- 100%
- Iteration 163: CoachPlay P0 Fixes (all 4 issues) -- 100%
- Iteration 164: Coach Insight Panel (3-tab pivot) -- 100% (8/8 backend, all frontend verified)
- Iteration 165: Adaptive Decryption V5 + Habits Fix -- 100% (15/15 backend, all frontend verified)
- Book opening guard: manually tested with python3 -c (d5, c5, e6, Nf6 all correctly identified as book)
- Inline flagging: visually verified via screenshot, backend endpoint tested with curl
- Fork detection: verified with chess.BB_KNIGHT_ATTACKS bitboard tests

## Critical Notes
- **Mohit** (user_62852a1b64e7) = super_admin
- **V5_COACHING_VERSION = 4**: Bump when coaching logic changes, old games auto-refresh
- **Player profile cached**: `player_profiles` collection, regenerates every 5 games
- **LLM**: GPT-4o-mini via emergentintegrations (EMERGENT_LLM_KEY) — also used for Coach Review narrative layer
- **llm_helper.py**: Updated to use `emergentintegrations` package properly (was previously a shim calling OpenAI directly)
- **Never generic text**: All prompts demand specific, contextual output
- **Adaptive by design**: No user-facing config dropdowns

*Last Updated: March 2026*
