# PWC Mastery Gate (Engine 2 Phase 2) — Scope Document

**Status:** SIGNED OFF 2026-06-05 (re-signed after EXPAND finding)
**Skill applied:** `/scope-driven-development` (with Section 0 existing-surfaces audit)
**Predecessor design draft:** [engine2_phase2_mastery_gate.md](engine2_phase2_mastery_gate.md) — earlier sketch, superseded by this scope
**Next skills:** `/lock-via-data` (for any new numeric thresholds) → `/audit-pre-code` (before first file)

---

## 0. Existing surfaces audit

### What exists today

PWC (Play with Coach) is the live-game surface where users play against the engine and get coaching feedback after each move.

| Surface | What it does | File |
|---|---|---|
| PWC main page | Renders the board, plays against Stockfish, surfaces coaching sidebar | [`frontend/src/pages/CoachPlay.jsx`](../frontend/src/pages/CoachPlay.jsx) |
| Coaching sidebar | Shows per-move coaching messages, escape-square quizzes, teaching modes, plan/move guidance | [`frontend/src/components/coach/CoachPlaySidebar.jsx`](../frontend/src/components/coach/CoachPlaySidebar.jsx) (1163 lines) |
| Live coaching engine | Generates per-move feedback when the user makes a move | [`backend/services/realtime_coaching_feedback.py`](../backend/services/realtime_coaching_feedback.py) |
| PWC coaching engine | The "second engine" — PWC's own move-critique + coaching-policy + coaching-voice path (NOT the central caption pipeline) | `backend/coach_play/` directory |
| Existing skill gate scaffold | A function exists but isn't called in production yet | [`backend/services/pwc_skill_gate.py`](../backend/services/pwc_skill_gate.py) |
| Phase 1 mastery data | Per-user × concept mastery state populated daily | `db.user_concept_understanding` (already shipped, 379 mastered + 799 struggling rows across population) |

Env flags ALREADY shipped, ALL default-off:
- `PWC_SKILL_GATE_ENABLED` (this scope's flag)
- `PWC_USE_CENTRAL_CAPTION_PIPELINE` (separate scope — central pipeline migration)
- `PWC_COACH_USE_UCI_ELO` (separate scope — Stockfish strength calibration)
- `PWC_LIVE_OPENING_NUDGE_ENABLED` (separate scope — real-time opening guidance)

### What it already provides

PWC ALREADY generates per-move coaching feedback. The current generation is **identical for every user** — it doesn't know what the user has mastered. So a user who has demonstrated piece safety 50 times still gets full "watch your pieces" coaching, and a user who has never seen rule-of-the-square also gets the same generic level of explanation.

Phase 1 already wrote the data (per-user × concept mastery state). The gate scaffold function already exists. **What doesn't exist is the actual wiring + activation.**

### Genuine gap this scope fills

| Dimension | PWC today | What this scope adds |
|---|---|---|
| User-state awareness | None — same coaching for every user | Reads `user_concept_understanding` before generating the message |
| Mastered concepts | Coached repeatedly | SUPPRESSED (no message, just the move) |
| Slipping concepts (was mastered, recent violation) | Coached repeatedly | DOWNGRADED to brief reminder |
| Learning concepts (mid-streak) | Full coaching | Full coaching (no change) |
| Unseen concepts | Full coaching | Full coaching (no change) |

### Decision

**EXTEND** existing PWC live coaching. Not a parallel surface, not a replacement. We're inserting one check (the gate) at the existing emission point in PWC's coaching engine. Same file layout, same UI shell, same coaching messages — but now informed by what the user has demonstrated.

PARALLEL was rejected because PWC already has a live coaching surface; adding a second one would split the user's attention. REPLACE was rejected because the existing coaching engine has lots of state and detector logic worth preserving — the gate sits BEFORE the emission, not in place of the generation.

### What is NOT in this scope (separate doc each, future)

The other three PWC env flags address different gaps and ship as separate scope docs:
- `PWC_USE_CENTRAL_CAPTION_PIPELINE` — migrate PWC's "second engine" onto the same central caption pipeline V5 uses (one source of truth refactor)
- `PWC_COACH_USE_UCI_ELO` — replace Stockfish skill-level with UCI_Elo for more realistic opponent strength
- `PWC_LIVE_OPENING_NUDGE_ENABLED` — real-time opening guidance during the opening phase

This scope covers ONLY `PWC_SKILL_GATE_ENABLED` activation + its supporting wiring.

---

## 1. What it is

PWC's coaching becomes user-state-aware. Today, every user gets the same coaching for the same mistake. After this ships, PWC checks what the user has demonstrated they know before deciding how loudly to teach.

In plain English:
- A user who has consistently handled rule-of-the-square across many endgames doesn't get a full rule-of-the-square lesson when it comes up — they get silence, or at most a quick reminder.
- A user who keeps falling for the same pattern gets full coaching every time, because they haven't learned it yet.
- The coaching messages themselves don't change. The DECISION TO SHOW THEM changes based on the user's history.

The user notices: *"the coach is paying attention to me, not just to the position."* That's the differentiation versus every chess-coaching product that re-teaches the same lessons regardless of who's playing.

---

## 2. What the user sees

### For a user with `END_RULE_OF_SQUARE` mastered (Mohit, today)

**Before (current behavior):**
```
[in PWC, after a king-and-pawn-race move]

   Coach: This is a "rule of the square" position.
          Count the squares from your king to the
          queening square. If the count is...
          [200 more words]
```

**After this scope ships:**
```
[in PWC, after the same move]

   [no coaching message — the move just shows]
```

(Mohit has handled rule-of-the-square in 18 clean games with 1 historical violation. The coach trusts him on this.)

### For a user with `TAC_CHANGED_AFTER_MOVE` struggling (Mohit, also today)

**Before:**
```
[in PWC, after missing what the opponent's last move changed]

   Coach: Watch out — the opponent's last move
          attacked a piece you weren't tracking.
          [explanation continues]
```

**After this scope ships:** identical — full coaching. He's struggling (299 violations across 340 games), no suppression.

### For a user who was MASTERED but recently slipped

```
[in PWC, after a small mistake on a concept they used to handle]

   Coach: Quick check on piece safety here.
```

(One brief sentence instead of the full lesson. The "slipping" state — fresh violation after prior mastery — gets a reminder, not a re-teach.)

### What stays the same

- The PWC board, the sidebar, the move history, the engine opponent
- The coaching messages themselves — no rewriting, no LLM polish, no new content
- The teaching modes (traps, endgames, escape squares)
- All existing flows

The user-visible change is **strictly subtractive on coaching volume**, not additive on new features. This is the "subtractive at small N" caveat — at 50 users, the cost is invisible. The benefit lands when a user notices the coach stopped repeating itself.

---

## 3. In scope (V1)

- **Tag PWC coach-typed messages with `concept_key`** (the EXPAND) — extend `coaching_policy` so every emitted coaching message carries the concept it's about
- Wire `services/pwc_skill_gate.py.gate_decision()` into PWC's per-move coaching emission path
- For each concept tagged on a coaching message, call the gate to decide SUPPRESS / DOWNGRADE / SHOW (`learning` and `unseen` collapse into SHOW)
- For DOWNGRADE, emit a brief reminder template per family (TAC_ / OP_ / MID_ / END_ / DEF_) — about 6-8 words each
- Behind env flag `PWC_SKILL_GATE_ENABLED`, default off, A/B rollout: 0% → Mohit's own session → 10% cohort → 50% → 100%
- Per-decision telemetry: log `{user_id, concept_id, mastery_state, gate_decision}` to a new `pwc_skill_gate_events` collection
- Cohort assignment via stable user-ID hash; `users.skill_gate_cohort` field set at first session post-rollout
- `slipping` definition: `mastered_at IS NOT NULL` AND violation within last 10 games (Q1 locked)

---

## 4. Explicitly out of scope (V1)

- **PWC central caption pipeline migration** — separate flag, separate scope doc, separate ship
- **Live opening nudge** — separate flag, separate scope doc
- **UCI_Elo coach strength calibration** — separate flag, separate scope doc
- **Opening-mastery gate** — only CONCEPT mastery (`user_concept_understanding`) is consulted in V1. The analogous gate for opening mastery (`user_opening_mastery`) is a V2 add.
- **Trap mastery gate** — only 1 user has any traps_fallen_for data. No gate.
- **Engine-side teaching mode changes** — the trap/endgame/escape-square teaching flows are untouched
- **V5 caption pipeline integration** — that's the "post-game review" side. This scope is PWC live only. The V5 hook is a parallel feature.
- **Custom DOWNGRADE messages per concept** — V1 uses family-level templates (one per TAC_/OP_/etc.). Per-concept polish is V2.
- **User-facing toggle** ("I'd like more coaching even on things I've mastered") — not in V1. Single behavior, rollout via env flag only.
- **Outcome tracking** — does the gate change long-term user behavior? Out of scope until ship + observe.

---

## 5. Success criteria

**Primary:** PWC coaching volume per session drops for users with high mastery counts, AND those users don't increase their flag-rate on PWC coaching ("I wanted that explanation"). Specifically:
- Users in treatment cohort with ≥10 mastered concepts see ≥30% fewer per-session coaching messages than control cohort
- Flag rate on PWC coaching does NOT increase in treatment cohort (controls for "we suppressed something they wanted")

Why two metrics: the gate's value is "less noise"; the risk is "less help when help was wanted." Both must move in the right direction.

**Secondary tracked (no targets in V1):**
- Per-concept SUPPRESS rate across user cohort (which concepts are being suppressed most — sanity check the mastery data)
- DOWNGRADE rate vs SUPPRESS rate (curiosity)
- Average decision time per move (must stay <5ms or the gate slows the live experience)

**Explicitly NOT a success metric:** "users tell us the coach feels smarter." Subjective, unmeasurable, prone to confirmation bias.

---

## 6. Open questions

### Q1. What's the threshold for `slipping` vs back-to-`learning`? [LOCKED 2026-06-05]

**LOCKED: N=10 games.** A user is `slipping` if they have a `mastered_at` timestamp on the concept AND have a violation within the last 10 of their games.

Probe ran across all `user_concept_understanding` rows with `mastered_at` set:
- 83% (10/12 measured concepts) had any post-mastery violation appear within 10 games
- Tail (median spacing for those that recurred) sat at ~6 games — 10 covers the cliff with margin
- Cap at 10 because beyond that we're outside the "recent" intuition

**Caveat:** 749 of 763 `mastered_at` stamps are from a one-shot backfill on 2026-06-04. Steady-state spacing data will accrue over the next 2-4 weeks of natural events. Re-measure then; expect the locked threshold to shift modestly. V1 ships with N=10; V1.1 will re-derive.

### Q2. DOWNGRADE message bank — author 5 (one per family) or skip and SUPPRESS even on slipping?

The 5 brief reminder strings (one per TAC_/OP_/MID_/END_/DEF_) need to be authored.

- **Why unresolved:** not yet written
- **Unblocking step:** author 5 strings (10 minutes), or decide SUPPRESS-only V1 (skip DOWNGRADE entirely)

### Q3. Cohort assignment — sticky user hash or session-level?

Sticky-by-user-ID gives clean A/B. Session-level could surface inconsistent behavior to the same user.

- **Why unresolved:** small choice not yet made
- **Unblocking step:** default to sticky-by-user-ID hash; session-level only if cohort assignment lags first session

### Q4. PWC coaching messages currently come from the "second engine" — does the gate need to know which concept_id is on the message? [EXPAND, LOCKED 2026-06-05]

**EXPAND: yes, and the scope grows by one file to do it.**

Probe finding: only 21% of recent `coach_messages` carry ANY concept tag (`concept_key`, `rule_id`, or `concept` free-text). Strict machine-readable `concept_key` is at 11%. The fields I originally listed in this scope (`principle_id_used`, `plan.concept_id`, `caption_facts_principles_violated`) **don't exist** on `coach_messages` — those are V5/post-game-review fields. PWC uses its own taxonomy.

**Concrete expand:** V1 now also writes `concept_key` on every coach-typed message that comes out of PWC's `coaching_policy` path. That's one file's worth of edit (`backend/coach_play/coaching_policy.py` plus wherever `coaching_voice` finalizes the message). Without this, the gate has no key to look up mastery on — it would return SHOW for 79% of messages, defeating the point.

Family taxonomy: PWC's existing `concept_key` strings already map to `TAC_*`, `OP_*`, `MID_*`, `END_*`, `DEF_*` — no new naming required. Just ensure the field is populated where it's currently null.

V1 now contains both the gate AND the tagging that the gate depends on.

---

## 7. Pre-code requirements

- [ ] **Mongo on port 27018 is reachable** — needed for the cohort hash + mastery lookups during testing
- [ ] **Q1 threshold locked** via `/lock-via-data` (slipping definition: games-based, not time-based)
- [ ] **Q2 decision** — author 5 DOWNGRADE strings, OR ship SUPPRESS-only V1
- [ ] **Q4 verification** — measure what % of PWC messages have a concept_id; if too low, expand scope or defer
- [ ] **`users.skill_gate_cohort` field** added to user schema (small migration)
- [ ] **`pwc_skill_gate_events` collection** created (telemetry storage)
- [ ] **Mohit explicit signoff** on this scope document — explicit "lock this and code", not implicit "sounds good"

After all gates pass: `/audit-pre-code` runs as final check, then implementation begins.

---

## Appendix A — what gets built (for reference, not part of scope contract)

**Backend:**
- `services/pwc_skill_gate.py` — extend existing scaffold with `get_mastery_state(db, user_id, concept_id)` that returns `{mastered, slipping, learning, unseen}` + `gate_decision(state) -> {SUPPRESS, DOWNGRADE, SHOW}`
- `services/realtime_coaching_feedback.py` — call `pwc_skill_gate.gate_decision()` before emitting each coaching message; honor the decision
- `db.pwc_skill_gate_events` — new collection for per-decision telemetry
- `db.users.skill_gate_cohort` — new field (control / treatment)

**Frontend:**
- No new components. The gate is a backend-only intervention; the UI only sees fewer / shorter messages.

**Env flag:**
- `PWC_SKILL_GATE_ENABLED` already exists, default-off. Rollout: 0% → Mohit-only → 10% → 50% → 100% over 2-3 weeks.

**Rollback:** flip the env flag to false. All gating disappears, behavior reverts. The `pwc_skill_gate_events` collection stays (read-only history); the user cohort field stays (no-op).

The appendix is descriptive, not contractual. Sections 0–7 are the contract.
