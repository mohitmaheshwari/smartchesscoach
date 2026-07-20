# Active Recall Implementation Guide

## Overview

Active recall enhances coaching with two pedagogically sound questions after a mistake:

1. **Ranking**: "Which move is best here?" (Options 3-4 moves to drag-rank)
2. **Concept**: "Why was your move worse?" (MCQ with 4 options)

Both are **verified** against:
- `chess_verification_layer.verify_move()` - ensures moves are ranked correctly
- `get_critical_facts()` - ensures cognitive gap matches position
- Position evidence - ensures this pattern actually exists

If verification fails, active recall is skipped silently (coaching text still shows).

---

## File Structure

```
backend/
├── active_recall_service.py          # Core service (413 lines)
├── active_recall_integration.py      # Endpoint integration layer
├── ACTIVE_RECALL_IMPLEMENTATION.md   # This file
└── routes/
    └── coach_play.py                 # /v5/interactive-feedback endpoint
```

---

## Integration into /v5/interactive-feedback

### Step 1: Import at top of coach_play.py

```python
from active_recall_integration import enrich_coaching_with_active_recall
```

### Step 2: After coaching decision, enrich with active recall

In `@router.post("/v5/interactive-feedback")` around where coaching response is built:

```python
# ... existing coaching logic ...

coaching_response = {
    "narrative": "...",
    "severity": "mistake",
    "best_move": "Nd5",
    # ... other fields ...
}

# NEW: Add active recall options if they verify
enriched = await enrich_coaching_with_active_recall(
    db=db,
    coaching_response=coaching_response,
    fen_before=fen_before,
    user_move_san=move_san,
    best_move_san=best_move_san,
    cognitive_gap=detected_gap,  # e.g., "centralization"
    user_rating=user_rating,
    cp_loss=cp_loss,
    user_id=user_id
)

return enriched
```

### Result Structure

```json
{
  "narrative": "Nf3 looks solid, but centralizing Nd5 is stronger...",
  "severity": "mistake",
  "active_recall": {
    "ranking": {
      "type": "ranking",
      "question": "Which move is best here?",
      "options": ["Nd5", "Nf3", "e3"],
      "correct_index": 0,
      "is_verified": true
    },
    "concept": {
      "type": "concept",
      "question": "Why is Nf3 worse than Nd5?",
      "options": [
        "Controls more squares",     ← CORRECT
        "Attacks opponent's pieces",
        "Develops faster",
        "Protects your king"
      ],
      "correct_index": 0,
      "is_verified": true,
      "cognitive_gap": "centralization"
    }
  }
}
```

If verification fails, `active_recall` = `null`, frontend shows coaching text only.

---

## Frontend Integration

### 1. Receive active recall options

```javascript
// In CoachPlay.jsx when coaching response arrives:
const coaching = data.active_recall;

if (coaching?.ranking && coaching?.concept) {
  // Show active recall UI
  setRankingQuestion(coaching.ranking);
  setConceptQuestion(coaching.concept);
} else {
  // Show coaching text only
  setChatMessage(coaching.narrative);
}
```

### 2. Rendering

#### Ranking Component
```javascript
<div className="active-recall-ranking">
  <p>{ranking.question}</p>
  <div className="drag-to-rank">
    {ranking.options.map((move, i) => (
      <div key={i} draggable onDragEnd={(e) => handleRank(i)}>
        {move}
      </div>
    ))}
  </div>
  <button onClick={() => submitRanking(userRanking)}>
    Check Answer
  </button>
</div>
```

#### Concept Component
```javascript
<div className="active-recall-concept">
  <p>{concept.question}</p>
  <div className="mcq-options">
    {concept.options.map((option, i) => (
      <label key={i}>
        <input 
          type="radio" 
          value={i}
          onChange={(e) => setConceptAnswer(i)}
        />
        {option}
      </label>
    ))}
  </div>
  <button onClick={() => submitConcept(conceptAnswer)}>
    Check Answer
  </button>
</div>
```

### 3. Submit responses

```javascript
// After user answers both questions:
await fetch("/api/coach/play/active-recall-response", {
  method: "POST",
  body: JSON.stringify({
    session_id: session.session_id,
    move_index: moveNumber,
    ranking_response: {
      selected_index: userRanking,
      correct_index: ranking.correct_index
    },
    concept_response: {
      selected_index: conceptAnswer,
      correct_index: concept.correct_index
    }
  })
});
```

---

## Backend: Recording Responses

### New endpoint: POST /api/coach/play/active-recall-response

```python
@router.post("/active-recall-response")
async def record_active_recall_response(
    request: Dict = Body(...),
    user: User = Depends(get_current_user)
):
    """Record user's active recall responses"""
    from active_recall_integration import record_active_recall_response
    
    session_id = request.get("session_id")
    ranking_response = request.get("ranking_response")
    concept_response = request.get("concept_response")
    
    checkpoint = await record_active_recall_response(
        db=db,
        user_id=user.user_id,
        session_id=session_id,
        move_index=request.get("move_index"),
        cognitive_gap=request.get("cognitive_gap"),
        ranking_response=ranking_response,
        concept_response=concept_response,
    )
    
    return {
        "recorded": checkpoint is not None,
        "score": checkpoint.get("combined_score") if checkpoint else None
    }
```

---

## Database: learning_checkpoints Collection

Schema:
```python
{
  "_id": ObjectId(),
  "user_id": "user_123",
  "session_id": "session_456",
  "move_index": 5,
  "pattern": "centralization",
  "ranking_correct": true,
  "concept_correct": true,
  "combined_score": "mastered",  # "mastered" | "partial" | "not_learned"
  "timestamp": "2026-07-20T18:30:00Z"
}
```

Index to add:
```python
db.learning_checkpoints.create_index([
    ("user_id", 1),
    ("pattern", 1),
    ("timestamp", -1)
])
```

---

## Quality Assurance

### Verification Rules

**Ranking options** skip if:
- ❌ FEN is invalid
- ❌ Moves are illegal
- ❌ verify_move() says best move isn't actually better
- ❌ Options don't differ by minimum cp_spread (calibrated by rating)

**Concept options** skip if:
- ❌ FEN is invalid
- ❌ get_critical_facts() doesn't detect the cognitive gap
- ❌ No explanation template for this gap

**Entire active recall** skips if:
- ❌ Either ranking OR concept fails verification

When skipped, coaching text still shows. User sees Q&A only for high-confidence positions.

---

## Testing Checklist

- [ ] Ranking options are always pedagogically distinct (not 1cp apart)
- [ ] Concept MCQ has correct answer + 3 plausible distractors
- [ ] Difficulty calibrates to user rating (800 gets easy options, 1800+ gets hard)
- [ ] Responses are recorded to learning_checkpoints
- [ ] Frontend shows "mastered" / "partial" / "not_learned" feedback
- [ ] Active recall is skipped silently (no errors) when verification fails
- [ ] Spaced repetition service can read learning_checkpoints

---

## Spaced Repetition Integration (Future)

```python
async def get_spaced_repetition_targets(db, user_id: str):
    """Find patterns user should review"""
    checkpoints = await db.learning_checkpoints.find({
        "user_id": user_id,
        "combined_score": {"$in": ["partial", "not_learned"]}
    }).sort("timestamp", -1).to_list(None)
    
    # Group by pattern, find recurring problems
    # In game 2: show this pattern again
    # In game 5: show if still weak
    # In game 10: show if mastered to maintain
```

---

## Metrics to Track

1. **Engagement**: % of moves with active recall shown
2. **Accuracy**: % of ranking/concept answers correct (per user, per pattern)
3. **Learning**: Do users who answer correctly improve faster?
4. **Coverage**: Which patterns have active recall? Which are skipped?

---

## Migration Script (Run once)

```python
async def create_learning_checkpoints_collection():
    await db.create_collection("learning_checkpoints")
    await db.learning_checkpoints.create_index([
        ("user_id", 1),
        ("pattern", 1),
        ("timestamp", -1)
    ])
    logger.info("Created learning_checkpoints collection")
```

---

## Rollout Plan

**Phase 1 (Week 1):** Deploy services, wire into /v5/interactive-feedback
- Backend: active_recall_service.py + integration
- Frontend: basic Q&A UI, response submission
- Measurement: verify % of positions get active recall

**Phase 2 (Week 2):** Improve frontend UX
- Add animations to ranking (drag to sort looks polished)
- Add feedback after each Q&A ("You got it!" / "Not quite...")
- Add progress bar (move X of Y this game)

**Phase 3 (Week 3):** Spaced repetition
- Read learning_checkpoints
- Show patterns in future games
- Track improvement velocity

---

## Debugging

Enable verbose logging:
```python
logging.getLogger("active_recall_service").setLevel(logging.DEBUG)
```

Check why a position skipped active recall:
```bash
# Look for "[AR]" log lines
docker logs chess-coach-backend | grep "\[AR\]"
```

Sample the learning checkpoints:
```python
db.learning_checkpoints.find().sort("timestamp", -1).limit(10)
```
