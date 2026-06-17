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
| 2 | **Endgames** | `data/endgames.json` (6 flat lessons) **+** `data/coaching/endgame_theory_tree.json` (7 categories) | 1 each | ❌ **NOT a redundant copy** (content-verified 2026-06-17) — 4/6 concept *names* overlap (opposition, square-rule, Lucena, Philidor) BUT **0 shared FENs**: each file teaches those concepts with completely different positions + lesson shapes (flat `solution_moves` lessons vs tree `rule`+`positions` nodes), feeding different surfaces. Like openings: same concept names, purpose-built different content. A merge would fuse two different lesson sets, not de-duplicate. (Earlier this was confirmed on NAME overlap alone — corrected after the FEN check.) |
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

## Final tally (all 6 content-verified)

**Real redundant-data duplicates worth a merge: NONE.** Every flagged "duplicate" was either a false positive or "same concept *name*, purpose-built different *content*" (different FENs/schemas/surfaces). Verified one by one:

- **Openings** — NOT a content duplicate (sources share only family name). Real pain ("multiple files per new opening") fixed with `scripts/add_opening.py` scaffold (`a7a38737`), not a merge.
- **Endgames** — NOT a content duplicate: 4/6 concept *names* overlap but **0 shared FENs** — different lessons/surfaces. No merge.
- **Traps** — false positive; single-source `traps.json`. Dead theory-tree loader removed (`384fb9b9`).
- **Move severity** — not a file-merge; the known PWC-second-engine divergence (`project_pwc_runs_second_coaching_engine`).
- **ECO names** — different jobs (code-lookup vs free-text collapse).
- **Caption principles** — two-tier (specific catalog + generic fallback); the bank's issue is filler quality.

**Headline:** the Explore-agent audit flagged 6 "duplicates"; on live + content verification, **0 warranted a consolidation merge**. The only genuinely shared thing anywhere was concept *names/identity*. Lesson (now baked into `/single-source-of-truth`): audit hits are HYPOTHESES — verify content (not just names) before scoping. Name-overlap ≠ data duplication.

Each real consolidation: pick canonical → migrate readers → collapse duplicate recognizers/loaders to one → guard test ("adding one item = one file; no reader references a retired source"). **Verify real, signed-off scope, then code.**
