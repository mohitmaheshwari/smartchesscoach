# Issue-Driven Coaching Loop

## 1. What it is

ChessGuru becomes a live coaching relationship, not a study library. The coach continuously analyzes your games, detects issues, explains why each one matters, prescribes training plans in the right sequence, and tracks improvement as you work. Users never search for content—the coach tells them what to work on next and why. When a user completes a training plan and improves, the coach prescribes the next one. Users can accept the coach's recommendation, choose an alternative training plan, or add multiple plans in parallel if they're progressing fast. The experience is: Coach analyzes → Coach prescribes → User accepts/chooses → System tracks all active plans → Coach prescribes next.

---

## 2. What the user sees

### HomePage (Coaching Loop)

**Coach Recommendation (Primary)**
```
Critical Moment Thinking

Why this training plan?

In your last 20 games, you rushed 18 critical moments.
You lost material in 7 of those 18.

This training plan teaches you to recognize when the board gets complex and slow down.

Estimated time: 15 minutes

Week 2 · ██████░░░░ 60% complete
Rushed moves: 0.55/game → 0.38/game (↓ 31%)

[Continue Training Plan]
```

**Also Training On (Your Choices)**
```
📚 Loose Piece Discipline
Week 1 · ████░░░░░░ 40% complete
Undefended pieces: 0.8/game → 0.68/game (↓ 15%)

📚 King Safety (Expert Mode)
Week 1 · ██░░░░░░░░ 20% complete
```

**After Completing a Plan:**
```
✅ Critical Moment Thinking COMPLETE

Improvement: Rushed moves ↓ 73%
Before: 0.55/game
After: 0.15/game

---

Coach Recommendation (Next)

Loose Piece Discipline

Why this training plan?

You've fixed the rushing problem. Great work.

Now that you have time to think, we can teach you to scan for safety before attacking.
In your last 30 games, you left 14 pieces undefended—all because you attacked before checking what was defended.

This training plan fixes that.

[Start Training Plan] [I'd rather learn something else]
```

---

### Lab (Two Tabs)

**Tab 1: Issues & Studies (NEW)**
```
Issues We've Found

❌ You rush critical moments
503 times · Costing ~0.2 rating/game

When board complexity spikes, you move within 3 seconds.
That habit is costing games.

Recommended: Critical Moment Thinking (18 min)
[Start Study] [Learn More]

---

❌ Skewers
161 times caught

Status: Studying (Week 1)
Progress: 12% → 31%
Target: 50%
[Continue Study]

---

✅ Time Management
30 clean games in a row · Status: Mastered
[Archive]

---

Explore more issues
🎯 Loose Piece Discipline
🎯 Threat Awareness
🎯 Calculation Depth
```

**Tab 2: Games (EXPANDED)**
```
Last 50 Games

Scotch Game (W) 1-0 vs Opponent
May 10 · 42 moves
Issues: 🔵 Skewers (2) 🔵 Critical Moments (1)

Ruy Lopez (L) 0-1 vs Opponent
May 9 · 58 moves
Issues: 🔴 Critical Moments (3) 🔵 Skewers (1)

Italian (D) ½-½
May 8 · 44 moves
Issues: None detected

[Filter by issue] [Filter by result] [Show all 50]
```

---

### Progress (Reorganized)

**Current:**
```
Accuracy: 62.3%
Win streak: 5 games
Mistakes per game: ↓ 12%
```

**New:**
```
Studies Completed

✅ Critical Moment Thinking
Rushed moves: 0.55/game → 0.38/game
Improvement: -31%
Completed: May 3

✅ Opening Principles
Opening blunders: 0.22/game → 0.08/game
Improvement: -64%
Completed: April 18

---

Active Studies

📚 Skewer Recognition (Week 2)
Target: Skewers caught (↑)
Before: 12%
Current: 31%
Goal: 50%

Progress: ████████░░ 62%

---

Issues Not Yet Addressed

❌ King Safety (47 times)
❌ Calculation Depth (38 times)
```

---

## 3. In scope (V1)

### Data Model
- [ ] Create `user_coaching_prescriptions` (active training plans per user)
  - Fields: user_id, prescription_id, training_plan_id, status (active/completed/paused), is_coach_recommended (bool), user_chose_alternative (bool), priority_order (1=primary, 2=secondary, 3=exploring), started_at, completed_at, baseline_metric, current_metric, improvement_pct, reason_for_prescription (text), games_since_start [game_ids]
- [ ] Create `coaching_prescription_history` (log of all prescriptions + user responses)
  - Fields: user_id, issue_detected, coach_recommended_plan, reasoning, user_response (accepted/chose_alternative/ignored), user_chose_instead, prescribed_at, accepted_at
- [ ] Create `training_plan_catalog` (5 core training plans)
  - Fields: plan_id, name, description, duration_minutes, components, issue_types_addressed
  - Content: Critical Moment Thinking, Loose Piece Discipline, Spot Tactical Opportunities, King Safety, Convert Winning Positions
- [ ] Create `issue_to_plan_mapping` (many-to-many with confidence %)
  - Maps: issue_type → [plan_id1 (95%), plan_id2 (70%), plan_id3 (45%)]

### Backend Auto-Prescription Engine
- [ ] After each game analyzed:
  - Detect issues in the game (cognitive_gap + motif)
  - Update issue trend for user (frequency + severity + trend)
  - Check if user has active prescriptions for these issues
  - If user has no active plans OR just completed one:
    - Find NEW issues not currently being trained
    - Coach selects best training plan for top issue (highest confidence % from mapping)
    - Create prescription with evidence-based reasoning
    - Queue for homepage display
- [ ] Continuous improvement tracking:
  - Track metric for each active plan (pieces undefended/game, rushed moves/game, etc)
  - Calculate improvement % against baseline
  - When improvement hits 50%: mark complete + auto-detect next issue + prescribe next plan

### Backend API Endpoints
- [ ] `GET /api/coaching/current-prescriptions` — Returns active training plans with progress + reasoning
- [ ] `GET /api/coaching/next-prescription` — Returns coach's recommended next plan (if user has no active plans)
- [ ] `POST /api/coaching/accept-prescription` — User accepts coach's recommendation
- [ ] `POST /api/coaching/choose-alternative` — User picks different training plan to focus on instead
- [ ] `POST /api/coaching/add-parallel-plan` — User adds alternative training plan alongside active ones (concurrent)
- [ ] `GET /api/coaching/prescription-history` — Returns historical prescriptions + user responses
- [ ] `POST /api/coaching/complete-plan` — Mark training plan complete (triggered when 50% improvement OR user marks done)
- [ ] `GET /api/lab/games?limit=50` — Last 50 games with issues per game highlighted

### Frontend Pages
- [ ] HomePage: Replace FocusCard with Coaching Prescriptions section
  - Show: Primary recommendation (coach's pick) + currently active plans (parallel) + progress on each
  - Each plan shows: Why (evidence), Progress bar, Metric improvement
  - CTA: "Start Training Plan" / "I'd rather learn something else"
- [ ] Lab: Keep game browser (last 50 games with issues tagged)
- [ ] Progress: Show training plan completion history + outcomes

### Training Plan Catalog (5 Plans)
- [ ] Critical Moment Thinking (15-20 min) — Addresses: rushing, time pressure, calculation_depth
  - Components: Lesson on candidate moves + 10-second rule, 3 puzzles, 1 coached game, post-game review
- [ ] Loose Piece Discipline (12-15 min) — Addresses: piece_safety, hanging pieces
  - Components: Lesson on piece safety, 3 puzzles, 1 coached game
- [ ] Spot Tactical Opportunities (15 min) — Addresses: missed_tactic, forks, pins, skewers
  - Components: Lesson on checks/captures/threats, 5 puzzles, 1 coached game
- [ ] King Safety (18 min) — Addresses: king_safety, weak king, back rank
  - Components: Lesson on weak squares/diagonals, 3 puzzles, 1 coached game
- [ ] Convert Winning Positions (12 min) — Addresses: conversion, throwing away wins
  - Components: Lesson on simplification, 3 puzzles, 1 endgame lesson

### Parallel Plan Support
- [ ] Track multiple active prescriptions simultaneously
  - Each plan has independent baseline + current metric + progress %
  - HomePage shows primary (coach-recommended) + secondary (user-chose)
- [ ] Auto-detect if user can handle parallel plans:
  - If user completes plans quickly (>50% in <1 week): Suggest parallel plans
  - If user progresses slowly: Stick to sequential
- [ ] User can manually add alternative plans mid-training

### Data Migration
- [ ] Backfill user_coaching_prescriptions from existing focus_locks (one-time migration)
- [ ] Backfill issue data from game_analyses (cognitive_gap) + player_profiles (motif_profile)
- [ ] Deprecate focus_locks (no new writes, keep for rollback)

---

## 4. Explicitly out of scope (V1)

- **Dynamic training plan generation** ("I found this pattern in YOUR games → create custom plan") — V2 (requires custom plan templating + component linking)
- **Training plan video components** — V1 plans reference video structure but don't produce videos. Plans link to existing Training infrastructure (puzzles, coached games)
- **Opening recommendations** (coach recommends which opening to study) — V2 (wait until training plan system is solid)
- **Community-sourced training data** (cross-player insights for recommendations) — V2 (single-player coaching first)
- **User-created training plans** — V2 (coach recommends, not user-generated)
- **Training plan scheduling** ("I recommend 15 min today at 7pm") — Out of scope (user self-paces)
- **Training plan team sharing/collab** — Out of scope (personal coaching only)
- **Offline training mode** — Out of scope
- **Certification/badge system** — Out of scope (skill mastery tracked, no badges)
- **Prerequisite chains longer than 2 levels** — V1 coaches user through Issue #1 → Issue #2; Issue #3+ comes in later prescriptions, not pre-planned chains

---

## 5. Success criteria

**Launch targets (measured in production after V1 ships):**

*Engagement:*
- [ ] Users who receive a coaching prescription start a training plan within 2 weeks: >= 40%
- [ ] Users who start a training plan complete it (hit 50% improvement or mark done): >= 60%

*Outcomes:*
- [ ] Users who complete a training plan show measurable improvement in that issue: >= 50% of completers improve
- [ ] Average improvement % among completers: >= 30% (e.g., rushed moves 0.55 → 0.39)

*Quality:*
- [ ] Issue detection from game analysis covers >= 80% of significant mistakes
- [ ] Coach recommendations feel relevant to user (qualitative feedback): >= 70% approve
- [ ] Outcome metrics match actual game statistics (auto-detected issues align with player perception)

*Adoption:*
- [ ] >= 50% of active users have at least one active or completed training plan
- [ ] Average time from issue detection to plan acceptance: < 7 days
- [ ] Users who complete one plan start a second plan: >= 40% (shows habit formation)

---

## 6. Open questions

**Q: How does coach sequence multiple issues?**
- Mohit's answer: Prerequisite dependencies. Fix rushing before teaching tactics (rushing blinds you to tactics)
- Implication: coach_prescription_history tracks which issues are prerequisites for which plans
- Implementation: issue_to_plan_mapping includes prerequisites (e.g., "teach Critical Moment Thinking before Spot Tactical Opportunities")
- Status: LOCKED — coach recommends by impact + prerequisites

**Q: What if user rejects coach's recommendation?**
- Mohit's answer: Coach explains why + user can choose alternative plan. Both get tracked + taught simultaneously.
- Implication: When user chooses different plan, coach shows: "OK, here's why I recommended X... But Y is also solid. Let's track both."
- Implementation: POST `/api/coaching/choose-alternative` creates second prescription with lower priority_order
- Status: LOCKED — support parallel plans + track both

**Q: How many plans can user do in parallel?**
- Mohit's answer: Flexible. Good players can handle 2-3. Average players stick to 1. System detects competence and adapts.
- Implication: If user completes plans fast (>50% in <1 week), coach offers parallel plans. If slow, keep sequential.
- Implementation: homePage can show 1 primary (coach-rec) + N secondary (user-chose) active at once
- Status: LOCKED — auto-detect competence + support parallel

**Q: When does coach prescribe the next plan?**
- Mohit's answer: Auto-analyze new games. See user improving. When last plan completes + find new issues, prescribe next.
- Implication: No delay. Game finishes → analyzed → metrics updated → coach checks completion → if completed, next prescription ready
- Implementation: Async job after game analysis: check all user's active prescriptions, if any hit 50%, mark complete + find next issue + create new prescription
- Status: LOCKED — continuous coaching loop

**Q: How do we name training plans?**
- Mohit's preference: "Training Plan" (not "Study"). Also test: "Coach Plan", "Improvement Plan", "Mission", "Program"
- Implication: Homepage says "Coach Recommendation" + "Training Plan" not "Recommended Study"
- Implementation: Rename all UI references from "study" → "training plan"
- Status: LOCKED — use "Training Plan" terminology

**Q: What if coach prescribes same plan twice to different users?**
- Assumption: Yes, multiple users can be prescribed "Loose Piece Discipline" for piece_safety issues
- Implication: training_plan_catalog has 5 shared plans. Multiple user_coaching_prescriptions point to same plan_id
- Implementation: No issue, many-to-many design supports this
- Status: Resolved by data model

---

## 7. Pre-code requirements

**Hard gates (must be true before line 1 of code):**

- [x] Mohit has explicitly signed off on this scope doc — YES ("lock this")
- [x] Training plan catalog authored (5 core plans with names + descriptions + components) — YES
  - Critical Moment Thinking
  - Loose Piece Discipline
  - Spot Tactical Opportunities
  - King Safety
  - Convert Winning Positions
- [x] Issue-to-plan mapping defined (many-to-many with confidence %) — YES
  - Rushing → Critical Moment Thinking (95%) + Loose Piece Discipline (60%)
  - Piece safety → Loose Piece Discipline (90%) + Spot Tactical Opportunities (60%)
  - Missed tactics → Spot Tactical Opportunities (95%) + Critical Moment Thinking (50%)
  - King safety → King Safety (95%)
  - Etc.
- [x] Outcome metrics defined (behavioral, not issue-specific) — YES
  - Frequency + Severity + Trend for each issue
  - Example: "Pieces left undefended/game", "Rushed moves in critical positions", "Skewer opportunities seen"
- [x] Prerequisite chains defined — YES
  - Critical Moment Thinking before Spot Tactical Opportunities (can't see tactics if you're rushing)
  - Loose Piece Discipline before King Safety (understand piece safety first)
- [x] Database connection stable on chess_coach (production) + test_database (local) — YES (verified)
- [x] FocusCard migration strategy decided — YES (Option C: Fallback. No active plan → show issues. Active plan → show primary + secondary. On completion → show next recommendation)
- [x] Parallel plan support architecture decided — YES (support 1 primary + N secondary. Auto-detect competence. Homepage shows all active plans with progress)

**Design decisions locked:**
- [x] HomePage coaching prescriptions layout (mockup approved) — Primary recommendation + Active plans + Progress bars
- [x] Prescription copy/tone (should read like a coach explaining, not system announcing) — YES ("In your last 20 games, you rushed 18 times. This plan teaches you to slow down.")
- [x] Terminology locked — "Training Plan" not "Study". "Coach Recommendation" not "Recommended Study"
- [x] Auto-prescription trigger logic — YES (after each game: detect new issues → if no active plan or just completed one → prescribe next)

---

## Summary

This is **the actual moat ChessGuru needs**: a live coaching relationship, not a study library.

**The shift:**
- Library model: "Here are 50 studies, pick one"
- Coaching model: "I found your problems, here's what to fix first"

**Core loop:**
1. Coach analyzes each game (auto)
2. Coach detects issues (auto)
3. Coach prescribes training plan with evidence (auto)
4. User accepts/chooses/adds parallel (manual)
5. Coach tracks improvement (auto)
6. Coach prescribes next issue (auto)

**Key differentiators:**
- Evidence-driven: Every recommendation explains why ("You rushed 18 times, lost material 7 times")
- Sequential: Coach understands prerequisites (fix rushing before teaching tactics)
- Parallel capable: System detects user competence and offers multiple plans
- Continuous: Live coaching loop, not weekly emails
- Personalized: 5 core plans map to all issues; each user gets different sequence based on their games

**Data migration risk:** Low (focus_locks → user_coaching_prescriptions backfill)

**Backend complexity:** Medium (new auto-prescription engine + parallel tracking + outcome measurement)

**Frontend changes:** Moderate (HomePage coaching section, remove FocusCard, terminology shift to "Training Plan")

**Timeline estimate:** 4-5 weeks (architecture + data model + auto-engine + frontend + migration + testing)

---

**SCOPE LOCKED** — All 7 pre-code requirements satisfied. Ready for architecture + design phase.
