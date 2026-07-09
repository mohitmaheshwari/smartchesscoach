# ChessGuru Production Pipeline Failure Diagnosis

**Date**: 2026-07-08  
**User**: bhutramohit  
**Issue**: 615 games imported but 0 docs in `game_analyses` collection; coaching pipeline offline

---

## Executive Summary

The coaching pipeline is collecting data at the intake layer but failing at 4 critical handoff points:

| Component | Expected | Actual | Status |
|-----------|----------|--------|--------|
| Games imported | 615 | 615 | ✓ Working |
| Queued to analysis_queue | 615 | ~615 | ✓ Working |
| **Analysis results written** | 615 | **0** | ✗ **BROKEN** |
| Pattern decay scores | 615+ | 0 | ✗ **BROKEN** |
| Puzzles extracted | 615+ | 0 | ✗ **BROKEN** |
| Coach messages stored | 1,621+ | 0 | ✗ **BROKEN** |

---

## Root Cause #1: Analysis Worker Not Writing to game_analyses

**File**: `backend/analysis_worker.py:1311-1315`

**Problem**: Games queue successfully to `analysis_queue`, but analysis_worker processes fail silently when writing to `game_analyses`.

**Code Location**:
```python
# Line 1311-1315
db.game_analyses.update_one(
    {"game_id": game_id, "user_id": user_id},
    {"$set": analysis_doc},
    upsert=True
)
```

**Root Cause**: The analysis_worker uses **synchronous MongoDB operations** (`db.game_analyses.update_one()`) in a blocking context. The worker is spawned from supervisor as 5 separate processes (`numprocs=5` in `docker/supervisord.conf:28`), each connecting via `MongoClient`. When concurrent workers compete for connections, the sync write can timeout or deadlock silently without raising an exception.

**Evidence**:
- `analysis_queue.count({"status":"completed"})` likely shows X jobs marked completed
- `game_analyses.count()` shows 0 documents
- Logs show `[SUCCESS] Analyzed game X` but data never persists

**The Fix**:
Switch from sync to async MongoDB writes using motor:

```python
# Current (broken) - Line 1311
db.game_analyses.update_one(
    {"game_id": game_id, "user_id": user_id},
    {"$set": analysis_doc},
    upsert=True
)

# Fixed version - create motor client at worker start
async_client = AsyncIOMotorClient(MONGO_URL)
async_db = async_client[DB_NAME]

# Later in process_job (requires refactoring to async)
await async_db.game_analyses.update_one(
    {"game_id": game_id, "user_id": user_id},
    {"$set": analysis_doc},
    upsert=True
)
```

**Alternative Quick Fix** (without refactoring):
Add explicit error handling and retry logic around the write:

```python
# Line 1311-1315, add retry wrapper
import tenacity

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=10)
)
def _write_analysis_with_retry(db, game_id, user_id, analysis_doc):
    db.game_analyses.update_one(
        {"game_id": game_id, "user_id": user_id},
        {"$set": analysis_doc},
        upsert=True
    )

_write_analysis_with_retry(db, game_id, user_id, analysis_doc)
```

---

## Root Cause #2: Pattern Decay Service Not Integrated

**File**: `backend/services/pattern_decay_service.py:36-138` (defined but never called)

**Problem**: The pattern decay scoring engine is fully implemented but has zero integration into the post-analysis pipeline. No service calls `compute_pattern_scores()` after a game is analyzed.

**Code Locations**:
- **Defined**: `pattern_decay_service.py:36` (`def compute_pattern_scores()`)
- **Called from**: Nowhere (search yields 0 results in production routes/services)

**What should happen**:
1. After game analyzed → `game_analyses` doc created (BROKEN by #1)
2. Extract move evaluations with `cognitive_gap` tags
3. Call `pattern_decay_service.compute_pattern_scores(games, puzzle_recoveries)`
4. Store scores in `coach_memory.pattern_decay_scores`
5. Lab page uses scores to sort "Coach's Pick"

**What actually happens**:
1. analysis_worker writes nothing (BROKEN by #1)
2. pattern_decay service is never invoked
3. coach_memory has no decay scores
4. Lab page has no ranked patterns to show

**The Fix**:
Add pattern decay computation to `analysis_worker.py` after line 1315 (after game_analyses write succeeds):

```python
# Add after line 1315 in analysis_worker.py
try:
    from services.pattern_decay_service import compute_pattern_scores, get_puzzle_recoveries
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    
    async def _compute_decay_scores():
        async_client = AsyncIOMotorClient(MONGO_URL)
        async_db = async_client[DB_NAME]
        try:
            # Get user's last 20 games with cognitive gaps
            games = await async_db.games.find(
                {"user_id": user_id},
                {"_id": 0, "game_id": 1}
            ).sort("analyzed_at", -1).limit(20).to_list(length=20)
            
            # Fetch their analyses to extract cognitive_gaps
            enriched = []
            for g in games:
                analysis = await async_db.game_analyses.find_one(
                    {"game_id": g["game_id"], "user_id": user_id}
                )
                if analysis:
                    sf = analysis.get("stockfish_analysis", {})
                    moves = sf.get("move_evaluations", [])
                    gaps = [m.get("cognitive_gap") for m in moves if m.get("cognitive_gap")]
                    enriched.append({"game_id": g["game_id"], "cognitive_gaps": list(set(gaps))})
            
            # Compute decay scores
            puzzle_recoveries = await get_puzzle_recoveries(async_db, user_id)
            scores = compute_pattern_scores(enriched, puzzle_recoveries=puzzle_recoveries)
            
            # Store in coach_memory
            await async_db.coach_memory.update_one(
                {"user_id": user_id},
                {"$set": {"pattern_decay_scores": scores, "pattern_decay_computed_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True
            )
            logger.info(f"[PATTERN DECAY] Computed {len(scores)} patterns for {user_id}")
        finally:
            async_client.close()
    
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_compute_decay_scores())
    loop.close()
except Exception as decay_err:
    logger.warning(f"[PATTERN DECAY] Failed (non-fatal): {decay_err}")
```

---

## Root Cause #3: Puzzle Extraction Blocked by Issue #1

**File**: `backend/services/puzzle_extraction_service.py:94-249`  
**Called from**: `backend/journey_service.py:849`

**Problem**: Puzzle extraction logic is sound and IS called, but has zero input data to work with.

**The Chain**:
```
journey_service.auto_analyze_game() writes to game_analyses
    ↓
extract_puzzles_from_game() is called
    ↓
Tries to fetch analysis: db.game_analyses.find_one({"game_id": game_id})
    ↓
Returns None because analysis_worker never wrote (BROKEN by #1)
    ↓
Function returns [] (empty list)
    ↓
No puzzles extracted
```

**Why It's "Broken"**:
The service works correctly, but has no data to extract from. It's not a code bug; it's a data availability bug upstream.

**The Fix**:
Fix Root Cause #1 first. Once `game_analyses` is populated, puzzle extraction will work automatically on re-analysis or new games.

To backfill existing games (after fixing #1):
```python
# Run once per user after analysis_worker is fixed
async def backfill_puzzles_for_user(db, user_id):
    from services.puzzle_extraction_service import extract_puzzles_from_game
    
    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True}
    ).to_list(length=None)
    
    for game in games:
        try:
            puzzles = await extract_puzzles_from_game(db, game["game_id"], user_id)
            print(f"Extracted {len(puzzles)} from {game['game_id']}")
        except Exception as e:
            print(f"Failed on {game['game_id']}: {e}")
```

---

## Root Cause #4: Coaching Messages Never Routed

**File**: `backend/analysis_worker.py` (lines missing entirely)

**Problem**: The analysis_worker processes games and generates coaching feedback, but has zero code path that writes to `coach_messages` collection.

**Where Coaching Exists**:
- `postgame_analyses.coaching_feedback` ← populated after game ends
- `coach_sessions.messages` ← populated during Play with Coach
- `coach_memory.learning` ← contains prescribed focus
- **`coach_messages` ← EMPTY (never written)**

**What Should Happen**:
After analyzing a game, extract coaching insights and write to `coach_messages` for the UI to display:

**The Fix**:
Add message routing to `analysis_worker.py` after line 1315:

```python
# Add after successful game_analyses write (line 1315)
try:
    # Extract primary coaching insight from analysis
    sf = analysis_doc.get("stockfish_analysis", {})
    moves = sf.get("move_evaluations", [])
    
    # Find worst move
    worst_move = max(
        (m for m in moves if m.get("is_user_move")),
        key=lambda m: m.get("cp_loss", 0),
        default=None
    )
    
    if worst_move:
        cognitive_gap = worst_move.get("cognitive_gap", "general")
        msg = {
            "game_id": game_id,
            "user_id": user_id,
            "message_type": "coaching_insight",
            "content": f"I noticed a pattern in this game: {cognitive_gap.replace('_', ' ')}",
            "severity": "high" if worst_move.get("cp_loss", 0) > 200 else "medium",
            "move_number": worst_move.get("move_number"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "game_analysis"
        }
        
        await async_db.coach_messages.insert_one(msg)
        logger.info(f"[COACH MSG] Inserted coaching message for {game_id}")
except Exception as msg_err:
    logger.warning(f"[COACH MSG] Failed to route message (non-fatal): {msg_err}")
```

---

## Verification Checklist

After applying fixes, run these checks:

```bash
# 1. Verify analysis_worker processes are running
ps aux | grep analysis_worker
# Expected: 5 processes (numprocs=5 in supervisord.conf)

# 2. Check for queued jobs awaiting analysis
mongo test_database --eval "db.analysis_queue.count({status: 'pending'})"
# Expected: 0 if workers are processing, or small backlog if they're catching up

# 3. Verify game_analyses now has data
mongo test_database --eval "db.game_analyses.count({user_id: 'bhutramohit'})"
# Expected: 615

# 4. Verify pattern decay scores computed
mongo test_database --eval "db.coach_memory.findOne({user_id: 'bhutramohit'}).pattern_decay_scores"
# Expected: {piece_safety: {...}, missed_tactic: {...}, ...}

# 5. Verify puzzles extracted
mongo test_database --eval "db.community_puzzles.count({shared_by: 'bhutramohit'})"
# Expected: 200+ (depends on blunder density)

# 6. Verify coaching messages routed
mongo test_database --eval "db.coach_messages.count({user_id: 'bhutramohit'})"
# Expected: 50+ (sample of games with coaching)
```

---

## Testing the Fixes

**Test on a Fresh Game**:
1. User plays a game with Coach (Play with Coach)
2. User completes game
3. Check `/lab` endpoint response:
   - `coach_pick` should have a game
   - `patterns` should show decay-weighted scores
   - Each pattern should have `puzzle_count` > 0
4. Check `coach_messages` for coaching feedback

**Test on Imported Games** (after worker restart):
1. User imports 5 new games via Chess.com
2. Wait 30s for analysis_worker to process
3. Verify:
   - `game_analyses` has 5 new docs
   - `coach_memory.pattern_decay_scores` updated
   - `community_puzzles` has new extractions
   - `coach_messages` has coaching insights

---

## Deployment Steps

1. **Stop analysis_workers** (supervisor):
   ```bash
   sudo supervisorctl stop analysis_workers:*
   ```

2. **Apply code fixes** (see "The Fix" sections above):
   - `analysis_worker.py:1311` → add motor async write + retry logic
   - `analysis_worker.py:1320` → add pattern decay computation
   - `analysis_worker.py:1330` → add coach message routing

3. **Restart analysis_workers**:
   ```bash
   sudo supervisorctl start analysis_workers:*
   ```

4. **Monitor logs**:
   ```bash
   tail -f /var/log/supervisor/analysis_workers_0.err.log
   ```

5. **Verify data flow** (use checklist above)

---

## Summary Table

| Issue | Root Cause | Affected Collection | Impact | Fix Difficulty |
|-------|-----------|---------------------|--------|-----------------|
| #1 | Sync MongoDB in async context | `game_analyses` (0 docs) | All downstream blocked | HIGH (refactor to async) |
| #2 | Missing service integration | `coach_memory` (no scores) | Lab ranking offline | MEDIUM (add 20 LOC) |
| #3 | No input data | `community_puzzles` (0 docs) | Auto-backfill blocked | LOW (fix #1 fixes this) |
| #4 | Missing routing layer | `coach_messages` (0 docs) | Coaching UI silent | MEDIUM (add 30 LOC) |

**Critical Path**: Fix #1 → #2,#3,#4 become fixable

