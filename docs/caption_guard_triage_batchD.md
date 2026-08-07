# Caption Source Guard — Batch D Triage (13 files)

Investigated 2026-08-07. Guard: `backend/scripts/check_caption_sources.py --strict`.

**Correction on opt-out marker**: the guard's actual opt-out comment is
`# allow-noncentral-caption` (see `check_caption_sources.py` line 19 and 83),
**not** `# allow-caption-source-guard` as assumed in the task brief. Use the
real marker if/when opting out any line below.

Evidence gathered by running the guard inside `chess-coach-backend`
(`docker exec chess-coach-backend python3 scripts/check_caption_sources.py --strict`),
then reading each flagged line in context and tracing the caller chain with
`grep`/`Read` up to the live route and the frontend component that renders
the response field.

---

## Summary table

| # | File | Classification |
|---|------|----------------|
| 1 | position_strategy_analyzer.py | REAL_VIOLATION_HIGH_RISK |
| 2 | postgame_analysis.py | REAL_VIOLATION_HIGH_RISK |
| 3 | principle_based_caption_generator.py | LEGITIMATE_EXEMPTION (dead code) |
| 4 | principle_blocked_pawn.py | LEGITIMATE_EXEMPTION (data supplier + docstring) |
| 5 | puzzle_move_evaluator.py | REAL_VIOLATION_LOW_RISK |
| 6 | pv_tactical_analyzer.py | REAL_VIOLATION_LOW_RISK |
| 7 | realtime_coaching_feedback.py | REAL_VIOLATION_HIGH_RISK |
| 8 | shape_detectors.py | LEGITIMATE_EXEMPTION (data supplier + docstring) |
| 9 | shared_coaching_v5.py | REAL_VIOLATION_HIGH_RISK |
| 10 | simple_endgame_caption_builder.py | LEGITIMATE_EXEMPTION (dead code) |
| 11 | socratic_engine.py | REAL_VIOLATION_HIGH_RISK |
| 12 | turning_point_explainer.py | REAL_VIOLATION_HIGH_RISK |
| 13 | trick_library_service.py | REAL_VIOLATION_LOW_RISK |

7 high-risk, 3 low-risk, 3 legitimate exemptions, 0 uncertain.

---

## 1. backend/services/position_strategy_analyzer.py
**REAL_VIOLATION_HIGH_RISK**

Flagged line 167 (`generate_move_specific_insight`, `why_your_move_was_wrong`)
is inside a function reached from **three** live call sites:

- `backend/routes/interactive.py:352` (`POST /api/games/{game_id}/move/{move_number}/analyze-gap`)
  — **no central-pipeline check at all**. Output overwrites
  `gap_result["explanation"]` and `gap_result["coaching_focus"]`
  (interactive.py:373-391). Frontend `frontend/src/pages/Reflect.jsx:361`
  calls this endpoint, and line 1254 renders
  `awarenessGap.cognitive_gap?.coaching_focus || awarenessGap.coaching_message`
  — `coaching_focus` is exactly the field this module populates. `/reflect`
  is a live routed page (App.js). This is the strongest live path — fully
  bespoke, unguarded.
- `backend/routes/games.py:720` (`GET /games/{game_id}/coach-review`,
  `key_moments`) — genuine central-first pattern: tries
  `build_move_teaching_decision` first (games.py:717-761), only falls back
  to `generate_move_specific_insight` when the central caption is empty
  (games.py:767). Consumed by `frontend/src/pages/LabV2.jsx:476` as
  `interactiveMoment` data for the practice-move widget.
- `backend/routes/lab.py:969` (`GET /lab/{game_id}/deep-strategy`) — live
  endpoint, fetched unconditionally by `LabV2.jsx:511` on every game load,
  but the `deepStrategy` state is **never rendered** anywhere in
  `LabV2.jsx` (grep for `deepStrategy` shows only the `useState`/fetch, no
  JSX use) — dead UI wiring on the routed page. (The only page that DOES
  render it, `LabClassic.jsx`, is not imported/routed in `App.js` — dead
  page.)
- `backend/coach_play/coach_commentary.py:880` inside
  `generate_coach_chat_message` — this function itself has **zero
  callers** anywhere in the codebase (confirmed via grep) — dead code path.

**Player-facing impact**: real, live, unguarded bespoke coaching text on
`/reflect`'s cognitive-gap card.

---

## 2. backend/services/postgame_analysis.py
**REAL_VIOLATION_HIGH_RISK**

Flagged lines 613/1113/1161/1194 are inside `_generate_personalized_summary`
and `_suggest_opening`, called from `analyze_postgame()` (the file's single
entry point, confirmed live via `backend/analysis_worker.py` and
`backend/routes/coach_play.py`).

Direct evidence of reach: `GET /coach/play/postgame/{session_id}`
(`backend/routes/coach_play.py:9817`) calls `analyze_postgame` and returns
`"coach_summary": analysis.coach_summary` and
`"encouragement": analysis.encouragement` verbatim
(`coach_play.py:9974-9975`) — these are exactly the strings built at
postgame_analysis.py:1113 (`"You played like a {X} player today..."`) and
:1161 (`"Close game! You played well but chess is tough..."`).
`frontend/src/pages/CoachPlay.jsx:671` fetches this endpoint into `summary`
state, which is passed to `<PostGameReflection data={summary} .../>`
(`CoachPlaySidebar.jsx:1810`), which renders `data.coach_summary` and
`data.encouragement` unconditionally at
`PostGameReflection.jsx:172-174`. No `build_move_teaching_decision` call
exists anywhere in `postgame_analysis.py`.

Note: a separate field on the same screen, `pattern_verdict`
(computed inline in `coach_play.py`, not from this file), is what a 2026-08-07
in-code comment on `PostGameReflection.jsx:29-43` calls "PWC's real postgame
personalization" — but `coach_summary`/`encouragement` render alongside it
unconditionally, not gated by it.

**Player-facing impact**: renders after literally every finished Play with
Coach game, on the core PWC surface.

---

## 3. backend/services/principle_based_caption_generator.py
**LEGITIMATE_EXEMPTION — dead code**

Flagged lines 102/104 (`_fallback_caption`). Traced every caller:
`generate_principle_based_caption` is imported by exactly one production
module, `backend/services/principle_caption_bridge.py:64`
(`enhance_caption_with_principles`) — and that bridge function itself has
**zero callers anywhere in the codebase** (`grep -rn
"enhance_caption_with_principles|should_enhance_caption|principle_caption_bridge"
backend --include=*.py` returns only its own definition). The only other
reference is a standalone test script
(`backend/scripts/test_principle_caption_rf3_plus.py`). Fully orphaned.

No line needs an opt-out comment — recommend deleting both files, or if kept,
mark file-level with `# allow-noncentral-caption` since the whole file is dead.

---

## 4. backend/services/principle_blocked_pawn.py
**LEGITIMATE_EXEMPTION — data supplier + docstring**

Flagged line 9 is inside the **module docstring**, quoting the bad caption
this detector was written to fix ("but currently just says \"Nc3 is a
mistake. c3 was better.\" — no why") — not runtime output. The actual
function `detect_blocked_pawn` returns a structured fact dict (`pawn_file`,
`blocked_square`, `would_support`, `would_prepare`), never prose. Confirmed
its only importer is `backend/services/caption_pipeline.py` (plus its own
test file) — this is exactly the "data supplier TO the central pipeline"
exemption category.

Recommend appending `# allow-noncentral-caption` to line 9 to silence the
docstring false-positive.

---

## 5. backend/services/puzzle_move_evaluator.py
**REAL_VIOLATION_LOW_RISK**

Flagged line 62 (`_build_feedback`, `"Not quite. {best_san} was better
here."`). Live call chain: `evaluate_puzzle_move` is called from
`POST /api/training/evaluate-puzzle-move`
(`backend/routes/training.py:300-337`), which also calls the
allowlisted, central-delegating `puzzle_miss_coaching.build_miss_coaching`
(training.py:351-378) and returns **both** `result["feedback"]` (this
file's bespoke one-liner) and `result["miss_coaching"]` (central-derived)
in the same payload. `frontend/src/pages/PrescribedTraining.jsx:350-377`
uses `result.feedback` directly as the `encouragement` banner text (for
correct/acceptable/incorrect states) while `result.miss_coaching` populates
a separate, more detailed panel.

**Player-facing impact**: real duplicate text on `/training/pattern/:pattern`
and `/training/prescribed`, but scoped to a short encouragement banner —
the substantive "why" already comes from the central-delegating
`miss_coaching` block shown alongside it.

---

## 6. backend/services/pv_tactical_analyzer.py
**REAL_VIOLATION_LOW_RISK**

Flagged lines 180/513/597. `explain_best_move_tactically` is called from
`backend/services/game_decryption_v5_service.py:4289`, inside a
"NARRATIVE ENHANCEMENT PASS" (lines 4258-4327) that runs for every
mistake/blunder/inaccuracy move and writes
`decryption_data[idx]["narrative"] = det_narrative`. This is the CORE
Game Review surface (`/game/:gameId`).

However, this collides with an explicit "LEGACY PROSE FIELDS RETIRED"
comment 150 lines earlier (game_decryption_v5_service.py:4087-4102) that
sets `"narrative": ""` and states the frontend "reads its move-by-move text
... via the new V5 caption pipeline" (the `caption` field, sourced from
`build_move_teaching_decision` at line 3552). Confirmed in
`frontend/src/components/GameDecryptionV5.jsx:317-362`: the frontend
explicitly **prefers** `m.caption` (central) over `m.narrative` whenever
`m.caption` is non-empty, and even actively **zeroes out** `narrative` when
the per-move endpoint says the central caption is genuinely silent
(GameDecryptionV5.jsx:384-396). `pv_tactical_analyzer`'s text only survives
to the screen in the edge case where the `/coach/decryption/per-move/{id}`
fetch itself fails (network error), per the `catch` fallback at
GameDecryptionV5.jsx:399-403.

**Player-facing impact**: real live computation on the core Game Review
surface that is architecturally supposed to be retired, and is shadowed by
the central caption in the common case, but is a genuine unreviewed
fallback path (not verified/gated the same way) when the per-move fetch
fails.

---

## 7. backend/services/realtime_coaching_feedback.py
**REAL_VIOLATION_HIGH_RISK** (the one CLAUDE.md flags as the "★ RATING-AWARE" engine)

`PWC_USE_CENTRAL_CAPTION_PIPELINE` **default is `"false"`** in code
(realtime_coaching_feedback.py:1361), but is explicitly set to `true` in
both `docker-compose.yml:76` and `docker-compose.prod.yml:47`, and
confirmed **actually `true`** in the running `chess-coach-backend`
container (`docker exec chess-coach-backend printenv` →
`PWC_USE_CENTRAL_CAPTION_PIPELINE=true`). So in the deployed configuration,
`coaching_message` **is** overridden by the central pipeline's caption when
central has something to say (lines 1401-1435).

But the override only touches `coaching_message`. Flagged line 1706
(`consequence = f"You missed winning the {tactical['best_move_captures']}"`)
sits inside `generate_move_feedback`'s `MoveFeedback` dataclass, and
`consequence` (plus `candidate_moves`, `golden_rule`) are **never touched**
by the central-override block — they ship straight through `to_dict()`
(lines 145-191) to `GET /coach/play/move-feedback/{session_id}`
(`get_last_move_feedback`, called from `routes/coach_play.py:1038-1052`).
`frontend/src/pages/CoachPlay.jsx:1479/1538/1937` reads
`data.feedback.consequence`/`candidate_moves` directly into
`currentInsight.why`/`candidate_moves`, rendered by
`V5CoachingCard.jsx:277-298` (`{coaching.consequence}` /
`Better: {candidate.move} - {candidate.idea}`).

(Flagged line 655 is a false positive — it's a filter condition,
`"takes the pawn" not in t.lower()`, not user-facing text generation.)

**Player-facing impact**: the headline "coaching_message" is centralized in
production, but the `consequence`/`candidate_moves[].idea` fields shown in
the same coaching card on the core PWC surface are not — a partial bypass,
not a full one.

---

## 8. backend/services/shape_detectors.py
**LEGITIMATE_EXEMPTION — data supplier + docstring**

Flagged line 1267 is a docstring bullet inside
`detect_strong_knight_square` ("'Defended by pawn' = at least one own pawn
attacks the knight's square."), not a rendered string. Confirmed direct
import by `backend/services/caption_pipeline.py:712/856/972/2876/2884`
(the central layer itself) and by the allowlisted
`backend/services/shape_layer.py:38`. Its functions return structured
"evidence" dicts (geometric facts), not prose. Classic data-supplier
exemption.

Recommend `# allow-noncentral-caption` on line 1267.

---

## 9. backend/services/shared_coaching_v5.py
**REAL_VIOLATION_HIGH_RISK**

This is the actual "MAIN ENTRY POINT for Play with Coach live coaching"
per its own docstring (line 904) — `generate_move_coaching` is imported
live at `backend/routes/coach_play.py:2722/2840/4224`, exposed as
`POST /coach/play/v5/feedback`, and called unconditionally by
`frontend/src/pages/CoachPlay.jsx:1915` (`fetchV5Coaching`, invoked after
every move) — this runs in parallel with (not instead of)
`realtime_coaching_feedback.py`'s `/move-feedback` polling, i.e. PWC has
**two live coaching engines feeding the same screen**.

Like file #7, this module DOES call the central pipeline
(`_central_narrative_for_move`, computed once at line 942-970) and prefers
it for the `narrative` field when non-empty (lines 985-993, 1374-1375). But
flagged lines 1351/1512 (`better_approach = candidate_moves[0]["idea"] if
candidate_moves else f"{best_move_san} was better"`) are never overridden
— `consequence`, `better_approach`, `transferable_learning` stay
legacy-authored even when `narrative` is centralized. Worse,
`generate_opponent_move_coaching` (lines 1391-1455, covers ALL opponent
moves) has **no central-pipeline call whatsoever** — entirely bespoke
prose ("Opponent takes your {captured_name} with {move_san}!", "Watch out!
{move_san} attacks your {attacked_name}!").

Confirmed reach: `frontend/src/pages/CoachPlay.jsx:1937-1938` maps
`coaching.consequence` → `currentInsight.why`,
`coaching.your_plan_now || coaching.better_approach` → `next_idea`,
`coaching.transferable_learning` → `deeper_explanation`, all rendered by
`V5CoachingCard.jsx`.

**Player-facing impact**: on the core PWC surface, the "why"/"what to do
next"/"transferable lesson" fields — and 100% of opponent-move commentary —
bypass the central pipeline even where `narrative` itself is centralized.

---

## 10. backend/services/simple_endgame_caption_builder.py
**LEGITIMATE_EXEMPTION — dead code**

Flagged lines 168/170/177 (`_fallback_caption`-style severity strings).
Traced every importer of `build_endgame_caption`: all six hits are under
`backend/scripts/` (test/audit/regen scripts — `regenerate_captions_verified.py`,
`test_captions_on_bhutramohit_games.py`, `test_captions_quality_on_real_games.py`,
`test_caption_verification.py`, `test_deterministic_detectors.py`,
`verify_caption_correctness.py`). No route or live service imports it.
Orphaned from production.

---

## 11. backend/services/socratic_engine.py
**REAL_VIOLATION_HIGH_RISK**

Flagged lines 466/662 (`_guide_final_step`, `_generate_contrastive_explanation`
fallback). Two reach paths:

- `backend/routes/coach.py` mounts `/coach/socratic/start|respond|hint|reveal`
  and `/coach/debug/test-socratic` directly on `SocraticEngine` — but a
  full-repo grep of `frontend/src` for these paths returns **zero** fetch
  call sites. These specific routes are orphaned (mounted, never called by
  the UI).
- However `backend/services/human_coach_service.py:460`
  (`get_socratic_mistake_response`) also calls
  `socratic_engine.create_socratic_dialogue`, and this IS live:
  `get_socratic_response` (human_coach_service.py:823) is called from
  `backend/routes/coach_play.py:8845`, inside `_process_move_and_respond` —
  the main move handler behind the live `/coach/play/move` flow. It fires
  as the `else` branch whenever `wisdom_enhanced` (a separate rule-based
  system) has no `rule_id` match (coach_play.py:8816-8845), and its result
  is inserted into `coach_messages` with `type: "coach"`
  (human_coach_service `create_human_coach`/session flow feeds this same
  collection pattern seen at coach_play.py:2500-3124). `frontend/src/pages/CoachPlay.jsx:828`
  reads `coach_messages` filtered to `type === "coach"` as the live chat
  panel content.

**Player-facing impact**: real fallback voice on the core PWC chat panel,
with zero central-pipeline awareness, firing whenever the separate
"wisdom" rule engine doesn't match.

---

## 12. backend/services/turning_point_explainer.py
**REAL_VIOLATION_HIGH_RISK**

Flagged lines 578/587 (`_generate_missed_idea`). `get_turning_point_explainer().explain(...)`
is called from `backend/routes/lab.py:417-428`, inside
`GET /lab/{game_id}` — a core, heavily-used endpoint
(`frontend/src/pages/LabV2.jsx` fetches it, per the earlier chain audited
for file #1). The full explanation object (`description`, `missed_idea`,
`opponent_idea`, `thinking_error`, `training_tip`) is placed on
`turning_point` in the response (`lab.py:430+`), and rendered directly by
`frontend/src/components/Lab/GameSummary.jsx:184-198`
(`explanation: turningPoint.description || "..."`, `missedIdea:
turningPoint.missed_idea`, etc.), which `GameSummary.jsx` is confirmed used
inside `LabV2.jsx` — the routed `/game/:gameId` page. No
`build_move_teaching_decision` call exists anywhere in this file.

**Player-facing impact**: the "story of the game" / biggest-moment
explanation shown at the top of Game Review is entirely this module's
prose, on the core review surface, fully bypassing the central pipeline.

---

## 13. backend/trick_library_service.py
**REAL_VIOLATION_LOW_RISK**

Flagged lines 236/266/392/565 are hand-authored `"explanation"` strings for
named, famous traps (Scholar's Mate-style sequences) in a hardcoded
`TRAPS_DATABASE`. Confirmed live: `teaching_engine.py:490`
(`get_lesson_catalog`) — the function backing the live
`GET /coach/play/teaching/catalog` endpoint that CLAUDE.md documents as
returning "18 traps + 10 endgames" — sources its trap list from
`trick_library_service.get_all_traps()`, **not** from
`backend/services/trap_library.py` as CLAUDE.md's architecture doc claims.
`frontend/src/components/coach/LessonPicker.jsx` (the Lesson Picker inside
Play with Coach) renders this catalog directly. Also reached via several
`/training/tricks*` endpoints in `routes/training_advanced.py`.

Unlike files #1/#2/#9/#11/#12, this is not a *dynamic per-move mistake
caption* competing with `build_move_teaching_decision` — it's static,
pre-authored curriculum text describing one specific named trap sequence
(analogous in kind to `data/traps.json`/`data/endgames.json`, which are
JSON and not scanned by the guard at all). That's a materially different
product surface (pre-built lesson content vs. reactive move analysis),
which is why this is scored low-risk rather than high-risk despite being
definitely live and definitely bespoke prose.

Separately worth flagging outside the guard's scope: **CLAUDE.md's
documented trap data source is stale** — it attributes the 18-trap catalog
to `trap_library.py`, but the live code path uses
`trick_library_service.py`. This looks like exactly the kind of "two
sources of truth for traps" sprawl called out in project memory
(`project_opening_recognizer_canonical.md`/`feedback_single_source_of_truth.md`)
and may be worth its own audit.

**Player-facing impact**: real, live authored trap-lesson text on the PWC
Lesson Picker; low risk because it isn't competing with per-move mistake
captions.
