# Principle-Based Caption Integration Guide

**Date:** July 9, 2026  
**Status:** Ready for integration  
**Integration Point:** `game_decryption_v5_service.py`

---

## Overview

This guide explains how to integrate the principle-based caption system into the existing caption pipeline so captions automatically enhance from eval-driven to principle-driven for endgame mistakes.

**Architecture:**
```
User move (blunder)
    ↓
Default caption generated (eval-driven: "X is mistake, Y is better")
    ↓
[PRINCIPLE ENHANCEMENT LAYER] (NEW)
    ↓
Check: Is this an endgame blunder (cp_loss > 150)?
    ↓
If YES: Try to generate principle-based caption using Claude
    ↓
Quality gate: Does it have 2+ principles and quality ≥ 0.75?
    ↓
If PASS: Replace default caption with principle version
If FAIL: Keep default caption
    ↓
Final caption delivered to UI
```

---

## Components

### 1. Principle Caption Bridge (`principle_caption_bridge.py`)

Provides two main functions:

#### `enhance_caption_with_principles()`
```python
async def enhance_caption_with_principles(
    caption_payload: Dict,
    fen_before: str,
    move_san: str,
    eval_before: int,
    eval_after: int,
    best_move_san: Optional[str],
    phase: str,
    cp_loss: float,
) -> Dict:
    """
    Enhance existing caption with principle-based explanation.
    
    Returns: caption_payload with enhanced "caption" field (if applicable)
    """
```

**Gates:**
1. Only processes endgame mistakes (phase == "endgame", cp_loss > 150)
2. Skips if existing caption already mentions principles
3. Only uses principle caption if quality_score ≥ 0.75 and ≥2 principles
4. Falls back to default if principle generation fails

#### `should_enhance_caption()`
```python
async def should_enhance_caption(
    phase: str,
    severity: str,
    cp_loss: float,
) -> bool:
    """
    Quick gate: is this worth enhancing?
    
    Returns True if endgame mistake with cp_loss > 150
    """
```

---

## Integration Steps

### Step 1: Import in `game_decryption_v5_service.py`

Add at the top with other imports (around line 115):

```python
from services.principle_caption_bridge import (
    enhance_caption_with_principles,
    should_enhance_caption,
)
```

### Step 2: Add Principle Enhancement Gate

In the `generate_game_decryption_v5()` function, after caption_payload is assembled but BEFORE it's added to move_output (around line 4090):

```python
# ── PRINCIPLE-BASED CAPTION ENHANCEMENT (NEW) ────
# For endgame blunders, enhance caption with principle-based explanation
# if it's higher quality than the default eval-driven caption.
if await should_enhance_caption(phase, severity, cp_loss):
    try:
        caption_payload = await enhance_caption_with_principles(
            caption_payload=caption_payload,
            fen_before=fen_before,
            move_san=move_san,
            eval_before=eval_data.get("eval_before"),
            eval_after=eval_data.get("eval_after"),
            best_move_san=best_move,
            phase=phase,
            cp_loss=cp_loss,
        )
    except Exception as _principle_exc:
        logger.debug(f"[principle-caption] enhancement failed: {_principle_exc}")
        # Fall back to default caption — move_output assembly continues unchanged
```

### Step 3: Verify Integration

The move_output assembly at line 4094 will now use the enhanced caption:

```python
"caption": caption_payload["caption"],  # ← Now includes principle-based if applicable
```

---

## Data Flow Example

### Before Enhancement

**Default caption (eval-driven):**
```
"Rf3+ is a serious mistake. Re1 was better."
```

**Principle-based caption (after enhancement):**
```
"Rf3+ removes your rook — the only defender against Black's a5 pawn. 
By the rule of the square, your king can't catch it alone. Play Re1 to keep defending."
```

### What Gets Stored

In move_output:
```python
{
    "move_san": "Rf3+",
    "phase": "endgame",
    "cp_loss": 450,
    "severity": "blunder",
    "caption": "Rf3+ removes your rook — the only defender...",  # Enhanced
    "rule_name": "R12_blunder→PRINCIPLE_ENHANCED",  # Tagged with enhancement
    "principles_applied": ["rule_of_square", "critical_piece"],  # Principles used
}
```

---

## Quality Gates (In Order)

1. **Phase Gate:** `phase == "endgame"` ← Principle-based only for endgames
2. **Severity Gate:** `severity in ("mistake", "blunder", ...)` ← Only for real errors
3. **Magnitude Gate:** `cp_loss > 150` ← Only for significant losses
4. **Principles Gate:** `len(principles) >= 2` ← Must explain multiple principles
5. **Quality Gate:** `quality_score >= 0.75` ← Must pass quality check
6. **Fallback Gate:** If any gate fails, revert to default caption

---

## Deployment Strategy

### Phase 1: Soft Launch (This Commit)
- Code merged to `working-code`
- Principle enhancement disabled by default (env var)
- Run on prod data but don't show to users yet
- Collect baseline: "% of endgame blunders with 2+ principles"

### Phase 2: A/B Test (Week 2)
- Enable for 10% of users
- Measure: Did captions improve? ("Does coach explain WHY?" → 4.5+/5 rating)
- Measure: Does principle-based coaching reduce future mistakes?

### Phase 3: Full Rollout (Week 3)
- Enable for all users
- Monitor error logs for principle caption failures
- Track: % of captions using principle enhancement

### Phase 4: Phase 2 Transition (Week 4)
- Start building deterministic detectors
- Begin replacing Claude with detector fleet
- Deprecate principle_based_caption_generator.py as detectors launch

---

## Configuration

### Environment Variables

Add to `backend/.env`:

```bash
# Enable principle-based caption enhancement (default: true)
PRINCIPLE_CAPTION_ENABLED=true

# Principle caption quality threshold (default: 0.75)
PRINCIPLE_CAPTION_QUALITY_THRESHOLD=0.75

# Minimum principles required (default: 2)
PRINCIPLE_CAPTION_MIN_PRINCIPLES=2

# Only apply to cp_loss above this (default: 150)
PRINCIPLE_CAPTION_MIN_CP_LOSS=150
```

### Feature Flag

In the code, wrap enhancement in a feature flag:

```python
PRINCIPLE_CAPTION_ENABLED = os.environ.get("PRINCIPLE_CAPTION_ENABLED", "true") not in ("0", "false", "False", "")

if PRINCIPLE_CAPTION_ENABLED and await should_enhance_caption(...):
    # Principle caption logic
```

---

## Testing

### Unit Test: Principle Generation

```bash
python backend/scripts/test_principle_caption_rf3_plus.py
```

Expected: Rf3+ position generates caption with 3+ principles.

### Integration Test: End-to-End

```bash
# 1. Analyze a game with endgame blunders
python backend/analysis_worker.py --game-id {game_id}

# 2. Check if moves were enhanced
curl http://localhost:8001/api/game/{game_id} | jq '.moves[] | select(.phase == "endgame" and .severity == "blunder")'

# 3. Verify principles_applied field is present
```

### Regression Test: Quality

Run audit on 50 games:
```bash
python backend/scripts/audit_principle_captions.py --sample 50
```

Verify:
- 0 hallucinated pieces/moves
- 0 confabulated principles
- ≥ 80% of enhanced captions have 2+ principles
- ≥ 70% rated "helpful" by human audit

---

## Monitoring & Alerts

### Metrics to Track

| Metric | Target | Alert |
|--------|--------|-------|
| % endgame blunders enhanced | 40-60% | < 20% or > 80% |
| Avg principles per caption | 2.5+ | < 2.0 |
| Quality score avg | 0.80+ | < 0.75 |
| Claude API errors | < 1% | > 5% |
| Fallback rate | < 20% | > 30% |

### Log Lines to Watch

```bash
# Success
[principle-caption] Enhanced Rf3+: quality=0.85, principles=[rule_of_square, critical_piece]

# Skipped (OK)
[principle-caption] Skipped Nf3: quality=0.60 (need ≥0.75)

# Error (alert if frequent)
[principle-caption] Generation failed for Rf3+: timeout
```

---

## Known Limitations (Phase 1)

1. **Claude Dependency:** Requires ANTHROPIC_API_KEY to be set
2. **Latency:** Claude calls add ~2s per caption (async, doesn't block)
3. **Cost:** ~0.001 USD per caption generated
4. **Coverage:** Only K+R, R+P, K+P endgame types supported
5. **Principles:** Limited to 9 principles (extensible in Phase 2)

---

## Phase 2: Deterministic Detectors

These will replace Claude:

| Detector | Replaces | Speed |
|----------|----------|-------|
| `detect_rule_of_square()` | Claude geometry | <10ms |
| `detect_critical_piece()` | Claude analysis | <10ms |
| `detect_promotion_threat()` | Claude threats | <10ms |
| `detect_opposition()` | Claude opposition | <10ms |
| `detect_lucena_technique()` | Claude rook+pawn | <10ms |
| `detect_philidor_technique()` | Claude defense | <10ms |

Once detectors exist, principle_based_caption_bridge switches from Claude to detectors with no UI change.

---

## Rollback Plan

If principle captions cause issues:

```bash
# Disable enhancement
export PRINCIPLE_CAPTION_ENABLED=false

# Restart backend
supervisorctl restart backend

# Re-generate affected games
python backend/scripts/regen_decryption_v5.py --after 2026-07-09
```

---

## Success Metrics (12-week Study)

**Hypothesis:** "Principle-based captions improve coaching quality from 5.5/10 to 8/10"

**Measurement:**
1. **Coaching quality (user feedback):** "Does coach explain WHY?" → baseline 3.2/5 → target 4.5/5
2. **Learning transfer:** Users drill fewer positions to master a pattern (study metric)
3. **Mistake reduction:** Principle-specific mistake rate drops by 20%+ after coaching
4. **Engagement:** % of users drilling principle-based training goes 40%→60%+

**Data Collected:**
- Pre/post caption ratings on 100 game reviews
- Puzzle attempt data (before/after training)
- Mistake frequency per pattern (12-week trend)
- Time-to-mastery per pattern

---

## Next Steps

1. ✅ Principle system built and tested
2. 🔄 Integrate into game_decryption_v5_service.py (this doc)
3. 🔄 Deploy to staging, run integration tests
4. 🔄 Enable for 10% users (A/B test)
5. 🔄 Measure user feedback + behavior
6. 🔄 Full rollout if > 80% positive feedback
7. 🔄 Start Phase 2 detector development

---

## Questions & Debugging

### Q: Why only endgame mistakes?
A: Endgames have well-defined principles (rule of square, opposition). Middlegame is too complex for Phase 1. Phase 2 adds middlegame detectors.

### Q: What if Claude API fails?
A: Falls back to default caption automatically. No user-visible impact.

### Q: How do I measure if it's working?
A: Check logs for `[principle-caption] Enhanced`. Count lines per day. Target: 10-20% of blunders enhanced.

### Q: Can users opt out?
A: In Phase 2, yes. Phase 1 enhancement is automatic (no UI toggle needed yet).

---

**Integration ready. Execute Step 1 in game_decryption_v5_service.py to activate.**
