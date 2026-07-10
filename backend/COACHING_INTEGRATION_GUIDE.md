# Coaching System Integration Guide

How to integrate the coaching system into ChessGuru's backend.

---

## Quick Start

### 1. Initialize the Database (One-Time Setup)

Update `backend/init_db.py`:

```python
# Near the top with other imports
from services.coaching_model import initialize_coaching_system

# In the init_database() function, add:
async def init_database():
    # ... existing collections and indexes ...
    
    # NEW: Initialize coaching system
    await initialize_coaching_system(db)
    
    print("\n✅ Database initialization complete!")
```

Then run:
```bash
python backend/init_db.py
```

This will:
- Create 4 coaching collections
- Create 26 indexes
- Seed 5 predefined training plans
- Create issue-to-plan mappings
- Add `coaching_profile` to all users

### 2. Create Coaching Routes

Create `backend/routes/coaching.py`:

```python
from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from services.coaching_model import (
    PrescriptionStatus,
    PlanDifficulty,
)
from datetime import datetime, timezone, timedelta
import uuid

router = APIRouter(prefix="/api/coaching", tags=["coaching"])

@router.get("/plans")
async def get_plans(db: AsyncIOMotorDatabase, difficulty: str = None):
    """List available training plans."""
    query = {"is_active": True}
    if difficulty:
        query["difficulty"] = difficulty
    
    plans = await db.training_plans.find(query).to_list(None)
    return {"plans": plans}

@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, db: AsyncIOMotorDatabase):
    """Get details of a specific plan."""
    plan = await db.training_plans.find_one({"plan_id": plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan

@router.get("/prescriptions/{user_id}")
async def get_user_prescriptions(user_id: str, db: AsyncIOMotorDatabase):
    """Get all prescriptions for a user."""
    prescriptions = await db.user_coaching_prescriptions.find(
        {"user_id": user_id}
    ).to_list(None)
    return {"prescriptions": prescriptions}

@router.get("/prescriptions/{user_id}/active")
async def get_active_prescriptions(user_id: str, db: AsyncIOMotorDatabase):
    """Get active/pending prescriptions for a user."""
    prescriptions = await db.user_coaching_prescriptions.find({
        "user_id": user_id,
        "status": {"$in": ["active", "pending"]}
    }).sort([("priority_order", 1)]).to_list(None)
    return {"prescriptions": prescriptions}

@router.post("/prescribe")
async def prescribe_plan(
    user_id: str,
    plan_id: str,
    issue_detected: str,
    baseline_metric: float,
    db: AsyncIOMotorDatabase
):
    """Auto-prescribe a training plan to a user."""
    
    # Verify plan exists
    plan = await db.training_plans.find_one({"plan_id": plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Create prescription
    prescription = {
        "prescription_id": str(uuid.uuid4()),
        "user_id": user_id,
        "plan_id": plan_id,
        "status": PrescriptionStatus.PENDING.value,
        "issue_detected": issue_detected,
        "reasoning": f"Auto-prescribed for {issue_detected} weakness",
        "baseline_metric": baseline_metric,
        "current_metric": baseline_metric,
        "improvement_pct": 0.0,
        "started_at": None,
        "completed_at": None,
        "expected_completion_date": datetime.now(timezone.utc) + timedelta(weeks=plan["duration_weeks"]),
        "priority_order": 1,
        "modules_completed": [],
        "current_module": None,
        "puzzles_completed": 0,
        "puzzle_accuracy": 0.0,
        "notes": f"Starting {plan['name']}",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    result = await db.user_coaching_prescriptions.insert_one(prescription)
    
    # Update user profile
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$push": {"coaching_profile.current_prescriptions": result.inserted_id},
            "$set": {"coaching_profile.last_prescription_date": datetime.now(timezone.utc)}
        }
    )
    
    # Log to history
    history = {
        "history_id": str(uuid.uuid4()),
        "prescription_id": result.inserted_id,
        "user_id": user_id,
        "action": "prescribed",
        "previous_status": None,
        "new_status": PrescriptionStatus.PENDING.value,
        "reason": "Auto-prescribed",
        "triggered_by": "system",
        "timestamp": datetime.now(timezone.utc),
    }
    await db.coaching_prescription_history.insert_one(history)
    
    return {"prescription_id": result.inserted_id, **prescription}

@router.patch("/prescriptions/{prescription_id}")
async def update_prescription(
    prescription_id: str,
    status: str = None,
    current_metric: float = None,
    puzzles_completed: int = None,
    puzzle_accuracy: float = None,
    db: AsyncIOMotorDatabase = None
):
    """Update prescription progress."""
    
    # Get current prescription
    prescription = await db.user_coaching_prescriptions.find_one({
        "prescription_id": prescription_id
    })
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    
    update_dict = {"updated_at": datetime.now(timezone.utc)}
    
    if status:
        update_dict["status"] = status
    if current_metric is not None:
        update_dict["current_metric"] = current_metric
        # Calculate improvement
        baseline = prescription["baseline_metric"]
        if baseline > 0:
            improvement = (current_metric - baseline) / baseline * 100
            update_dict["improvement_pct"] = improvement
    if puzzles_completed is not None:
        update_dict["puzzles_completed"] = puzzles_completed
    if puzzle_accuracy is not None:
        update_dict["puzzle_accuracy"] = puzzle_accuracy
    
    result = await db.user_coaching_prescriptions.update_one(
        {"prescription_id": prescription_id},
        {"$set": update_dict}
    )
    
    # Log to history
    history = {
        "history_id": str(uuid.uuid4()),
        "prescription_id": prescription_id,
        "user_id": prescription["user_id"],
        "action": "metric_updated" if current_metric else "status_changed",
        "previous_status": prescription["status"],
        "new_status": status or prescription["status"],
        "metric_before": prescription.get("current_metric"),
        "metric_after": current_metric,
        "triggered_by": "system",
        "timestamp": datetime.now(timezone.utc),
    }
    await db.coaching_prescription_history.insert_one(history)
    
    return {"updated": result.modified_count > 0}

@router.get("/history/{prescription_id}")
async def get_prescription_history(prescription_id: str, db: AsyncIOMotorDatabase):
    """Get audit trail for a prescription."""
    history = await db.coaching_prescription_history.find({
        "prescription_id": prescription_id
    }).sort([("timestamp", -1)]).to_list(None)
    return {"history": history}

@router.get("/mappings")
async def get_issue_mappings(db: AsyncIOMotorDatabase):
    """Get all issue-to-plan mappings."""
    mappings = await db.issue_to_plan_mapping.find({}).to_list(None)
    return {"mappings": mappings}

@router.get("/mappings/{cognitive_gap}")
async def get_mapping(cognitive_gap: str, db: AsyncIOMotorDatabase):
    """Get mapping for a specific cognitive gap."""
    mapping = await db.issue_to_plan_mapping.find_one({
        "cognitive_gap": cognitive_gap
    })
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return mapping
```

### 3. Register Routes in server.py

```python
# In server.py, add to imports:
from routes.coaching import router as coaching_router

# In the app setup section:
api_router.include_router(coaching_router)
```

### 4. Call from Game Analysis

When game analysis detects cognitive gaps:

```python
# In services/game_analysis.py or similar

from services.coaching_model import PrescriptionStatus
from motor.motor_asyncio import AsyncIOMotorDatabase

async def prescribe_if_needed(
    db: AsyncIOMotorDatabase,
    user_id: str,
    cognitive_gaps: list,
    gap_metrics: dict  # {gap: accuracy_metric}
):
    """Auto-prescribe plans based on detected gaps."""
    
    for gap in cognitive_gaps:
        # Look up mapping for this gap
        mapping = await db.issue_to_plan_mapping.find_one({
            "cognitive_gap": gap
        })
        if not mapping:
            continue
        
        # Check if prescription already exists
        existing = await db.user_coaching_prescriptions.find_one({
            "user_id": user_id,
            "issue_detected": gap,
            "status": {"$in": ["pending", "active"]}
        })
        if existing:
            continue  # Already prescribed
        
        # Check trigger criteria
        triggers = mapping.get("trigger_criteria", {})
        metric = gap_metrics.get(gap, 1.0)
        threshold = triggers.get("metric_threshold", 0.5)
        
        if metric < threshold:
            # Prescribe the plan
            plan_id = mapping["plan_ids"][0]
            
            prescription = {
                "prescription_id": str(uuid.uuid4()),
                "user_id": user_id,
                "plan_id": plan_id,
                "status": PrescriptionStatus.PENDING.value,
                "issue_detected": gap,
                "reasoning": f"Detected {gap} weakness in game analysis",
                "baseline_metric": metric,
                "current_metric": metric,
                "improvement_pct": 0.0,
                "started_at": None,
                "completed_at": None,
                "expected_completion_date": datetime.now(timezone.utc) + timedelta(weeks=4),
                "priority_order": 1,
                "modules_completed": [],
                "current_module": None,
                "puzzles_completed": 0,
                "puzzle_accuracy": 0.0,
                "notes": "Auto-prescribed from game analysis",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            
            result = await db.user_coaching_prescriptions.insert_one(prescription)
            
            # Update user profile
            await db.users.update_one(
                {"user_id": user_id},
                {
                    "$push": {"coaching_profile.current_prescriptions": result.inserted_id},
                    "$set": {"coaching_profile.last_prescription_date": datetime.now(timezone.utc)}
                }
            )
```

### 5. Frontend Integration (React)

Create `frontend/src/components/CoachingPanel.jsx`:

```javascript
import { useEffect, useState } from 'react';
import { usePlayerData } from '../hooks/usePlayerData';
import { API_URL } from '../config';

export function CoachingPanel() {
  const { user } = usePlayerData();
  const [prescriptions, setPrescriptions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.user_id) return;

    async function fetchPrescriptions() {
      try {
        const res = await fetch(
          `${API_URL}/api/coaching/prescriptions/${user.user_id}/active`,
          { credentials: 'include' }
        );
        const data = await res.json();
        setPrescriptions(data.prescriptions);
      } catch (err) {
        console.error('Failed to fetch prescriptions:', err);
      } finally {
        setLoading(false);
      }
    }

    fetchPrescriptions();
  }, [user?.user_id]);

  if (loading) return <div>Loading coaching plans...</div>;

  return (
    <div className="coaching-panel">
      <h2>Your Coaching Plans</h2>
      {prescriptions.length === 0 ? (
        <p>No active coaching plans. Great job!</p>
      ) : (
        <div className="prescription-list">
          {prescriptions.map((rx) => (
            <div key={rx.prescription_id} className="prescription-card">
              <h3>{rx.issue_detected}</h3>
              <p>Progress: {Math.round(rx.improvement_pct)}% improvement</p>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${rx.improvement_pct}%` }}
                />
              </div>
              <p>{rx.puzzles_completed} puzzles completed</p>
              <button onClick={() => startPlan(rx)}>
                {rx.status === 'pending' ? 'Start Plan' : 'Continue'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## File Structure

```
backend/
├── services/
│   └── coaching_model.py              ← Main service
├── routes/
│   └── coaching.py                    ← API routes (CREATE THIS)
├── tests/
│   └── test_coaching_model.py         ← Tests
├── init_db.py                         ← UPDATE THIS
├── server.py                          ← UPDATE THIS
├── COACHING_SYSTEM_VERIFICATION.md    ← Verification report
├── COACHING_MONGODB_REFERENCE.md      ← MongoDB reference
└── COACHING_INTEGRATION_GUIDE.md      ← THIS FILE

docs/
└── coaching_system_schema.md          ← Full documentation

frontend/
└── src/
    └── components/
        └── CoachingPanel.jsx          ← CREATE THIS
```

---

## Testing the Integration

### 1. Test Database Initialization

```bash
cd backend
python init_db.py
# Should print: ✅ Coaching system initialized successfully!
```

### 2. Run Test Suite

```bash
cd backend
python -m pytest tests/test_coaching_model.py -v
# Should show: 24 passed
```

### 3. Test API Endpoints

```bash
# Get available plans
curl -s http://localhost:8001/api/coaching/plans | python -m json.tool

# Get user's prescriptions
curl -s http://localhost:8001/api/coaching/prescriptions/user_123 | python -m json.tool

# Prescribe a plan
curl -s -X POST http://localhost:8001/api/coaching/prescribe \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "plan_id": "plan_piece_safety_001",
    "issue_detected": "piece_safety",
    "baseline_metric": 0.45
  }' | python -m json.tool
```

### 4. Verify MongoDB

```javascript
// In MongoDB shell
db.training_plans.count()  // Should be 5
db.issue_to_plan_mapping.count()  // Should be 5

// Check user's coaching profile
db.users.findOne({}, { "coaching_profile": 1 })
```

---

## Next Steps

1. **Create routes/coaching.py** with endpoints above
2. **Update init_db.py** to call `initialize_coaching_system(db)`
3. **Update server.py** to register coaching routes
4. **Integrate with game analysis** to call `prescribe_if_needed()`
5. **Create CoachingPanel.jsx** for frontend
6. **Test endpoints** with curl or Postman
7. **Add to HomePage** to show active prescriptions
8. **Monitor** coaching metrics and engagement

---

## Monitoring & Debugging

### Check Coaching System Health

```python
async def check_coaching_health(db):
    """Verify coaching system is properly set up."""
    
    # Check collections exist
    collections = await db.list_collection_names()
    assert "training_plans" in collections
    assert "user_coaching_prescriptions" in collections
    assert "coaching_prescription_history" in collections
    assert "issue_to_plan_mapping" in collections
    
    # Check plans seeded
    plans = await db.training_plans.count_documents({})
    assert plans == 5, f"Expected 5 plans, got {plans}"
    
    # Check mappings created
    mappings = await db.issue_to_plan_mapping.count_documents({})
    assert mappings >= 5, f"Expected ≥5 mappings, got {mappings}"
    
    # Check indexes exist
    training_indexes = await db.training_plans.index_information()
    assert len(training_indexes) >= 5, "Missing training_plans indexes"
    
    return {"status": "healthy", "plans": plans, "mappings": mappings}
```

### Monitor Prescription Activity

```javascript
// Get active prescriptions count
db.user_coaching_prescriptions.countDocuments({ status: "active" })

// Get completion rate
db.user_coaching_prescriptions.aggregate([
  { $group: {
      _id: null,
      total: { $sum: 1 },
      completed: { $sum: { $cond: [{ $eq: ["$status", "completed"] }, 1, 0] } },
      completion_rate: { $avg: { $cond: [{ $eq: ["$status", "completed"] }, 1, 0] } }
  } }
])

// Get average improvement by gap
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

## Troubleshooting

### Collections not created
- Check `initialize_coaching_system()` was called in `init_db.py`
- Run `python init_db.py` again

### Indexes missing
- Run `ensure_coaching_indexes(db)` or `python init_db.py`

### Plans not seeding
- Check `seed_training_plans()` completes without errors
- Verify database connection

### Prescriptions not appearing
- Check user_id matches between tables
- Verify `coaching_profile` exists on users

### Routes not working
- Verify `routes/coaching.py` is created
- Verify `server.py` includes `coaching_router`
- Check FastAPI logs for import errors

---

**Last updated:** July 10, 2026  
**Ready to integrate:** Yes ✅
