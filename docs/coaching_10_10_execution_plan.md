# ChessGuru Coaching Platform: Path to 10/10

**Mission:** Transform the coaching platform from 5.5/10 to 10/10  
**Current Status:** 7.4/10 (as of 2026-07-09)  
**Target Date:** 2026-09-30 (12 weeks)

---

## Executive Summary

You're not at 7.4 by accident — you've fixed the critical pipeline (0→9.5) and wired in goal-aware personalization (Phase 1-3 PWC). The gap from 7.4→10 is well-understood and achievable:

- **2.6 points missing:** ~1 point from accuracy/polish, ~1.5 from architecture extension + behavior validation
- **Best path:** Weekly iteration (not big bang) with real-user feedback
- **Critical gate:** Behavior change validation (3-month wait, but it unlocks 10/10 credibility)

---

## Scorecard: Week 1 Completions ✅

| Priority | Component | Status | Impact | New Score |
|----------|-----------|--------|--------|-----------|
| 1 | piece_safety engine-grounding | ✅ Done | +0.3 accuracy | 7.7 |
| 2 | Session goal reflection UI | ✅ Done | +0.3 engagement | 8.0 |
| 3 | Puzzle backfill + extraction | ✅ Done | +0.2 training | 8.2 |
| 4 | Mastery gate definition | ✅ Done | +0.2 closure | 8.4 |

**Week 1 Result: 7.4 → 8.4 (est.)**  
**Effort:** ~8 hours of code, 1 hour review

---

## Remaining Work to 10/10

### **Week 2-3: Extend Architecture (8.4 → 8.9)**

Goal: Wire the time_management 3-phase system (Phase 1-3 PWC) to other focus areas.

#### Phase 2.1: piece_safety Architecture Extension
**What:** Replicate time_management flow for piece_safety
- Session goal: "Scan for hanging pieces"
- Reactive layer: Warn on piece_safety violations, affirm safe moves
- Proactive layer: Pre-move nag ("Scan before you move")

**Implementation:**
- Backend: Extend `_apply_coach_move()` to check piece_safety (already has detection)
- Frontend: Re-use phase_check message components (color: teal)
- Mission scoreboard: Count safe moves vs. critical moments

**Estimate:** 4-6 hours  
**Impact:** +0.15 (personalization breadth)

#### Phase 2.2: king_safety Architecture Extension
**What:** Same flow for king safety
- Session goal: "Protect your king"
- Reactive: Warn on king threats, affirm safe moves
- Proactive: Pre-move check ("King on X, check Y file")

**Implementation:** 3-4 hours (template reuse from piece_safety)  
**Impact:** +0.15 (personalization breadth)

#### Phase 2.3: missed_tactic Architecture Extension
**What:** Teach forcing move discovery
- Session goal: "Look for checks, captures, threats"
- Reactive: Celebrate when you find forcing moves
- Proactive: "Look for forcing moves on this position"

**Implementation:** 3-4 hours  
**Impact:** +0.15 (personalization breadth)

**Week 2-3 Result: 8.4 → 8.7** (3 focus areas × 0.15 each)

---

### **Week 4-5: Behavior Change Validation (Kickoff)**

Goal: **Prove that coaching actually works** (this is your 10/10 unlock)

#### Study Design
- **Sample:** 20 active users (recommend: bhutramohit, shobhit + 18 others)
- **Duration:** 12 weeks (data collection + analysis)
- **Measurement:** Does puzzle training on pattern X reduce blunders in that pattern?

**Hypothesis:** Users who solve 3+ puzzles on their weakness pattern reduce that mistake by 20-30% in future games (vs. control: 0-5% natural regression)

**Execution Plan:**
1. **Week 4:** Identify 20 test users with diverse patterns (sampling + consent)
2. **Week 5:** Baseline measurement: capture current mistake rate per user
3. **Weeks 6-15:** Run intervention (puzzle training visible on Training page)
4. **Week 16:** Analyze results

**Data Pipeline:**
- Track: puzzle solves per pattern, solved ✓ or ✗
- Measure: next-game mistake rate for that pattern
- Compare: pre-training vs. post-training (BEFORE/AFTER)

**Estimate:** 20 hours (design + analytics setup)  
**Impact:** +0.5 (credibility lock) **IF hypothesis confirmed**

**Risk:** If hypothesis FAILS (no improvement), we know coaching has a flaw and must diagnose it (deeper research needed)

---

### **Week 6-8: Mobile + Polish (8.7 → 9.2)**

#### Mobile Responsiveness Testing
- Test SessionReflectionCard on mobile (currently untested)
- Adjust sidebar for small screens
- Test touch interactions (mission scoreboard, message list)

**Estimate:** 4 hours  
**Impact:** +0.1 (coverage)

#### Puzzle Difficulty Scaling
- Add easy/medium/hard filter to Training page
- Show player's current level + recommended difficulty
- Auto-recommend progressively harder puzzles as player solves

**Estimate:** 6 hours  
**Impact:** +0.2 (training effectiveness)

#### Adaptive Opening Teaching
- Auto-detect if player is weak in an opening
- Suggest opening lessons before Play with Coach starts
- Track opening mastery separately

**Estimate:** 4 hours  
**Impact:** +0.1 (scope extension)

**Week 6-8 Result: 8.7 → 9.2**

---

### **Week 9-12: Mastery Celebration + Long-term Narrative (9.2 → 9.9)**

#### Mastery Badges & Leaderboards
- Display "You've mastered piece_safety" badge on dashboard
- Show progression: piece_safety (🟢 mastered), king_safety (🟡 70%), missed_tactic (🔴 40%)
- Peer comparison: "You're stronger than 65% of your cohort on piece_safety"

**Estimate:** 6 hours  
**Impact:** +0.2 (engagement, motivation)

#### 4-Week Progress Narrative
- Show player: "4 weeks ago, you blundered on piece_safety every 3rd game. Now: every 7th game. Here's the trend."
- Graph: mistake rate over time with pattern slope
- Reinforces behavior change proof

**Estimate:** 4 hours  
**Impact:** +0.2 (retention, psychological anchor)

#### Daily Challenge Loop
- "Today's challenge: solve 2 puzzles on piece_safety"
- Re-engagement email if user hasn't played in 3 days
- Show progress: "You're 1 game away from a 5-game time_management streak"

**Estimate:** 6 hours  
**Impact:** +0.2 (engagement)

#### Streak Leaderboard + Social
- "Your 7-game time_management streak beats 58% of players at your rating"
- Optional: share streak on social media

**Estimate:** 4 hours  
**Impact:** +0.1 (engagement, viral coefficient)

**Week 9-12 Result: 9.2 → 9.7**

---

### **Final Push: Behavior Validation Results (Week 16)**

If your 20-user, 12-week study CONFIRMS the hypothesis (20%+ mistake reduction post-training):
- **+0.3 points:** "Coaching proven to work" messaging unlocks
- **Final Score: 9.7 → 10.0** 🎯

If it **FAILS** (no improvement):
- Diagnose blocker (puzzles too hard? training not seen? pattern detection wrong?)
- Don't fake the data — instead:
  - Fix the blocker
  - Extend timeline to Sept + run 2.0 validation
  - Score caps at 9.5 (good coaching, just unproven)

---

## The 10/10 Definition

Your 10/10 checklist:

| Dimension | Requirement | Status |
|-----------|-------------|--------|
| 🧠 Coaching Quality | Move-by-move explanation + goal-aware context | ✅ Phase 1-3 |
| 📊 Data Pipeline | 100% of games analyzed, patterns tracked, puzzles extracted | ✅ Fixed |
| 🎯 Personalization | ≥4 focus areas wired + mastery gates | ⏳ Week 2-3 |
| 🎨 UX | Mobile tested, difficulty scaling, celebration cards | ⏳ Week 6-8 |
| 🔥 Engagement | Win streaks, peer comparison, daily challenges | ⏳ Week 9-12 |
| ✅ **Behavior Validation** | **Prove users improve their chess** | ⏳ Week 16 |

**The single most important:** Behavior validation. Without it, you're at 9.5. With it, you're 10/10.

---

## Weekly Cadence

### **Week 1 (DONE): Quick Wins**
- [x] Cognitive gap accuracy (piece_safety fix)
- [x] Session reflection UI
- [x] Puzzle backfill
- [x] Mastery gate definition
- **Deliverable:** 8.4/10 platform

### **Week 2-3: Extension**
- [ ] Extend time_management→piece_safety
- [ ] Extend time_management→king_safety
- [ ] Extend time_management→missed_tactic
- **Deliverable:** 8.7/10 platform

### **Week 4-5: Behavior Study Kickoff**
- [ ] Design 20-user study
- [ ] Capture baseline metrics
- [ ] Launch intervention
- **Deliverable:** Study running (results in 12 weeks)

### **Week 6-8: Mobile + Scaling**
- [ ] Mobile responsiveness
- [ ] Puzzle difficulty scaling
- [ ] Adaptive opening teaching
- **Deliverable:** 9.2/10 platform

### **Week 9-12: Mastery + Narrative**
- [ ] Mastery badges
- [ ] 4-week progress graph
- [ ] Daily challenge loop
- [ ] Streak leaderboards
- **Deliverable:** 9.7/10 platform

### **Week 16 (Async): Behavior Results**
- [ ] Analyze 20-user study
- [ ] Publish results
- **Deliverable:** 10/10 OR 9.5/10 (depends on validation)

---

## Dependencies & Blockers

| Item | Blocker | Mitigation |
|------|---------|-----------|
| Behavior validation | 12-week data collection | Start NOW (week 4), results in week 16 |
| Mobile testing | Requires device | Use Chrome DevTools for first pass |
| Peer comparison leaderboard | No cohort baselines yet | Use avg across all users for MVP |
| Daily challenges | Notification infrastructure | Start with in-app only, email later |

---

## Success Metrics

**By end of Sept 2026:**
- [ ] 8+ focus areas fully extended (vs. 1 now)
- [ ] 20-user behavior study complete
- [ ] Hypothesis: ≥60% of users show 20%+ mistake reduction
- [ ] Mastery badges shipped + 30% of active users have ≥1 badge
- [ ] Mobile fully supported
- [ ] Platform rated 10/10 by Mohit's criteria

---

## Commit Strategy

Each week = 1 clean commit per feature (not 1 commit per file):
- `feat(coaching): extend piece_safety coaching architecture`
- `feat(coaching): extend king_safety coaching architecture`
- `feat(coaching): extend missed_tactic coaching architecture`
- `feat(coaching): mobile responsiveness audit + fixes`
- etc.

Push to working-code after each week's work. Merge to main only after behavior validation confirms hypothesis.

---

## How to Handle Failures

**If cognitive gap accuracy doesn't improve:**
- Check: are high-confidence moves (good_move, excellent) being misclassified as mistakes?
- Fix: add "phase gate" on gap detection (only flag if eval_swing > 50cp)

**If mastery gates feel too lenient:**
- Tighten: raise min_sessions from 3 to 4, clean_streak from 5 to 7
- Test on bhutramohit/shobhit first before deploying

**If behavior study shows NO improvement:**
- Hypothesis options to test:
  1. Puzzles are too hard (users quit mid-session)
  2. Training page isn't being seen (marketing problem, not coaching)
  3. Puzzle-to-game pattern mismatch (puzzle is tactical_oversight, user made calculation_depth blunder)
  4. Time horizon (need >3 months to see signal)
- Action: Diagnose via user interviews + backend logs

---

## Resources

**Documentation:**
- `docs/coaching_engine_v2_scope.md` — Original v2 spec
- `docs/pwc_improvements_audit.md` — Phase 1-3 PWC details
- `docs/coaching_platform_reassessment_2026_07_09.md` — Full audit

**Key Files:**
- Backend: `backend/services/mastery_gate_service.py`, `backend/services/session_reflection_service.py`
- Frontend: `frontend/src/components/coach/SessionReflectionCard.jsx`
- Routes: `backend/routes/coach_play.py` (GET `/session-reflection`)

**Test Data:**
- bhutramohit: 584 analyzed games, active user
- shobhit: similar profile, good control

---

## FAQ

**Q: Why 12 weeks for behavior validation?**  
A: You need 10+ games per user post-training to see signal. At 2 games/week, that's 5 weeks minimum. Add 1 week for baseline + 6 weeks for luck factor. 12 weeks = high confidence.

**Q: Why 20 users, not 100?**  
A: 20 users with 10 games each = 200 data points. At 600-1500 rating, patterns are idiosyncratic. 200 points enough to see directional signal. 100 users = overkill + slow.

**Q: What if behavior validation fails?**  
A: You're at 9.5/10 (still excellent). Coaching quality + personalization + UX are solid. The "unlocks 10" is PROOF. Without proof, skeptical users will say "show me it works" instead of "this coach is great."

**Q: Can I ship before week 16?**  
A: Yes. Ship 9.7/10 at end of week 12. Behavior validation runs in parallel. When results land (week 16), either celebrate 10/10 or diagnose the blocker and iterate.

---

## Bottom Line

You're 2.6 points from 10/10. You have a clear path:

1. **Week 1:** ✅ Quick wins (done)
2. **Week 2-5:** Architecture extension + behavior study kickoff
3. **Week 6-12:** Mobile + mastery + narrative
4. **Week 16:** Behavior results → 10/10 or 9.5/10 (with diagnosis)

**Confidence Level:** HIGH (85%)  
**Risk:** LOW (all work is scoped + de-risked by behavior study)  
**Timeline:** Realistic (12 weeks, not optimistic)

Start with week 2: extend piece_safety. When that ships, iterate. Don't wait for perfection.
