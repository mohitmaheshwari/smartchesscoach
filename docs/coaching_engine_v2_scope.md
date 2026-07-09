# ChessGuru Coaching Engine v2: Scope

## 0. Existing Surfaces Audit

**Finding: This is primarily an EXTENSION initiative, not a parallel feature.**

### Existing surfaces that touch coaching/personalization:

1. **Play with Coach** (`/play-with-coach`, CoachPlay.jsx)
   - Shows real-time move-by-move feedback after each user move
   - Currently: Generic coaching by rating band (no player-specific hooks)
   - Will receive: Session Goal, Pre-move teaching prototype, Focus Areas, Post-game Story, Early Profile

2. **Lab page** (`/lab`, LabV2.jsx)
   - Shows Coach's Pick (best unreviewed game via decay model)
   - Shows pattern buttons ("Practice X puzzles")
   - Currently: Works; will remain (no changes needed)

3. **Training page** (`/training/pattern/:pattern`, TrainingNew.jsx)
   - Shows puzzles extracted from user's mistakes
   - Currently: No mastery signal (solves are counted but don't close the loop)
   - Will receive: Behavior-change validation + mastery gate

4. **Game Analysis** (`/game/:gameId`)
   - Shows move-by-move analysis with cognitive gaps
   - Currently: Rich data; only shown in review, not in-game
   - Will receive: Gap accuracy fixes (piece_safety over-fire, king_safety endgame confusion)

5. **Journey page** (`/journey`)
   - Shows player identity ("You're aggressive when winning", "You leak time in endgames")
   - Currently: Computed correctly; only visible on Journey page
   - Will receive: Wire into Play with Coach (session goals, pre-move context)

### Overlap Analysis

| Component | Current Owner | V2 Enhancement |
|-----------|---------------|-----------------|
| Move feedback | Play with Coach | Add pre-move teaching + session goal context |
| Pattern decay | Lab + Training | Validate it works; add mastery signal |
| Player identity | Journey page | Wire into Play with Coach |
| Gap accuracy | Game Analysis | Fix detection algorithm |
| Coaching brain | Deterministic coach service | Add prediction layer |

**Decision:** This is EXTENSION across 3 surfaces (Play with Coach, Training, Game Analysis) + backend (gap accuracy, behavior validation). No new UI surfaces needed. V1 wires existing pieces together and fixes data quality.

---

## 1. What It Is

ChessGuru Coaching Engine v2 transforms the platform from a **generic analysis tool with personalization aspirations** into a **personalized coaching system where the coach knows you, adapts to you, and proves you're getting better.**

The core change: the coach becomes a conversation partner, not a loudspeaker. It:
- Tells you what to focus on TODAY before you play (session goal)
- Warns you mid-game when you're about to repeat a pattern
- Closes the loop: mistakes → training → measures whether you stopped making them
- Treats you as an individual learner, not a rating band

Success looks like: a 1100-rated player comes back because the coach got them right, and a 1600-rated player plays more games because the pre-move teaching prevents the same blunders happening twice.

---

## 2. What the User Sees

### Current State (5.5/10)

**Play with Coach, move 5:**
```
Your move: Nf3
--
Nf3 is a good developing move. Brings your knight to the center.
Next, look for tactical opportunities.
```
*(Generic. Could apply to anyone.)*

### V2 State (10/10)

**Play with Coach, move 5:**
```
Session Goal: Slow down before attacking.
Watch your king safety — you tend to leave it exposed when attacking.
```
*(Then user plays Nf3)*
```
Good move. Safe development.

⚠️ Two moves ahead: Don't open lines toward your king.
```
*(Later, user is about to push e4 prematurely)*
```
Hold on — this is where you usually attack early without checking back rank.
Your king is on g1, opponent has a rook on d-file. Safe first?
```
*(User reconsiders, plays a safer move)*

**After game:**
```
Session goal met: You checked king safety 4 times before attacking.
That pattern (piece_safety > tactical_outlook) is improving.
Puzzles from your games → Next session goal: Endgame technique.
```

### What changed

1. **Before game:** Coaching tells you what to work on (session goal from player_identity)
2. **During game:** Coaching warns you before you blunder (pre-move prediction)
3. **After game:** Coaching tells you whether you improved (behavior-change validation)
4. **No more generic:** Every message references your specific patterns

---

## 3. In Scope (V1)

- [ ] Fix cognitive_gap accuracy
  - [ ] piece_safety: filter incidental-pawn hangs (engine punishment only)
  - [ ] king_safety: complete queens-off backfill
  - [ ] Exclude low-confidence categories from coaching (piece_activity, calculation_depth)
  - [ ] Target: ~70% accuracy (vs current ~50%)

- [ ] Wire player_identity into Play with Coach (6 v1 capabilities)
  - [ ] Session Goal: display player's top focus area + reason (from identity_engine)
  - [ ] Pre-move teaching prototype: coach speaks BEFORE move if you're in a risky position
  - [ ] Focus Areas sidebar: show top 3 patterns you're working on
  - [ ] Accountability: "Today's goal: X. Did you do it?" post-game
  - [ ] Post-game Story: coach reflects on session ("You avoided attacks 3x this game")
  - [ ] Early Profile: render identity at game 3-5 (not game 20)

- [ ] Behavior-change validation (L4 gate)
  - [ ] Measure: do users who train on a pattern reduce that mistake in future games?
  - [ ] Run on 20 users, 3-month window, 2-3 patterns per user
  - [ ] Success: mistake-rate drops 20-30% post-training for ≥60% of pattern-user pairs
  - [ ] If fails: diagnose blocker (puzzle difficulty? training not seen? pattern mislabeled?)

- [ ] Pre-move prediction (foundation only, not full UX)
  - [ ] Implement prediction layer in coach_play/coach_opponent.py
  - [ ] Detect board position matches player's known risk zone (e.g., "king safety in tactics")
  - [ ] Flag before-move (model ready, UX blocked on behavior-change validation results)
  - [ ] Test on bhutramohit (62 games) and shobhit (similar profile): does prediction surface patterns they actually make?

- [ ] Testing & validation
  - [ ] Unit tests for gap-accuracy fixes (20+ test cases per category)
  - [ ] Integration test: play 10 full games, verify session goals are displayed
  - [ ] Behavior-change analysis: full audit + write report
  - [ ] Real-user test on bhutramohit & shobhit: does coaching feel personal?

- [ ] Documentation
  - [ ] Update coaching_presence_scope.md with v1 completion status
  - [ ] Document pre-move prediction API (for future UX teams)
  - [ ] Add behavior-change audit results to coaching rationale docs

---

## 4. Explicitly Out of Scope (V1)

- **Full pre-move UX:** Model is ready; UI/UX surface ships after behavior-change validation
- **Opponent adaptation:** Coach doesn't yet adapt engine difficulty based on your weaknesses (e.g., "you hang pieces, so I'll punish captures"). Deferred to v2.1.
- **Opening trap teaching mid-game:** Trap library exists; triggering during real games deferred pending opening_recognizer accuracy audit
- **Theme classifier labels:** Cards won't show theme badges (e.g., "🎯 Tactical Oversight") — backlog item, requires separate NLP training
- **Community cohort baselines:** Personalization won't yet compare your patterns to similar-rated players (e.g., "you blunder on king safety 40% more than the 1200 cohort")
- **Automated intensity loop refinement:** The 5-level intensity system (miss/execute → ±1) won't auto-adjust yet; manual oversight remains
- **Mastery certification:** No "you've beaten piece_safety" badge/lock yet. Behavior-change validation must inform this.

---

## 5. Success Criteria

All must be met for V1 to count as shipped:

1. **Coaching Accuracy:** Cognitive_gap detection accuracy improves from ~50% to ≥70% across piece_safety, king_safety, missed_tactic, tactical_oversight
   - Measured: Manual audit of 100 user moves, compare system-labeled gap vs. Stockfish diagnosis + coach judgment

2. **Personalization Adoption:** Session goals appear in ≥80% of Play with Coach games for active users
   - Measured: analytics ping on "session goal rendered"

3. **Player Alignment:** On real users (bhutramohit, shobhit), does the system identify their top 2 patterns correctly?
   - bhutramohit: if system says "piece_safety > tactic_oversight", verify against their last 10 games' actual gaps
   - shobhit: same test
   - Success: ≥1 user agrees with top-2 pattern list (informal poll)

4. **Behavior Change Hypothesis Validated:** Puzzle training reduces target pattern in ≥60% of cases
   - Measured: 20-user, 3-month audit; for each user's top pattern, track mistake-count before/after training
   - Success: ≥12 of 20 users show 20%+ drop in mistake-count post-training

5. **Pre-move Prediction Accuracy:** Prediction layer detects upcoming mistakes with ≥60% precision
   - Measured: 10 full games, count "coach warned before blunder" vs. "missed it" vs. "false positive"
   - Success: ≥6 of 10 games have at least one valid pre-move warning

6. **Coaching Rating:** Platform moves from 5.5/10 to ≥8.5/10 in blind re-audit
   - Audit: same methodology as prior (COACHING_QUALITY, DATA_PIPELINE, UX, PERSONALIZATION, ENGAGEMENT)
   - Success: ≥2 of 5 dimensions improve by ≥1 point

---

## 6. Open Questions

| Question | Why Unresolved | Unblocking Step |
|----------|----------------|-----------------|
| How many games does a player need before identity is stable? | Current data: game 3-5 identified patterns; but sample was tiny. Needs larger audit. | Audit 50+ users: at what game count does top-3-pattern list stabilize? (Recommend 10-game threshold for v1) |
| Does "mystery pattern" detection (player.player_identity.unknown_gaps) surface new weaknesses? | Not yet used in coaching; unclear if useful. | Query 20 users: count how often top unknown_gap matches next-week's real mistakes. If ≥50%, wire in; else deprioritize. |
| Which cognitive_gap categories can we safely exclude from coaching? | piece_activity, calculation_depth, pawn_structure are low-confidence (≤50% accuracy). Including them confuses users. | Run audit: for each low-confidence category, measure user-disagreement rate. Exclude any >40% disagreement. |
| Does puzzle difficulty progressively improve mistake-reduction, or is one level enough? | Current: puzzles are difficulty-ranked, but training doesn't dynamically scale. | A/B test on 20 users: fixed difficulty vs. adaptive difficulty. Does adaptive improve recovery? (May defer if not significant.) |
| How do we handle the "flat weakness profile" finding? | Finding: 600-1500 players often make ≥3 mistake types equally. So saying "focus on piece_safety" is true but not differentiating. | Strategy design: Instead of "here's your #1 pattern," try "today we're focusing on piece_safety (your 2nd-biggest leak); tomorrow we'll tackle tactics." Coaches rotate, not rank. Requires messaging change. |

---

## 7. Pre-Code Requirements

**All items below must be true before the first line of code is written:**

- [ ] **Mohit has signed off on this scope document.** Explicit: "locked", "ship it", or "go code"
- [ ] **Section 0 decision is confirmed:** EXTENSION (not parallel feature) approved
- [ ] **Cognitive_gap audit findings are filed in CAPTION_BACKLOG.md** with concrete fix specs (not vague)
- [ ] **player_identity_engine is confirmed working** on real users (test: pull identity for bhutramohit, verify it matches reality)
- [ ] **Backend routes for session goals exist** (or placeholder exists for coaching_brain to fill in later)
- [ ] **Pre-move teaching API is designed** (input: board state + user's pattern history; output: warning text or null). Documented, not coded yet.
- [ ] **Behavior-change audit sample is locked:** 20 users, 3-month window, 2-3 patterns per user identified (list provided before code starts)
- [ ] **Frontend Session Goal rendering location is chosen** (Play with Coach sidebar, top banner, modal?) — mockup approved by Mohit
- [ ] **Test data is ready:** bhutramohit and shobhit are designated real-world validators (Mohit confirms they're still active)

---

## Summary

| Dimension | V1 Delivers |
|-----------|------------|
| **Rating target** | 5.5/10 → 8.5/10 |
| **Duration** | ~6-8 weeks (4 phases, 2 weeks each + 2-week buffer) |
| **Primary surfaces changed** | Play with Coach, Training (behavior-change), Game Analysis (gap accuracy) |
| **New surfaces** | None; all enhancements to existing |
| **Risk level** | Medium (depends on cognitive_gap accuracy fix working) |
| **Real-world validation** | bhutramohit, shobhit (informal feedback); 20-user behavior-change audit (formal) |

---

**AWAITING MOHIT SIGNOFF before any code is written.**

Once locked, next steps:
1. Run `/lock-via-data` on the numeric criteria (70% accuracy gate, 20-30% mistake-rate drop, 60% precision)
2. Run `/audit-pre-code` on the pre-code requirements checklist
3. Begin Phase 1: Cognitive_gap accuracy fixes
