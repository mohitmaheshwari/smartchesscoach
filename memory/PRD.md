# Chess Coaching App - Product Requirements Document

## Original Problem Statement
Build a hyper-personalized chess coaching application "Thinking Simulator" focusing on deep, insightful coaching for every move. Core features: "Play with Coach", "The Lab" for post-game analysis, "Community Intelligence Training", personalized Opening & Endgame study. UX principle: "One screen = one job."

## Vision
NOT a "move explanation system" but a "Thinking Simulator" that trains the user's thinking process. Never generic coaching — always specific.

---

## What's Been Implemented

### Super Admin Dashboard - NEW (March 2026)
- **Role system**: `super_admin`, `admin`, `user` roles in DB
- **Admin Dashboard** at `/admin` with 3 tabs:
  - **Overview**: Total users, active 7d/30d, games, analyses, community pool, feedback pending
  - **Users**: Search, filter by role, per-user drill-down (habits, games, progress), create users, change roles
  - **Feedback Queue**: Status/source filters, expand for details (FEN, move, coaching text), admin actions (Ack/Valid/Dismiss)
- **Feedback Flag System**: Users can flag incorrect coaching in both Lab and Coach via "Flag" button
- **Nav link**: Admin link in sidebar, only visible to admin/super_admin users
- APIs: `GET /api/admin/overview`, `GET /api/admin/users`, `GET/POST /api/admin/users/*`, `GET/PATCH /api/admin/feedback/*`, `POST /api/feedback/flag`
- Mohit Maheshwari (user_62852a1b64e7) set as super_admin

### Endgame Lesson System (March 2026)
- **Study page** has Openings | Endgames tabs
- **10 endgame lessons** across 3 categories (King & Pawn, Rook, Queen vs Pawn)
- **30 validated positions** with interactive Position → Try → Teach flow
- APIs: `GET /api/endgames/categories`, `GET /api/endgames/lesson/{cat}/{key}`, `POST /api/endgames/check-move`

### Previous Features (All Working)
- Community Intelligence Training, Opening Portrait, Pattern Memory
- V5 Decryption Engine, Pedagogical Opponent, Habit Insights
- Pattern Prescriptions, Theory Applied tracking
- Interactive board previews, Variation selectors

---

## Architecture
```
/app
├── backend/
│   ├── data/coaching/
│   │   ├── opening_theory_tree.json
│   │   └── endgame_theory_tree.json
│   ├── services/
│   │   ├── endgame_theory_service.py
│   │   ├── community_training_service.py
│   │   ├── shared_coaching_v5.py
│   ├── server.py  (admin + feedback + endgame endpoints)
└── frontend/src/
    ├── pages/
    │   ├── AdminDashboard.jsx        # NEW: Admin Overview/Users/Feedback
    │   ├── EndgameLesson.jsx         # NEW: Interactive endgame lessons
    │   ├── OpeningsOverview.jsx      # UPDATED: Study tabs
    │   ├── HomePage.jsx, CoachPlay.jsx, etc.
    ├── components/
    │   ├── shared/
    │   │   ├── FlagMoveDialog.jsx    # NEW: Flag button + dialog
    │   │   └── V5CoachingCard.jsx    # UPDATED: Flag button added
    │   ├── GameDecryptionV5.jsx      # UPDATED: Flag button added
```

## Tech Stack
- Frontend: React, Tailwind CSS, Shadcn/UI, chess.js, Chessground
- Backend: FastAPI, MongoDB (Motor async), python-chess, Stockfish
- LLM: GPT-4.1-mini via emergentintegrations

---

## Backlog

### P1 - High Priority
- [ ] Refactor `GameDecryptionV5.jsx` to use shared `V5CoachingCard.jsx`
- [ ] Admin content management (edit openings/endgames theory)

### P2 - Medium Priority
- [ ] Endgame expansion (minor piece endgames, more positions)
- [ ] "Theory Applied" celebration streak indicator
- [ ] Community position opt-in/opt-out
- [ ] Habits Trend Dashboard

### P3 - Nice to Have
- [ ] Voice coaching mode
- [ ] Major refactoring of `CoachPlay.jsx` (3500+ lines)
- [ ] Weekly learning summary
- [ ] Comparative analysis with similar-rated players

---

## Testing Status
- Iteration 160: Endgame Lessons — Backend 22/22, Frontend 100%
- Iteration 161: Super Admin Dashboard — Backend 22/22, Frontend 100%

## Critical Notes
- **Mohit Maheshwari** (user_62852a1b64e7) = super_admin
- **Endgame JSON cached**: Restart backend after changes
- **Feedback collection**: `move_feedback` in MongoDB
- **Role field**: Added to User model, returned by `/auth/me`
- **Never generic LLM text**: Prompts must demand specific explanations

*Last Updated: March 2026*
