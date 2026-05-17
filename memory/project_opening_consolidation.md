---
name: Opening data consolidation
description: Active blocker. Three+ parallel opening data sources (curriculum.json, theory_tree.json, opening_plans.py, OPENING_DATABASE in opening_mastery.py, eco_openings.json) means every opening-related fix has to chase the same change through 4-5 places — and audit-driven point fixes keep tripping over fragmentation. Pick a canonical source, migrate, delete the rest.
type: project
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
ChessGuru has at least **5 parallel opening data sources** that overlap and disagree:

1. `backend/data/opening_curriculum.json` — 9 curated openings, voice-cleaned in Pass 3. Used by `services/opening_theory_note.py` for the per-move PwC opening-theory callout.
2. `backend/data/coaching/opening_theory_tree.json` — 27 openings, broader catalog, less voice-curated. Used by `services/opening_theory_tree_service.py`.
3. `backend/coach_engine/opening_plans.py` — Python literal with per-move "teach" strings keyed by SAN. Used by ... unclear; multiple smart_coaching paths.
4. `backend/services/opening_mastery.py:OPENING_DATABASE` — the in-code dict that powers `detect_opening_from_moves()`. The most-up-to-date detector but its data is in code, not editable.
5. `backend/data/eco_openings.json` — ECO codes mapped to opening names. Used by `opening_detection_service.py`.

**Why this is now an active blocker:** every category of bug fix in the Parth audit (Categories 6, 7, 8) needs to know "is this move in the opening book?" — but each source disagrees about what counts. I shipped `9dec45da` (Category 7 Petrov fix) using only `opening_mastery`'s detector and discovered it returns the broad family ("kings_pawn") for any e4-e5 continuation, so Qh5 gets called book. The detector is correct for what IT does; the gap is that we don't have a single canonical "is this a real book line at this depth" function.

**Why:** When voice-cleaning "minority attack" in Pass 3, I had to edit the term out of 11 separate files because the same content lives in multiple sources. Every iteration on opening data forces a multi-file migration. Every audit-driven fix to one path leaves the other paths inconsistent.

**How to apply:**

When you (future-me) come back to this:

1. **Pick the canonical source.** Recommended: `opening_mastery.py:OPENING_DATABASE` because it's the most actively used by the working detector. Externalise it into a JSON file (`data/openings/canonical.json`) so it can be edited without code changes.

2. **Migrate content** from the other 4 sources into the canonical:
   - Voice-cleaned text from `opening_curriculum.json` (summary, golden_rules, middlegame_plans)
   - Per-move teach strings from `opening_plans.py`
   - Theory tree branches from `opening_theory_tree.json` (the 18 extra openings beyond curriculum's 9)
   - ECO codes from `eco_openings.json`

3. **Update consumers** to read from the canonical:
   - `services/opening_theory_note.py` — currently reads `opening_curriculum.json`
   - `services/opening_theory_tree_service.py` — currently reads `opening_theory_tree.json`
   - `services/opening_curriculum_engine.py` — uses curriculum
   - `coach_engine/opening_plans.py` — replace literal with JSON load
   - `opening_detection_service.py` — uses ECO mapping
   - `services/opening_mastery.py` — replace OPENING_DATABASE literal with JSON load

4. **Delete the redundant sources** after consumers migrated. Verify no live imports.

5. **Add a polyglot opening book reader** as the FINAL precision check. python-chess has built-in support (`chess.polyglot`). A polyglot file (.bin) gives line-level book identification that family-level detectors can't. Use it where precision matters (the cp_loss=50 Qh5-vs-Petrov edge case in `is_book_opening_move`).

**Estimated effort:** 1-2 days focused work. NOT a 30-minute polish item — content reconciliation between 5 sources is the bulk of it. Some openings have inconsistent names/keys/voice across sources that need merging.

**Why this is in `project_` and not `feedback_`:** It's a backlog item, not a behavioural rule. The behavioural rule is already captured in `feedback_no_parallel_surfaces.md` ("don't fragment surfaces"); this memo names the specific fragmentation that needs cleaning.

**Specific consequences this consolidation unblocks:**

- Category 7 false-positive edge (Qh5 called "book" because detector returns family-level match) — polyglot book solves this.
- Long-tail opening coverage (Pirc, Reti, English, Modern) — the 27-opening theory_tree has these but they're not in the curriculum the per-move callout reads from.
- Voice consistency — when curriculum says "Queen's Gambit teaches X" and theory_tree says "Queen's Gambit teaches Y", the surfaces disagree. After consolidation: one source of truth.
- Future opening additions — adding a new opening becomes 1 edit, not 4-5.
