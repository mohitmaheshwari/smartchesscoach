# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized chess coaching application "Thinking Simulator" focusing on deep, insightful coaching for every move. Core features: "Play with Coach", "The Lab" for post-game analysis, "Community Intelligence Training", personalized Opening & Endgame study. UX principle: "One screen = one job."

---

## What's Been Implemented

### CoachPlay P0 Fixes - March 2026
- **Issue 1: State Sync** - executeMove now immediately clears all coaching state (v5Coaching, interactiveCoaching, behavioralCoaching, currentInsight) and shows "Analyzing your move..." indicator until new feedback arrives
- **Issue 2: LLM Hallucination on Tactics** - Fork detection in `shared_coaching_v5.py` now uses `BB_KNIGHT_ATTACKS` bitboard for precise knight-only attack detection (prevents false positives from other pieces). Threshold raised from 5 to 6.
- **Issue 3: Opening Lesson Persists** - Opening suggestion card auto-dismisses after 14 half-moves. Rendering condition also checks move count.
- **Issue 4: Adaptive UX** - Removed Time Control and Coaching Style selectors from setup screen. Removed "Lvl X" badge from coach info bar. Only Color Selection + Start Game remain.

### Player Profile Narrative (March 2026)
- LLM-generated 2-3 sentence coaching narrative comparing user to rating band
- Cached in DB, regenerates every 5 new games
- API: `GET /api/progress/player-profile`

### Super Admin Dashboard (March 2026)
- Role system: `super_admin`, `admin`, `user`
- Overview, Users, Feedback Queue tabs
- Flag button in Lab + Coach for users to report incorrect coaching

### Endgame Lesson System (March 2026)
- 10 lessons, 30 positions, interactive Position -> Try -> Teach flow

### Previous Features (All Working)
- Community Intelligence Training, Opening Portrait, Pattern Memory
- V5 Decryption Engine, Pedagogical Opponent, Habit Insights
- Pattern Prescriptions, Theory Applied tracking

---

## Architecture
```
/app/backend/
  services/
    shared_coaching_v5.py          # UPDATED: Fork detection fix
    player_profile_service.py
    endgame_theory_service.py
    v5_llm_narrator.py
  server.py
/app/frontend/src/
  pages/
    CoachPlay.jsx                  # UPDATED: P0 fixes (state sync, adaptive UI, opening phase)
    AdminDashboard.jsx
    EndgameLesson.jsx
    UnifiedProgress.jsx
  components/shared/
    FlagMoveDialog.jsx
    V5CoachingCard.jsx
```

---

## Backlog

### P1 - High Priority
- [ ] Refactor `GameDecryptionV5.jsx` to use shared `V5CoachingCard.jsx`
- [ ] Admin content management (edit openings/endgames theory)

### P2 - Medium Priority
- [ ] Endgame expansion (minor piece endgames)
- [ ] "Theory Applied" celebration streak indicator
- [ ] Habits Trend Dashboard

### P3 - Nice to Have
- [ ] Voice coaching mode
- [ ] CoachPlay.jsx refactoring (3500+ lines - split into smaller components)
- [ ] Weekly learning summary

---

## Testing Status
- Iteration 160: Endgame Lessons -- 100%
- Iteration 161: Super Admin Dashboard -- 100%
- Iteration 162: Player Profile Narrative -- 100%
- Iteration 163: CoachPlay P0 Fixes (all 4 issues) -- 100%

## Critical Notes
- **Mohit** (user_62852a1b64e7) = super_admin
- **Player profile cached**: `player_profiles` collection, regenerates every 5 games
- **Endgame JSON cached**: Restart backend after changes
- **LLM**: GPT-4.1-mini via emergentintegrations (EMERGENT_LLM_KEY)
- **Never generic text**: All prompts demand specific, contextual output
- **Adaptive by design**: No user-facing config dropdowns -- app adapts to user behind the scenes

*Last Updated: March 2026*
