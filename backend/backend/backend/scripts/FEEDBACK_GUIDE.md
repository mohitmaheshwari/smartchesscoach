# ChessGuru Admin Feedback Queue Guide

## Quick Summary

**Endpoint:** `GET /api/admin/feedback`

**Parameters:**
- `status` (optional): Filter by status (`pending`, `acknowledged`, `valid`, `dismissed`)
- `source` (optional): Filter by source (`pwc` = Play with Coach, `review` = Game Review, `training` = Training)
- `limit` (default: 50): Max items per request
- `skip` (default: 0): Pagination offset

**Response:**
```json
{
  "feedback": [
    { /* feedback item 1 */ },
    { /* feedback item 2 */ },
    ...
  ],
  "total": 47,
  "pending": 23
}
```

---

## Feedback Document Structure

Each feedback item has the following fields:

### Core Fields
| Field | Type | Description |
|-------|------|-------------|
| `feedback_id` | string | Unique ID (e.g., `fb_a1b2c3d4e5f6`) |
| `user_id` | string | User who submitted feedback |
| `user_name` | string | User's display name |
| `user_rating` | int/null | User's chess rating at time of feedback |
| `created_at` | ISO datetime | When feedback was submitted |
| `status` | string | `pending` \| `acknowledged` \| `valid` \| `dismissed` |
| `source` | string | Where issue came from: `pwc` (Play with Coach) \| `review` (Game Review) \| `training` (Training) |

### Position Context
| Field | Type | Description |
|-------|------|-------------|
| `game_id` | string | The game where issue occurred |
| `session_id` | string | (For PWC) The Play with Coach session ID |
| `move_number` | int | Move number in the game |
| `move_san` | string | The move played (e.g., `Nf3`, `Bxe4`) |
| `fen` | string | FEN of the position where the move was played |

### Coaching Data (What went wrong)
| Field | Type | Description |
|-------|------|-------------|
| `coaching_text` | string | The exact coaching message shown to user |
| `rule_name` | string | Which detection rule fired (e.g., `hung_piece`, `missed_fork`) |

### Issue Feedback
| Field | Type | Description |
|-------|------|-------------|
| `user_note` | string | Why user thinks coaching is wrong |
| `inaccuracy_reason` | string | Admin/user explanation of the inaccuracy |

### Authoring Submissions
| Field | Type | Description |
|-------|------|-------------|
| `is_authoring_submission` | bool | `true` if user submitted a better caption |
| `suggested_caption` | string/null | The caption the user proposes |

### Diagnostic Data (Technical context)
```python
{
  "diagnostics": {
    "severity": "wrong_move" | "misleading" | "incomplete" | "terse",
    "cp_loss": -120,               # Centipawn loss from the move
    "best_move": "Nd5",            # What Stockfish evaluated as better
    "eval_before": "+0.5",         # Position eval before this move
    "eval_after": "+0.3",          # Position eval after this move
    "phase": "opening" | "middlegame" | "endgame",
    "component": "primary_caption" | "secondary_narrative",
    "concept_id": "concept_safety_hub",
    "goal": "Improve piece safety",
    "consequence": "Piece captured",
    "better_approach": "Move the rook to safety first",
    "your_plan_now": "Attack the king",
  }
}
```

---

## Issue Severity Types

### **"wrong_move"**
The coaching recommended or accepted a move that analysis shows was worse than alternatives.

**Example:**
```
Position: 1k6/8/8/8/8/8/R7/K7 w - - 0 1
User played: Ra8+
Coaching said: "Good move, checks the king!"
Stockfish says: Ra1 was better (+1.0 vs +0.5)
Severity: wrong_move (User lost ~50cp due to coaching error)
```

### **"misleading"**
The coaching explanation was technically inaccurate or misleading, even if the move itself was reasonable.

**Example:**
```
Coaching said: "Nf3 blocks the bishop" (but it doesn't)
User note: "That makes no sense, Nf3 doesn't block anything"
Issue: Coach's explanation is factually wrong about the position
```

### **"incomplete"**
The coaching missed key details or didn't explain WHY the move matters.

**Example:**
```
Coaching: "Bxe5 is a mistake"
User wanted: "Why is it a mistake? What do you see?"
Issue: Coach flagged the mistake but didn't explain the tactical reason
```

### **"terse"**
The coaching was too brief, not teaching-focused enough for a 600-1500 player.

**Example:**
```
Coaching: "Nf3 is better here"
User wanted: "OK but... what's the idea? Why should I learn this?"
Issue: No pattern/principle explanation, just move recommendation
```

---

## Common Rule Names You'll See

These are the detectors that fired and need review:

| Rule | Detection | Common Issue |
|------|-----------|--------------|
| `hung_piece` | Piece with no defense | Usually correct, but may miss x-ray/pin scenarios |
| `missed_fork` | Opportunity for fork/skewer | Can hallucinate forks that don't exist |
| `missed_capture` | Free material available | Usually correct |
| `blunder_by_rating` | Move falls outside rating band | May be too aggressive/conservative for user |
| `tactics_depth_2` | Misses 2-move tactic | Medium reliability |
| `king_safety_violation` | King position weakened | Often correct but can over-fire |
| `time_pressure_blunder` | Blunder in time trouble | Useful context but doesn't excuse wrong coaching |

---

## How to Analyze a Feedback Item

### Step 1: Identify the Issue Type
Look at `diagnostics.severity`:
- **wrong_move?** → Check if `best_move` > `move_san` in cp_loss
- **misleading?** → Check `user_note` and `inaccuracy_reason`
- **incomplete?** → See if coaching_text lacks "because..." explanation
- **terse?** → See if coaching_text is <50 characters with no principle

### Step 2: Verify Position Context
- `fen`: Paste into chess board
- `move_san`: What move was played
- `best_move`: What Stockfish says was better
- `cp_loss`: The margin (>150cp is usually significant)

### Step 3: Evaluate the Rule
- Check `rule_name` — did that rule fire correctly?
- If `rule_name` = `hung_piece` but the piece was actually defended → false positive
- If `rule_name` = `missed_fork` but no fork exists → hallucination

### Step 4: Judge the Coaching Text
- Is the explanation **position-specific**? Or generic filler?
- Does it **explain why** the user's move was wrong?
- Is it in **beginner-friendly language** (no "zwischenzug", etc.)?

---

## Authoring Submissions

When `is_authoring_submission` is `true`:
- User has **proposed a better caption** in `suggested_caption`
- This should be **reviewed and potentially merged** into the template
- Check: Is the suggested caption better than what's stored?

---

## Next Steps: What to Do With Feedbacks

### For "wrong_move" / "misleading"
1. **Query engine** on the FEN to verify Stockfish agrees
2. **Find the template** that generated the coaching (using `rule_name`)
3. **Fix the template** or **add a guard** to prevent the rule from firing in similar positions

### For "incomplete" / "terse"
1. **Enhance the template** with "because..." reasoning
2. **Add a teaching principle** (e.g., "This opens your king to attack")
3. **Test** on a fresh board position to verify the coaching is better

### For Authoring Submissions
1. **Review** the user's proposed caption
2. **Verify** it's position-specific, not generic
3. **Update the template** if the suggestion is good
4. **Mark as "valid"** to credit the user's contribution

---

## Database Details

The feedback queue lives in MongoDB collection: `move_feedback`

**Common queries:**
```python
# All pending feedbacks
db.move_feedback.find({"status": "pending"})

# By source (e.g., all Play with Coach feedbacks)
db.move_feedback.find({"source": "pwc"})

# By rule name (find all "missed_fork" false positives)
db.move_feedback.find({"rule_name": "missed_fork"})

# Authoring submissions only
db.move_feedback.find({"is_authoring_submission": true})

# Recent feedbacks (last 24 hours)
db.move_feedback.find({"created_at": {"$gte": ISODate("2026-06-11")}})
```

---

## API Usage Examples

### Fetch latest 20 pending feedbacks (you don't have the creds yet)
```bash
curl "http://localhost:8001/api/admin/feedback?status=pending&limit=20" \
  -H "Cookie: dev_mode=true"
```

### Filter by source
```bash
# Get all Play with Coach feedbacks
curl "http://localhost:8001/api/admin/feedback?source=pwc&limit=50" \
  -H "Cookie: dev_mode=true"
```

### Update feedback status
```bash
curl -X PATCH "http://localhost:8001/api/admin/feedback/fb_a1b2c3d4e5f6" \
  -H "Content-Type: application/json" \
  -d '{"status": "valid", "admin_notes": "Confirmed issue, template fixed"}' \
  -H "Cookie: dev_mode=true"
```

---

## Data-Driven Analysis

To understand what feedback is most impactful, look for:
1. **High cp_loss feedbacks** (>150cp) — these are significant coaching errors
2. **Repeated rule_name** (e.g., `missed_fork` appearing 5+ times) — systematic issue
3. **Authoring submissions** with high user_rating — experts catching real problems
4. **Multiple users flagging the same rule** — not a one-off edge case
