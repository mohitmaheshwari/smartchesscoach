# Drill System Status — Comprehensive Coverage
**Date:** July 9, 2026  
**Status:** 🟢 LIVE  
**Access:** Users visit `/training/skill/{skill_id}` to drill

---

## 🎯 What Works Now

### ✅ COGNITIVE GAP PATTERNS (Engine 1 — ~1,009 puzzles)
Users can drill on weakness patterns extracted from real games:

| Pattern | Puzzles | Notes |
|---------|---------|-------|
| endgame_technique | 596 | Highest volume — endgame-specific mistakes |
| piece_safety | 101 | Hanging pieces, unprotected material |
| missed_tactic | 97 | Forks, pins, skewers not seen |
| tactical_oversight | 58 | Missing opponent's threats |
| calculation_depth | 70 | Shallow calculation errors |
| piece_activity | 26 | Passive pieces |
| opening_knowledge | 20 | Opening theory deviations |
| king_safety | 37 | King exposed to attack |
| pawn_structure | 4 | Weak pawns (small sample) |

**How it works:**
1. User plays games → Stockfish analyzes
2. Blunders identified with cognitive_gap label (piece_safety, missed_tactic, etc.)
3. Position auto-extracted to community_puzzles collection
4. User visits `/training/pattern/piece_safety` → sees personalized puzzles from real games
5. Solves puzzle → system grades move as SAN match

---

### ✅ ENGINE 2 SKILL PUZZLES (Learning Tree — 596+ puzzles)

#### **ENDGAMES** (Interactive lessons + drill)

| Skill | Status | Puzzles | Drill Available |
|-------|--------|---------|-----------------|
| endgame_rule_of_square | ✅ Complete | 594 | ✅ Yes |
| endgame_opposition | ✅ Complete | 2 | ✅ Yes |
| endgame_lucena | 🟡 In progress | — | 🔲 No* |
| endgame_philidor | 🟡 In progress | — | 🔲 No* |
| mate_kq_vs_k | 🟡 In progress | — | 🔲 No* |
| mate_kr_vs_k | 🟡 In progress | — | 🔲 No* |

*Note: Evidence being collected from user games; waiting for first coach_memory entries.

#### **CONCEPTS** (Defensive + strategic ideas)

| Skill | Status | Drill |
|-------|--------|-------|
| defend_scholars_mate | 🟡 Evidence collection active | 🔲 Waiting |
| defend_fried_liver | 🟡 Evidence collection active | 🔲 Waiting |
| concept_iqp | 🟡 Evidence collection active | 🔲 Waiting |
| concept_prophylaxis | 🟡 Evidence collection active | 🔲 Waiting |
| concept_minority_attack | 🟡 Evidence collection active | 🔲 Waiting |

#### **OPENINGS** (39 openings tracked)

| Skill | Status | Drill |
|-------|--------|-------|
| opening_london_white | 🟡 Evidence collection active | 🔲 Waiting |
| opening_caro_kann_black | 🟡 Evidence collection active | 🔲 Waiting |
| opening_italian_white | 🟡 Evidence collection active | 🔲 Waiting |
| (+ 36 more) | 🟡 All active | 🔲 All waiting |

#### **TRAP SETS** (3 sets currently)

| Skill | Status | Drill |
|-------|--------|-------|
| trap_set_italian | 🟡 Evidence collection active | 🔲 Waiting |
| trap_set_caro_kann | 🟡 Evidence collection active | 🔲 Waiting |
| trap_set_london | 🟡 Evidence collection active | 🔲 Waiting |

---

## 📊 Current Drill Coverage by Type

```
LIVE TODAY:
  ├─ Cognitive Gaps (9 types)      1,009 puzzles  ✅ Full extraction
  ├─ Endgames (rule_of_square)       594 puzzles  ✅ Full extraction
  └─ Endgames (opposition)             2 puzzles  ✅ Just wired
  
COLLECTING EVIDENCE (no puzzles yet):
  ├─ Concepts (5 types)
  ├─ Openings (39 types)
  ├─ Trap Sets (3 types)
  └─ Mate Patterns (2 types)
```

---

## 🔄 How the Extraction Works

### For Cognitive Gaps:
```
Game played → Stockfish analyzes
  ↓
Move evaluated: "cp_loss=180, cognitive_gap=piece_safety"
  ↓
puzzle_extraction_service extracts position
  ↓
Stored in community_puzzles with issue_type=piece_safety
  ↓
User can drill on /training/pattern/piece_safety
  ↓
Grade: exact SAN match required
```

### For Engine 2 Skills:
```
Game played → Coach session records skill application
  ↓
Detector runs: "Did user apply opposition correctly?"
  ↓
Outcome: "applied", "wrong", or "correct"
  ↓
Evidence stored in coach_memory.learning.skills[].evidence
  ↓
extract_skill_puzzles_for_user() converts "wrong" to puzzles
  ↓
Stored in community_puzzles with skill_id=endgame_opposition
  ↓
User can drill on /training/skill/endgame_opposition
  ↓
Grade: detector-specific (not just SAN match)
```

---

## ⚙️ What Needs to Happen for Full Coverage

### Phase 1: Wire up all Engine 2 Skill Detectors (NEEDED)
Currently only these detectors fire during game analysis:
- ✅ endgame_rule_of_square
- ✅ endgame_opposition

Need to wire (if detector exists):
- ⏳ endgame_lucena
- ⏳ endgame_philidor
- ⏳ mate_kq_vs_k
- �� endgame_technique (might need creation)
- ⏳ All concepts (might need creation)
- ⏳ All openings (might need creation)
- ⏳ All traps (might need creation)

Check: `backend/services/concept_detectors/registry.py` to see which are registered.

### Phase 2: Let Evidence Accumulate
- Detectors must run on real user games
- Evidence builds up in coach_memory
- extract_skill_puzzles_for_user() triggers when user visits `/training/skill/{skill_id}`
- First puzzle appears when first "wrong" evidence entry exists

### Phase 3: Monitor & Expand
- Track which skills accumulate evidence fastest
- Prioritize detector fixes for high-traffic skills
- Add practice_positions to endgames.json for additional drills

---

## 🚀 User Experience

### TODAY:
User can do this RIGHT NOW:
```
1. Play games → Chess Coach analyzes
2. Make a piece_safety mistake
3. Visit /training/pattern/piece_safety
4. See 100+ puzzles from real games where you hung material
5. Drill & master the pattern
6. Fewer hangs in future games
```

User visiting `/training/skill/endgame_opposition`:
```
1. Click Skill → Opposition
2. See 2 puzzles where user applied opposition wrong
3. Drill → system grades using opposition-specific detector
4. Correct move = any king move that actually uses opposition (not just Kc5 rote)
```

### COMING SOON (when detectors wire up):
User will see drills for:
- Lucena positions (rook+pawn endgame winning technique)
- Philidor positions (rook+pawn endgame defending technique)
- Concepts (prophylaxis, IQP play, etc.)
- Openings they play (London System, Italian, etc.)
- Traps they fall for

---

## 📈 Extraction Script

Run comprehensive extraction across all users:
```bash
cd /app/backend
python3 scripts/extract_all_skill_puzzles.py
```

This will:
1. Check every user's coach_memory
2. Find evidence for every skill
3. Extract "wrong" evidence entries as drillable puzzles
4. Report: how many puzzles created per skill
5. Show drill readiness by type

---

## 🎯 Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Cognitive gap puzzles | 1000+ | 1009 | ✅ Hit |
| Endgame drill puzzles | 500+ | 596 | ✅ Hit |
| Skills with drills | 20+ | 2 full + more collecting | 🟡 In progress |
| Users accessing drills | 80%+ | TBD (just wired) | 🔄 Track |
| Average drill solve rate | 65%+ | TBD | 🔄 Track |

---

## 💾 Database Collections

Drill puzzles stored in:
- `community_puzzles` — all drillable positions
  - Indexed by `issue_type` (cognitive gaps)
  - Indexed by `skill_id` (Engine 2 skills)
  - Field `grading_strategy`: "san_match" (gaps) vs "detector" (skills)

- `puzzle_attempts` — tracks user solutions
  - user_id + puzzle_id + correct (bool)
  - Used to exclude already-solved from drills

---

## 📝 Next Steps

1. **TODAY:** Endgame opposition drill is live. Users can drill it.
2. **THIS WEEK:** Monitor engagement on opposition drill → refine UX
3. **NEXT WEEK:** Wire up remaining endgame detectors
4. **MONTH 2:** Wire up concept detectors
5. **MONTH 3:** Wire up opening/trap detectors
6. **FULL LAUNCH:** All 39 skills drilling from real games

---

*Drill system is not a feature — it's the core of the closed-loop learning loop. Every pattern a user struggles with becomes a reusable puzzle. Every drill solve reduces future mistakes.*

