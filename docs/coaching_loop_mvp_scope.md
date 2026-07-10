# Coaching Loop MVP - Scope Document

**Goal:** Build a working end-to-end coaching loop where users receive recommendations, accept training, complete it, and see improvement.

---

## Phase 1: Issue Aggregation (Backend Fix)
**Problem:** Recommendation engine only analyzes last 10 games, missing 90% of user's patterns.

**Solution:**
- Aggregate cognitive gaps from ALL user games (not last 10)
- Count frequency of each issue type
- Weight by recency (recent issues matter more)
- Identify top 3 issues per user

**Output:** Better recommendations based on complete history

**Testing:** Verify top issues match actual game patterns

---

## Phase 2: Training Content Wiring
**Problem:** Accepting prescription navigates to `/training/prescribed` but nothing happens.

**Solution:**
- Create training modules for each plan
- When prescription accepted → load first module
- Module should have:
  - Puzzles relevant to the issue
  - Educational content
  - Progress tracking

**Output:** Real training flow starts when user accepts

**Testing:** Accept prescription → see training content

---

## Phase 3: Improvement Tracking
**Problem:** No way to know if user improved after training.

**Solution:**
- Track baseline metric when prescription created
- Monitor user's new games during prescription
- Calculate improvement % 
- Auto-complete at 50% improvement

**Output:** Prescriptions complete automatically when user improves

**Testing:** Accept prescription → play games → verify auto-completion works

---

## Phase 4: Full Loop Testing
**Problem:** Need to verify entire flow works end-to-end.

**Solution:**
1. User sees recommendation
2. Clicks "Start Training"
3. Completes training modules
4. Plays games
5. System detects improvement
6. Prescription auto-completes
7. New recommendation appears

**Testing:** Real user flow from start to finish

---

## Success Criteria
- ✅ Recommendations based on complete game history (not last 10)
- ✅ Accepting prescription starts actual training
- ✅ Training content displays and tracks progress
- ✅ Improvement tracked from new games
- ✅ Auto-completion works at 50% improvement
- ✅ New recommendations appear after completion
- ✅ End-to-end flow tested and verified

---

## Not in Scope (V1)
- Parallel training plans
- Custom training difficulty scaling
- Streak tracking integration
- Mobile optimization

---

## Timeline Estimate
- Phase 1: 2-3 hours (aggregation logic)
- Phase 2: 3-4 hours (training wiring)
- Phase 3: 2-3 hours (improvement tracking)
- Phase 4: 1-2 hours (testing & fixes)

**Total: ~8-12 hours of solid work**
