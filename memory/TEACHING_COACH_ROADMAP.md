# TEACHING COACH - ACTION ITEMS

## Vision Summary
Build an AI coach that TEACHES like a human coach - not defeating you, but actively teaching patterns, plans, tactics, openings, endgames as the game progresses.

---

## COMPLETED ✅

### 1. Game Phase Calculator
- **File**: `/app/backend/services/game_phase_service.py`
- **Features**:
  - Stockfish-style continuous phase (0-100%)
  - 18 endgame type classifications
  - Phase-specific coaching priorities
  - Endgame teaching database (Lucena, Philidor, Opposition, etc.)
- **Endpoint**: `POST /api/coach/analyze/phase`

---

## TO BUILD 🔨

### Priority 1: Teaching Move Selector
**Goal**: Coach selects moves that CREATE learning opportunities, not just best moves.

```
Location: /app/backend/services/teaching_move_selector.py

Features:
├── Get candidate moves from position
├── Score each move for TEACHING VALUE:
│   ├── Does it create a tactic user can find?
│   ├── Does it demonstrate a pattern user needs?
│   ├── Does it target user's weakness area?
│   └── Does it keep game interesting (not crushing)?
├── Select most instructive move (not necessarily strongest)
└── Generate explanation of WHY this move was chosen
```

### Priority 2: Position Teaching Engine (CUS)
**Goal**: For any position, know WHAT to teach.

```
Location: /app/backend/services/chess_understanding_service.py

Features:
├── Enhance existing position_strategy_analyzer.py:
│   ├── Add pawn structure classification
│   ├── Add pin/skewer detection (currently partial)
│   └── Add "what changes after this move" analysis
├── Create structure → plan mapping:
│   ├── "Sicilian Scheveningen" → "f4-f5 break, Nd5 sacrifice"
│   ├── "French Advance" → "c5 break, f6 break"
│   └── 50+ structure types
└── Pattern recognition for teaching moments
```

### Priority 3: Active Teaching Flow
**Goal**: Teach BEFORE, DURING, and AFTER each move.

```
Location: /app/backend/services/active_teaching_engine.py

Features:
├── before_user_move():
│   ├── "This is a key position because..."
│   ├── "The plan here is..."
│   ├── "Watch out for these patterns..."
│   └── "Before you move, what's your opponent's threat?"
├── during_thinking():
│   ├── [Optional] "Would you like a hint?"
│   └── [If stuck] "Look at the diagonal..."
├── after_user_move():
│   ├── "Good! That supports your plan because..."
│   ├── "Interesting choice. There was also..."
│   └── "Be careful! You left this undefended..."
└── after_coach_move():
    ├── "I played X because..."
    ├── "This is a classic pattern called..."
    └── "The idea is... Watch out for..."
```

### Priority 4: Opening Book Integration
**Goal**: Detect when in theory, teach opening principles.

```
Location: /app/backend/services/opening_teaching_service.py

Features:
├── Check if position is in opening book
├── Identify opening name and variation
├── Provide opening-specific teaching:
│   ├── "This is the Italian Game"
│   ├── "White's plan is..."
│   ├── "Black's plan is..."
│   ├── "Typical traps to avoid..."
│   └── "This leads to [type] of middlegame"
└── Announce when leaving theory
```

### Priority 5: Coach Play Endpoint Enhancement
**Goal**: Transform `/coach/play` into full teaching experience.

```
Location: /app/backend/routes/coach.py

New/Enhanced Endpoints:
├── POST /coach/play/start-lesson
│   └── Start a teaching game with curriculum
├── POST /coach/play/get-coach-move
│   └── Coach plays AND explains
├── POST /coach/play/get-teaching
│   └── Get teaching content for current position
├── POST /coach/play/submit-user-move
│   └── User plays, coach responds with feedback
└── POST /coach/play/get-hint
    └── Progressive hints without giving answer
```

### Priority 6: Human Coach Training Dashboard
**Goal**: 100% accuracy via human verification.

```
Location: /app/backend/routes/admin.py + /app/frontend/src/pages/CoachDashboard.jsx

Features:
├── View AI-generated explanations pending review
├── Approve / Edit / Reject flow
├── Verified explanations go to teaching database
├── Track coach quality metrics
└── Payment system for coach contributions
```

---

## EXISTING CODE TO ENHANCE

| File | Current | Enhancement Needed |
|------|---------|-------------------|
| `position_strategy_analyzer.py` | Basic position analysis | Add pawn structure, full tactical patterns |
| `stockfish_service.py` | Move evaluation | Add teaching-focused analysis |
| `CoachPlay.jsx` | User plays, coach comments | Coach plays AND teaches |
| `opening_detection_service.py` | Detect opening name | Add opening teaching content |

---

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                    TEACHING COACH SYSTEM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User's Position                                                 │
│        │                                                         │
│        ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │         CHESS UNDERSTANDING SERVICE (CUS)                │    │
│  │                                                          │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │    │
│  │  │ Game Phase  │  │ Position    │  │ Opening     │      │    │
│  │  │ Calculator  │  │ Analyzer    │  │ Detector    │      │    │
│  │  │ ✅ DONE     │  │ (enhance)   │  │ (enhance)   │      │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘      │    │
│  │                                                          │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │    │
│  │  │ Pawn        │  │ Tactical    │  │ Move Effect │      │    │
│  │  │ Structure   │  │ Pattern     │  │ Analyzer    │      │    │
│  │  │ (to build)  │  │ Detector    │  │ (to build)  │      │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘      │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              TEACHING MOVE SELECTOR                      │    │
│  │                                                          │    │
│  │  Input: Position + User's weaknesses + Lesson plan       │    │
│  │  Output: Most instructive move + Explanation             │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              ACTIVE TEACHING ENGINE                      │    │
│  │                                                          │    │
│  │  Before move: "The plan here is..."                     │    │
│  │  After user move: "Good! Because..."                    │    │
│  │  After coach move: "I played this because..."           │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                       LLM                                │    │
│  │                                                          │    │
│  │  Converts structured teaching → Natural language         │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│                    HUMAN-LIKE EXPLANATION                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## SUGGESTED BUILD ORDER

### Week 1: Core Teaching Infrastructure
1. ✅ Game Phase Calculator (DONE)
2. 🔨 Pawn Structure Classifier
3. 🔨 Enhanced Tactical Pattern Detector
4. 🔨 Move Effect Analyzer

### Week 2: Teaching Engine
5. 🔨 Teaching Move Selector
6. 🔨 Active Teaching Engine
7. 🔨 Opening Teaching Service

### Week 3: Integration & UI
8. 🔨 Coach Play Endpoint Enhancement
9. 🔨 CoachPlay.jsx - Full teaching UI
10. 🔨 Teaching content database (structures, plans)

### Week 4: Quality & Scale
11. 🔨 Human Coach Training Dashboard
12. 🔨 Verification workflow
13. 🔨 Content expansion

---

## SUCCESS METRICS

| Metric | Target |
|--------|--------|
| Teaching accuracy | 95%+ (with human verification) |
| User engagement in teaching games | 5+ min avg |
| Concepts taught per game | 3-5 |
| User reports "learned something" | 80%+ |
| Endgame position recognition | 95%+ |

---

*Last updated: 2025-03-07*
