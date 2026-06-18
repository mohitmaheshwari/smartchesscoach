# ChessGuru Feedback Self-Improvement System

## Overview

A closed-loop system that automatically processes user feedback, ships improvements, and tracks app quality metrics.

```
User Feedback (251 pending)
           ↓
    Triage & Classify
    (LLM Exposer API)
           ↓
    ├─ Authoring Submissions (ship to production)
    ├─ Wrong Reasoning (file in CAPTION_BACKLOG)
    ├─ Below-Band (dismiss as expected)
    └─ Incomplete Teaching (rewrite and ship)
           ↓
    Auto-Deploy Fixes
           ↓
    Monitor Improvements
```

---

## Current Status (2026-06-12)

| Metric | Count |
|--------|-------|
| Total pending feedbacks | 251 |
| New (since batch 2) | 157 |
| Processed (batch 1-2) | 120 |
| Captions shipped to production | 43 |
| Templates with overrides | 184 |

### Breakdown of 157 New Feedbacks
- **good**: 55 items — moves rated good by coach (may be wrong classification)
- **mistake**: 29 items — engine-confirmed mistakes  
- **context**: 26 items — position context issues
- **unknown**: 19 items — unclassified
- **opp_inaccuracy**: 8 items — opponent's inaccurate moves
- **inaccuracy**: 7 items — user's inaccurate moves
- **blunder**: 5 items — major blunders
- **opp_mistake**: 4 items
- **opp_blunder**: 4 items

---

## How to Run

### 1. **View Current Status**
```bash
docker exec chess-coach-backend python scripts/feedback_status_dashboard.py
```

### 2. **Run Batch Triage (Manual)**
```bash
# Triage next batch of 100 feedbacks
docker exec -e LLM_EXPOSER_URL=http://host.docker.internal:8000 \
  -e LLM_EXPOSER_KEY=<key> \
  chess-coach-backend python scripts/triage_batched.py
```

### 3. **Ship Authoring Submissions**
```bash
docker exec chess-coach-backend python scripts/ship_authoring_submissions.py
```

### 4. **Run Continuous Loop** (Background)
```bash
# Start auto-processing loop (5-minute poll interval)
docker exec -d \
  -e MONGO_URL="mongodb://..." \
  -e LLM_EXPOSER_URL="http://host.docker.internal:8000" \
  -e LLM_EXPOSER_KEY="<key>" \
  chess-coach-backend nohup python scripts/feedback_self_improvement_loop.py > /tmp/feedback_loop.log 2>&1 &
```

---

## Pipeline Details

### Phase 1: Triage (LLM Exposer)
**Input**: Batch of pending feedbacks  
**Process**: LLM classifies each feedback into:
- **AUTHORING** (52.5%) — user proposed caption
- **CLASS_B** (7.5%) — wrong reasoning in coach
- **CLASS_D** (2.5%) — incomplete teaching
- **CLASS_A_SILENT** (7.5%) — silent on routine moves
- **CLASS_A_BAND** (7.5%) — below-band precision  
- **DISMISS** (22.5%) — off-topic

**Output**: Classification CSV with recommendations

### Phase 2: Auto-Ship Authoring
**Input**: Feedbacks with `is_authoring_submission=true` and `suggested_caption`  
**Process**: Insert into `authored_caption_overrides` collection  
**Output**: Live captions served to users at position match

### Phase 3: File Patterns
**Input**: Classified feedbacks  
**Process**: 
- Group CLASS_B items by rule name  
- Check if pattern exists in CAPTION_BACKLOG  
- Create new backlog entry if novel (≥2 examples)

**Output**: Updated CAPTION_BACKLOG.md with pattern references

### Phase 4: Deploy
**Input**: Shipped captions + filed patterns  
**Process**:
- Merge `authored_caption_overrides` into caption templates
- Redeploy backend with updated coaching logic
- Verify no regressions in test suite

**Output**: Live fixes in production

---

## Metrics & KPIs

### Quality Signals
- **Feedback actionability**: 52.5% (batches 1-2)
- **Authoring submission rate**: 20-25% of all feedback
- **Patterns fielded per 100 feedback**: ~10-15 (wrong-reasoning + incomplete-teaching)

### Improvement Tracking
- **Captions shipped this month**: 43 (and growing)
- **Templates with overrides**: 184
- **False-positive rate (below-band)**: ~35% (expected, dismiss these)

### Cycle Time
- **Triage latency**: ~30s per batch (20 items)
- **Ship latency**: <2m (bulk insert)
- **Deploy latency**: ~3-5m (rebuild + CI)

---

## Files

| File | Purpose |
|------|---------|
| `scripts/triage_via_exposer.py` | Single-batch triage (legacy, timeout issues) |
| `scripts/triage_batched.py` | **Optimized** batched triage (5 parallel batches) |
| `scripts/ship_authoring_submissions.py` | Auto-ship user captions to production |
| `scripts/feedback_self_improvement_loop.py` | Continuous 5-min poll loop (background) |
| `scripts/feedback_status_dashboard.py` | Status snapshot (run anytime) |
| `FEEDBACK_GUIDE.md` | Complete feedback schema reference |

---

## Next Steps (Priority)

1. **[IMMEDIATE]** Triage 157 new feedbacks → run `/triage-feedback` skill
2. **[TODAY]** File patterns from batches 1-2 in CAPTION_BACKLOG
3. **[TODAY]** Ship all authoring submissions to production
4. **[TOMORROW]** Deploy updated coaching logic with new templates
5. **[WEEKLY]** Monitor feedback quality metrics and iterate

---

## Architecture

### Database Collections

**move_feedback**
```javascript
{
  feedback_id: "fb_xxx",
  status: "pending|shipped|acknowledged|dismissed",
  is_authoring_submission: boolean,
  suggested_caption: string|null,
  diagnostics: {severity, cp_loss, best_move, ...},
  classification: "AUTHORING|CLASS_B|CLASS_D|..."
}
```

**authored_caption_overrides**
```javascript
{
  feedback_id: "fb_xxx",
  game_id: "...",
  move_san: "Nf3",
  authored_caption: "...",
  status: "live",
  applied_at: timestamp
}
```

### API Endpoints

- `GET /api/admin/feedback?limit=100` — List pending feedbacks
- `PATCH /api/admin/feedback/{id}` — Update status
- `POST /api/feedback/flag` — Submit flag (user-facing)

---

## Troubleshooting

### Issue: Triage timeout
- **Cause**: Single batch too large or LLM Exposer overloaded
- **Fix**: Use `triage_batched.py` (5 parallel batches of 20)

### Issue: Authoring submissions not shipping
- **Cause**: `suggested_caption` is NULL or empty
- **Fix**: Check `is_authoring_submission=true AND suggested_caption != null` in DB

### Issue: Patterns not being filed
- **Cause**: No CAPTION_BACKLOG.md or patterns already exist
- **Fix**: Verify file exists, check for duplicates before adding

---

## Success Criteria

✅ 52.5% of feedback is actionable (authoring + patterns)  
✅ 43 captions shipped to production (and growing)  
✅ Zero regressions from coached captions  
✅ User feedback quality improving (fewer silent complaints)  
✅ Sub-5min triage + ship cycle time  

---

*Last updated: 2026-06-12*  
*Contact: Coaching Platform Team*
