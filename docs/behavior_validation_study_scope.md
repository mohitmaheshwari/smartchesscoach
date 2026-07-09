# Behavior Validation Study: Proof of Coaching Effectiveness

**Goal:** Prove that ChessGuru coaching (specifically puzzle training) reduces player mistakes  
**Timeline:** 12 weeks (data collection + analysis)  
**Impact:** +0.5 points (9.7 → 10/10) — **IF hypothesis confirmed**  
**Status:** 🔒 Locked scope — DO NOT START implementation until Mohit signs off

---

## 0. Existing Measurement Infrastructure Audit

**What already exists:**
- ✅ `coach_memory` collection — tracks patterns (9 tracked per user)
- ✅ `game_analyses` — every move has `cp_loss` + `cognitive_gap` (piece_safety/missed_tactic/etc)
- ✅ `community_puzzles` — 998+ puzzles extracted from games, tagged by `issue_type`
- ✅ `puzzle_attempts` — records solve ✓/✗ per user per puzzle
- ✅ Pattern decay model — recency-weighted mistake scoring (0.85^t decay)
- ✅ `mission_scoreboard` — session-level moment tracking

**What's MISSING (must build):**
- Baseline measurement: current mistake rate per user per pattern (before intervention)
- Intervention tracking: which users solve which puzzles (exposure log)
- Outcome measurement: post-training mistake rate per pattern (after intervention)
- Control group comparison: natural regression baseline

**Design Decision:** No separate control group (20 users is too small to split). Instead, use **historical comparison**: measure each user's pre-training mistake rate as their own control.

---

## 1. What This Study Is

A **12-week before/after quasi-experiment** measuring whether puzzle training on a specific weakness pattern reduces that mistake in future games.

**NOT a randomized controlled trial** — we have 20 active users, not 200. Design trades RCT rigor for speed. We use each player as their own baseline.

**The Core Question:** 
> When a user solves 3+ puzzles tagged with `issue_type=piece_safety`, do they make fewer piece_safety mistakes in the next 10+ games?

**Success = YES with 20%+ improvement** (e.g., pre: 1 piece_safety blunder per 5 games → post: 1 per 7+ games)

---

## 2. What the User Sees

No UI change required for MVP. Existing surfaces:
- `Training` page → `training/pattern/{pattern}` shows their own puzzles first
- `puzzle_attempts` already tracks solves
- Game analyses already tag mistakes with `cognitive_gap`

**Optional nice-to-have (NOT in scope for Week 4-5):**
- "You've solved 2/3 puzzles on piece_safety. You're on track!" badge
- Difficulty filter (moved to separate task)

---

## 3. In Scope (Week 4-5)

**Phase 1: Study Design & Sampling (Week 4)**
- [ ] Identify 20 active users with diverse patterns (see sampling strategy below)
- [ ] Get consent (email + opt-in flag in DB)
- [ ] Assign 4 users per pattern (5 patterns × 4 users = 20)

**Phase 2: Baseline Measurement (Week 5, Jan 27-31)**
- [ ] For each user + pattern: count mistake rate in last 50 games
- [ ] Compute: "blunders per game" for piece_safety, missed_tactic, king_safety, time_pressure, calculation_depth
- [ ] Store baseline snapshot: `study_baseline` collection
- [ ] Lock baseline (no retroactive changes after this date)

**Phase 3: Intervention Start (Feb 1 — Week 6)**
- [ ] Activate: user sees their pattern-specific puzzles on Training page
- [ ] Tracking: log every puzzle solve (already in `puzzle_attempts`)
- [ ] Duration: 8 weeks (Feb 1 – Mar 26)
- [ ] Success gate: user must attempt ≥3 puzzles on their assigned pattern to be counted

**Phase 4: Outcome Measurement (Mar 27 — Week 15)**
- [ ] For each user + pattern: count mistake rate in NEXT 50 games post-intervention
- [ ] Compute: "blunders per game" (same metric as baseline)
- [ ] Store outcome snapshot: `study_outcome` collection

**Phase 5: Analysis (Week 16)**
- [ ] Compare: pre vs post mistake rate per user per pattern
- [ ] Success: ≥60% of users show ≥20% improvement
- [ ] Report: publish results (commit to repo or email)

---

## 4. Explicitly Out of Scope (V1)

- Difficulty scaling (separate Week 6-8 task)
- Mobile testing during study period (run post-study)
- Peer comparison / leaderboards (future feature)
- Multiple intervention types (only puzzle training tested here)
- Statistical significance testing (12-week timeline doesn't support p-value rigor)
- Coaching quality audit (study assumes coaching is sound)

---

## 5. Success Criteria

**Study succeeds if:**
1. ✅ 20 users enrolled + baseline measured by end of Week 5
2. ✅ ≥80% of enrolled users complete 8-week intervention (attempt ≥3 puzzles)
3. ✅ ≥60% of users show ≥20% improvement in pattern-specific mistakes
   - Example: piece_safety blunder rate drops from 20% to 16% (20% improvement)
4. ✅ Outcome measured by end of Week 15 (8-week post-training window)

**Study fails if:**
- <50% of users attempt ≥3 puzzles (engagement problem)
- <30% show ≥20% improvement (coaching ineffective, needs diagnosis)
- Measurement impossible (data corruption, missing game analyses)

**Diagnosis if it fails:**
- Is puzzle difficulty appropriate? (interview users)
- Are puzzle patterns matching game mistakes? (random audit)
- Did coaching quality degrade? (spot-check last week's captions)
- Did puzzle training not surface? (log check)

---

## 6. Open Questions

| Question | Why unresolved | Unblocking step |
|----------|---|---|
| How do we measure "mistake rate"? | Need exact formula | See Data Pipeline section |
| Which 20 users? | Sampling strategy needed | See Sampling Strategy section |
| What if a user plays <50 games in window? | Can't measure trend | Set minimum 30 games, exclude rest |
| How do we handle rating changes? | User rating might improve overall | Measure delta %, not absolute; rating-adjust if time permits |
| What if puzzle patterns don't match game mistakes? | Study assumes alignment | Random audit 10 users' puzzles vs their actual mistakes (Week 4) |

---

## 7. Pre-Code Requirements

- [ ] Mohit signs off on this design (yes/no → go/no-go)
- [ ] Sampling strategy approved (which 20 users, how to pick them)
- [ ] Baseline measurement formula locked (see Data Pipeline)
- [ ] Consent email drafted (users know they're in a study)
- [ ] `study_baseline` + `study_outcome` collections can be created (no schema conflicts)

---

## Data Pipeline: Exact Measurement

### Baseline & Outcome: Same Metric

For each user + pattern:

```python
def compute_mistake_rate(user_id: str, pattern: str, game_window: list[game_id]) -> dict:
    """
    Pattern choices: piece_safety, missed_tactic, king_safety, time_pressure, calculation_depth
    
    For each game in window:
        - Get game_analyses.stockfish_analysis.move_evaluations
        - Filter: move.cognitive_gap == pattern AND move.classification in ["mistake", "blunder"]
        - Count: N_mistakes = count
    
    Mistake rate = (N_mistakes) / (N_user_moves_in_window)
    
    Example: piece_safety
      - 50 games, 45 moves avg per game = 2250 user moves total
      - 60 piece_safety mistakes found
      - Rate = 60/2250 = 2.67% OR "1 per 37 moves"
    
    Return:
      {
        "user_id": "...",
        "pattern": "piece_safety",
        "window_start": "2026-01-20",
        "window_end": "2026-01-31",
        "n_games": 50,
        "n_user_moves": 2250,
        "n_mistakes": 60,
        "rate_pct": 2.67,
        "rate_text": "1 per 37 moves"
      }
    ```

### Improvement = (Baseline Rate - Outcome Rate) / Baseline Rate × 100%

Example:
- Baseline: 2.67% (1 piece_safety mistake per 37 moves)
- Outcome: 2.13% (1 per 47 moves)
- Improvement: (2.67 - 2.13) / 2.67 × 100 = **20.2%** ✅ Meets threshold

### Key Assumptions

1. **Cognitive gap accuracy** is ≥85% (validated in Week 1 fixes)
2. **User rating is stable** (±100 rating points over 12 weeks) — if >100 swings, use rating-band thresholds from RATING_BANDS
3. **Recent games are representative** (not a fluke streak) — enforce minimum 30 games per window
4. **Natural regression is 0-5%** (baseline assumption for control; actual natural improvement might be 2-3%, which still leaves 17%+ signal if hypothesis is true)

---

## Sampling Strategy

**Goal:** 20 users, 4 per pattern, diverse rating range (600-1900)

**Pattern assignment (5 patterns):**
1. piece_safety
2. missed_tactic
3. king_safety
4. time_pressure
5. calculation_depth

**Selection criteria per user:**
- At least 20 games analyzed in last 60 days (active player)
- ≥10 mistakes in their assigned pattern (enough signal to measure)
- Rating range: 600-1900 (covers target audience)
- No previous puzzle solve rate >80% (we want to measure NEW training)

**Candidates:**
- bhutramohit (required, known active)
- shobhit (required, known active)
- 18 others from `users` collection (random sample from activity logs)

**Assignment method:**
- Rank users by "mistakes per pattern" (highest first)
- Assign first 4 users with high piece_safety mistakes → piece_safety group
- Assign next 4 users with high missed_tactic mistakes → missed_tactic group
- ... repeat for all 5 patterns

**Blocking:**
- If a user doesn't have ≥10 mistakes in their assigned pattern, skip them
- Select next-best user instead

---

## Intervention: What Happens Weeks 6-15

**For each enrolled user:**
1. `Training` page displays their assigned pattern prominently ("Your focus: piece_safety")
2. `training/pattern/{pattern}` shows puzzles in order (user's own puzzles first, then community)
3. `puzzle_attempts` logs every solve (already automatic)
4. No restrictions (user can solve other patterns too, we just track their assigned one)

**Success gate:** User must attempt ≥3 puzzles on their pattern by end of Week 15

**Non-compliance handling:**
- If user attempts <3 puzzles, exclude from outcome analysis (but report as engagement drop)
- If user attempts ≥3 puzzles, include in outcome regardless of solve % (measure exposure, not perfection)

---

## Timeline

| Week | Task | Owner | Gate |
|------|------|-------|------|
| 4 (Jan 20-24) | Identify 20 users + get consent | Claude | Sampling locked |
| 5 (Jan 27-31) | Measure baseline for all 20 users | Claude | Baseline snapshot saved |
| 6-15 (Feb 1 – Mar 26) | Intervention runs (8 weeks) | Async | Puzzles visible + tracked |
| 15 (Mar 20-26) | Outcome measurement for all 20 users | Claude | Outcome snapshot saved |
| 16 (Mar 27 – Apr 2) | Analysis + report | Claude | Results published |

---

## Commit Message (When Code Ships)

```
feat(study): behavior validation study v1 — 20-user, 12-week protocol

Proof-of-coaching-effectiveness study measuring whether puzzle training
reduces pattern-specific mistakes.

Design:
  - 20 active users, 4 per pattern (5 patterns)
  - Baseline: mistake rate in 50 games pre-intervention
  - Intervention: 8 weeks of puzzle training on assigned pattern
  - Outcome: mistake rate in 50 games post-intervention
  - Success: ≥60% of users show ≥20% improvement

Measurement:
  - Metric: cognitive_gap mistakes per total moves
  - Formula: (pre_rate - post_rate) / pre_rate × 100%
  - Minimum: 30 games per window, ≥3 puzzle attempts

Data:
  - study_baseline collection: baseline snapshots
  - study_outcome collection: outcome snapshots
  - puzzle_attempts: already tracks solves (no change needed)

Impact: +0.5 points (9.7 → 10/10) IF hypothesis confirmed

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## Success Path to 10/10

**If study confirms (≥60% show ≥20% improvement):**
- ✅ Week 16: Publish results
- ✅ Week 16+: Add "Proven coaching" messaging to marketing
- ✅ Score: 9.7 → 10/10 🎯

**If study inconclusive (<60% improvement):**
- ⚠️ Diagnosis needed: interview users, audit puzzles, check captions
- ⚠️ Score caps at 9.5 (excellent coaching, just unproven)
- ⚠️ Run 2.0 study after fixes (adds 4 weeks to timeline)

