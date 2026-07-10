# Coaching Loop MVP - Scope Document

**Goal:** Build a working end-to-end coaching loop where users receive recommendations, accept training, complete it, and see improvement.

---

## Phase 1: Issue Aggregation ✅ COMPLETE
**Problem:** Recommendation engine only analyzes last 10 games, missing 90% of user's patterns.

**Solution:**
- ✅ Aggregate cognitive gaps from ALL 585 user games (not just last 10)
- ✅ Count frequency with recency weighting (games 0-9 weight=1.0, older weighted 0.5+decay)
- ✅ Identify top 3-5 issues per user
- ✅ Fixed prescription data with proper baseline/current metrics

**Output:** Recommendations now based on complete game history with recency bias

**Verified:** User_8b599930d7ef has 293 mistakes analyzed, prescriptions created with accurate metrics

---

## Phase 2: Training Content Wiring

### Part A: PWC Integration ✅ COMPLETE
- ✅ PWC auto-detects active training plans at session start
- ✅ Sets coaching_focus to training plan's cognitive_gap
- ✅ Coach feedback emphasizes the trained gap
- ✅ Deployed and verified live

**Verified:** Tactical Calculation Trainer → coaching_focus = calculation_depth

### Part B: Game Review Integration ✅ COMPLETE
- ✅ Game review endpoint enriches moves with related_training_plans
- ✅ Frontend displays blue "Training: [Plan Name]" badges
- ✅ Badges link to `/training/prescribed?plan={plan_id}`
- ✅ Deployed and verified live

**Verified:** Game review shows training badges on related mistakes

### Part C: Training Modules Content Wiring ⏳ NEXT
**Problem:** Accepting prescription navigates to `/training/prescribed` but training content not yet displayed.

**Solution:**
- Fetch training modules for active prescription
- Display module list with progress tracking
- Load puzzles from community_puzzles for each module
- Track puzzle solve progress per module

**Output:** User sees actual training content when accepts prescription

**Testing:** Accept prescription → see training modules and puzzles

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
