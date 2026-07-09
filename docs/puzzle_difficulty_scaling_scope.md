# Puzzle Difficulty Scaling: Auto-Progression System

**Goal:** Guide players through puzzles from easy → hard, boosting solve rate + confidence  
**Timeline:** Week 6-8 (6 hours)  
**Impact:** +0.2 points (8.7 → 8.9/10) via training effectiveness  
**Status:** 🔒 Locked scope — DO NOT START implementation until Mohit signs off

---

## 0. Existing Puzzle Infrastructure Audit

**What already exists:**
- ✅ `community_puzzles` (998 docs) — each has:
  - `fen`, `best_move_san`, `issue_type` (cognitive_gap)
  - `difficulty` (field may or may not be set)
  - `rating_min` / `rating_max` (auto-computed from extraction)
- ✅ `puzzle_attempts` (solves tracked) — puzzle_id, user_id, correct ✓/✗
- ✅ `PatternTraining.jsx` — renders puzzles in order
- ✅ `training/pattern/{pattern}` route — returns puzzles for that pattern
- ✅ User rating in `users` collection

**What's MISSING (must build):**
- Difficulty estimation algorithm (turn cp_loss into easy/medium/hard)
- Recommended difficulty picker (based on user rating)
- Auto-progression logic (show next difficulty when user hits 70% solve rate)
- UI filters (user can override, pick easy/medium/hard)
- Solve rate tracking per difficulty tier

**Design Decision:** Difficulty is NOT stored in DB initially. It's **computed on-the-fly** from `rating_min`, `rating_max`, and `cp_loss`. This keeps schema simple and avoids lock-in if we change the grading formula later.

---

## 1. What This Study Is

A **difficulty progression system** that:
1. Estimates puzzle difficulty from its metadata (cp_loss, rating range)
2. Recommends difficulty tier for each user (based on their rating)
3. Shows puzzles in ascending difficulty order
4. Auto-suggests next tier when user hits 70% solve rate on current tier
5. Allows manual override (user can request "give me hard puzzles")

**Why it matters:**
- Too easy → boring, user quits (solve rate: 95%, no learning)
- Too hard → frustrating, user quits (solve rate: 20%, demoralizing)
- Right difficulty → engaged, learning (solve rate: 60-75%, "flow" state)

---

## 2. What the User Sees

### Before (Current)
```
Training → Pattern: piece_safety
[List all 24 puzzles randomly ordered]
Puzzle 1: [Your knight on f3...]  ← No sense of progression
Puzzle 2: [Opponent's queen...]
Puzzle 3: [Rook on a1...]
```

### After (This Task)
```
Training → Pattern: piece_safety

🎯 Your Level: Intermediate (based on 1450 rating)
📊 Recommended: Medium difficulty

Difficulty:  [Easy] [Medium (you are here)] [Hard]

Solve rate: 12/18 on Medium (67%) — great! Try Hard next?
[+ Hard Puzzles button]

Medium Puzzles (18 total):
  ✓ Puzzle 1: Hang on f6 (cp_loss: 80)
  ✗ Puzzle 2: Queen on h5 (cp_loss: 120)
  ✓ Puzzle 3: Bishop fork (cp_loss: 95)
  
[Load more]
```

### UI Changes Required
- **Difficulty filter tabs** (Easy / Medium / Hard) above puzzle list
- **Recommended difficulty badge** ("📊 Recommended for your rating")
- **Solve rate meter** per difficulty ("12/18 solved, 67%")
- **Auto-progression prompt** ("You've solved 70%+ on Medium. Ready for Hard?")
- **Optional:** Sort by solve rate (show hardest-first within tier for challenge-seekers)

---

## 3. In Scope (Week 6-8)

**Phase 1: Difficulty Estimation (2 hours)**
- [ ] Algorithm: translate cp_loss → easy/medium/hard (see section 6)
- [ ] Compute on-demand: no DB writes (for now)
- [ ] Validate: spot-check 20 puzzles against human judgment

**Phase 2: Recommended Difficulty (1 hour)**
- [ ] Tier assignment: user rating → recommended difficulty
  - Rating 600-1000: Easy
  - Rating 1000-1500: Medium
  - Rating 1500+: Hard
- [ ] Fallback: if user has 0 puzzle history, recommend "Medium" (middle default)

**Phase 3: Backend API (1.5 hours)**
- [ ] `GET /api/training/pattern-puzzles/{pattern}?difficulty=medium`
- [ ] Returns: puzzles filtered by tier, sorted by cp_loss ascending
- [ ] Includes: `user_solve_rate_on_difficulty` (how many solved on Medium)

**Phase 4: Frontend Rendering (1 hour)**
- [ ] Add filter tabs (Easy/Medium/Hard) in PatternTraining.jsx
- [ ] Show recommended tier + solve rate meter
- [ ] Add optional "Ready for Hard?" prompt when ≥70%

**Phase 5: Testing (0.5 hours)**
- [ ] Manual: play trainer with different difficulty levels
- [ ] Verify: filter switching works, solve rate updates

---

## 4. Explicitly Out of Scope (V1)

- **Adaptive engine** (auto-scale difficulty without user choice) — deferred
- **Difficulty percentiles** (show user "You're harder than 85% of puzzles") — deferred
- **Spaced repetition** (show missed puzzles again after N days) — deferred
- **Puzzle tiers as stored data** (will compute on-demand only)
- **Elo-style rating for puzzles** (rating_min/rating_max only, no Elo)
- **Cross-pattern difficulty** (difficulty is per-pattern, not global)
- **Mobile UI tweaks** (will be part of Week 6-8 mobile testing task)

---

## 5. Success Criteria

**V1 succeeds if:**
1. ✅ Difficulty filter works (Easy/Medium/Hard tabs switch without errors)
2. ✅ Recommended tier displays correctly for 3 test users (different ratings)
3. ✅ Solve rate meter updates after each puzzle attempt
4. ✅ Auto-progression prompt fires at 70% solve rate on a tier
5. ✅ User can override (manually request "Hard" even on Easy rating)

**Metrics to track after launch (Week 8+):**
- Puzzle solve rate by difficulty (baseline: avg 45%, target: 60-75% per tier)
- Tier progression rate (% of users who advance from Easy → Medium → Hard)
- Training page retention (time spent, return visits)

---

## 6. Open Questions

| Question | Why unresolved | Unblocking step |
|----------|---|---|
| How do we compute "easy/medium/hard"? | Need exact formula | See Data Pipeline section |
| What if puzzle has no cp_loss? | Edge case | Default to Medium |
| Can user skip ahead (start on Hard)? | Override design needed | YES, allow manual selection |
| Should solved puzzles be hidden? | UX preference | NO, show all, sort by solve status |
| How many puzzles per tier? | Depends on extraction | Aim for ≥10 per tier per pattern |

---

## 7. Pre-Code Requirements

- [ ] Mohit approves difficulty formula (see section below)
- [ ] Difficulty estimation validated against 20 sample puzzles
- [ ] Schema confirmed (no new DB fields needed)
- [ ] Frontend route `/training/pattern/{pattern}?difficulty=medium` approved
- [ ] Mobile layout sketched (will adjust in Week 6-8 mobile task)

---

## Data Pipeline: Difficulty Formula

### Difficulty Estimation (Computed On-Demand)

For each puzzle in `community_puzzles`:

```python
def estimate_difficulty(puzzle: dict) -> str:
    """
    Compute easy/medium/hard from cp_loss and rating range.
    
    Inputs:
      puzzle["cp_loss"]: centipawn loss if best move not found
      puzzle["rating_min"]: min rating for this puzzle (auto-computed during extraction)
      puzzle["rating_max"]: max rating for this puzzle
    
    Returns: "easy" | "medium" | "hard"
    """
    cp_loss = puzzle.get("cp_loss", 100)  # default: medium
    rating_min = puzzle.get("rating_min", 1000)
    rating_max = puzzle.get("rating_max", 1500)
    
    # Two signals: cp_loss (material swing) + rating_min (who would find it hard)
    
    # Signal 1: cp_loss tier (tactic difficulty)
    if cp_loss <= 100:
        cp_tier = "easy"      # Small mistake
    elif cp_loss <= 250:
        cp_tier = "medium"    # Real mistake
    else:
        cp_tier = "hard"      # Big blunder/forcing sequence
    
    # Signal 2: rating_min tier (who struggles with this)
    if rating_min <= 1000:
        rating_tier = "easy"       # Beginners find it hard
    elif rating_min <= 1400:
        rating_tier = "medium"     # Intermediates find it hard
    else:
        rating_tier = "hard"       # Advanced players find it hard
    
    # Combine: use rating_min as primary (captures tactical depth better than cp_loss)
    # Upgrade cp_tier if cp_loss is very high (forcing sequence override)
    if cp_loss >= 400 and cp_tier == "easy":
        cp_tier = "hard"  # Even small-rating puzzles can be hard if forcing
    
    # Return rating_min-based tier, but allow cp_loss to upgrade
    if rating_tier == "easy":
        return "easy"
    elif rating_tier == "medium":
        return "medium" if cp_loss <= 200 else "hard"
    else:  # rating_tier == "hard"
        return "hard"
```

### Recommended Difficulty (User-Based)

For each user:

```python
def recommend_difficulty(user_rating: int) -> str:
    """
    Suggest difficulty tier based on player rating.
    """
    if user_rating < 1000:
        return "easy"
    elif user_rating < 1500:
        return "medium"
    else:
        return "hard"
```

### Auto-Progression (Per Difficulty Tier)

For each user + pattern + difficulty:

```python
def compute_solve_rate(user_id: str, pattern: str, difficulty: str) -> dict:
    """
    Solve rate = N_correct / N_attempted
    
    Returns: {
        "n_attempted": 5,
        "n_correct": 3,
        "solve_rate": 0.60,  # 60%
        "next_difficulty": "hard" if solve_rate >= 0.70 else None
    }
    """
    # Fetch from puzzle_attempts + community_puzzles (with computed difficulty)
    # Filter by pattern + difficulty tier
    attempts = db.puzzle_attempts.find({
        "user_id": user_id,
        "puzzle_id": { "$in": pattern_puzzle_ids },
        "difficulty_tier": difficulty
    })
    
    n_correct = sum(1 for a in attempts if a["correct"])
    n_attempted = len(attempts)
    solve_rate = n_correct / n_attempted if n_attempted > 0 else 0.0
    
    # Progression rule: 70% solve rate = ready for next tier
    next_tier = None
    if difficulty == "easy" and solve_rate >= 0.70:
        next_tier = "medium"
    elif difficulty == "medium" and solve_rate >= 0.70:
        next_tier = "hard"
    
    return {
        "n_attempted": n_attempted,
        "n_correct": n_correct,
        "solve_rate": solve_rate,
        "next_difficulty": next_tier,
    }
```

### Query: Puzzles by Difficulty

```python
async def get_pattern_puzzles(user_id: str, pattern: str, difficulty: str = None) -> list:
    """
    Returns puzzles for pattern, optionally filtered by difficulty.
    
    Difficulty is computed on-the-fly (not stored).
    """
    puzzles = await db.community_puzzles.find({
        "issue_type": pattern
    }).to_list(None)
    
    # Compute difficulty for each puzzle
    for p in puzzles:
        p["difficulty"] = estimate_difficulty(p)
    
    # Filter if requested
    if difficulty:
        puzzles = [p for p in puzzles if p["difficulty"] == difficulty]
    
    # Sort by cp_loss ascending (easy first within tier)
    puzzles.sort(key=lambda p: p.get("cp_loss", 100))
    
    # Annotate each with user's solve status
    puzzle_ids = [p["_id"] for p in puzzles]
    attempts = await db.puzzle_attempts.find({
        "user_id": user_id,
        "puzzle_id": {"$in": puzzle_ids}
    }).to_list(None)
    attempt_map = {a["puzzle_id"]: a["correct"] for a in attempts}
    
    for p in puzzles:
        p["user_solved"] = attempt_map.get(p["_id"], None)  # True/False/None
    
    return puzzles
```

---

## 8. API Endpoints (No New Endpoints, Query Param Only)

### Existing Endpoint Enhanced
```
GET /api/training/pattern-puzzles/{pattern}?difficulty=medium

Response:
{
  "pattern": "piece_safety",
  "recommended_difficulty": "medium",
  "user_rating": 1450,
  "filters": {
    "easy": {"available": 12, "user_solved": 8, "solve_rate": 0.67},
    "medium": {"available": 18, "user_solved": 12, "solve_rate": 0.67},
    "hard": {"available": 5, "user_solved": 1, "solve_rate": 0.20}
  },
  "next_recommended": "hard",  # null if not yet at 70%
  "puzzles": [
    {
      "_id": "pid_123",
      "fen": "...",
      "best_move_san": "Nxf3",
      "cp_loss": 95,
      "difficulty": "medium",
      "user_solved": true,
      "issue_type": "piece_safety"
    },
    ...
  ]
}
```

### New Optional Endpoint (Nice-to-Have)
```
GET /api/training/pattern-difficulty-summary/{pattern}

Response (for dashboard card):
{
  "pattern": "piece_safety",
  "user_level": "intermediate",
  "progress": {
    "easy": {"solved": 8, "total": 12, "progress": 0.67},
    "medium": {"solved": 12, "total": 18, "progress": 0.67},
    "hard": {"solved": 1, "total": 5, "progress": 0.20}
  },
  "can_progress_to": "hard",
  "mastered": false
}
```

---

## 9. Frontend: PatternTraining.jsx Changes

### Current Structure (Relevant Parts)
```jsx
<PatternTraining>
  <h1>{pattern}</h1>
  <PuzzleList puzzles={puzzles} />
</PatternTraining>
```

### After Difficulty Scaling
```jsx
<PatternTraining>
  <h1>{pattern}</h1>
  
  {/* NEW: Recommended difficulty banner */}
  <DifficultyRecommendation
    userRating={user.rating}
    recommended={recommendedDifficulty}
  />
  
  {/* NEW: Difficulty tabs + solve rate meter */}
  <DifficultySelector
    pattern={pattern}
    selectedDifficulty={difficulty}
    onSelectDifficulty={setDifficulty}
    solveRates={solveRates}  // e.g. {easy: 0.5, medium: 0.67, hard: 0.2}
  />
  
  {/* NEW: Auto-progression prompt */}
  {nextSuggested && (
    <ProgressionPrompt
      currentDifficulty={difficulty}
      nextDifficulty={nextSuggested}
      onAccept={() => setDifficulty(nextSuggested)}
    />
  )}
  
  {/* MODIFIED: PuzzleList now receives difficulty filter */}
  <PuzzleList puzzles={puzzles} difficulty={difficulty} />
</PatternTraining>
```

### New Components (Simple, ~100 lines each)
- `DifficultyRecommendation`: Shows "📊 Recommended: Medium for your 1450 rating"
- `DifficultySelector`: Three tabs (Easy/Medium/Hard) + solve rate under each
- `ProgressionPrompt`: "You've solved 70%+ on Medium. Ready for Hard?" with Yes/Skip buttons

---

## 10. Testing

### Manual Testing Checklist
- [ ] Play 5 puzzles on Easy difficulty → solve rate updates
- [ ] Difficulty tabs filter correctly (Easy shows N puzzles, Medium shows M, etc.)
- [ ] Recommended difficulty matches user rating (rating 800 → Easy, 1400 → Medium, 1800 → Hard)
- [ ] At 70% solve rate on Medium, "Ready for Hard?" prompt appears
- [ ] Can manually select difficulty (override recommendation)
- [ ] Solved puzzles show checkmark, unsolved show empty

### Edge Cases
- User with 0 puzzle history → defaults to recommended tier
- Puzzle with no cp_loss data → treated as Medium
- User rating recently changed → recommendation updates on page load
- User attempts Hard immediately (low rating) → allowed, but solve rate will be low

---

## 11. Commit Message

```
feat(training): puzzle difficulty scaling — auto-progression

Introduces difficulty tiers (easy/medium/hard) for puzzle training.
Players progress through tiers based on solve rate (70% = ready for next).

Features:
  - Difficulty estimation: easy/medium/hard computed from cp_loss + rating_min
  - Recommended tier: based on user rating (600-1000=easy, 1000-1500=medium, 1500+=hard)
  - Filter tabs: user can manually select tier
  - Solve rate meter: shows progress per tier
  - Auto-progression: "Ready for Hard?" prompt at 70% solve rate

UI:
  - DifficultySelector component (tabs + solve rate)
  - ProgressionPrompt component (context-aware next-tier nudge)
  - Enhanced PatternTraining.jsx

API:
  - GET /api/training/pattern-puzzles/{pattern}?difficulty=medium
  - Returns filtered puzzles + solve rate metadata

Impact: +0.2 points (8.7 → 8.9/10) via training effectiveness

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## Success Metrics (Post-Launch)

Track these after Week 8 to evaluate effectiveness:

| Metric | Target | How |
|--------|--------|-----|
| Puzzle solve rate (Easy) | 75-85% | Underestimating if too easy |
| Puzzle solve rate (Medium) | 60-70% | "Flow" state target |
| Puzzle solve rate (Hard) | 40-55% | Challenging but not demoralizing |
| Tier progression rate | ≥50% advance to Medium | Engagement signal |
| Training page time | +20% vs baseline | Stickiness (assuming better UX) |
| Puzzle attempts per user | +15% vs baseline | Driven by better progression |

If metrics show solve rates way off target, iterate:
- Too many "Easy" solves (>85%) → raise difficulty threshold
- Too many "Hard" quits (<30%) → lower difficulty threshold

