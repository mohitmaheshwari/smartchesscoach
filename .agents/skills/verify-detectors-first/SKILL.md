# Verify Detectors First — Don't Build New Ones

**CRITICAL PRINCIPLE:** When feedback items show coaching failures, verify EXISTING detectors before designing new ones.

## The Wrong Approach ❌

```
Feedback item: "Coach didn't explain WHY move is bad"
→ Design a new detect_explains_why() detector
→ Add it to caption_facts.py
→ Update R12_blunder.json with new why-clause
```

**Problem:** The existing detectors probably already SET the facts needed. The issue is:
- Template is poorly written
- Gate is blocking the caption
- Existing detector isn't firing (debug why!)

## The Right Approach ✅

```
Feedback item: "Coach didn't explain WHY move is bad"

Step 1: Run pipeline on the position
  → Check caption_facts output
  → Is opp_failure_missed_capture set? ✓
  → Is opp_replied_san set? ✓
  → Is why_clause selected? ✗

Step 2: Diagnose the gap
  - Fact is missing? → Debug the detector
  - Fact is set? → Check why_clauses_opp gate
  - Gate blocks it? → Fix the gate condition
  - Template is sparse? → Rewrite template

Step 3: Fix ONE THING (not add code)
  → Fix the detector logic
  → OR fix the why_clause gate
  → OR rewrite the template
```

## The Audit Workflow

For EACH feedback item:

**1. Is the fact being set?**
```
caption_facts dict → look for expected fact
  ✓ opp_failure_missed_capture
  ✓ why_clause
  ✓ missed_tactic_kind
```

**2. If fact IS set, is template using it?**
```
R12_blunder.json → why_clauses_opp array
  Check: { "when": {"opp_failure_missed_capture": true}, "variant": "..." }
  
  If gate exists but caption is wrong → FIX TEMPLATE
  If gate is missing → ADD GATE
```

**3. If fact is MISSING, which detector broke?**
```
caption_facts.py → grep for detector function
  Example: inject_opp_side_narration_facts()
  
  Check: Why didn't it fire on this position?
  → FIX THE DETECTOR (don't build a new one)
```

## Common Scenarios

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Coach silent on move | Fact set but gate blocks | Add/fix gate in why_clauses |
| Caption is wrong | Detector fires but template is sparse | Rewrite template |
| No explanation | Detector not firing | Debug detector logic |
| Explanation is generic | Why-clause selected but wrong | Fix template variant |

## Key Insight

Existing detectors are COMPREHENSIVE. Most failures aren't "missing detector" — they're:
- "Gate is too restrictive" (silent when should speak)
- "Template is generic" (firing but badly written)
- "Detector has a bug" (edge case not handled)

**Before adding code: trace the existing pipeline. 90% of the time, the fix is in the gate or template.**

## Example Trace

**Feedback:** fb_957fb320d332 — "Opponent's a3 is a mistake. Why??"

**Audit:**
1. Check caption_facts for this position
   - `opp_failure_missed_capture` → is it set?
   - `opp_replied_san` → "Bxc5"?
   - `why_clause` → which one fired?

2. If `opp_failure_missed_capture` is set:
   - Check R12_blunder.json for gate
   - Is `opp_failure_missed_capture` variant defined?
   - What's the template text?
   - Is it good or generic?

3. If `opp_failure_missed_capture` is NOT set:
   - Grep caption_facts.py for "missed_capture" detector
   - Run it manually on this FEN
   - Why didn't it detect the missed Bxc5?
   - Fix the detector logic

**Result:** 9/10 times, you find an existing detector that works, a gate that needs fixing, or a template that needs rewriting. You DON'T need a new detector.

## When to Add a Detector

**ONLY after you've verified:**
- The gap is NOT covered by existing facts
- NO existing detector could detect this
- This is genuinely NEW behavior

**Example:** "Coach never explains king safety tactics"
→ Check if there's a king_safety detector
→ If yes, audit it before adding a new one
→ If genuinely missing, THEN design new detector

## Implementation Pattern

```python
# WRONG: Add new detector
def detect_explains_why():
    return ...

# RIGHT: Debug why existing detector isn't firing
# → Check inject_opp_side_narration_facts()
# → See why it's not setting opp_failure_missed_capture
# → Fix the condition or gate
```

---

**Golden Rule:** Every feedback item is a CLUE that something in the existing system is broken, not missing. Trace it, find it, fix it. Don't add code.
