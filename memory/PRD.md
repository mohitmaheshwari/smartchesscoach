# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized chess coaching application "Thinking Simulator" focusing on deep, insightful coaching for every move. Core features: "Play with Coach", "The Lab" for post-game analysis, "Community Intelligence Training", personalized Opening & Endgame study. UX principle: "One screen = one job."

---

## What's Been Implemented

### Player Profile Narrative - NEW (March 2026)
- **"Your Player Profile"** card on Progress page
- LLM-generated **2-3 sentence coaching narrative** comparing user to their rating band
- Purely observational — "who you are as a player", not prescriptive
- Based on real data: game results, opening diversity, phase where mistakes happen, blunder count
- **Cached in DB**, regenerates every **5 new games**
- Fallback narrative if LLM key unavailable
- API: `GET /api/progress/player-profile`

### Super Admin Dashboard (March 2026)
- Role system: `super_admin`, `admin`, `user`
- Overview, Users (search/filter/drill-down/create/role-change), Feedback Queue
- Flag button in Lab + Coach for users to report incorrect coaching
- Mohit Maheshwari set as super_admin

### Endgame Lesson System (March 2026)
- Study page with Openings | Endgames tabs
- 10 lessons, 30 positions, interactive Position → Try → Teach flow

### Previous Features (All Working)
- Community Intelligence Training, Opening Portrait, Pattern Memory
- V5 Decryption Engine, Pedagogical Opponent, Habit Insights
- Pattern Prescriptions, Theory Applied tracking

---

## Architecture
```
/app/backend/
├── services/
│   ├── player_profile_service.py    # NEW: Coaching narrative generation
│   ├── endgame_theory_service.py
│   ├── community_training_service.py
│   ├── shared_coaching_v5.py
│   ├── v5_llm_narrator.py
├── server.py  (all endpoints)
/app/frontend/src/
├── pages/
│   ├── AdminDashboard.jsx
│   ├── EndgameLesson.jsx
│   ├── UnifiedProgress.jsx          # UPDATED: Player Profile card
│   ├── OpeningsOverview.jsx
├── components/shared/
│   ├── FlagMoveDialog.jsx
│   ├── V5CoachingCard.jsx
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
- [ ] CoachPlay.jsx refactoring (3500+ lines)
- [ ] Weekly learning summary

---

## Testing Status
- Iteration 160: Endgame Lessons — 100%
- Iteration 161: Super Admin Dashboard — 100%
- Iteration 162: Player Profile Narrative — 100%

## Critical Notes
- **Mohit** (user_62852a1b64e7) = super_admin
- **Player profile cached**: `player_profiles` collection, regenerates every 5 games
- **Endgame JSON cached**: Restart backend after changes
- **LLM**: GPT-4.1-mini via emergentintegrations (EMERGENT_LLM_KEY)
- **Never generic text**: All prompts demand specific, contextual output

*Last Updated: March 2026*
