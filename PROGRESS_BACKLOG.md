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
