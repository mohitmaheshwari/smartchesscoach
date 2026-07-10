# Coaching System - MongoDB Reference Guide

Quick reference for common MongoDB operations on the coaching system collections.

---

## Collection Overview

```
training_plans (5 documents)
├─ Predefined coaching programs
├─ Seed with initialize_coaching_system()
└─ Never modify; use is_active flag to retire

user_coaching_prescriptions (N documents)
├─ One per user + plan assignment
├─ Tracks progress, status, metrics
└─ Central operational collection

coaching_prescription_history (M documents)
├─ Immutable audit trail
├─ Never delete; append only
└─ M > N (multiple history entries per prescription)

issue_to_plan_mapping (5 documents)
├─ Many-to-many with prerequisites
├─ Trigger criteria for auto-prescription
└─ Static reference data

users
├─ Embedded coaching_profile
├─ Links to prescriptions, hours, engagement
└─ Updated with prescription changes
```

---

## Common Queries

### Training Plans

**List all active plans:**
```javascript
db.training_plans.find({ is_active: true })
```

**Get plan by ID:**
```javascript
db.training_plans.findOne({ plan_id: "plan_piece_safety_001" })
```

**Find plans for rating range:**
```javascript
db.training_plans.find({
  target_rating_min: { $lte: 1200 },
  target_rating_max: { $gte: 1200 }
})
```

**Find plans by difficulty:**
```javascript
db.training_plans.find({ difficulty: "beginner" })
```

**Find plans by cognitive gap:**
```javascript
db.training_plans.find({ cognitive_gap: "piece_safety" })
```

---

### User Coaching Prescriptions

**Get user's active prescriptions:**
```javascript
db.user_coaching_prescriptions.find({
  user_id: "user_123",
  status: { $in: ["pending", "active"] }
}).sort({ priority_order: 1 })
```

**Get single prescription:**
```javascript
db.user_coaching_prescriptions.findOne({ prescription_id: "rx_456" })
```

**Get prescription details with progress:**
```javascript
db.user_coaching_prescriptions.findOne(
  { prescription_id: "rx_456" },
  {
    status: 1,
    baseline_metric: 1,
    current_metric: 1,
    improvement_pct: 1,
    puzzles_completed: 1,
    puzzle_accuracy: 1,
    modules_completed: 1
  }
)
```

**Get all prescriptions for a user:**
```javascript
db.user_coaching_prescriptions.find({ user_id: "user_123" })
```

**Get completed prescriptions for a user:**
```javascript
db.user_coaching_prescriptions.find({
  user_id: "user_123",
  status: "completed"
})
```

**Find prescriptions by priority (high → low):**
```javascript
db.user_coaching_prescriptions.find({
  status: "active"
}).sort({ priority_order: 1 }).limit(5)
```

**Find prescriptions expiring soon:**
```javascript
db.user_coaching_prescriptions.find({
  status: "active",
  expected_completion_date: {
    $lt: new Date("2026-07-17"),
    $gte: new Date("2026-07-10")
  }
})
```

**Get prescriptions by issue detected:**
```javascript
db.user_coaching_prescriptions.find({
  user_id: "user_123",
  issue_detected: "piece_safety"
})
```

**Update prescription status:**
```javascript
db.user_coaching_prescriptions.updateOne(
  { prescription_id: "rx_456" },
  {
    $set: {
      status: "active",
      started_at: new Date("2026-07-10T14:30:00Z"),
      updated_at: new Date()
    }
  }
)
```

**Update prescription metrics:**
```javascript
db.user_coaching_prescriptions.updateOne(
  { prescription_id: "rx_456" },
  {
    $set: {
      current_metric: 0.65,
      improvement_pct: 44.4,
      updated_at: new Date()
    }
  }
)
```

**Add completed module:**
```javascript
db.user_coaching_prescriptions.updateOne(
  { prescription_id: "rx_456" },
  {
    $push: { modules_completed: "mod_ps_001" },
    $set: { current_module: "mod_ps_002" }
  }
)
```

**Mark prescription complete:**
```javascript
db.user_coaching_prescriptions.updateOne(
  { prescription_id: "rx_456" },
  {
    $set: {
      status: "completed",
      completed_at: new Date(),
      updated_at: new Date()
    }
  }
)
```

**Pause prescription:**
```javascript
db.user_coaching_prescriptions.updateOne(
  { prescription_id: "rx_456" },
  {
    $set: {
      status: "paused",
      updated_at: new Date()
    }
  }
)
```

---

### Coaching Prescription History

**Get audit trail for a prescription:**
```javascript
db.coaching_prescription_history.find({
  prescription_id: "rx_456"
}).sort({ timestamp: -1 })
```

**Get user's complete coaching history:**
```javascript
db.coaching_prescription_history.find({
  user_id: "user_123"
}).sort({ timestamp: -1 })
```

**Find prescriptions that were completed:**
```javascript
db.coaching_prescription_history.find({
  action: "completed"
})
```

**Find metric updates for a prescription:**
```javascript
db.coaching_prescription_history.find({
  prescription_id: "rx_456",
  action: "metric_updated"
}).sort({ timestamp: -1 })
```

**Get history entries by action type:**
```javascript
db.coaching_prescription_history.find({
  action: "activated"
})
```

**Get history entries triggered by system:**
```javascript
db.coaching_prescription_history.find({
  triggered_by: "system"
})
```

**Timeline of prescription lifecycle:**
```javascript
db.coaching_prescription_history.find({
  prescription_id: "rx_456",
  action: { $in: ["prescribed", "activated", "completed"] }
}).sort({ timestamp: 1 })
```

**Find unusual activity (coach-triggered changes):**
```javascript
db.coaching_prescription_history.find({
  triggered_by: "coach"
}).sort({ timestamp: -1 }).limit(10)
```

**Add history entry:**
```javascript
db.coaching_prescription_history.insertOne({
  history_id: "hist_789",
  prescription_id: "rx_456",
  user_id: "user_123",
  action: "metric_updated",
  previous_status: "active",
  new_status: "active",
  metric_before: 0.45,
  metric_after: 0.65,
  reason: "Module 1 completed, 25 puzzles solved",
  triggered_by: "system",
  timestamp: new Date()
})
```

---

### Issue to Plan Mapping

**Get mapping for a cognitive gap:**
```javascript
db.issue_to_plan_mapping.findOne({
  cognitive_gap: "piece_safety"
})
```

**Get all mappings:**
```javascript
db.issue_to_plan_mapping.find({})
```

**Find plans addressing a gap:**
```javascript
const mapping = db.issue_to_plan_mapping.findOne({
  cognitive_gap: "piece_safety"
})
// mapping.plan_ids = ["plan_piece_safety_001"]
```

**Get trigger criteria for a gap:**
```javascript
const mapping = db.issue_to_plan_mapping.findOne({
  cognitive_gap: "piece_safety"
})
// mapping.trigger_criteria = { metric_threshold: 0.5, consecutive_games: 3, minimum_severity: "high" }
```

**Find gaps by severity:**
```javascript
db.issue_to_plan_mapping.find({
  severity_threshold: { $gte: "high" }
})
```

**Check prerequisites:**
```javascript
const mapping = db.issue_to_plan_mapping.findOne({
  cognitive_gap: "calculation_depth"
})
// mapping.prerequisite_mappings = [{ plan_id: "plan_tactical_advanced", requires_plan_id: "plan_calculation_001" }]
```

---

### Users (Coaching Profile)

**Get user's coaching profile:**
```javascript
db.users.findOne(
  { user_id: "user_123" },
  { coaching_profile: 1 }
)
```

**Get user's current prescriptions:**
```javascript
const user = db.users.findOne(
  { user_id: "user_123" },
  { "coaching_profile.current_prescriptions": 1 }
)
// user.coaching_profile.current_prescriptions = ["rx_001", "rx_002"]
```

**Get user's total training hours:**
```javascript
const user = db.users.findOne(
  { user_id: "user_123" },
  { "coaching_profile.total_training_hours": 1 }
)
// user.coaching_profile.total_training_hours = 24
```

**Update coaching profile:**
```javascript
db.users.updateOne(
  { user_id: "user_123" },
  {
    $set: {
      "coaching_profile.engagement_score": 85,
      "coaching_profile.coaching_level": "intermediate"
    }
  }
)
```

**Add prescription to user's current list:**
```javascript
db.users.updateOne(
  { user_id: "user_123" },
  {
    $push: { "coaching_profile.current_prescriptions": "rx_456" },
    $set: {
      "coaching_profile.last_prescription_date": new Date()
    }
  }
)
```

**Move prescription from current to completed:**
```javascript
db.users.updateOne(
  { user_id: "user_123" },
  {
    $pull: { "coaching_profile.current_prescriptions": "rx_456" },
    $push: { "coaching_profile.completed_prescriptions": "rx_456" },
    $inc: { "coaching_profile.total_training_hours": 12 }
  }
)
```

**Initialize coaching profile for new user:**
```javascript
db.users.updateOne(
  { user_id: "user_new" },
  {
    $set: {
      "coaching_profile": {
        current_prescriptions: [],
        completed_prescriptions: [],
        total_training_hours: 0,
        preferred_learning_style: "practice",
        engagement_score: 50,
        last_prescription_date: null,
        coaching_level: "beginner",
        coaching_notes: "Profile initialized"
      }
    }
  }
)
```

---

## Indexes

### Create Missing Indexes

```javascript
// training_plans
db.training_plans.createIndex({ plan_id: 1 }, { unique: true })
db.training_plans.createIndex({ difficulty: 1 })
db.training_plans.createIndex({ cognitive_gap: 1 })
db.training_plans.createIndex([("target_rating_min", 1), ("target_rating_max", 1)])
db.training_plans.createIndex({ is_active: 1 })

// user_coaching_prescriptions
db.user_coaching_prescriptions.createIndex({ prescription_id: 1 }, { unique: true })
db.user_coaching_prescriptions.createIndex({ user_id: 1 })
db.user_coaching_prescriptions.createIndex({ plan_id: 1 })
db.user_coaching_prescriptions.createIndex([("user_id", 1), ("status", 1)])
db.user_coaching_prescriptions.createIndex([("user_id", 1), ("created_at", -1)])
db.user_coaching_prescriptions.createIndex([("status", 1), ("priority_order", 1)])
db.user_coaching_prescriptions.createIndex({ issue_detected: 1 })
db.user_coaching_prescriptions.createIndex({ expected_completion_date: 1 })

// coaching_prescription_history
db.coaching_prescription_history.createIndex({ history_id: 1 }, { unique: true })
db.coaching_prescription_history.createIndex({ prescription_id: 1 })
db.coaching_prescription_history.createIndex({ user_id: 1 })
db.coaching_prescription_history.createIndex([("prescription_id", 1), ("timestamp", -1)])
db.coaching_prescription_history.createIndex([("user_id", 1), ("timestamp", -1)])
db.coaching_prescription_history.createIndex({ action: 1 })
db.coaching_prescription_history.createIndex({ timestamp: 1 })

// issue_to_plan_mapping
db.issue_to_plan_mapping.createIndex({ mapping_id: 1 }, { unique: true })
db.issue_to_plan_mapping.createIndex({ cognitive_gap: 1 }, { unique: true })
db.issue_to_plan_mapping.createIndex({ plan_ids: 1 })
db.issue_to_plan_mapping.createIndex({ severity_threshold: 1 })
```

### List All Indexes

```javascript
db.training_plans.getIndexes()
db.user_coaching_prescriptions.getIndexes()
db.coaching_prescription_history.getIndexes()
db.issue_to_plan_mapping.getIndexes()
```

---

## Aggregations

### Get user coaching statistics

```javascript
db.user_coaching_prescriptions.aggregate([
  { $match: { user_id: "user_123" } },
  { $group: {
      _id: "$user_id",
      total_prescriptions: { $sum: 1 },
      completed: { $sum: { $cond: [{ $eq: ["$status", "completed"] }, 1, 0] } },
      active: { $sum: { $cond: [{ $eq: ["$status", "active"] }, 1, 0] } },
      avg_improvement: { $avg: "$improvement_pct" },
      avg_puzzle_accuracy: { $avg: "$puzzle_accuracy" }
  } }
])
```

### Get completion rate by plan

```javascript
db.user_coaching_prescriptions.aggregate([
  { $group: {
      _id: "$plan_id",
      total: { $sum: 1 },
      completed: { $sum: { $cond: [{ $eq: ["$status", "completed"] }, 1, 0] } }
  } },
  { $project: {
      plan_id: "$_id",
      total: 1,
      completed: 1,
      completion_rate: { $divide: ["$completed", "$total"] }
  } }
])
```

### Get most prescribed issues

```javascript
db.user_coaching_prescriptions.aggregate([
  { $group: {
      _id: "$issue_detected",
      count: { $sum: 1 }
  } },
  { $sort: { count: -1 } },
  { $limit: 10 }
])
```

### Get average improvement by cognitive gap

```javascript
db.user_coaching_prescriptions.aggregate([
  { $match: { status: "completed" } },
  { $group: {
      _id: "$issue_detected",
      avg_improvement: { $avg: "$improvement_pct" },
      count: { $sum: 1 }
  } },
  { $sort: { avg_improvement: -1 } }
])
```

---

## Data Cleanup / Admin

### Pause all active prescriptions for a user

```javascript
db.user_coaching_prescriptions.updateMany(
  { user_id: "user_123", status: "active" },
  {
    $set: {
      status: "paused",
      updated_at: new Date()
    }
  }
)
```

### Delete prescriptions (careful!)

```javascript
// Only delete if necessary; history will remain
db.user_coaching_prescriptions.deleteMany({
  user_id: "user_123",
  status: "abandoned"
})
```

### Archive old history entries

```javascript
// Move entries older than 1 year to archive
const cutoff = new Date()
cutoff.setFullYear(cutoff.getFullYear() - 1)

db.coaching_prescription_history.deleteMany({
  timestamp: { $lt: cutoff }
})
// Note: Consider adding an archive collection first
```

### Reset user coaching profile

```javascript
db.users.updateOne(
  { user_id: "user_123" },
  {
    $set: {
      "coaching_profile": {
        current_prescriptions: [],
        completed_prescriptions: [],
        total_training_hours: 0,
        preferred_learning_style: "practice",
        engagement_score: 50,
        last_prescription_date: null,
        coaching_level: "beginner",
        coaching_notes: "Profile reset"
      }
    }
  }
)
```

---

## Debugging

### Check for orphaned prescriptions

```javascript
// Prescriptions with non-existent plan IDs
const invalid_plans = db.user_coaching_prescriptions.aggregate([
  { $lookup: {
      from: "training_plans",
      localField: "plan_id",
      foreignField: "plan_id",
      as: "plan"
  } },
  { $match: { plan: { $size: 0 } } }
])
```

### Find prescriptions missing from user profile

```javascript
// User has prescription but it's not in coaching_profile.current_prescriptions
db.user_coaching_prescriptions.aggregate([
  { $match: { status: "active" } },
  { $lookup: {
      from: "users",
      localField: "user_id",
      foreignField: "user_id",
      as: "user"
  } },
  { $match: {
      "user.coaching_profile.current_prescriptions": { $ne: "$prescription_id" }
  } }
])
```

### Validate data consistency

```javascript
// Check for prescriptions without history entries
const orphaned = db.user_coaching_prescriptions.aggregate([
  { $lookup: {
      from: "coaching_prescription_history",
      localField: "prescription_id",
      foreignField: "prescription_id",
      as: "history"
  } },
  { $match: { history: { $size: 0 } } }
])
```

---

## Performance Tips

1. **Use indexes in queries:** Always filter by indexed fields first
2. **Limit results:** Use `.limit()` for large result sets
3. **Project fields:** Only retrieve needed fields with `findOne({...}, {field: 1})`
4. **Batch updates:** Use `updateMany()` instead of loops
5. **TTL indexes:** Consider adding for history if retention policy is < lifetime

---

**Last updated:** July 10, 2026
