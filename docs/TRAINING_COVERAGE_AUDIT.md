# Training Coverage Audit — What We Have vs. What's Missing
**Date:** July 9, 2026  
**Question:** With 10,282 analyzed games, do we have enough training for all Engine 2 skills + traps?  
**Answer:** YES for cognitive gaps, PARTIAL for Engine 2, NO for traps (not wired).

---

## 📊 Current Training Coverage

### ✅ FULLY WIRED (Evidence → Puzzles → Drills)

**Cognitive Gap Patterns (Engine 1):**
```
piece_safety          101 puzzles    ✅ LIVE
endgame_technique     596 puzzles    ✅ LIVE
missed_tactic         97 puzzles     ✅ LIVE
tactical_oversight    58 puzzles     ✅ LIVE
calculation_depth     70 puzzles     ✅ LIVE
piece_activity        26 puzzles     ✅ LIVE
opening_knowledge     20 puzzles     ✅ LIVE
king_safety           37 puzzles     ✅ LIVE
pawn_structure        4 puzzles      ✅ LIVE
────────────────────────────────────
TOTAL: ~1,200+ puzzles from real games
```

**How it works:**
1. User plays game → analyzed
2. Move marked with `cognitive_gap: "piece_safety"`
3. Position auto-extracted to community_puzzles
4. User drills on `/training/pattern/piece_safety`
5. Graded by exact move match

---

### 🟡 PARTIALLY WIRED (Detectors exist, but not collecting evidence)

**Engine 2 Endgames:**

| Skill | Detector | Evidence | Puzzles | Status |
|-------|----------|----------|---------|--------|
| endgame_rule_of_square | ✅ YES | 🟡 Some | 594 | 🟡 Partially |
| endgame_opposition | ✅ YES | 🟡 Some | 2 | 🟡 Partially |
| endgame_lucena | ✅ YES | ❌ NO | 0 | ❌ Not collecting |
| endgame_philidor | ✅ YES | ❌ NO | 0 | ❌ Not collecting |
| mate_kq_vs_k | ✅ YES | ❌ NO | 0 | ❌ Not collecting |
| mate_kr_vs_k | ✅ YES | ❌ NO | 0 | ❌ Not collecting |

**Engine 2 Concepts:**

| Skill | Detector | Evidence | Puzzles | Status |
|-------|----------|----------|---------|--------|
| defend_scholars_mate | ✅ YES | ❌ NO | 0 | ❌ Not collecting |
| defend_fried_liver | ✅ YES | ❌ NO | 0 | ❌ Not collecting |
| concept_iqp | ❌ NO | ❌ NO | 0 | ❌ Not wired |
| concept_prophylaxis | ❌ NO | ❌ NO | 0 | ❌ Not wired |
| concept_minority_attack | ❌ NO | ❌ NO | 0 | ❌ Not wired |

**Problem:** Detectors exist but aren't firing during game analysis → no evidence collected → no puzzles extracted.

---

### ❌ NOT WIRED (No detectors, no evidence, no puzzles)

**Openings (39 total):**
```
opening_london_white         No detector  No evidence  0 puzzles
opening_caro_kann_black      No detector  No evidence  0 puzzles
opening_italian_white        No detector  No evidence  0 puzzles
opening_ruy_lopez            No detector  No evidence  0 puzzles
... (35 more)
```

**Why:** Opening evaluation happens via `opening_played` field in game analysis, not detector-based evidence.

**Trap Sets (3 total):**
```
trap_set_italian             No detector  No evidence  0 puzzles
trap_set_caro_kann           No detector  No evidence  0 puzzles
trap_set_london              No detector  No evidence  0 puzzles
```

**What exists:**
- ✅ 28 traps defined in trap_library.py
- ✅ Trap detection code (trap_recognition.py, trap_detection_service.py)
- ✅ Trap mastery tracking exists
- ❌ BUT: Not integrated into postgame_analysis to collect evidence

**Motifs (if tracked):**
```
fork                         No detector  No evidence  0 puzzles
pin                          No detector  No evidence  0 puzzles
skewer                       No detector  No evidence  0 puzzles
```

---

## 🔍 Why the Gap?

### Architecture Issue: Two Separate Systems

**Engine 1 (Cognitive Gaps):**
```
Game analyzed
  ↓
Each move marked with cognitive_gap (piece_safety, missed_tactic, etc.)
  ↓
extract_and_store_puzzles() auto-extracts positions
  ↓
community_puzzles collection
  ↓
User drills on /training/pattern/piece_safety
  ✅ FULLY AUTOMATED
```

**Engine 2 (Skills/Traps/Openings):**
```
Game analyzed
  ↓
Detectors RUN (endgame_opposition detector fires on K+P positions)
  ↓
Evidence stored in coach_memory.learning.skills[].evidence
  ✓ HAPPENS (partially)
  ↓
extract_skill_puzzles_for_user() needs to be called manually
  ⚠️ MANUAL TRIGGER (not automatic)
  ↓
community_puzzles collection (skill_id=endgame_opposition)
  ↓
User drills on /training/skill/endgame_opposition
  🟡 PARTIALLY AUTOMATED
```

**For Traps:**
```
Game analyzed
  ↓
Trap detection code EXISTS in caption_pipeline, trap_recognition.py
  ✓ CODE EXISTS
  ↓
BUT: Not wired into postgame_analysis.py to record evidence
  ❌ NOT COLLECTED
  ↓
No evidence in coach_memory
  ❌ DEAD END
  ↓
No drill puzzles
  ❌ NO TRAINING
```

---

## 📋 What We Have vs. What's Missing

```
HAVE GAME DATA:        ✅ YES (10,282 analyzed games)
HAVE DETECTORS:        ✅ YES (8 Engine 2 + trap code exists)
HAVE EXTRACTION:       ✅ YES (for cognitive gaps + some skills)
HAVE EVIDENCE:         🟡 PARTIAL (only rule_of_square & opposition)
HAVE PUZZLES:          🟡 ~1,600 (mostly cognitive gaps)
HAVE COACHING:         ✅ YES (traps used in prescriptions/captions)

CAN COACH DETECT TRAPS: 🟡 YES for captions/prescriptions, NO for drilling
```

---

## 🎯 To Enable FULL Coverage

### Tier 1: Wire up existing detectors (1-2 hours work)

**Endgames:**
- [ ] Ensure `record_concept_applications_from_game()` is called for ALL detectors
- [ ] Currently only firing for rule_of_square & opposition
- [ ] Need to fire for: lucena, philidor, mate_kq_vs_k, mate_kr_vs_k
- [ ] Fix: Add to PostGameAnalysis pipeline

**Result:** 5 more endgame drills available

### Tier 2: Wire trap detection (2-3 hours work)

**Traps:**
- [ ] Extract trap detection from caption_pipeline
- [ ] Create trap detector analogous to endgame detectors
- [ ] Call during postgame_analysis  
- [ ] Record evidence in coach_memory.learning.traps[]
- [ ] Extract puzzles from trap evidence

**Result:** 28 traps + drills available

### Tier 3: Wire opening detection (3-4 hours work)

**Openings:**
- [ ] Create opening detectors (check if player stayed in book)
- [ ] Track opening deviation/mistake
- [ ] Call during postgame_analysis
- [ ] Record in coach_memory.learning.openings[]
- [ ] Extract puzzles from wrong-opening evidence

**Result:** 39 opening drills available

### Tier 4: Wire concepts (2-3 hours work)

**Concepts:**
- [ ] Create concept detectors (IQP play, prophylaxis, minority attack)
- [ ] These are harder (more positional, less algorithmic)
- [ ] Could use LLM to evaluate concept application
- [ ] Record in coach_memory

**Result:** 5+ concept drills available

---

## 💾 Expected Total Coverage After Wiring

| Category | Current | After Tier 1 | After All |
|----------|---------|--------------|-----------|
| Cognitive gaps | 1,014 | 1,014 | 1,014 |
| Endgames | 596 | +200 → 800 | 800 |
| Traps | 0 | 0 | +200 → 200 |
| Openings | 0 | 0 | +300 → 300 |
| Concepts | 0 | 0 | +100 → 100 |
| **TOTAL** | **1,614** | **1,814** | **2,414+** |

---

## 🎓 Coach Trap Detection Capability

### Current State: PARTIAL

**The coach CAN detect traps:**
- ✅ During game review (caption_pipeline detects trap was set)
- ✅ In prescriptions ("You lost in opening, learn the Fried Liver trap")
- ✅ In postgame analysis comments

**The coach CANNOT collect trap evidence:**
- ❌ Not recording "user fell for Italian trap" in coach_memory
- ❌ Not extracting trap positions as drill puzzles
- ❌ Not recommending "drill Italian traps" based on falls

### After Tier 2 (Wiring Traps):

**The coach WILL:**
- ✅ Detect when user plays the trap line
- ✅ Identify if user fell for it or escaped
- ✅ Record evidence in coach_memory
- ✅ Recommend "Drill Italian traps — you fell for it 3x this month"
- ✅ Provide trap positions as drill puzzles
- ✅ Track whether training reduced trap falls

---

## 🚀 Recommendation

### SHORT TERM (Today)
✅ Cognitive gap drills are LIVE and working (1,000+ puzzles)
✅ Endgame opposition drill is LIVE (just wired)
✅ Use these immediately for training

### MEDIUM TERM (This week)
🟡 Wire existing endgame detectors (Tier 1 → +200 puzzles)
🟡 Wire trap detection (Tier 2 → +200 puzzles)
= **2,000+ total drills available**

### LONG TERM (Next 2 weeks)
🟡 Wire opening detection (Tier 3 → +300 puzzles)
🟡 Wire concepts (Tier 4 → +100 puzzles)
= **2,400+ total drills with full coach trap/opening/concept awareness**

---

## 📝 Bottom Line

**Do we have enough game data?** ✅ YES (10,282 games)

**Are detectors ready?** 🟡 PARTIALLY (endgames yes, traps/openings need wiring)

**Can coach detect traps?** 🟡 YES for display, NO for evidence/drilling

**How much work to full coverage?** ~8-10 hours = Wire 4 detector layers into postgame_analysis

**Impact:** From 1,600 → 2,400+ drills, with coach fully aware of what user falls for.

