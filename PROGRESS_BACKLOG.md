# Progress Page Backlog — Filed for Future

Items surfaced during the 2026-06-05 Engine 2 deploy session that aren't already covered by a scope document. Each entry is a problem statement, not a fix — design before implementing.

See also: [CAPTION_BACKLOG.md](CAPTION_BACKLOG.md) for caption-voice items, [docs/mastery_panel_cleanup_scope.md](docs/mastery_panel_cleanup_scope.md) for the "Not started" override scope (separate, in active review).

---

## 1. Scholar's Mate lesson evidence modal — RETRACTED 2026-06-05

**Status:** Filed and retracted in the same session. Mohit initially questioned whether the lesson was rendering Scholar's Mate at all, then verified the opponent had actually attempted the mate in the credited games. Detector is doing its job; the PGN-length cosmetic concern was downstream of misreading the data.

Kept as a historical note so the same false alarm doesn't get re-filed.

---

## 2. MasteryPanel "Not started" framing for skills already demonstrated (in scope)

**Status:** Scope doc shipped 2026-06-05 → [docs/mastery_panel_cleanup_scope.md](docs/mastery_panel_cleanup_scope.md). Awaiting Mohit sign-off + 4 open-question decisions before code.

**Symptom:** "Develop your pieces — Not started · Study" rendered on a 165-game player who develops pieces every game. Reads as patronizing.

**Status:** in scope, this entry is just a pointer.

---

## 3. PWC Mastery Gate artifact-mastery cleanup (shipped fix is partial)

**Status:** Filed 2026-06-05. Tonight's `42f4b0be` fix covered the obvious bugs (slipping logic + dead-namespace filtering). The deeper issue remains: 749 of 763 `mastered_at` stamps in `user_concept_understanding` are from the 2026-06-04 one-shot backfill, meaning many "mastered" concepts may not reflect genuine in-game streak accumulation.

**Why filed not fixed:** the Path C scope (`docs/pwc_mastery_gate_scope.md`) explicitly noted this as a V1.1 concern. Cleanup needs `/scope-driven-development` + `/lock-via-data` work to:
- Define the criterion for a "real" mastery (e.g. N actual clean games AFTER the most recent violation)
- Lock the threshold against the actual distribution of clean-game spacing
- Run a one-time cleanup pass that strips `mastered_at` from rows that don't meet the stricter rule
- Let natural events re-master the legitimate ones over 2-4 weeks

**When to design:** ~2 weeks after deploy (let natural events accrue first so the distribution is meaningful, not backfill-dominated).

---

## 4. Game metadata: Dashboard reads wrong field + date_played never set — ✅ DONE

**Status:** ✅ DONE (verified 2026-07-06). Both concerns resolved:
- `date_played`: 10,346 / 10,495 games populated (99%). Backend now
  parses the PGN date at sync time. Recent games show real timestamps.
- `opponent` field: 10,030 / 10,495 populated (96%). Canonical fields
  `white` (100%), `white_player` (100%), `opponent_name` (96%),
  `opponent` (96%) all coexist and are populated.
- Dashboard field mismatch: no longer a blank-Dashboard symptom since
  the canonical fields are set. Verified via audit that ordering by
  `date_played` sorts correctly across the full 43-user cohort.

**Filed 2026-06-06 investigation kept below for reference.**

---

Investigated — NOT the broad "metadata not extracted" I first thought (that was me querying wrong field names).

**Reality:** sync (`journey_service.sync_user_games`) DOES capture player names, under `white_player` / `black_player` / `opponent_name`. The `opponent` / `white` / `black` fields are unused (None). So:
- `GameAnalysis.jsx` (review page) reads `black_player`/`white_player` → correct ✓
- `LabV2.jsx` reads `opponent_name` → correct ✓
- **`Dashboard.jsx` (lines 505/586/978) + `LabV2.jsx:279` read `g.opponent` → blank ✗** (field is None; data is in `opponent_name`)
- **`date_played` is genuinely never populated** — sync doesn't parse the PGN `[Date]` / `[UTCDate]` header.

**Two fix options (needs a decision):**
- **(a) Frontend-only:** change Dashboard.jsx + LabV2:279 to read `opponent_name` (or `opponent || opponent_name`). Minimal, fixes the visible symptom. No backfill.
- **(b) Backend canonical fields:** populate `opponent`, `white`, `black`, `date_played` on the game doc at sync time so every consumer works regardless of field name. More robust, but needs a backfill for existing games (all have None today).

**date_played fix (either way):** in `sync_user_games`, parse the PGN `[UTCDate]`+`[UTCTime]` (or `[Date]`) into `date_played`. The PGN has it (e.g. `[UTCDate "2026.06.06"]`).

**Recommendation:** (b) for opponent/white/black canonical fields + add date_played parsing — one robust fix. Frontend (a) is the quick stopgap if you just want Dashboard names back now.
