# Coaching System Database Schema

## Overview

The coaching system provides personalized, structured training plans to address identified cognitive gaps in chess performance. It consists of 5 interconnected MongoDB collections plus coaching metadata embedded in the users collection.

**Status:** Schema created, indexes defined, 24 tests passing ✅

---

## Collections

### 1. training_plans

**Purpose:** Stores 5 predefined coaching programs, each targeting specific cognitive gaps.

**Sample Documents:** 5 (preloaded)

**Key Fields:**
- `plan_id` (string, unique): Stable identifier (e.g., `plan_piece_safety_001`)
- `name` (string): Display name
- `description` (string): What the plan teaches
- `difficulty` (enum): `beginner` | `intermediate` | `advanced` | `expert`
- `target_rating_min/max` (int): Recommended rating range
- `duration_weeks` (int): Expected completion time
- `weekly_commitment_hours` (int): Recommended weekly study time
- `cognitive_gap` (string): Primary gap addressed (e.g., `piece_safety`, `calculation_depth`)
- `related_gaps` (array): Secondary gaps this plan also helps with
- `learning_outcomes` (array): What students will learn
- `modules` (array): Structured modules with:
  - `module_id`, `title`, `description`
  - `duration_minutes`, `content_type` (interactive_lesson, pattern_drill, puzzle_rush, personalized_review)
  - `puzzle_count`
- `success_criteria` (object):
  - `min_puzzle_accuracy`: Minimum accuracy needed (0-1)
  - `min_modules_completed`: Modules that must be completed
  - `metric_improvement`: Target improvement percentage (0-1)
- `is_active` (bool): Available for new prescriptions

**Indexes:**
- `plan_id` (unique)
- `difficulty`
- `cognitive_gap`
- Rating range (`[target_rating_min, target_rating_max]`)
- `is_active`

---

### 2. user_coaching_prescriptions

**Purpose:** Individual coaching prescriptions assigned to each user, tracking progress and status.

**Relationship:** One prescription per user + plan combination

**Key Fields:**
- `prescription_id` (string, unique): UUID
- `user_id` (string): Reference to `users.user_id`
- `plan_id` (string): Reference to `training_plans.plan_id`
- `status` (enum): `pending` | `active` | `paused` | `completed` | `abandoned`
  - `pending`: Prescribed but not yet started
  - `active`: Currently in progress
  - `paused`: Temporarily paused
  - `completed`: Finished successfully
  - `abandoned`: User stopped
- `issue_detected` (string): The cognitive gap this prescription addresses
- `reasoning` (string): Why this plan was recommended
- `baseline_metric` (float): Starting measurement (e.g., 0.45 accuracy)
- `current_metric` (float): Most recent measurement
- `improvement_pct` (float): Percentage improvement (0-100)
- `started_at` (datetime | null): When prescription became active
- `completed_at` (datetime | null): When marked complete
- `expected_completion_date` (datetime): Projected end based on plan duration
- `priority_order` (int): 1=highest, ascending for lower priority
- `modules_completed` (array): Completed module IDs
- `current_module` (string | null): Currently active module ID
- `puzzles_completed` (int): Total puzzles solved
- `puzzle_accuracy` (float): Accuracy rate across all puzzles (0-1)
- `notes` (string): Coaching feedback
- `created_at` (datetime): When prescription was issued
- `updated_at` (datetime): Last update

**Indexes:**
- `prescription_id` (unique)
- `user_id`
- `plan_id`
- `(user_id, status)` - Fast lookup of user's active prescriptions
- `(user_id, created_at)` - Chronological ordering
- `(status, priority_order)` - Priority-based filtering
- `issue_detected` - Gap-based queries
- `expected_completion_date` - Deadline-aware sorting

**Example Query Patterns:**
```javascript
// Get user's active prescriptions
db.user_coaching_prescriptions.find({
  user_id: "user_123",
  status: { $in: ["pending", "active"] }
}).sort({ priority_order: 1 })

// Check prescription progress
db.user_coaching_prescriptions.findOne({ prescription_id: "rx_456" })
// Returns: baseline_metric=0.45, current_metric=0.65, improvement_pct=44.4
```

---

### 3. coaching_prescription_history

**Purpose:** Complete audit trail of all prescription changes and events.

**Relationship:** Many-to-one with `user_coaching_prescriptions`

**Key Fields:**
- `history_id` (string, unique): UUID
- `prescription_id` (string): Reference to prescription
- `user_id` (string): Reference to user
- `action` (enum): `prescribed` | `activated` | `paused` | `resumed` | `completed` | `abandoned` | `metric_updated`
- `previous_status` (string): Status before action
- `new_status` (string): Status after action
- `metric_before` (float | null): Metric value before update
- `metric_after` (float | null): Metric value after update
- `reason` (string | null): Why change was made
- `triggered_by` (enum): `user` | `system` | `coach`
- `coach_id` (string | null): ID of coach who triggered change
- `timestamp` (datetime): ISO format

**Indexes:**
- `history_id` (unique)
- `prescription_id`
- `user_id`
- `(prescription_id, timestamp)` - Reverse-chronological audit trail
- `(user_id, timestamp)` - User's complete coaching history
- `action` - Query by action type
- `timestamp` - Time-based filtering

**Example:**
```javascript
// View prescription's complete history
db.coaching_prescription_history.find({
  prescription_id: "rx_456"
}).sort({ timestamp: -1 })
// Shows: prescribed → activated → metric_updated → paused → resumed

// Understand why a prescription was completed
db.coaching_prescription_history.findOne({
  prescription_id: "rx_456",
  action: "completed"
})
// Returns: reason, triggered_by, timestamp
```

---

### 4. issue_to_plan_mapping

**Purpose:** Many-to-many relationship between cognitive gaps and training plans, with prerequisites and trigger criteria.

**Sample Documents:** 5 (one per cognitive gap)

**Key Fields:**
- `mapping_id` (string, unique): UUID
- `cognitive_gap` (string, unique): The issue type (piece_safety, calculation_depth, king_safety, opening_knowledge, endgame_technique)
- `severity_threshold` (enum): `low` | `medium` | `high` | `critical`
- `plan_ids` (array): Plans addressing this gap
- `recommended_order` (array): Suggested completion order
- `prerequisite_mappings` (array): Prerequisites
  - `{ plan_id: "X", requires_plan_id: "Y" }`
  - Meaning: User must complete plan Y before starting plan X
- `trigger_criteria` (object):
  - `metric_threshold`: Minimum accuracy to trigger auto-prescription
  - `consecutive_games`: How many games showing the issue
  - `minimum_severity`: Lowest severity to trigger
- `notes` (string): Guidance
- `created_at` (datetime)
- `updated_at` (datetime)

**Indexes:**
- `mapping_id` (unique)
- `cognitive_gap` (unique)
- `plan_ids` - Query plans by gap
- `severity_threshold`

**Example:**
```javascript
// Find all plans for a cognitive gap
db.issue_to_plan_mapping.findOne({
  cognitive_gap: "piece_safety"
})
// Returns: plan_ids: ["plan_piece_safety_001"]

// Auto-prescription logic uses trigger_criteria:
// IF accuracy < 0.50 AND consecutive_games >= 3 AND severity >= "high"
// THEN recommend_plan("plan_piece_safety_001")
```

---

### 5. users (coaching_profile field)

**Purpose:** Extended user profile with coaching metadata (embedded field).

**Embedded Field:** `coaching_profile` (object)

**Fields:**
- `current_prescriptions` (array): Active prescription IDs
- `completed_prescriptions` (array): Completed prescription IDs
- `total_training_hours` (int): Cumulative hours in coaching plans
- `preferred_learning_style` (string): `visual` | `practice` | `explanation`
- `engagement_score` (float): 0-100, higher = more engaged
- `last_prescription_date` (datetime | null)
- `coaching_level` (string): `beginner` | `intermediate` | `advanced`
- `coaching_notes` (string): Personalized coaching summary

**Example Document:**
```javascript
{
  user_id: "user_123",
  email: "player@example.com",
  // ... other user fields ...
  coaching_profile: {
    current_prescriptions: ["rx_001", "rx_002"],
    completed_prescriptions: ["rx_999"],
    total_training_hours: 24,
    preferred_learning_style: "practice",
    engagement_score: 78,
    last_prescription_date: "2026-07-10T14:30:00Z",
    coaching_level: "intermediate",
    coaching_notes: "Strong piece safety, needs opening theory"
  }
}
```

---

## Predefined Training Plans

All 5 plans are seeded at initialization.

### Plan 1: Piece Safety Fundamentals
- **ID:** `plan_piece_safety_001`
- **Difficulty:** Beginner (600-1000 rating)
- **Duration:** 4 weeks, 3 hours/week
- **Gap:** `piece_safety`
- **Modules:** 3 (Piece Counting, Hanging Recognition, Position Review)
- **Puzzles:** 30 total
- **Success:** 80% accuracy, all 3 modules, 25% improvement

### Plan 2: Tactical Calculation Trainer
- **ID:** `plan_calculation_001`
- **Difficulty:** Intermediate (1000-1400 rating)
- **Duration:** 6 weeks, 4 hours/week
- **Gap:** `calculation_depth`
- **Modules:** 4 (Forcing Moves, Three-Move Tactics, Deep Calculation, Game Analysis)
- **Puzzles:** 70 total
- **Success:** 75% accuracy, all 4 modules, 30% improvement

### Plan 3: King Safety & Defense
- **ID:** `plan_king_safety_001`
- **Difficulty:** Intermediate (1200-1600 rating)
- **Duration:** 5 weeks, 3 hours/week
- **Gap:** `king_safety`
- **Modules:** 3 (King Vulnerability, Defensive Patterns, King Attack Combinations)
- **Puzzles:** 52 total
- **Success:** 78% accuracy, all 3 modules, 25% improvement

### Plan 4: Opening Principles Mastery
- **ID:** `plan_opening_principles_001`
- **Difficulty:** Beginner (700-1100 rating)
- **Duration:** 3 weeks, 2 hours/week
- **Gap:** `opening_knowledge`
- **Modules:** 3 (Core Principles, Mistake Patterns, Your Opening Errors)
- **Puzzles:** 23 total
- **Success:** 82% accuracy, all 3 modules, 20% improvement

### Plan 5: Endgame Technique Essentials
- **ID:** `plan_endgame_technique_001`
- **Difficulty:** Advanced (1400-1900 rating)
- **Duration:** 7 weeks, 5 hours/week
- **Gap:** `endgame_technique`
- **Modules:** 4 (Pawn Endgames, Rook Endgames, Queen Endgames, Game Analysis)
- **Puzzles:** 75 total
- **Success:** 80% accuracy, all 4 modules, 35% improvement

---

## Initialization

### Database Setup

The coaching system is initialized via `services/coaching_model.py`:

```python
from services.coaching_model import initialize_coaching_system

# Call once per fresh database setup
await initialize_coaching_system(db)
```

This function:
1. Creates 4 coaching collections
2. Creates all indexes
3. Seeds 5 predefined training plans
4. Creates sample issue-to-plan mappings
5. Adds `coaching_profile` to all users

### Index Strategy

**Write Optimization:**
- Single-field indexes on frequent queries: `user_id`, `prescription_id`, `plan_id`
- Compound indexes for common filters: `(user_id, status)`, `(user_id, created_at)`

**Read Optimization:**
- Indexes on audit trail: `(prescription_id, timestamp)`
- Priority-based sorting: `(status, priority_order)`

**Total Indexes:** 26 across 4 collections

---

## Workflow Examples

### Prescribing a Plan

```python
from services.coaching_model import PrescriptionStatus
from datetime import datetime, timedelta, timezone

# 1. Detect issue (elsewhere in codebase)
issue = "piece_safety"  # from game analysis

# 2. Look up mapping
mapping = await db.issue_to_plan_mapping.find_one({
    "cognitive_gap": issue,
    "severity_threshold": {"$lte": "high"}
})
plan_id = mapping["plan_ids"][0]

# 3. Create prescription
prescription = {
    "prescription_id": str(uuid.uuid4()),
    "user_id": "user_123",
    "plan_id": plan_id,
    "status": PrescriptionStatus.PENDING.value,
    "issue_detected": issue,
    "reasoning": "3 consecutive games with undefended pieces",
    "baseline_metric": 0.45,  # Current accuracy
    "current_metric": 0.45,
    "improvement_pct": 0.0,
    "started_at": None,
    "completed_at": None,
    "expected_completion_date": datetime.now(timezone.utc) + timedelta(weeks=4),
    "priority_order": 1,
    "modules_completed": [],
    "current_module": None,
    "puzzles_completed": 0,
    "puzzle_accuracy": 0.0,
    "notes": "Recommended: start with module_ps_001",
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc),
}

result = await db.user_coaching_prescriptions.insert_one(prescription)

# 4. Update user's coaching profile
await db.users.update_one(
    {"user_id": "user_123"},
    {
        "$push": {"coaching_profile.current_prescriptions": result.inserted_id},
        "$set": {"coaching_profile.last_prescription_date": datetime.now(timezone.utc)}
    }
)

# 5. Log to history
history = {
    "history_id": str(uuid.uuid4()),
    "prescription_id": result.inserted_id,
    "user_id": "user_123",
    "action": "prescribed",
    "previous_status": None,
    "new_status": PrescriptionStatus.PENDING.value,
    "reason": "Auto-detected piece_safety weakness",
    "triggered_by": "system",
    "timestamp": datetime.now(timezone.utc),
}
await db.coaching_prescription_history.insert_one(history)
```

### Updating Progress

```python
# 1. User completes a module
await db.user_coaching_prescriptions.update_one(
    {"prescription_id": "rx_456"},
    {
        "$push": {"modules_completed": "mod_ps_001"},
        "$set": {"current_module": "mod_ps_002"}
    }
)

# 2. User completes puzzles, update accuracy
await db.user_coaching_prescriptions.update_one(
    {"prescription_id": "rx_456"},
    {
        "$inc": {"puzzles_completed": 10},
        "$set": {"puzzle_accuracy": 0.85}
    }
)

# 3. System measures improvement
new_metric = 0.65  # accuracy improved from 0.45 to 0.65
improvement = (new_metric - 0.45) / 0.45 * 100  # 44.4%

await db.user_coaching_prescriptions.update_one(
    {"prescription_id": "rx_456"},
    {
        "$set": {
            "current_metric": new_metric,
            "improvement_pct": improvement,
            "updated_at": datetime.now(timezone.utc)
        }
    }
)

# 4. Log to history
history = {
    "history_id": str(uuid.uuid4()),
    "prescription_id": "rx_456",
    "user_id": "user_123",
    "action": "metric_updated",
    "previous_status": "active",
    "new_status": "active",
    "metric_before": 0.45,
    "metric_after": 0.65,
    "reason": "Module 1 completed, puzzles solved",
    "triggered_by": "system",
    "timestamp": datetime.now(timezone.utc),
}
await db.coaching_prescription_history.insert_one(history)
```

### Completing a Plan

```python
# 1. Check success criteria
prescription = await db.user_coaching_prescriptions.find_one({"prescription_id": "rx_456"})
plan = await db.training_plans.find_one({"plan_id": prescription["plan_id"]})

success = (
    prescription["puzzle_accuracy"] >= plan["success_criteria"]["min_puzzle_accuracy"] and
    len(prescription["modules_completed"]) >= plan["success_criteria"]["min_modules_completed"] and
    prescription["improvement_pct"] >= plan["success_criteria"]["metric_improvement"] * 100
)

# 2. Mark as completed
if success:
    await db.user_coaching_prescriptions.update_one(
        {"prescription_id": "rx_456"},
        {
            "$set": {
                "status": PrescriptionStatus.COMPLETED.value,
                "completed_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    # 3. Update user profile
    await db.users.update_one(
        {"user_id": "user_123"},
        {
            "$pull": {"coaching_profile.current_prescriptions": "rx_456"},
            "$push": {"coaching_profile.completed_prescriptions": "rx_456"},
            "$inc": {
                "coaching_profile.total_training_hours": plan["duration_weeks"] * plan["weekly_commitment_hours"]
            }
        }
    )

    # 4. Log to history
    history = {
        "history_id": str(uuid.uuid4()),
        "prescription_id": "rx_456",
        "user_id": "user_123",
        "action": "completed",
        "previous_status": "active",
        "new_status": "completed",
        "reason": "All success criteria met",
        "triggered_by": "system",
        "timestamp": datetime.now(timezone.utc),
    }
    await db.coaching_prescription_history.insert_one(history)
```

---

## Testing

Run the comprehensive test suite:

```bash
cd backend
python3 -m pytest tests/test_coaching_model.py -v
```

**Test Coverage (24 tests):**
- ✓ 10 tests on predefined plans (uniqueness, structure, validity)
- ✓ 5 tests on schema completeness
- ✓ 3 tests on enum definitions
- ✓ 2 tests on plan targeting
- ✓ 3 tests on database readiness
- ✓ 1 integration test

**Result:** All 24 tests passing ✅

---

## Key Decisions

### Why Embedded coaching_profile vs. Separate Collection?
- **Embedded:** Users frequently check their own coaching status
- **Efficient:** Single query reads user + all coaching metadata
- **Consistent:** Atomic updates with user profile
- **Trade-off:** Slightly larger user documents, but query patterns justify it

### Why Separate History Collection?
- **Audit trail:** Never delete or modify prescription records
- **Accountability:** Track who triggered changes and why
- **Analysis:** Understand coaching effectiveness over time
- **Compliance:** Immutable record for user-facing transparency

### Why Issue-to-Plan Mapping?
- **Flexibility:** Add new plans without touching detection code
- **Prerequisites:** Enforce learning order (e.g., Calculation before Advanced Tactics)
- **Trigger Criteria:** Automatic prescription based on data, not hardcoded rules
- **Maintenance:** Single source of truth for gap → plan relationship

### Rating-Aware Plan Targeting
- **5 plans × 4 difficulties = good coverage**
- **No hard cutoffs:** Target ranges overlap slightly to allow progression
- **Coach override:** System recommends, but coach can override based on student style

---

## Future Enhancements

- [ ] Add mastery gates: Require > 90% accuracy to unlock advanced modules
- [ ] Adaptive difficulty: Adjust puzzle complexity based on performance
- [ ] Peer learning: Share solutions between users on same plan
- [ ] Leaderboards: Weekly/monthly coaching plan completion rankings
- [ ] Mobile API: Push notifications for prescription reminders
- [ ] Spaced repetition: Auto-schedule puzzle reviews based on retention curves

---

## Integration Checklist

- [x] Schema designed and documented
- [x] 5 predefined plans created with full structure
- [x] 4 collections with proper indexes
- [x] Initialization function implemented
- [x] 24 comprehensive tests passing
- [ ] Integration into routes/coach.py
- [ ] Auto-prescription logic in game analysis pipeline
- [ ] Frontend prescription rendering
- [ ] User tests on mobile/web

---

**Last updated:** July 10, 2026  
**Status:** Ready for integration testing
