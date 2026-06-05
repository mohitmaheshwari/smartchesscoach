# Artifact-Mastery Cleanup — Scope Document

**Status:** AWAITING MOHIT SIGNOFF + THRESHOLD LOCK (2026-06-06)
**Skill applied:** `/scope-driven-development`, `/lock-via-data` (threshold needs your number)
**Predecessor:** `docs/pwc_mastery_gate_scope.md` Q1 caveat — 749 of 763 `mastered_at` stamps from the 2026-06-04 one-shot backfill

---

## 0. Existing surfaces audit

### What exists today

| Surface | What it does | File |
|---|---|---|
| 2026-06-04 backfill script | One-shot run that walked every analyzed game oldest-first and stamped `mastered_at` whenever the streak math passed at that moment | [`backend/scripts/backfill_concept_mastery.py`](../backend/scripts/backfill_concept_mastery.py) |
| Live analysis hook | Wired in `analysis_worker.py:1171` — every new game runs `update_user_mastery_for_game` automatically | [`backend/analysis_worker.py`](../backend/analysis_worker.py) |
| PWC Mastery Gate | Reads `mastered_at` + `last_violation_at` from `user_concept_understanding` to decide SUPPRESS/DOWNGRADE/SHOW | [`backend/services/pwc_skill_gate.py`](../backend/services/pwc_skill_gate.py) |
| InGameMasteryPanel | Renders mastered tier on `/progress` | [`frontend/src/components/coach/InGameMasteryPanel.jsx`](../frontend/src/components/coach/InGameMasteryPanel.jsx) |

### The problem

The 2026-06-04 backfill stamped `mastered_at` against the streak math AT THE TIME OF THE BACKFILL. Per Mohit's diagnostic curl earlier this session: 46 of 76 concepts on his account showed as "mastered" — far more than reflects organic in-game mastery accumulation.

Concrete signal of artifact-mastery (from prod data):
- `streak_clean: 329` on a concept with `clean_games_total: 166` — the streak counter is decoupled from real game count
- Most `mastered_at` timestamps cluster at `2026-06-04T10:08-10:19` (the backfill window)
- High `violations_total` (e.g. 204) on concepts also showing `mastered_at` — would require many post-violation clean streaks to legitimately master

Result: the gate over-suppresses, MasteryPanel reports false demonstrated counts, and Path C's "≥30% volume drop" target is met by inflation.

### Decision

**EXTEND** the existing concept_mastery_tracker semantics with a one-shot cleanup pass that strips `mastered_at` from rows that don't meet a stricter rule. Future organic events re-master legitimately over the next 2-4 weeks.

**Why EXTEND not REPLACE:** the streak math itself is correct; only the BACKFILL pass that initially populated the table created artifacts. Future games run through the same code path correctly.

---

## 1. What it is

A one-shot script that audits every `user_concept_understanding` row with a `mastered_at` stamp and unstamps the ones that don't meet a stricter "real mastery" rule. The next 2-4 weeks of natural play will re-master the legitimate ones via the live hook.

In plain English: the system was overconfident about what users had mastered because the initial data load was permissive. This pass undoes that overconfidence so the PWC gate only suppresses where the user actually has demonstrated mastery in real games.

---

## 2. What the user sees

**Before cleanup (today on Mohit's account):**
- `/progress` "In-game concept mastery" shows 46 mastered concepts (many they wouldn't recognize as mastered)
- PWC suppresses ~60% of coaching messages (≥30% target inflated)
- MasteryPanel demonstrated overrides may fire on concepts user hasn't truly mastered

**After cleanup:**
- Mastered count drops to whatever survives the stricter rule (estimated 5-15 concepts based on the data shape — those with clear post-violation clean streaks)
- PWC suppress rate falls into the ~20-30% real range
- MasteryPanel demonstrated only renders for concepts with strong organic signal

**Over the next 2-4 weeks:**
- Natural play re-masters legitimate concepts as users accumulate clean streaks
- Numbers stabilize around the steady-state distribution

---

## 3. In scope (V1)

- New script: `backend/scripts/cleanup_artifact_mastery.py`
- Dry-run mode by default — prints what WOULD be unstamped + counts per user
- `--apply` flag triggers actual writes
- Per-row decision logic:
  - Keep `mastered_at` if BOTH conditions hold (Rule R1 — see Q1 below for threshold lock):
    1. `clean_games_total >= TBD_LOCK_clean_min`
    2. `violations_total <= TBD_LOCK_violation_max` OR `clean_games_total >= TBD_LOCK_clean_high_floor` (lots of clean games can overcome a noisy violation history)
  - Strip `mastered_at` otherwise + add `mastery_stripped_at` + `mastery_stripped_reason: "artifact_backfill_cleanup"`
- Idempotent: re-running is a no-op when no new artifact rows exist
- Audit log written to `backend/logs/artifact_mastery_cleanup_YYYY-MM-DD.json` (user_id, concept_id, before_state, after_state)
- Telemetry: per-user before/after mastery counts logged so we can verify the cleanup didn't catastrophically over-strip

---

## 4. Explicitly out of scope (V1)

- **Re-deriving the streak_clean counter** — the 329-on-166 anomaly is real but separate; the cleanup strips `mastered_at` based on visible totals, not on recomputing the streak. Future organic events will re-converge the streak counter.
- **Touching `last_violation_at`** — that field is independently maintained by the live hook and reflects real events even when `mastered_at` is wrong.
- **Migrating concept_id namespace** — out of scope; the 2026-06-05 dead-namespace filter already hides those from the UI/gate.
- **User-facing "your mastery was re-evaluated" message** — too granular for V1. Cleanup is silent; the only user-visible change is the gate becoming less aggressive.
- **Re-running the cleanup on every backfill in the future** — this is a one-shot for the 2026-06-04 backfill artifact. Future backfills should use stricter rules from the start.

---

## 5. Success criteria

**Primary:** after cleanup + 2-4 weeks of organic events, the PWC gate's SUPPRESS rate stabilizes in the ~20-30% range (matching the Path C "≥30% volume drop" target without inflation).

**Secondary tracked:**
- Per-user mastered-count distribution before vs after cleanup (verify cleanup didn't catastrophically over-strip — most users should end with 3-15 mastered concepts, not 0 or 50+)
- Re-master events in the 2-4 weeks post-cleanup (organic events overwrite the stripped stamps)
- Flag rate on PWC coaching (must NOT increase — if it does, the gate is now under-suppressing legitimate cases)

**Explicitly NOT a success metric:**
- "User says it feels better" — subjective
- "Mastered count went down" — a number going down isn't success; HONEST count going down is

---

## 6. Open questions

### Q1. THRESHOLD LOCK — TBD_LOCK_clean_min, TBD_LOCK_violation_max, TBD_LOCK_clean_high_floor

**Why unresolved:** the data is still backfill-dominated. Locking thresholds against backfill-dominated data is the `[[threshold_before_distribution_is_sin]]`.

**Proposed defaults (for your morning review, NOT locked):**

| Threshold | Suggested default | Rationale |
|---|---|---|
| `clean_min` | 5 | Minimum 5 clean games to claim mastery — matches the 5-game graduation contract elsewhere in the codebase |
| `violation_max` | 3 | A concept with >3 historical violations needs more than `clean_min` clean games to overcome the noise |
| `clean_high_floor` | 20 | When violations exceed `violation_max`, require ≥20 clean games (4x the floor) to still claim mastery |

**These are gut numbers** — not data-locked. The script ships with these as defaults but emits a histogram of what WOULD be stripped at each threshold so you can pick informed numbers in the morning.

**Unblocking step:** dry-run the script with default thresholds, look at the histogram, pick locked values, re-run with `--apply`.

### Q2. Should the cleanup also strip rows where `streak_clean` is wildly inconsistent with `clean_games_total`?

The 329-vs-166 anomaly suggests the streak counter has its own bug. Resetting `streak_clean` is conservative but might over-strip cases where the counter is just stale.

**Why unresolved:** root cause of the streak-vs-games disconnect is unknown.
**Default for V1:** don't touch `streak_clean`. Strip only `mastered_at`. Streak counter convergence happens organically over the next 2-4 weeks of analyzed games.

### Q3. Backup before cleanup?

A pre-cleanup snapshot of `user_concept_understanding` could be useful for rollback.

**Default:** YES. Script writes `backend/snapshots/user_concept_understanding_pre_cleanup_YYYY-MM-DD.json` before any `--apply` writes. Restore command: `python backend/scripts/restore_concept_mastery_snapshot.py <snapshot.json>` (separate script, also in this commit).

---

## 7. Pre-code requirements

- [ ] **Q1 threshold values locked** by Mohit after reviewing the dry-run histogram
- [ ] **Q2 decision** — touch streak_clean or not (default: not)
- [ ] **Q3 backup** — confirm snapshot strategy (default: yes, JSON dump)
- [ ] **Dry-run output reviewed** — Mohit confirms the proposed-strip list looks sensible (no false-positive over-strip)
- [ ] **Mohit explicit signoff** on this scope document
- [ ] **Run timing**: cleanup should run during a low-traffic window since it touches the table the live gate reads

After all gates pass: `/audit-pre-code` runs as final check, then the cleanup runs with `--apply`.

---

## Appendix A — implementation note

Two scripts:
1. `backend/scripts/cleanup_artifact_mastery.py` — the cleanup itself
2. `backend/scripts/restore_concept_mastery_snapshot.py` — rollback (separate file for clarity)

Both ship with the scope. The cleanup is wired but NOT auto-run; awaits Q1 threshold lock + `--apply` flag.
