# DEPLOYMENT: Pattern #2 - ASSESSMENT_CONFLICTS Gate

## Status: READY TO DEPLOY ✅

**Changed file:** `backend/services/caption_pipeline.py`
**Lines modified:** 3782-3821 (added cp_loss gate before caption render)
**Syntax verified:** ✓ (Python compile check passed)

---

## Deployment Steps

### 1. Start Docker (if not running)
```bash
# Windows: Open Docker Desktop
# OR run from WSL/PowerShell:
# docker run ... or docker compose up
```

### 2. Copy updated file to container
```bash
docker cp backend/services/caption_pipeline.py chess-coach-backend:/app/backend/services/
```

### 3. Verify import
```bash
docker exec chess-coach-backend python3 -c "from services.caption_pipeline import build_move_teaching_decision; print('✓ Import OK')"
```

### 4. Restart backend service (to pick up new code)
```bash
docker exec chess-coach-backend supervisorctl restart backend
# OR
docker compose restart backend
```

### 5. Verify backend is healthy
```bash
curl -s http://127.0.0.1:8001/api/auth/dev-login | python3 -m json.tool
```

---

## Testing: Verify Pattern #2 Fix

### Test Positions (Assessment Conflicts — should NOW render NO caption)

**Before fix:** Coach renders caption even though cp_loss is low and move is rated "good"
**After fix:** Coach is silent (assessment conflict suppressed)

#### Position 1: fb_f901258f7831
- Game: game_ef9f422a062d
- Move: Qd8
- Severity: **good** (10cp loss)
- Expected: **NO caption** (suppressed by gate)
- Command:
```bash
curl -s http://127.0.0.1:8001/api/game/game_ef9f422a062d -b "dev_mode=true" | python3 -m json.tool | grep -A 5 "Qd8"
```

#### Position 2: fb_c7b7be53b387
- Game: game_bc41022831e0
- Move: Nc6
- Severity: **good** (38cp loss)
- Expected: **NO caption** (suppressed by gate)

#### Position 3: fb_05710bfc7125
- Game: game_692ab776c5b1
- Move: Nc3
- Severity: **context** (32cp loss)
- Expected: **NO caption** (suppressed by gate)

#### Positions 4-6
Same pattern — 3 more assessment conflict positions. Check that captions are suppressed.

---

## Success Criteria

✅ All 6 positions render **empty caption** (assessment conflicts resolved)
✅ Concrete tactics (forks, mates, checks) on LOW cp_loss still render (no false positives)
✅ High cp_loss captions still render normally (gate doesn't over-suppress)
✅ Backend health check passes

---

## Rollback (if needed)

If the gate over-suppresses legitimate captions:

```bash
git checkout HEAD -- backend/services/caption_pipeline.py
docker cp backend/services/caption_pipeline.py chess-coach-backend:/app/backend/services/
docker exec chess-coach-backend supervisorctl restart backend
```

---

## Next: Test Positions

Once deployed, run the test commands above to verify:
- 6/6 assessment conflicts suppressed
- 0/6 false positives

Then proceed to Pattern #1 (WANTS_WHY_EXPLANATION) implementation in Phase 2.

---

## Changes Summary

```diff
# Before: All captions render if any fact fires
if render_caption_dict is not None:
    rendered = render_caption_dict(caption_facts)

# After: Gate suppresses low-cp captions that conflict with severity rating
if render_caption_dict is not None and not _should_gate_low_cp_caption:
    rendered = render_caption_dict(caption_facts)

# Gate logic:
# - User move + rating available
# - cp_loss below rating-band threshold (30-150cp depending on rating)
# - No concrete tactic fact fired (fork, mate, check, major capture)
# => Suppress caption (assessment conflict gate)
```
