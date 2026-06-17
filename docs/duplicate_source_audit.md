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
| 2 | **Endgames** | `data/endgames.json` (6 flat lessons, each w/ `setup_fen`) **+** `data/coaching/endgame_theory_tree.json` (7 categories, ~18 lessons) | 2 | ✅ **CONFIRMED partial duplicate** (verified 2026-06-17) — 4 of 6 concepts taught in BOTH with separate, drift-prone content: opposition↔opposition, rule_of_square↔square_rule, lucena_position↔lucena, philidor_position↔philidor. Flat file uniquely has 2 basic mates; tree uniquely has ~14 concepts. **Two reader sets:** flat → endgame_teaching/PWC coach_play/postgame/caption_principles; tree → endgame_theory_service/teaching_engine catalog/training_advanced/concept_mastery. Worth a scope (canonical = the richer **theory tree**; fold the 2 mates in; repoint flat-file readers; deprecate `endgames.json`). Lower priority than openings. |
| 3 | **ECO / opening-name normalization** | `data/eco_openings.json` (440, code→name) **+** `opening_normalizer._PRIORITY_MATCHES` (~30, keyword→family) | 1 each | ❌ **NOT A DUPLICATE** (verified 2026-06-17) — different jobs/keys: eco = ECO-code lookup; normalizer = free-text→family collapse. Adding a code edits one; adding a collapse rule edits the other. No dual-edit-for-one-fact. Mild name overlap only. |
| 4 | **Caption principles** | `data/captions/principle_bank.json` (generic, phase-bucketed fallback) **+** `services/caption_principles.py` (~110 specific, id-keyed) | 1 each | ❌ **NOT A DUPLICATE** (verified 2026-06-17) — two-tier design: specific id-keyed catalog vs generic phase-bucket fallback. Different keys/roles, no dual-edit. (Bank's real issue is filler *quality*, not duplication — see `feedback_principle_bank_is_filler`.) |
| — | ~~**Traps**~~ | `data/traps.json` (54) | **1** | ❌ **FALSE POSITIVE** — `traps.json` is the SINGLE source. Both `trap_library.py` and `verified_opening_traps.py` read it (the latter via `_load_traps_from_library_json`, wired 2026-06-09). The `opening_theory_tree.json` trap branch loads **0** (vestigial dead code). Adding a trap = edit `traps.json` only. *Optional tidy:* delete the dead `_load_traps_from_json()` theory-tree branch that misled this audit. |
| — | ~~**Move severity**~~ | `severity.py` (cp_loss tiers) **+** `realtime_coaching_feedback._classify_move_quality` (eval-delta, rating-band) | n/a | ⚠️ **NOT A SIMPLE DUPLICATE** — two genuinely different models (cp_loss caption tiers vs the rating-aware eval-delta differentiator). Their divergence is the already-documented **PWC-second-engine** issue (`project_pwc_runs_second_coaching_engine`), not a file merge. |

## Healthy (single source — leave alone, use as the model)

| Concept | Single source | Notes |
|---|---|---|
| Rating bands | `deterministic_coach_service.py` `RATING_BANDS` | 29 readers import it. *Caveat:* `realtime_coaching_feedback.py` hardcodes band-keyed thresholds without importing — see #3. |
| Move categories | `position_facts.py` `MoveCategory` enum | imported by all readers |
| Pattern/puzzle taxonomy | `data/pattern_catalog.json` | ~15 readers, schema-documented |
| Caption RULE templates | `data/captions/*.json` via one loader (`caption_templates.py`) | centralized directory + single loader |

## Final tally (all 6 verified)

**Real duplicates worth consolidating (2):**
1. **Openings** — the one HIGH-priority duplicate. Scope drafted (`opening_source_consolidation_scope.md`). Canonical = FEN-keyed `opening_theory_tree.json`. **Ready for sign-off.**
2. **Endgames** — ✅ verified real but partial (4/6 concepts in both), lower priority. Scope when ready: canonical = `endgame_theory_tree.json`; fold the 2 unique basic mates in; repoint flat-file readers (PWC/postgame/captions); deprecate `endgames.json`.

**Verified away — NOT harmful duplicates (4):**
- **Traps** — false positive; single-source (`traps.json`). Dead theory-tree loader removed 2026-06-17 (`384fb9b9`).
- **Move severity** — not a file-merge; the known PWC-second-engine divergence (`project_pwc_runs_second_coaching_engine`).
- **ECO names** — different jobs (code-lookup vs free-text collapse).
- **Caption principles** — two-tier (specific catalog + generic fallback); the bank's issue is filler quality, not duplication.

**Headline:** of 6 agent-flagged "duplicates," only **2 were real** and only **1 is high-priority**. The audit over-flagged 4×. Lesson (now in the `/single-source-of-truth` skill): treat audit hits as hypotheses; verify live before scoping.

Each real consolidation: pick canonical → migrate readers → collapse duplicate recognizers/loaders to one → guard test ("adding one item = one file; no reader references a retired source"). **Verify real, signed-off scope, then code.**
