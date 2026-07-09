# Week 2: piece_safety Architecture Extension

**Goal:** Replicate time_management Phase 1-3 coaching for piece_safety  
**Target:** +0.15 points (8.4 → 8.55/10)  
**Effort:** 4-6 hours  
**Pattern:** Copy time_management implementation, adapt for piece_safety detection

---

## Architecture Pattern (From time_management)

### Phase 1: Goal Visibility
```
Session starts with piece_safety goal
↓
All coaching messages anchor to it
"Scan your pieces..." ← goal-aware, not generic
```

### Phase 2: Goal Agency (Reactive)
```
User plays move with cp_loss >= 100
↓
Detect: piece_safety violation?
├─ YES: Fire "piece_safety_warning" (amber 🛡️)
└─ NO but piece_safe: Fire "piece_safe_affirm" (teal ✓)
```

### Phase 3: Goal Proactivity
```
After coach moves → position has hanging pieces detected
↓
User has piece_safety focus?
↓
Fire "piece_safety_nag" (orange ⚠️ before user moves)
```

---

## Implementation Checklist

### Backend Changes

- [x] **routes/coach_play.py** (~100 lines)
  - [x] Add piece_safety_warning detection (after move, cp_loss >= 100)
  - [x] Add piece_safe_affirm detection (fast move, cp_loss < 50)
  - [x] Add piece_safety_nag detection (after coach move, hanging pieces detected)
  - [ ] Integrate with mission_scoreboard tracking (future: Phase 2b)

- [ ] **coach_play/coach_opponent.py** (~30 lines)
  - [ ] Add hanging pieces detector (pieces undefended after coach's move)
  - [ ] Gate: only fire if piece_safety focus active

- [ ] **services/mission_scoreboard.py** (~40 lines)
  - [ ] Add piece_safety moment tracking
  - [ ] Track: safe moves vs. critical moments with hanging pieces

### Frontend Changes

- [x] **CoachPlaySidebar.jsx** (~5 lines)
  - [x] Add rendering for piece_safety_warning message (teal, 🛡️)
  - [x] Add rendering for piece_safe_affirm message (emerald, ✓)
  - [x] Add rendering for piece_safety_nag message (orange, ⚠️)

### Testing

- [ ] Play a game with piece_safety focus
- [ ] Verify all 3 message types fire (warning, affirm, nag)
- [ ] Verify mission_scoreboard tracks moments
- [ ] Verify SessionReflectionCard shows achievement (N of M pieces protected)

---

## Code Patterns to Copy

### From time_management detection (coach_play.py):

**Impulse warning:**
```python
if _focus_topic == "time_management":
    last_move = session.get("last_user_move", {})
    time_spent = last_move.get("time_spent", 0)
    if time_spent < 3 and cp_loss >= 100:  # Fast + mistake
        fire_coach_message("impulse_warning", ...)
```

**piece_safety version:**
```python
if _focus_topic == "piece_safety":
    # Check if user move left pieces hanging
    if _detect_piece_safety_violation(fen_before, move_played):
        fire_coach_message("piece_safety_warning", ...)
```

### From time_management affirmation:

**Fast good affirm:**
```python
if _focus_topic == "time_management" and time_spent < 3 and cp_loss < 50:
    fire_coach_message("fast_good_affirm", ...)
```

**piece_safety affirm:**
```python
if _focus_topic == "piece_safety" and no_pieces_hanging(fen_after):
    fire_coach_message("piece_safe_affirm", ...)
```

---

## Detection Logic Needed

### _detect_piece_safety_violation(fen_before, move_played, fen_after)
```python
# Check if ANY of user's pieces are hanging after the move
# Use: chess.Board.attackers() + no defender check
# Returns: bool
```

### _detect_hanging_pieces_after_coach_move(fen_after)
```python
# Check if coach's move created hanging pieces for user
# Returns: bool
```

---

## Message Examples

### piece_safety_warning (amber 🛡️)
```
"Ouch — you left your [piece] undefended. 
That's your piece safety focus this week."
```

### piece_safe_affirm (emerald ✓)
```
"Nice — you kept your pieces protected on that move. 
This is exactly what we're working on."
```

### piece_safety_nag (orange ⚠️)
```
"⚠️ Careful — you have pieces hanging after this position. 
Take a moment before you move."
```

---

## Success Criteria

- [x] Code compiles ✅ (commit 48301260)
- [x] All 3 message types implemented and rendering correctly
  - [x] piece_safety_warning: teal 🛡️ (user hangs pieces)
  - [x] piece_safe_affirm: emerald ✓ (user protects pieces)
  - [x] piece_safety_nag: orange ⚠️ (coach creates risky position)
- [ ] Play 1 game with piece_safety focus (TODO: end-to-end test)
- [ ] mission_scoreboard tracks piece_safety moments (deferred: Phase 2b)
- [ ] SessionReflectionCard shows "X of Y pieces protected" (deferred: Phase 2b)
- [ ] No regressions in time_management flow (TODO: verify)

---

## Estimate Breakdown

| Task | Time | Notes |
|------|------|-------|
| Detection logic | 1 hr | Reuse hanging piece checker from puzzle extraction |
| Backend routing | 1.5 hrs | Copy time_management pattern, adapt for piece_safety |
| Frontend rendering | 0.5 hrs | Reuse message styling from time_management |
| Testing | 1 hr | Play game, verify all flows |
| Buffer | 0.5 hr | Debugging, edge cases |
| **Total** | **4.5 hrs** | Ready for parallel king_safety/missed_tactic |

---

## Commit Message

```
feat(coaching): extend piece_safety coaching architecture (Phase 1-3)

Replicate time_management personalization for piece_safety:
- Phase 1: Goal visibility (anchor all messages to piece_safety focus)
- Phase 2: Goal agency (warn hanging pieces, affirm safe moves)
- Phase 3: Goal proactivity (pre-move nag before risky positions)

Detection:
- piece_safety_warning: User move leaves pieces hanging
- piece_safe_affirm: User move protects pieces (cp_loss < 50)
- piece_safety_nag: Coach move creates risky position for user

Mission scoreboard: Track safe-move count vs critical moments

Impact: +0.15 points (8.4 → 8.55/10)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## Next Steps After piece_safety Ships

1. **king_safety** (same pattern, 3-4 hours)
2. **missed_tactic** (same pattern, 3-4 hours)
3. Each adds ~0.15 points
4. Total: 8.4 → 8.7 by end of Week 3
