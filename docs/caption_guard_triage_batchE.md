# Caption-source guard triage — Batch E (13 files)

Covers the first 13 files investigated during the caption-source guard
backlog triage (2026-08-07), originally run before the batch A-D split.
Written to disk after the fact since the spawning agent did not persist
this itself — reconstructed verbatim from its returned report.

---

**1. `backend/services/coaching_puzzle_service.py`** — **REAL_VIOLATION_LOW_RISK**
`CoachingPuzzleService` is instantiated live in `routes/training.py` (`GET /training/prescribed/{weakness}`). `get_prescribed_training()` (line 166) calls `_get_puzzles_from_user_games()` (produces line 440's `context_line`) and unconditionally calls `_get_coaching_context()` (lines 839, 841) for every returned puzzle. This is real, reachable, per-puzzle prose generation that bypasses `caption_pipeline.py` — but it's bounded to the puzzle-prescription panel (short, formulaic sentences), not the main per-move review engine.

**2. `backend/services/community_training_service.py`** — **REAL_VIOLATION_LOW_RISK**
`_build_comparison_sentence()` (defined line 1526, called line 786) runs inside `record_solve_attempt()`, which is wired to a live `POST` endpoint in `routes/training_advanced.py` (line 3471-3477) — fires every time a user submits a community puzzle attempt. Line 1541 is only the last-resort fallback branch when no structured fact strings are available. Real and live, but a single isolated fallback string in one training-feedback panel.

**3. `backend/services/decryption_voice/concept_templates.py`** (19 findings) — **REAL_VIOLATION_HIGH_RISK**
Confirmed on the live render path, and NOT superseded by the central pipeline. Chain: `routes/coach.py` (post-game background generation, unconditional, no flag) → `decryption_voice/orchestrator.py::generate_post_game_voice()` → for each detected "top moment," `concept_dispatcher.caption_for_moment()` is tried **first, ahead of** the V5/central caption (explicit priority-order comment at orchestrator.py:203-228: "1. concept_dispatcher... 2. V5 caption... 3. engine_fallback") → `concept_dispatcher.py` imports `render_caption` from `concept_templates.py` → result lands in `decryption_block.moments[]` → rendered by `<GameMoments>` in `GameDecryptionV5.jsx` (line 987), which is **not** disabled (unlike the neighboring `<TruthHeadline>` which is explicitly gated `{false && ...}`). This is a full 19-template parallel caption engine that structurally duplicates `caption_pipeline.py`'s job and, by design, outranks it for this surface. This is the clearest "second engine" in the batch.

**4. `backend/services/decryption_voice/opening_book.py`** — **LEGITIMATE_EXEMPTION**
`recognize_opening_from_history` is imported directly by `caption_pipeline.py` (lines 2038, 2638) — it's a supplier *to* the central layer, not a bypass of it. This is a curated, ~25-entry static data table (moves → name → caption), architecturally the openings equivalent of `traps.json`. Lines needing `# allow-noncentral-caption`: 41, 66, 131, 168, 173, 371.

**5. `backend/services/decryption_voice/per_move_caption.py`** — **LEGITIMATE_EXEMPTION**
Line 614 is inside a docstring for `_derive_engine_preference_why()` — quotes example caption text as documentation, not a caption generator. Pure regex false positive. This module's own `caption_for_move()` is explicitly retired per `routes/coach.py` line 1194 comment. Line needing `# allow-noncentral-caption`: 614.

**6. `backend/services/deterministic_principle_caption_generator.py`** — **LEGITIMATE_EXEMPTION**
Zero callers anywhere in `backend/` — grep for the module name across the entire backend returns no matches. Orphaned/dead code. Lines needing `# allow-noncentral-caption`: 139, 141, 148.

**7. `backend/services/distilled_caption_service.py`** — **LEGITIMATE_EXEMPTION**
Line 231 is a template string in the `_SEED_MISTAKE` dict, consumed by `try_distilled_caption()`, which is directly imported and called by `caption_pipeline.py` (line 4587). Central-adjacent template infrastructure, not a bypass. Line needing `# allow-noncentral-caption`: 231.

**8. `backend/services/fundamentals_checklist_service.py`** — **REAL_VIOLATION_LOW_RISK**
`FundamentalsChecklistService.diagnose()` is called live from `shared_coaching_v5.py::_enrich_with_fundamentals()`, gated to Play with Coach only. Output lands in a **separate** field (`coaching.socratic_question`), not merged into the main caption — a distinct Socratic-question sub-feature that never touches `caption_pipeline.py`. Real and live, but small/bounded in scope.

**9. `backend/services/game_decryption_service.py`** — **UNCERTAIN**
The pre-V5 decryption service. Called from a background-generation branch in `routes/coach.py` (line 650, only fires when `decryption_data` doesn't exist yet) and `analysis_worker.py` (line 2181, "PHASE 9: GAME DECRYPTION", runs for every analyzed game, stores `decryption_data`/`decryption_summary`). Could not determine from static reading alone whether any currently-routed frontend page still reads `decryption_data`/`decryption_summary` (vs. `decryption_v5_data`), or whether this is a vestigial write nothing consumes. **What's needed to resolve:** confirm with Mohit or grep the full frontend for any live page reading the legacy fields.

**10. `backend/services/game_decryption_v5_service.py`** (17 findings) — **LEGITIMATE_EXEMPTION**
Renders `MoveCoachingCardV5` for `/game/:gameId`; `CAPTION_V5_PIPELINE_ENABLED` defaults to `True` (line 106) — the central pipeline is the live, default-on caption source (`move_output["caption"]`, line 4138). All 16 of 17 flagged f-string lines belong to legacy `extract_plan_from_pv`/`generate_simple_narrative`/`_format_better_approach` functions that still execute (wasted compute) but whose output is explicitly discarded (`"narrative": ""`, nulled `plan.*` fields; code comment confirms "LEGACY PROSE FIELDS RETIRED"). The 17th finding (line 380) is a static curated opening-idea dict imported by `caption_pipeline.py` (line 2614) — supply data, not a bypass. Net: dead-code-heavy but not an architecture risk; worth flagging as a cleanup opportunity (~1,700 lines) separate from this guard. Lines needing `# allow-noncentral-caption`: 380, 749, 1639, 1684, 1719, 1733, 1738, 1740, 1940, 1950, 1952, 2741, 2748, 3383, 3422, 3424, 3426.

**11. `backend/services/line_parser.py`** — **REAL_VIOLATION_LOW_RISK**
`explain_line()` is called from `routes/coach.py`'s live `POST /coach/explain-mistake` endpoint, fetched from `LabClassic.jsx`, `GameSummary.jsx`, `PlateauBreakerReview.jsx`. Only `PlateauBreakerReview.jsx` is routed in `App.js` (`/plateau-breaker/review/:gameId`); `LabClassic.jsx` isn't in `App.js` routes and `GameSummary.jsx`'s import is commented out in `LabV2.jsx`. Real, live prose generation, confined to the secondary Plateau Breaker feature.

**12. `backend/services/meta_patterns.py`** — **REAL_VIOLATION_HIGH_RISK**
Confirmed as THE default-live coaching-message engine for real-time PWC feedback. `realtime_coaching_feedback.py` does call `caption_pipeline.build_move_teaching_decision()` (line 1401), but only when `PWC_USE_CENTRAL_CAPTION_PIPELINE` is true — and that flag **defaults to `"false"`** in code (line 1360-1362, comment: "Mohit 2026-06-02 — PWC central-caption migration phase 2... Default-off env flag"). Note: batch D's investigation of the running container found this flag is actually set `true` in `docker-compose.yml`/`docker-compose.prod.yml` and confirmed `true` in the live container — so in practice the headline message IS centralized in production; `meta_patterns.py`'s `rule_*` functions are the fallback path when the flag is off (e.g. local dev), not the live default. Cross-reference batch D for the fuller picture.

**13. `backend/services/move_by_move_coach.py`** — **REAL_VIOLATION_LOW_RISK**
`generate_move_commentary()` is imported live at two call sites inside `routes/coach_play.py` (lines 8730, 9521). Line 423 sits inside `_generate_user_move_commentary()`'s opening-teaching branch — real, live, bespoke text generator, scoped specifically to opening-phase commentary rather than general per-move mistake explanation.

---

### Summary counts
- LEGITIMATE_EXEMPTION: 5 files (`opening_book.py`, `per_move_caption.py`, `deterministic_principle_caption_generator.py`, `distilled_caption_service.py`, `game_decryption_v5_service.py`)
- REAL_VIOLATION_LOW_RISK: 6 files (`coaching_puzzle_service.py`, `community_training_service.py`, `fundamentals_checklist_service.py`, `line_parser.py`, `move_by_move_coach.py`, `game_decryption_service.py` pending its one open question)
- REAL_VIOLATION_HIGH_RISK: 2 files (`concept_templates.py`, `meta_patterns.py` — see note above re: batch D cross-reference on the PWC_USE_CENTRAL_CAPTION_PIPELINE flag's real production value)
- UNCERTAIN: 1 file (`game_decryption_service.py`)
