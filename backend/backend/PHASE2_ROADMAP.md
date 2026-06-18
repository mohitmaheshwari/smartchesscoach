# PHASE 2: Detector Improvements — Pattern #1 to #5

## Overview

Pattern #2 (ASSESSMENT_CONFLICTS gate) is deployed. Next: patterns #1-5 require detector design + testing.

---

## Pattern #1: WANTS_WHY_EXPLANATION (8 items) — HIGH IMPACT

**What:** Coach says "move is bad" but doesn't explain WHY

**Root Cause:** Some moves have NO failure-mode predicate firing in caption_facts.py

**Solution:** Add 3 new failure-mode detectors

### Detectors to Add

#### 1. `detect_allows_undefended_tactic()`
- **When:** Opponent can play a forcing tactic (like Ne5) that attacks an undefended piece
- **Detection:** Engine's best move is a tactic that wins a hanging piece
- **Fact to set:** `allows_undefended_tactic = True`
- **Why-clause template:** "Your move allows {opp_move}, attacking your {piece} on {square}"
- **Example:** fb_957fb320d332 (a3 allows Qxd4 capturing free pawn)

#### 2. `detect_no_follow_up()`
- **When:** Move doesn't accomplish strategic goal; better move does
- **Detection:** Played move and best move are both "development" or "quiet", but best controls key squares
- **Fact to set:** `no_follow_up = True` + `follow_up_idea = str`
- **Why-clause template:** "{played_san} doesn't accomplish much. {best_san} is better because {idea}"
- **Example:** fb_3c15abde86a2 (a3 has no purpose; e5 attacks/controls)

#### 3. `detect_structure_weakening()`
- **When:** Pawn move weakens king safety or central structure
- **Detection:** Played move is pawn push that removes defender OR opens line to king
- **Fact to set:** `structure_weakening = True` + `weakened_element = str`
- **Why-clause template:** "Your {pawn_move} weakens your {structure}, allowing {opp_threat}"
- **Example:** h6 weakens kingside, allowing Ng5 attack

---

## Pattern #3: NARRATIVE_WRONG (5 items)

**What:** Caption mentions pieces/squares that aren't on the board

**Solution:** Add board-state verification gate before serving narrative

### Implementation
1. Add `verify_narrative_against_fen(narrative: str, fen: str) -> bool`
2. Parse narrative for piece mentions ("your bishop", "the knight on e5", etc.)
3. Check each against FEN — fail if piece not found
4. Gate: suppress caption if verification fails

**Files:** `caption_pipeline.py` (add verification before render)

---

## Pattern #4: WANTS_OPENING_THEORY (4 items)

**What:** Caption misses opening context/variation

**Solution:** Wire opening_curriculum into caption pipeline

### Implementation
1. Check if move is in opening phase (full_move_number < 12)
2. Look up opening_name + move in opening_curriculum.json
3. If theory context exists, prepend to caption
4. Example: "Bc5 develops the bishop (Giucco Piano — control center)"

**Files:** `caption_pipeline.py` (add opening context injection)

---

## Pattern #5: WANTS_ALTERNATIVE_SUGGESTION (4 items)

**What:** Caption says "X is bad" without explaining "why Y is better"

**Solution:** Add move-comparison clause to why_clauses

### Implementation
1. When a caption fires with best_move available
2. Add comparison: "X is fine, but Y is better because {reason}"
3. Reason comes from engine's evaluation or tactic (e.g., "attacks hanging pawn")

**Files:** 
- `R12_blunder.json` (add why-clause variant)
- `caption_pipeline.py` (populate comparison fact)

---

## CLASS_A_SILENT: Assessment Gates (19 items) — PHASE 3

**What:** Coach silent when should speak OR over-speaking

**Solution:** Refine 19 individual assessment gates

### Implementation
Per item: check cp_loss vs user rating band
- If cp_loss >= threshold: lower gates to enable caption
- If cp_loss < threshold: add gate to silence

---

## Timeline

| Phase | Pattern | Items | Effort | Status |
|-------|---------|-------|--------|--------|
| **1** | #2 ASSESSMENT_CONFLICTS | 6 | 30min | ✅ DEPLOYED |
| **2a** | #1 WANTS_WHY_EXPLANATION | 8 | 2h | ⏳ Next |
| **2b** | #3 NARRATIVE_WRONG | 5 | 1h | ⏳ Next |
| **2c** | #4 WANTS_OPENING_THEORY | 4 | 30min | ⏳ Next |
| **2d** | #5 WANTS_ALTERNATIVE | 4 | 1h | ⏳ Next |
| **3** | CLASS_A_SILENT gates | 19 | 3h | 🔮 Future |

**Total Phase 2 effort:** ~5 hours (can parallelize some work)

---

## Testing Protocol (per pattern)

1. **Design:** Write detector logic
2. **Test:** Run on 8/5/4/4 feedback positions
3. **Measure:** Count TP (captions improved) vs FP (new false positives)
4. **Ship:** Deploy if TP rate ≥ 80% and FP rate ≤ 5%
5. **Verify:** Spot-check 3-5 positions on server post-deployment

---

## Success Criteria (Phase 2)

- [ ] Pattern #1: 6-8/8 captions improved (80%+)
- [ ] Pattern #3: 4-5/5 false mentions removed
- [ ] Pattern #4: 3-4/4 opening context injected
- [ ] Pattern #5: 3-4/4 comparison clauses added
- [ ] Zero false positives across all patterns
- [ ] User feedback rate on improved captions ≥ 80% positive

---

## Start Pattern #1 When

1. Pattern #2 deployed + verified on server (5 min)
2. Test results show 6/6 assessment conflicts suppressed
3. No regression in other captions (spot-check 10 games)

Then begin Pattern #1 detector implementation.

---

## Files to Modify (Phase 2)

1. `services/caption_facts.py` — add detect_* functions (patterns #1, #3-5)
2. `services/caption_pipeline.py` — add gates (patterns #3-5), verification (pattern #3)
3. `data/captions/R12_blunder.json` — add why-clause variants (patterns #1, #5)
4. `data/opening_curriculum.json` — ensure structure for pattern #4

---

## Git Commits

Each pattern = 1 commit:

```
feat: add failure-mode detectors for WANTS_WHY_EXPLANATION (pattern #1)
feat: add narrative-verification gate (pattern #3)
feat: wire opening-curriculum context (pattern #4)
feat: add move-comparison clauses (pattern #5)
```

---

## Next Immediate Action

1. ✅ Wait for Pattern #2 commit to complete
2. ✅ Verify Pattern #2 deployed on server
3. ⏳ **Start Pattern #1: Design detectors** (2h work)
   - Implement `detect_allows_undefended_tactic()`
   - Implement `detect_no_follow_up()`
   - Implement `detect_structure_weakening()`
   - Add corresponding why-clauses to R12_blunder.json

Estimated **completion of all Phase 2 patterns: 2-3 days** (including testing + deployment)
