# Duplicate Source-of-Truth Audit — Backend

**Date:** 2026-06-17
**Method:** codebase sweep (Explore agent) for concepts encoded in >1 place. Enforcement principle + procedure: `/single-source-of-truth` skill; standing rule: memory `feedback_single_source_of_truth`.
**ADD-COST** = number of files you must edit to add ONE new item of that concept.

> Note on counts: top-level *opening* counts in the consolidation scope (24 / 28 / 67) are distinct openings; the agent's higher numbers (166 / 97) count nested lesson/line entries. Same sources, different granularity.

## Ranked findings

| # | Concept | Sources | ADD-COST | Verdict |
|---|---|---|---|---|
| 1 | **Traps** | `data/traps.json` (~41) **+** traps nested in `data/coaching/opening_theory_tree.json` | **6+** | DUPLICATE — `trap_library.py` reads one, `verified_opening_traps.py` reads the other; no canonical authority |
| 2 | **Openings** | `opening_curriculum.json` **+** `opening_theory_tree.json` **+** `opening_book.py` `_OPENINGS` (inline) | **3–4 + recognizers** | DUPLICATE — see `opening_source_consolidation_scope.md` |
| 3 | **Move severity thresholds** | `services/severity.py` (canonical, Mohit-locked 2026-05-25) **+** inline per-band thresholds in `realtime_coaching_feedback.py` | **2** | INVESTIGATE — may be a true duplicate OR legitimately different (cp_loss vs eval-delta). Decide + lock or reconcile. |
| 4 | **Endgames** | `data/endgames.json` **+** `data/coaching/endgame_theory_tree.json` | **2** | DUPLICATE — `endgame_teaching.py` vs `endgame_theory_service.py` read different ones |
| 5 | **ECO / opening-name normalization** | `data/eco_openings.json` (reference) **+** hardcoded names in `opening_normalizer.py` | **2** | PARTIAL — normalizer should source canonical names FROM eco_openings.json, not hardcode |
| 6 | **Caption principles** | `data/captions/principle_bank.json` **+** `services/caption_principles.py` (110+ hand-authored dict) | **2–3** | INVESTIGATE — both answer "what principle should this caption teach?"; clarify split or merge |

## Healthy (single source — leave alone, use as the model)

| Concept | Single source | Notes |
|---|---|---|
| Rating bands | `deterministic_coach_service.py` `RATING_BANDS` | 29 readers import it. *Caveat:* `realtime_coaching_feedback.py` hardcodes band-keyed thresholds without importing — see #3. |
| Move categories | `position_facts.py` `MoveCategory` enum | imported by all readers |
| Pattern/puzzle taxonomy | `data/pattern_catalog.json` | ~15 readers, schema-documented |
| Caption RULE templates | `data/captions/*.json` via one loader (`caption_templates.py`) | centralized directory + single loader |

## Recommended order of attack (each = its own scope-driven consolidation)

1. **Openings** — scope already drafted (`opening_source_consolidation_scope.md`). Canonical = FEN-keyed `opening_theory_tree.json`.
2. **Traps** — highest ADD-COST (6+). Pick canonical (likely fold standalone `traps.json` into the opening theory tree, or make `traps.json` canonical and reference from the tree). One trap reader.
3. **Move severity** — quick + high-value: confirm whether `realtime_coaching_feedback.py` should import `severity.py`; reconcile or document+lock the intentional split.
4. **Endgames** — mirror the openings/traps decision (one tree is canonical; deprecate the flat file or make it a view).
5. **ECO normalization** — `opening_normalizer.py` reads names from `eco_openings.json`.
6. **Caption principles** — decide if `principle_bank.json` and `caption_principles.py` are one concept; merge if so.

Each consolidation: pick canonical → migrate readers to it → collapse duplicate recognizers/loaders to one → add a guard test ("adding one item = one file; no reader references a retired source"). Do NOT start any without a signed-off scope.
