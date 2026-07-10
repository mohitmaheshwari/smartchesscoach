# Coaching Prescriptions Integration Tests

## Overview

Comprehensive integration test suite for the coaching prescription system (`test_coaching_integration.py`). Tests complete end-to-end workflows including game analysis, issue detection, prescription generation, acceptance, tracking, and completion.

## Test Coverage

### Test 1: Game -> Issues -> Prescription
**Scenario:** A game is analyzed, cognitive issues are detected, coach generates a prescription
**Validates:**
- Next prescription endpoint returns 200
- Response has recommended_plan
- Response has alternatives and reasoning
- Plan has valid structure

### Test 2: No Active Plans -> Next Prescription
**Scenario:** User has no active prescriptions; system recommends next focus
**Validates:**
- User starts with 0 active prescriptions
- Next prescription endpoint returns recommendation
- Recommendation includes urgency level
- Parallel plan capability flag is set

### Test 3: Accept Prescription -> Status Active
**Scenario:** User accepts a recommendation, prescription status changes to active
**Validates:**
- Choose alternative creates new prescription
- Accept prescription changes status to "active"
- Prescription appears in current-prescriptions list
- Status is correctly tracked

### Test 4: Play 10 Games -> Metrics Update -> Auto-Complete
**Scenario:** User plays games, metrics update automatically, plan auto-completes at 50% threshold
**Validates:**
- Prescription remains in current list while active
- Metrics can be updated (simulated)
- System tracks progress toward completion

### Test 5: Multiple Prescriptions Priority Order
**Scenario:** User has two prescriptions (primary + alternative/parallel)
**Validates:**
- Both prescriptions created via different flows
- Both appear in current-prescriptions list
- Priority orders are correctly assigned (1st < 2nd)
- Orders reflect acceptance sequence

### Test 6: Multiple Prescriptions Metrics Update
**Scenario:** Multiple active prescriptions tracked simultaneously
**Validates:**
- Both prescriptions retrieved in one call
- Metrics for each tracked independently
- Multiple plans don't interfere with each other

### Test 7: Focus Lock Migration to Prescription
**Scenario:** Legacy focus-lock system behavior replicated by prescriptions
**Validates:**
- Next prescription provides focused goal (replaces focus_lock)
- Prescription system has all required tracking fields
- Can activate focused plan via prescription

### Test 8: Competence - Complete 3 Plans in 7 Days -> Offers Parallel
**Scenario:** User completes plans rapidly, system offers parallel capability
**Validates:**
- Plans can be quickly completed
- Parallel plan can be added (always available with max limits)
- System enforces max_concurrent_plans limit

### Test 9: Prescription History Audit Trail
**Scenario:** All prescription changes are recorded for audit/analytics
**Validates:**
- History endpoint returns 200
- Status transitions are tracked (pending -> active -> paused -> completed)
- Each action is timestamped
- Reason for each change is recorded

### Test 10: Data Consistency Validation
**Scenario:** Verify data integrity across multiple operations
**Validates:**
- All active prescriptions have status="active"
- All prescriptions have created_at and updated_at timestamps
- Priority orders are sequential (no gaps)
- No data loss during concurrent updates

## Running the Tests

### Prerequisites

1. **Backend Server Running**
   ```bash
   # Start via supervisor
   sudo supervisorctl restart backend
   
   # OR start via Docker
   docker-compose up -d backend
   
   # OR start manually (in backend directory)
   cd backend
   python server.py
   ```

2. **MongoDB Available**
   - Backend .env must have valid MONGO_URL
   - Default: mongodb://localhost:27017
   - Database: test_database

3. **Environment Variables**
   ```bash
   # Backend/.env
   REACT_APP_BACKEND_URL=http://localhost:8001
   MONGO_URL=mongodb://localhost:27017
   DB_NAME=test_database
   DEV_MODE=true
   ```

### Running Tests

```bash
# Run all tests with Python
cd backend
python tests/test_coaching_integration.py

# Run with pytest
pytest tests/test_coaching_integration.py -v

# Run single test
pytest tests/test_coaching_integration.py::test_game_to_issues_to_prescription -v

# Run with output
python tests/test_coaching_integration.py 2>&1 | tee test_results.log
```

### Expected Output

```
======================================================================
COACHING PRESCRIPTIONS INTEGRATION TESTS
======================================================================

=== TEST 1: Game -> Issues -> Prescription ===
  [PASS] Next prescription endpoint returns 200
  [PASS] Response has recommended_plan
  [PASS] Response has alternatives
  [PASS] Response has reasoning
  [PASS] Recommended plan has plan_id

=== TEST 2: No Active Plans -> Next Prescription ===
  [PASS] Current prescriptions endpoint returns 200
  [PASS] User starts with no active plans
  [PASS] Next prescription returns recommendation when no active plans
  [PASS] Recommendation has urgency level
  [PASS] Can add parallel plan flag present

... (more tests)

======================================================================
TEST SUMMARY
======================================================================
[PASS] Passed: 45
[FAIL] Failed: 0
[STATS] Total:  45
[RATE] Pass Rate: 100.0%
```

## Test Data

### Sample Training Plans

Tests create 3 sample training plans:

1. **plan_piece_safety_1200**
   - Cognitive gap: piece_safety
   - Rating range: 600-1399
   - Duration: 4 weeks
   - Modules: Piece Basics, Tactical Patterns

2. **plan_tactics_1200**
   - Cognitive gap: missed_tactic
   - Rating range: 800-1599
   - Duration: 6 weeks
   - Modules: Fork Recognition

3. **plan_king_safety_1200**
   - Cognitive gap: king_safety
   - Rating range: 1000-1799
   - Duration: 5 weeks
   - Modules: King Vulnerabilities

### Database Collections Used

- `user_coaching_prescriptions` - Active and historical prescriptions
- `training_plans` - Available training plans
- `coaching_prescription_history` - Audit trail of all changes
- `users` - User profiles and ratings
- `game_analyses` - Game analysis with cognitive gaps

## Common Issues

### Backend Connection Error
```
[FAIL] Could not connect to backend at http://localhost:8001/api
```
**Solution:** Start the backend server
```bash
cd backend
python server.py
# or
docker-compose up -d backend
# or
sudo supervisorctl restart backend
```

### MongoDB Connection Error
**Solution:** Ensure MongoDB is running
```bash
# Check if running
mongo --eval "db.adminCommand('ping')"

# Start if not running
sudo systemctl start mongodb
# or
mongod --config /etc/mongodb.conf
```

### Dev Login Failed
**Solution:** Ensure DEV_MODE=true in backend/.env
```bash
echo "DEV_MODE=true" >> backend/.env
```

## Architecture

### Endpoints Tested

- `GET /api/coaching/next-prescription` - Get recommendation
- `POST /api/coaching/choose-alternative` - Create prescription
- `POST /api/coaching/accept-prescription` - Activate prescription
- `GET /api/coaching/current-prescriptions` - List active prescriptions
- `POST /api/coaching/add-parallel-plan` - Add concurrent prescription
- `POST /api/coaching/complete-prescription` - Mark as completed
- `POST /api/coaching/pause-prescription` - Pause temporarily
- `GET /api/coaching/prescription-history` - Audit trail

### Data Models

**Prescription Document**
```json
{
  "prescription_id": "uuid",
  "user_id": "user_id",
  "plan_id": "plan_id",
  "status": "pending|active|paused|completed|abandoned",
  "priority_order": 1,
  "started_at": "iso-datetime",
  "completed_at": "iso-datetime",
  "puzzles_completed": 0,
  "puzzle_accuracy": 0.0,
  "improvement_pct": 0.0,
  "created_at": "iso-datetime",
  "updated_at": "iso-datetime"
}
```

## Integration with Production

### Before Deployment

1. **Run full test suite**
   ```bash
   python tests/test_coaching_integration.py
   pytest tests/test_coaching_integration.py -v
   ```

2. **Verify endpoints exist**
   ```bash
   curl http://localhost:8001/api/coaching/next-prescription \
     -H "Cookie: dev_mode=true"
   ```

3. **Check database indexes**
   ```bash
   # Ensure user_coaching_prescriptions has indexes on:
   # - user_id, status
   # - prescription_id, user_id
   # - priority_order
   ```

### Monitoring in Production

Monitor these metrics:
- Prescription acceptance rate (recommended vs accepted)
- Average prescription completion time
- Parallel plan usage rate
- Plan abandonment rate
- Metrics update frequency

## Extending the Tests

### Adding a New Test

```python
async def test_my_new_scenario():
    """Test: My new scenario description"""
    print("\n=== TEST N: My New Scenario ===")

    async with await setup_authenticated_client() as client:
        # Setup
        await create_test_training_plans(client)

        # Test logic
        res = await client.get(f"{API_URL}/coaching/next-prescription")
        result("Description", res.status_code == 200, f"Status: {res.status_code}")

        # Verify
        if res.status_code == 200:
            data = res.json()
            result("Check field", "field" in data, "Missing field")
```

Then add to `tests` list in `run_all_tests()`.

## Performance Notes

- Each test takes ~1-5 seconds
- Full suite: ~60 seconds
- Tests run sequentially (safe for dev mode)
- No cleanup needed (test data isolated per run)

## References

- **Coaching Routes:** `/backend/routes/coaching.py`
- **Training Plans:** `training_plans` collection
- **Prescription History:** `coaching_prescription_history` collection
- **CLAUDE.md:** Project documentation
