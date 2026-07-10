# Issue-Driven Coaching Loop — Architecture

## 1. Data Schema

### Collections

#### `training_plans` (shared catalog)
```javascript
{
  _id: ObjectId,
  plan_id: "critical_moment_thinking" | "loose_piece_discipline" | "spot_tactical_opportunities" | "king_safety" | "convert_winning_positions",
  name: string,
  description: string,
  duration_minutes: number,
  issue_types_addressed: ["rushing", "calculation_depth", ...],
  components: {
    lesson: { description: string },
    puzzles: { count: number, source: "pattern_training" },
    coached_game: { description: string },
    review: { description: string }
  },
  created_at: date
}
```

**Records:** 5 (static, created once)

---

#### `user_coaching_prescriptions` (active/completed)
```javascript
{
  _id: ObjectId,
  user_id: string,
  prescription_id: UUID,
  plan_id: string (ref to training_plans),
  status: "active" | "completed" | "paused",
  is_coach_recommended: boolean,
  user_chose_alternative: boolean,
  priority_order: 1 | 2 | 3, // 1=primary (coach), 2+=secondary (user)
  
  // Evidence + reasoning
  issue_detected: "rushing" | "piece_safety" | "missed_tactic" | "king_safety" | "conversion",
  reasoning: string, // "You rushed 18 times, lost material 7 times. This plan teaches you to slow down."
  
  // Metrics tracking
  baseline_metric: {
    name: "rushed_moves_per_game", // or "pieces_undefended_per_game", etc
    value: 0.55,
    calculated_from_games: ["game_id1", "game_id2", ...] // last 20 games
  },
  current_metric: {
    value: 0.38,
    calculated_at: date,
    calculated_from_games: ["game_id1", ...]
  },
  improvement_pct: 31, // (0.55 - 0.38) / 0.55 * 100
  
  // Lifecycle
  started_at: date,
  completed_at: date | null,
  last_metric_update: date,
  games_since_start: ["game_id1", "game_id2", ...],
  
  created_at: date,
  updated_at: date
}
```

**Indexes:**
- `{user_id, status}` — Fetch active prescriptions for user
- `{user_id, status, priority_order}` — Fetch by priority
- `{user_id, completed_at}` — Fetch completion history

---

#### `coaching_prescription_history` (audit log)
```javascript
{
  _id: ObjectId,
  user_id: string,
  prescription_id: UUID,
  action: "prescribed" | "accepted" | "chose_alternative" | "ignored" | "completed",
  
  // If action = "prescribed"
  issue_detected: string,
  coach_recommended_plan_id: string,
  reasoning: string,
  prescribed_at: date,
  
  // If action = "accepted" or "chose_alternative"
  user_response: "accepted" | "chose_alternative" | "ignored",
  user_chose_plan_id: string, // if chose_alternative
  accepted_at: date,
  
  // If action = "completed"
  baseline_metric_value: 0.55,
  final_metric_value: 0.15,
  improvement_pct: 73,
  completed_at: date,
  total_games_during_plan: number,
  
  created_at: date
}
```

**Index:** `{user_id, created_at}` — Fetch prescription history

---

#### `issue_to_plan_mapping` (configuration)
```javascript
{
  _id: ObjectId,
  issue_type: "rushing" | "piece_safety" | "missed_tactic" | "king_safety" | "conversion",
  recommended_plans: [
    {
      plan_id: string,
      confidence_pct: 95,
      reason: "This plan directly teaches..."
    },
    {
      plan_id: string,
      confidence_pct: 60,
      reason: "Addresses root cause..."
    }
  ],
  prerequisites: [
    {
      issue_type: "other_issue",
      reason: "Fix this first because..."
    }
  ],
  
  created_at: date,
  updated_at: date
}
```

**Records:** ~10 (one per issue type)

---

### Modified Collections

#### `users` (add field)
```javascript
{
  ...existing fields...,
  
  // Track if user can handle parallel plans
  coaching_profile: {
    competence_level: "single_threaded" | "multi_threaded", // Auto-detected
    plan_completion_speed: "slow" | "medium" | "fast", // Based on historical data
    last_assessed_at: date
  }
}
```

---

## 2. Auto-Prescription Engine

### Trigger Points

After each game is analyzed (in `analysis_worker.py`):

```
if game_analysis.is_analyzed:
  1. Detect issues in this game (cognitive_gap + motif)
  2. Update user's issue tracking
  3. Check user's active prescriptions
  4. If user has no active prescriptions OR just completed one:
     → Auto-generate next prescription
     → Queue for homepage display (don't show until page load)
  5. If user has active prescriptions:
     → Update metrics for each
     → Check if any hit 50% improvement (auto-complete)
```

---

### Issue Detection Logic

For each move in game_analysis.stockfish_analysis.move_evaluations:

```python
def detect_issues_from_move(move, user_color):
  issues = []
  
  # Cognitive gap (from analysis_interpreter.py)
  cognitive_gap = move.get("cognitive_gap")
  if cognitive_gap in ["piece_safety", "king_safety", "missed_tactic", ...]:
    issues.append({
      type: cognitive_gap,
      source: "cognitive_gap",
      severity: "high" if cp_loss > threshold else "medium"
    })
  
  # Motif profile (from motif_profile_service.py)
  if motif_was_missed(move):
    issues.append({
      type: "missed_tactic_fork" | "missed_tactic_pin" | "missed_tactic_skewer",
      source: "motif",
      severity: "high"
    })
  
  # Time-based rushing detection
  if move.time_spent_seconds < 3 and position_is_complex(move.fen_before):
    issues.append({
      type: "rushing",
      source: "time_pressure",
      severity: "high" if cp_loss > 300 else "medium"
    })
  
  return issues
```

---

### Prescription Generation Logic

```python
async def generate_next_prescription(user_id):
  # 1. Get user's active prescriptions
  active = await db.user_coaching_prescriptions.find({
    "user_id": user_id,
    "status": "active"
  }).to_list(None)
  
  # If user has no active prescriptions
  if not active:
    # 2. Analyze last 20 games for issues
    games = await db.games.find({"user_id": user_id}).sort("date_played", -1).to_list(20)
    
    all_issues = []
    for game in games:
      analysis = await db.game_analyses.find_one({"game_id": game["game_id"]})
      moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
      for move in moves:
        issues = detect_issues_from_move(move, game["user_color"])
        all_issues.extend(issues)
    
    # 3. Aggregate issues by type (frequency + severity + trend)
    issue_summary = aggregate_issues(all_issues)  # {"rushing": 18, "piece_safety": 7, ...}
    
    # 4. Pick top issue (highest impact)
    top_issue = max(issue_summary, key=lambda x: x["frequency"])
    
    # 5. Look up best training plan for this issue
    mapping = await db.issue_to_plan_mapping.find_one({
      "issue_type": top_issue["type"]
    })
    
    best_plan = mapping["recommended_plans"][0]  # Highest confidence
    
    # 6. Check prerequisites (is user ready for this plan?)
    for prereq in mapping.get("prerequisites", []):
      prereq_active = await db.user_coaching_prescriptions.find_one({
        "user_id": user_id,
        "issue_detected": prereq["issue_type"],
        "status": "completed"
      })
      if not prereq_active:
        # Prescribe prerequisite first
        best_plan = await get_plan_for_issue(prereq["issue_type"])
    
    # 7. Create prescription
    prescription = {
      user_id: user_id,
      prescription_id: uuid(),
      plan_id: best_plan["plan_id"],
      status: "active",
      is_coach_recommended: True,
      issue_detected: top_issue["type"],
      reasoning: f"In your last 20 games, you {issue_description}. This plan teaches you to {solution}.",
      baseline_metric: {
        name: get_metric_for_issue(top_issue["type"]),
        value: calculate_baseline(user_id, top_issue["type"]),
        calculated_from_games: [g.get("game_id") for g in games]
      },
      current_metric: None,
      started_at: None,
      priority_order: 1,
      created_at: now()
    }
    
    # 8. Save prescription
    result = await db.user_coaching_prescriptions.insert_one(prescription)
    
    # 9. Log in prescription history
    await db.coaching_prescription_history.insert_one({
      user_id: user_id,
      prescription_id: prescription["prescription_id"],
      action: "prescribed",
      issue_detected: top_issue["type"],
      coach_recommended_plan_id: best_plan["plan_id"],
      reasoning: prescription["reasoning"],
      prescribed_at: now()
    })
    
    return prescription
  
  # If user has active prescriptions, update metrics
  else:
    for prescription in active:
      # Calculate current metric from games since start
      new_metric_value = calculate_metric(user_id, prescription["baseline_metric"]["name"])
      improvement_pct = ((prescription["baseline_metric"]["value"] - new_metric_value) / 
                         prescription["baseline_metric"]["value"] * 100)
      
      # Update prescription
      await db.user_coaching_prescriptions.update_one(
        {"_id": prescription["_id"]},
        {"$set": {
          "current_metric": {
            "value": new_metric_value,
            "calculated_at": now()
          },
          "improvement_pct": improvement_pct,
          "updated_at": now()
        }}
      )
      
      # If improvement >= 50%, auto-complete
      if improvement_pct >= 50:
        await db.user_coaching_prescriptions.update_one(
          {"_id": prescription["_id"]},
          {"$set": {
            "status": "completed",
            "completed_at": now()
          }}
        )
        
        # Log completion
        await db.coaching_prescription_history.insert_one({
          user_id: user_id,
          prescription_id: prescription["prescription_id"],
          action: "completed",
          baseline_metric_value: prescription["baseline_metric"]["value"],
          final_metric_value: new_metric_value,
          improvement_pct: improvement_pct,
          completed_at: now()
        })
        
        # Trigger next prescription (recursive call after short delay)
        # This ensures coaching never pauses
```

---

## 3. Metric Calculation

### Per-Issue-Type Metrics

```python
ISSUE_METRICS = {
  "rushing": {
    name: "rushed_moves_per_game",
    calculate: lambda user, games: (
      count(moves where time < 3s AND position_complex) / len(games)
    ),
    baseline_window: 20,  # Use last 20 games
  },
  "piece_safety": {
    name: "pieces_undefended_per_game",
    calculate: lambda user, games: (
      count(undefended pieces that were lost) / len(games)
    ),
    baseline_window: 20,
  },
  "missed_tactic": {
    name: "tactical_opportunities_seen_pct",
    calculate: lambda user, games: (
      count(tactics user found) / count(tactics that existed) * 100
    ),
    baseline_window: 20,
  },
  "king_safety": {
    name: "king_threats_defended_pct",
    calculate: lambda user, games: (
      count(king threats user defended) / count(total king threats) * 100
    ),
    baseline_window: 20,
  },
  "conversion": {
    name: "won_positions_converted_pct",
    calculate: lambda user, games: (
      count(won games from won positions) / count(total won positions) * 100
    ),
    baseline_window: 20,
  },
}
```

---

## 4. API Endpoints

### GET `/api/coaching/current-prescriptions`

**Response:**
```javascript
{
  active_prescriptions: [
    {
      prescription_id: UUID,
      plan_id: "critical_moment_thinking",
      plan_name: "Critical Moment Thinking",
      status: "active",
      priority_order: 1, // 1 = primary (coach-recommended), 2+ = secondary
      is_coach_recommended: true,
      
      issue_detected: "rushing",
      reasoning: "In your last 20 games, you rushed 18 critical moments and lost material 7 times...",
      
      duration_minutes: 15,
      
      baseline_metric: {
        label: "Rushed moves per game",
        value: 0.55
      },
      current_metric: {
        label: "Rushed moves per game",
        value: 0.38
      },
      improvement_pct: 31,
      progress_pct: 62, // (31 / 50) * 100
      
      started_at: "2026-07-10T14:30:00Z",
      estimated_completion: "2026-07-17T14:30:00Z", // start + duration (estimated)
    },
    {
      prescription_id: UUID,
      plan_id: "loose_piece_discipline",
      priority_order: 2,
      is_coach_recommended: false,
      user_chose_alternative: true,
      
      issue_detected: "piece_safety",
      reasoning: "You suggested we also work on piece safety...",
      
      baseline_metric: { label: "Pieces undefended per game", value: 0.8 },
      current_metric: { label: "Pieces undefended per game", value: 0.68 },
      improvement_pct: 15,
      progress_pct: 30,
    }
  ],
  
  total_active: 2,
  primary_plan_index: 0
}
```

---

### GET `/api/coaching/next-prescription`

Called when user has NO active prescriptions (or just completed one).

**Response:**
```javascript
{
  available: true, // or false if all issues solved
  
  prescription: {
    prescription_id: UUID,
    plan_id: "loose_piece_discipline",
    plan_name: "Loose Piece Discipline",
    
    issue_detected: "piece_safety",
    reasoning: "You've fixed the rushing problem. Now that you have time to think, we can work on piece safety. In your last 30 games, you left 14 pieces undefended—all because you attacked before checking what was defended.",
    
    duration_minutes: 12,
    
    // Confidence from issue_to_plan_mapping
    confidence_pct: 90,
    confidence_reason: "This plan directly addresses undefended pieces",
    
    components: [
      "Lesson: Scan for safety before attacking",
      "3 puzzles on piece safety",
      "1 coached game",
      "Post-game review"
    ]
  },
  
  // Alternative plans user can choose instead
  alternatives: [
    {
      plan_id: "spot_tactical_opportunities",
      confidence_pct: 60,
      reason: "Missed tactics often come from hasty piece placement"
    }
  ]
}
```

---

### POST `/api/coaching/accept-prescription`

User accepts the coach's recommendation.

**Request:**
```javascript
{
  prescription_id: UUID
}
```

**Response:**
```javascript
{
  status: "accepted",
  message: "Great! Let's work on Loose Piece Discipline.",
  prescription: { ...same as GET /current-prescriptions[0] }
}
```

---

### POST `/api/coaching/choose-alternative`

User picks a different plan instead of coach's recommendation.

**Request:**
```javascript
{
  prescription_id: UUID, // The coach's recommendation (to reject)
  chosen_plan_id: "spot_tactical_opportunities"
}
```

**Response:**
```javascript
{
  status: "accepted_alternative",
  message: "OK, here's why I recommended Loose Piece Discipline... But you're right, Spot Tactical Opportunities is also important. Let's track both.",
  
  primary: { ...coach recommendation... },
  secondary: { ...user's chosen alternative... }
}
```

---

### POST `/api/coaching/add-parallel-plan`

User adds another plan to work on alongside their current one.

**Request:**
```javascript
{
  plan_id: "king_safety"
}
```

**Response:**
```javascript
{
  status: "added",
  message: "Added! You're now working on both plans.",
  all_prescriptions: [ ...updated list... ]
}
```

---

### GET `/api/coaching/prescription-history`

User views their completed training plans.

**Response:**
```javascript
{
  completed_prescriptions: [
    {
      plan_id: "critical_moment_thinking",
      plan_name: "Critical Moment Thinking",
      issue_detected: "rushing",
      
      baseline_metric: { label: "Rushed moves per game", value: 0.55 },
      final_metric: { label: "Rushed moves per game", value: 0.15 },
      improvement_pct: 73,
      
      completed_at: "2026-07-17T14:30:00Z",
      duration_days: 7
    }
  ]
}
```

---

## 5. Frontend Data Flow

### HomePage Component Flow

```
HomePage loads
  ↓
fetch GET /api/coaching/current-prescriptions
  ↓
  IF active prescriptions exist:
    → Render primary prescription (priority_order=1) prominently
    → Render secondary prescriptions (priority_order=2+) below
    → Show progress bars + metrics
  ↓
  IF no active prescriptions:
    → fetch GET /api/coaching/next-prescription
    → Render coach recommendation card with evidence + reasoning
    → Show alternatives (if any)
    → Show [Start Training Plan] + [I'd rather learn something else] CTAs
  ↓
  IF user clicks [Start Training Plan]:
    → POST /api/coaching/accept-prescription
    → Redirect to training plan (link to /training/pattern/:pattern or /training/coach-play)
  ↓
  IF user clicks [I'd rather learn something else]:
    → Show alternatives dropdown
    → POST /api/coaching/choose-alternative with chosen plan_id
```

---

## 6. Migration Strategy

### From focus_locks to user_coaching_prescriptions

**One-time backfill (non-destructive):**

```python
async def migrate_focus_locks_to_prescriptions():
  # 1. Read all active focus_locks
  focus_locks = await db.focus_locks.find({
    "active": True
  }).to_list(None)
  
  # 2. For each focus_lock, create a user_coaching_prescription
  for lock in focus_locks:
    user_id = lock["user_id"]
    focus_type = lock["focus_type"]  # e.g., "THREAT_VERIFICATION"
    
    # Map focus_type to issue type + plan
    issue_type = map_focus_to_issue(focus_type)
    plan_id = get_plan_for_issue(issue_type)
    
    # Get current metrics (from last 20 games)
    baseline = calculate_baseline(user_id, issue_type)
    current = calculate_metric(user_id, issue_type)
    improvement = ((baseline - current) / baseline * 100) if baseline > 0 else 0
    
    # Create prescription
    prescription = {
      user_id: user_id,
      prescription_id: uuid(),
      plan_id: plan_id,
      status: "active" if improvement < 50 else "completed", // Auto-complete if already improved
      is_coach_recommended: True,
      issue_detected: issue_type,
      reasoning: f"Migrated from focus system: {focus_type}",
      baseline_metric: { value: baseline },
      current_metric: { value: current },
      improvement_pct: improvement,
      started_at: lock.get("created_at", now()),
      priority_order: 1,
      created_at: now()
    }
    
    await db.user_coaching_prescriptions.insert_one(prescription)
  
  # 3. Log migration in prescription history
  for prescription in await db.user_coaching_prescriptions.find({"created_at": {"$gte": now()}}):
    await db.coaching_prescription_history.insert_one({
      user_id: prescription["user_id"],
      prescription_id: prescription["prescription_id"],
      action: "prescribed",
      issue_detected: prescription["issue_detected"],
      reasoning: "Migrated from legacy focus system",
      prescribed_at: prescription["created_at"]
    })
  
  print(f"Migrated {len(focus_locks)} focus_locks to prescriptions")
```

**Result:** Users keep their current training, seamlessly moved to new system. No disruption.

---

## 7. Competence Detection (Auto-Parallel)

```python
async def assess_user_competence(user_id):
  # Get user's completed prescriptions
  completions = await db.coaching_prescription_history.find({
    "user_id": user_id,
    "action": "completed"
  }).to_list(None)
  
  if not completions:
    return "single_threaded"
  
  # Calculate completion speed (avg days per plan)
  completion_speeds = []
  for completion in completions:
    duration = (completion["completed_at"] - completion["prescribed_at"]).days
    completion_speeds.append(duration)
  
  avg_speed = sum(completion_speeds) / len(completion_speeds)
  
  if avg_speed < 7:  # Completes plans in less than a week
    level = "multi_threaded"
  elif avg_speed < 14:  # 1-2 weeks
    level = "single_threaded"
  else:  # 2+ weeks
    level = "single_threaded"
  
  # Update user profile
  await db.users.update_one(
    {"user_id": user_id},
    {"$set": {
      "coaching_profile": {
        "competence_level": level,
        "plan_completion_speed": "fast" if avg_speed < 7 else ("medium" if avg_speed < 14 else "slow"),
        "last_assessed_at": now()
      }
    }}
  )
  
  return level
```

---

## 8. Implementation Phases

### Phase 1: Data Model + Auto-Engine (Week 1-2)
- [ ] Create MongoDB collections
- [ ] Implement issue detection logic
- [ ] Implement auto-prescription generation
- [ ] Implement metric calculation

### Phase 2: APIs (Week 2)
- [ ] Implement GET `/api/coaching/current-prescriptions`
- [ ] Implement GET `/api/coaching/next-prescription`
- [ ] Implement POST endpoints (accept/choose/add)
- [ ] Implement prescription history

### Phase 3: Frontend (Week 3)
- [ ] Replace FocusCard with CoachingPrescriptions component
- [ ] Implement prescription display (primary + secondary)
- [ ] Implement recommendation card (next prescription)
- [ ] Implement CTA flows (accept/choose/add)

### Phase 4: Migration + Testing (Week 3-4)
- [ ] Run focus_locks → prescriptions backfill
- [ ] Test auto-prescription triggering on game completion
- [ ] Test metric updates on game analysis
- [ ] Test 50% auto-complete
- [ ] Test parallel plan tracking

---

## Summary

This architecture creates a **closed-loop coaching system**:

1. User plays game
2. Game analyzed → issues detected
3. Coach prescribes next training plan (if no active plans)
4. User accepts/chooses/adds parallel
5. System tracks improvement
6. At 50% improvement → auto-complete → prescribe next
7. Repeat

All data-driven. No human intervention. Continuous coaching loop.

