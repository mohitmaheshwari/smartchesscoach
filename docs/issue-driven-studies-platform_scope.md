# Issue-Driven Studies Platform

## 1. What it is

ChessGuru shifts from assigning users a single locked focus to helping them discover their specific problems and commit to studies that fix them. Users see a clear diagnosis (e.g., "You rush 503 critical moments"), choose from recommended studies (e.g., "Critical Moment Thinking"), and track concrete improvements before/after. Instead of "Your focus is time management," it's "Here's what we found. Here's how to fix it. You pick."

---

## 2. What the user sees

### HomePage (Updated)

**Current:**
```
Focus
Time Management
Locked for 6 days

Pattern of the Day
Loose Pieces
```

**New:**
```
Current Studies

📚 Critical Moment Thinking
Week 2 · 60% complete
Rushed moves: 0.55/game → 0.38/game
Continue →

📚 Skewer Recognition
Week 1 · 20% complete
Skewers caught: 12% → 31%
Continue →

Recommended Next

🎯 Loose Piece Discipline
We found this 47 times in your last 10 games
[Start Study]
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
- [ ] Create `user_studies` collection (stores active studies per user)
  - Fields: user_id, study_id, status (studying/completed/archived), started_at, baseline_metric, current_metric, target_metric, progress_pct
- [ ] Create `study_catalog` collection (predefined studies)
  - Fields: study_id, name, description, duration_minutes, issue_type, components (lesson, puzzles, coached_game, review, homework)
- [ ] Create `issue_to_study_mapping` (which studies fix which issues)
  - Maps: issue_type → [study_id1, study_id2, ...] with confidence %

### Backend API Endpoints
- [ ] `GET /api/lab/issues` — Returns detected issues for user with evidence (count, rating impact, recommendations)
- [ ] `GET /api/lab/games?limit=50` — Returns last 50 games with issues per game highlighted
- [ ] `GET /api/studies/catalog` — Returns all available studies
- [ ] `POST /api/studies/start` — User starts a study (captures baseline metric)
- [ ] `GET /api/studies/active` — Returns user's active studies with progress
- [ ] `GET /api/studies/:study_id` — Returns study details (components, progress, metrics)
- [ ] `POST /api/studies/:study_id/complete` — Marks study complete (captures final metric, calculates improvement %)
- [ ] `POST /api/studies/:study_id/archive` — User archives a completed study

### Frontend Pages
- [ ] HomePage: Replace FocusCard with Studies panel (show active studies + recommended next)
- [ ] Lab: Add two tabs: "Issues & Studies" + "Games (last 50)"
- [ ] Progress: Replace generic metrics with study outcomes + completed study history

### Issue Detection
- [ ] Integrate motif_profile (fork/pin/skewer/loose/discovered) as issue types
- [ ] Integrate cognitive_gap types (piece_safety, king_safety, calculation_depth, etc.) as issue types
- [ ] Issue card shows: issue name + evidence (count in last N games) + rating impact estimate + recommended studies

### Study Recommendation Engine
- [ ] Map each issue type to 3-5 recommended studies (use issue_to_study_mapping)
- [ ] Rank by confidence % (e.g., "83% confidence Critical Moment Thinking fixes your rushing problem")
- [ ] Show recommendation reason (e.g., "This study targets your specific pattern")

### Study Outcomes Tracking
- [ ] Auto-capture baseline metric when study starts (e.g., "Rushed moves: 0.55/game")
- [ ] Track progress weekly (e.g., "Week 2: 0.38/game, ↓ 31%")
- [ ] Auto-close study when improvement hits 50% threshold OR user manually completes
- [ ] Capture final metric + improvement % + show on Progress page

### Data Migration
- [ ] Backfill user_studies from existing focus_locks (map current focus → study)
- [ ] Backfill issue data from game_analyses (cognitive_gap) + player_profiles (motif_profile)
- [ ] Deprecate focus_locks (keep for backwards compatibility, but don't write new data)

---

## 4. Explicitly out of scope (V1)

- **Dynamic study generation** ("I found this pattern in YOUR games → create custom study") — Deferred to V2 (scope: design custom study templating first)
- **Study components** (lesson videos, coached game integration, etc.) — V1 references them but doesn't build them. Studies link to existing Training pages
- **Multi-user study recommendations** (community insights) — V2 (first make single-user recommendations solid)
- **Study difficulty progression** (adaptive studies that scale) — V2
- **Custom study creation by users** — V2 (users can only start recommended studies)
- **Study scheduling** ("Do 15 min of skewers today") — V2
- **Study team collaboration** — Out of scope entirely (personal platform)
- **Offline study mode** — Out of scope
- **Study certifications/badges** — Out of scope (just tracking, no gamification badges)

---

## 5. Success criteria

**Launch criteria (user-facing engagement):**
- [ ] Users who see an issue recommendation start a study within 2 weeks: >= 40%
- [ ] Users who start a study complete it (hit 50% improvement or mark complete): >= 60%
- [ ] Users with completed study show measurable improvement in that issue type: >= 50% of completers improve

**Data quality criteria:**
- [ ] Issue detection covers >= 80% of analyzed moves (every significant weakness surfaced)
- [ ] Study recommendations have >= 70% relevance (users feel recommended studies match their issue)
- [ ] Outcome metrics (before/after) are trustworthy (match actual game statistics)

**Adoption criteria:**
- [ ] >= 50% of active users have at least one study (completed or active)
- [ ] Average time-to-study (from issue detection to study start): < 7 days

---

## 6. Open questions

**Q: How do we measure the baseline metric?**
- Example: For "Skewers" issue, baseline = "% of skewer opportunities caught in last 10 games"
- Why unresolved: Different issues need different baselines (some count frequency, some count %)
- Unblocking step: Audit game_analyses + player_profiles + motif_profile to define 1 metric per issue type

**Q: When should a study auto-close?**
- Option A: Fixed timeline (14 days)
- Option B: Improvement threshold (50% improvement in baseline metric)
- Option C: User-driven (user marks complete)
- Mohit's preference: Option B (outcome-based)
- Why unresolved: Need to verify outcome metrics are stable enough to close automatically
- Unblocking step: Backtest on 10 users' existing game histories — does 50% threshold close studies at reasonable times?

**Q: What does "study component" mean in V1?**
- Current assumption: Studies are links to existing Training pages + placeholder for future lesson videos
- Mohit's clarification: Studies should reference existing infrastructure (PatternTraining, traps, endgames)
- Why unresolved: Need to define study data structure (does it store lesson video URLs, or does it compose from existing pages?)
- Unblocking step: Design study_catalog schema + map to existing Training infrastructure

**Q: How do we rank recommended studies by confidence?**
- Example: "Critical Moment Thinking" 83%, "Time Management" 71%
- Why unresolved: Need heuristic for "how likely does this study fix this issue?"
- Options: Rule-based (domain expertise), ML-based (learned from completion data), or hybrid
- Unblocking step: Define issue_to_study_mapping.confidence formula (start with domain rules, upgrade later)

**Q: Should users be able to pause/resume studies?**
- Current assumption: No (V1: start → progress → complete → archive)
- Why unresolved: User experience question (do people want to context-switch between studies?)
- Unblocking step: Mohit decision

**Q: How do we handle studies with overlapping issues?**
- Example: "Critical Moment Thinking" helps BOTH "rushing" AND "calculation depth"
- Why unresolved: Need to avoid recommending 10 studies for 3 issues
- Unblocking step: Apply deduping logic when recommending (show top 3 studies, each fixes 1+ issues)

---

## 7. Pre-code requirements

**Hard gates (must be true before line 1 of code):**

- [ ] Mohit has explicitly signed off on this scope doc
- [ ] Study catalog is authored (at least 5 predefined studies with names + descriptions)
- [ ] Issue-to-study mapping is defined (which issue types map to which studies + confidence %)
- [ ] Outcome metrics are defined (for each issue type, what's the "before" and "after" metric?)
- [ ] Database connection is stable on both chess_coach (production) and test_database (local)
- [ ] Backlog decision: Should FocusCard be immediately replaced or run parallel for N days? (affects migration plan)

**Design decisions locked:**
- [ ] HomePage Studies panel layout (mockup approved)
- [ ] Lab two-tab structure (mockup approved)
- [ ] Progress study outcomes format (mockup approved)
- [ ] Issue card copy/tone (should read like a coach diagnosis, not a database query)

---

## Summary

This is a **product direction shift** that keeps existing data infrastructure but reorganizes the UX:
- Single focus → Multiple user-committed studies
- System assigns → User chooses
- "Here's your focus" → "Here's what we found. Here's how to fix it."

Data migration is low-risk (focus_locks → user_studies backfill). Frontend changes are moderate (3 pages reorganized, no new data sources). Backend is mostly new endpoints reading from existing collections + new outcome tracking logic.

**Timeline estimate:** 3-4 weeks (design + backend + frontend + testing + migration)

---

**AWAITING MOHIT SIGNOFF** before proceeding to lock numeric thresholds and pre-code audit.
