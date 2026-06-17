# Duplicate Source-of-Truth Audit — Backend

**Date:** 2026-06-17
**Method:** codebase sweep (Explore agent) for concepts encoded in >1 place. Enforcement principle + procedure: `/single-source-of-truth` skill; standing rule: memory `feedback_single_source_of_truth`.
**ADD-COST** = number of files you must edit to add ONE new item of that concept.

> ⚠️ **Audit findings are HYPOTHESES, not facts.** This register was first produced by an Explore agent and **over-flagged**. Live verification (loading each source in the container) corrected several. **Always verify a duplication live before scoping it** — the `/single-source-of-truth` skill's "distinguish real duplicate from legitimate concern" step exists for exactly this. Verified status below.

> Note on counts: top-level *opening* counts (24 / 28 / 67) are distinct openings; the agent's higher numbers (166 / 97) counted nested lesson/line entries.

## Ranked findings (post-verification)

| # | Concept | Sources | ADD-COST | Verified verdict |
|---|---|---|---|---|
| 1 | **Openings** | `opening_curriculum.json` (24) **+** `opening_theory_tree.json` (28) **+** `opening_book.py` `_OPENINGS` (67, inline) | **3–4 + recognizers** | ✅ **REAL** — three populated lists, different recognizers. Scoped → `opening_source_consolidation_scope.md`. |
| 2 | **Endgames** | `data/endgames.json` (6 flat lessons) **+** `data/coaching/endgame_theory_tree.json` (7 categories) | 2 | ❓ **UNCONFIRMED** — different *structures* (flat named lessons vs category tree). Verify FEN/content overlap before calling it a duplicate; may be legitimately different teaching organizations. |
| 3 | **ECO / opening-name normalization** | `data/eco_openings.json` (reference) **+** hardcoded names in `opening_normalizer.py` | 2 | ❓ **PARTIAL/UNVERIFIED** — normalizer *should* source canonical names FROM eco_openings.json rather than hardcode. Verify before scoping. |
| 4 | **Caption principles** | `data/captions/principle_bank.json` **+** `services/caption_principles.py` | 2–3 | ❓ **UNVERIFIED** — do both answer "what principle?" Check overlap before scoping. |
| — | ~~**Traps**~~ | `data/traps.json` (54) | **1** | ❌ **FALSE POSITIVE** — `traps.json` is the SINGLE source. Both `trap_library.py` and `verified_opening_traps.py` read it (the latter via `_load_traps_from_library_json`, wired 2026-06-09). The `opening_theory_tree.json` trap branch loads **0** (vestigial dead code). Adding a trap = edit `traps.json` only. *Optional tidy:* delete the dead `_load_traps_from_json()` theory-tree branch that misled this audit. |
| — | ~~**Move severity**~~ | `severity.py` (cp_loss tiers) **+** `realtime_coaching_feedback._classify_move_quality` (eval-delta, rating-band) | n/a | ⚠️ **NOT A SIMPLE DUPLICATE** — two genuinely different models (cp_loss caption tiers vs the rating-aware eval-delta differentiator). Their divergence is the already-documented **PWC-second-engine** issue (`project_pwc_runs_second_coaching_engine`), not a file merge. |

## Healthy (single source — leave alone, use as the model)

| Concept | Single source | Notes |
|---|---|---|
| Rating bands | `deterministic_coach_service.py` `RATING_BANDS` | 29 readers import it. *Caveat:* `realtime_coaching_feedback.py` hardcodes band-keyed thresholds without importing — see #3. |
| Move categories | `position_facts.py` `MoveCategory` enum | imported by all readers |
| Pattern/puzzle taxonomy | `data/pattern_catalog.json` | ~15 readers, schema-documented |
| Caption RULE templates | `data/captions/*.json` via one loader (`caption_templates.py`) | centralized directory + single loader |

## Recommended order of attack (post-verification)

1. **Openings** — the one CONFIRMED clean duplicate. Scope drafted (`opening_source_consolidation_scope.md`). Canonical = FEN-keyed `opening_theory_tree.json`. **Ready for sign-off.**
2. **Endgames** — first VERIFY content overlap (do the 6 flat lessons duplicate positions in the 7-category tree?). Only scope if overlap is real.
3. **ECO normalization** — VERIFY, then likely a small fix: `opening_normalizer.py` reads canonical names from `eco_openings.json` instead of hardcoding.
4. **Caption principles** — VERIFY whether `principle_bank.json` and `caption_principles.py` encode the same thing before scoping.

**Not on the list (verified away):**
- **Traps** — false positive; already single-source (`traps.json`). Optional 5-min tidy: delete the dead `_load_traps_from_json()` theory-tree branch.
- **Move severity** — not a file-merge; it's the known PWC-second-engine divergence (already memorialized). Handle there, not here.

Each real consolidation: pick canonical → migrate readers → collapse duplicate recognizers/loaders to one → guard test ("adding one item = one file; no reader references a retired source"). **Verify the duplication is real, then get a signed-off scope, before any code.**
