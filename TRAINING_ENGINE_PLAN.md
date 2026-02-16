# Training Engine Implementation Plan

## Overview
Build a **personalized behavioral correction system** that replaces Focus + Coach pages with a single step-by-step Training experience.

## Core Philosophy
- **Data-driven phases** (not rating-based)
- **One leak at a time** (1 Phase → 1 Micro Habit → 2 Rules)
- **Reflection reinforcement** (user input modifies weights)
- **Cross-user drill sourcing** (user's mistakes + similar users)

---

## Phase 1: Backend - Training Profile Service

### 1.1 Layer Definitions (Cost Scoring)

**Stability Layer** (blunders, hanging pieces)
- Blunders per game
- Hanging piece frequency (cp_loss >= 300)
- Rushed critical move % (moves < 5 seconds in critical positions)
- Threat blindness % (opponent had threat, user missed it)

**Conversion Layer** (failing to win won games)
- Win-state detection (+1.5 threshold)
- Eval drop when ahead (losing advantage)
- Win conversion rate (games where user was +2 but lost/drew)

**Structure Layer** (positional/opening issues)
- Opening deviation first 12 moves
- Equal-position eval stability
- Worst-piece inactivity (future)

**Precision Layer** (tactical/calculation errors)
- Eval drop in complex positions
- Depth error detection (shallow calculation)
- Endgame accuracy

### 1.2 Phase Selection Logic
```python
def select_active_phase(user_profile):
    layer_costs = {
        "stability": compute_stability_cost(games),
        "conversion": compute_conversion_cost(games),
        "structure": compute_structure_cost(games),
        "precision": compute_precision_cost(games)
    }
    return max(layer_costs, key=lambda k: layer_costs[k])
```

### 1.3 Micro Habit Selection
Within active phase, compute pattern weights:
```python
# Example for Stability phase
patterns = {
    "rushing": 0.41,  # moves too fast in critical positions
    "threat_blindness": 0.22,  # misses opponent threats
    "hanging_pieces": 0.37  # leaves pieces undefended
}
micro_habit = max(patterns, key=lambda k: patterns[k])
```

### 1.4 Rule Generation
2 rules per micro habit, scaled by rating:
- 400 rating: Simple, concrete
- 1800 rating: Deeper, more nuanced

---

## Phase 2: Reflection System

### 2.1 Post-Game Reflection (triggers after analysis)
Questions based on detected mistake patterns:
- "Were you rushing?"
- "Did you miss a threat?"
- "Were you overconfident?"

Store with game context for pattern analysis.

### 2.2 Pattern Weight Updates
User reflections nudge pattern weights:
- Repeatedly selects "We rushed" → Rushing weight increases
- Engine + reflection disagree → Engine wins, but weight nudges

---

## Phase 3: Drill System

### 3.1 Drill Sources
1. **User's own mistakes** - positions from their analyzed games
2. **Similar users' mistakes** - same rating band, same micro habit

### 3.2 Drill Matching
Match drills to:
- Current Phase
- Current Micro Habit
- Player rating band
- Real mistake contexts

### 3.3 Drill Progress Tracking
- Mark drills as completed
- Track success rate
- Rotate to new drills weekly

---

## Phase 4: Frontend - Training Page

### 4.1 Step-by-Step Flow

**Step 1: Phase Context**
- Show which layer is their biggest leak
- Visual breakdown of 4 layers
- Why this phase matters

**Step 2: Micro Habit**
- Within the phase, what specific pattern
- Pattern weights visualization
- Real examples from their games

**Step 3: Your Rules**
- 2 actionable rules for the week
- Simple, memorable
- Rating-appropriate language

**Step 4: Last Game Reflection**
- Did you follow the rules?
- What happened?
- Tag your thinking pattern

**Step 5: Training Drill**
- Position from user/similar user mistake
- Practice the correct response
- Track completion

### 4.2 Progress Tracking
- Weekly goals
- Drill completion rate
- Reflection consistency

---

## Database Schema

### training_profiles collection
```json
{
  "user_id": "user_xxx",
  "computed_at": "2025-02-16T...",
  "games_analyzed": 20,
  "layer_costs": {
    "stability": 1245.5,
    "conversion": 890.2,
    "structure": 450.1,
    "precision": 320.0
  },
  "active_phase": "stability",
  "pattern_weights": {
    "rushing": 0.41,
    "threat_blindness": 0.22,
    "hanging_pieces": 0.37
  },
  "micro_habit": "rushing",
  "current_rules": [
    "In sharp positions, pause before moving",
    "List two candidate moves before committing"
  ],
  "rating_at_computation": 1150
}
```

### reflections collection
```json
{
  "reflection_id": "ref_xxx",
  "user_id": "user_xxx",
  "game_id": "game_xxx",
  "created_at": "2025-02-16T...",
  "reflection_type": "post_game",
  "selected_tags": ["rushed", "missed_threat"],
  "free_text": "I was trying to attack but...",
  "pattern_impact": {
    "rushing": +0.05,
    "threat_blindness": +0.03
  }
}
```

### drill_positions collection
```json
{
  "drill_id": "drill_xxx",
  "source_user_id": "user_xxx",
  "source_game_id": "game_xxx",
  "fen": "r1bqkb1r/...",
  "phase": "stability",
  "micro_habit": "hanging_pieces",
  "rating_band": "900-1400",
  "correct_move": "Nf3",
  "explanation": "This protects the hanging knight...",
  "times_served": 0,
  "success_rate": null
}
```

---

## Implementation Order

### Week 1: Backend Foundation
1. Create training_profile_service.py
2. Implement 4-layer cost computation
3. Add phase selection + micro habit selection
4. Create API endpoints

### Week 2: Drill System
1. Create drill generation logic
2. Build cross-user drill matching
3. Add drill tracking

### Week 3: Frontend Training Page
1. Step-by-step wizard UI
2. Layer visualization
3. Rule display
4. Drill component

### Week 4: Reflection System
1. Post-game reflection prompt
2. Pattern weight updates
3. Integration with Training page

---

## Files to Create
- `/app/backend/training_profile_service.py` - Core training engine
- `/app/frontend/src/pages/Training.jsx` - New Training page
- Update `/app/frontend/src/App.js` - Routes
- Update `/app/frontend/src/components/Layout.jsx` - Nav
- Delete `/app/frontend/src/pages/FocusPage.jsx`
- Delete `/app/frontend/src/pages/Coach.jsx`

## Files to Modify
- `/app/backend/server.py` - Add training endpoints
