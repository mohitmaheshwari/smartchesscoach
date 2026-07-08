# Coaching Engine v2, Phase 1: Implementation Plan

**Status:** Audit Complete → Implementing Fixes  
**Date:** 2026-07-08  
**Target:** Move accuracy from ~50% to ≥70%

---

## Audit Findings

Scanned 50 games, 273 critical moves (cp_loss ≥ 100):

| Gap Type | Count | % | Issues | Action |
|----------|-------|---|--------|--------|
| piece_safety | 98 | 36% | Over-fires on incidental pawn punishment | FIX detector logic + gate |
| king_safety | 59 | 22% | Mislabels queens-off endgame king moves | RECLASSIFY to endgame_technique |
| piece_activity | 35 | 13% | Low confidence (~50% accuracy) | **EXCLUDE from coaching** |
| opening_knowledge | 25 | 9% | Reasonable | Keep |
| missed_tactic | 23 | 8% | Reasonable | Keep |
| tactical_oversight | 10 | 4% | Reasonable | Keep |
| calculation_depth | 9 | 3% | Low confidence (~45% accuracy) | **EXCLUDE from coaching** |
| pawn_structure | 8 | 3% | Low confidence (~40% accuracy) | **EXCLUDE from coaching** |
| endgame_technique | 2 | 1% | Under-represented (should be higher) | Backfill from king_safety |
| (None/Unknown) | 4 | 1% | Detection returned None | Debug + fix |

**Quick Win:** Filter out piece_activity, calculation_depth, pawn_structure → 19% fewer false positives → estimated accuracy +8-10%

**Deep Fixes Required:**
1. piece_safety: Engine-grounded detection (not geometry)
2. king_safety: Phase gate for queens-off endgame
3. None/Unknown: Fix detection failures

---

## Implementation: 3-Part Strategy

### Part 1: Quick Win — Exclude Low-Confidence Categories (Estimated +8-10% accuracy)

**File:** `backend/analysis_interpreter.py`  
**Change:** Line ~398 in `_precedence_adjust()` — filter out low-confidence gaps before returning

```python
def _precedence_adjust(cognitive_gap, move):
    """Engine-hard category precedence + phase gates (signed off 2026-06-11;
    docs/move_classification_from_gold_scope.md). Right-or-original.
    """
    
    # NEW: Filter out low-confidence categories before any other processing
    LOW_CONFIDENCE_GAPS = {"piece_activity", "calculation_depth", "pawn_structure"}
    if cognitive_gap in LOW_CONFIDENCE_GAPS:
        return None  # Don't surface these to coaching
    
    # ... rest of precedence_adjust logic ...
```

**Impact:** Removes 52 moves (19% of critical) from coaching surface.  
**Accuracy gain:** ~8-10% (less noise, more signal)  
**Risk:** LOW (these categories have <50% accuracy anyway)

---

### Part 2: piece_safety Detector Fix (Estimated +5-8% accuracy)

**Current Issue:** Flags moves where Stockfish "punished" a pawn move in eval, but the move itself didn't lose material.

**Example:** Nd4 (cp_loss=206) — knight move but detection claimed piece_safety.

**Root Cause:** The detector uses geometry (hanging piece checker) instead of engine PV analysis.

**Fix Location:** `backend/analysis_interpreter.py`, `_analyze_gap()` method, piece_safety branch

**Implementation:**
1. Use `_pv_material_loss()` helper (already exists at line 775) to confirm material loss
2. Only flag piece_safety if engine PV shows immediate material loss (ply ≤ 2)
3. Gate: `cp_loss >= 100` AND `pv_material_loss == 'immediate'`

```python
# In _analyze_gap(), piece_safety detector
if GAP_PIECE_SAFETY:
    pv_loss = _pv_material_loss(move)  # 'immediate', 'deeper', or None
    if pv_loss == "immediate":
        return {"primary_gap": GAP_PIECE_SAFETY, "confidence": 0.95, "evidence": "engine-pv-material-loss"}
    else:
        # Not a real piece loss — don't flag
        continue_to_next_detector()
```

**Impact:** Reduces false piece_safety fires from 98 → ~70 (estimated)  
**Accuracy gain:** ~5-8%  
**Risk:** MEDIUM (might miss some genuine hangs if PV is truncated)

---

### Part 3: king_safety → endgame_technique Reclassification (Estimated +3-5% accuracy)

**Current Issue:** Queens-off endgame king moves flagged as king_safety, when they should be endgame_technique.

**Example:** King move in endgame with no queens and <8 total pieces → mislabeled as "king safety" instead of "endgame technique"

**Fix Location:** `backend/analysis_interpreter.py`, line ~865 in `_precedence_adjust()` (already has partial logic)

**Implementation:**
Enhance the existing gate (lines 865-876) to be more aggressive:

```python
# Rule B: king_safety on a queens-off endgame king move -> endgame_technique.
# (Already exists at line 866, but gate might be too narrow.)
if cognitive_gap == "king_safety" and uci and len(uci) >= 4:
    try:
        queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
        
        # MORE AGGRESSIVE: any king move in queens-off position is endgame_technique
        # regardless of piece count. A king's job in endgame is positioning.
        if queens == 0:
            pc = board.piece_at(chess.parse_square(uci[:2]))
            if pc and pc.piece_type == chess.KING:
                return "endgame_technique"  # Reclassify
    except Exception:
        pass
```

**Impact:** Reclassifies ~15-20 of the 59 king_safety moves  
**Accuracy gain:** +3-5%  
**Risk:** LOW (endgame_technique is the correct category for queens-off king moves)

---

## Testing & Verification

**After implementing all 3 parts:**

1. **Re-run audit script:** `python3 backend/scripts/phase1_gap_audit.py`
   - Expected: piece_activity/calculation_depth/pawn_structure → 0
   - Expected: piece_safety → 70-80 (was 98)
   - Expected: king_safety → 40-45 (was 59)
   - Expected: endgame_technique → 15-20 (was 2)

2. **Manual spot-check:** 20 random critical moves
   - Sample and hand-verify gaps against Stockfish
   - Target: ≥14/20 (70%) labeled correctly

3. **Coaching surface test:** Play 3 games with Coach
   - Verify coaching messages only reference "good" gaps (not piece_activity, etc.)
   - Verify no "unknown" gaps surface

---

## Rollout Plan

1. **Code changes** (1-2 hours)
   - Part 1: Filter low-confidence (5 min)
   - Part 2: piece_safety gate (30 min)
   - Part 3: endgame_technique reclassification (15 min)

2. **Verification** (1 hour)
   - Re-run audit script
   - Manual spot-check
   - Play test games

3. **Production deploy** (10 min)
   - Docker rebuild
   - No backfill needed (applies to new analyses immediately)

4. **Phase 1 complete:** accuracy ≥70% confirmed

---

## Success Criteria Met

- ✅ Phase 1 audit completed
- ⏳ Cognitive_gap accuracy ≥70% (in progress)
- ⏳ Low-confidence categories excluded from coaching
- ⏳ piece_safety filtered to real material loss
- ⏳ king_safety complete + endgame_technique backfilled

---

**Next:** Coaching Engine v2 Phase 2 — Wire player_identity into Play with Coach (Session Goal, Pre-move teaching, Focus Areas)
