# Caption-source guard — full 66-file triage (Sprint 1, 2026-08-07)

**What this is.** `backend/scripts/check_caption_sources.py --strict` flags any
non-allowlisted backend file that imports `chess` and contains chess-teaching
prose (mistake/blunder framing, "wins/forks/pins the X" phrasing, "was better"
phrasing). It runs in CI as **warn-only** (`|| true`) — see `.github/workflows/ci.yml`.
The guard's real opt-out marker is `# allow-noncentral-caption` (its docstring
briefly says something close to this; earlier drafts of this triage guessed
`# allow-caption-source-guard`, which is wrong — do not use that string).

**Why this triage happened.** Sprint 1 called for scoping the 66-file backlog
before ever making the guard blocking. This is that scoping — every file read
in context, every flagged function traced to its actual caller chain, and
where live, to the actual frontend component that renders (or doesn't render)
the string. Done via 5 parallel batches (A-E, ~13 files each); full per-file
evidence lives in `docs/caption_guard_triage_batch[A-E].md`. This file is the
roll-up.

**Do NOT flip `--strict` on in CI from this triage alone.** 37 files below
(21 high-risk + 16 low-risk) are confirmed real, live, player-facing
violations. Flipping now would break every PR touching any of them. This
triage's job was to scope the backlog, not clear it.

---

## Totals across all 66 files

**Correction, written immediately after first drafting this doc**: the first
pass of this table (21/16/28 vs. an earlier miscount of 24/17/24) trusted
each batch agent's own prose summary line instead of recounting from each
file's individual verdict. Two of the five batches' prose headers (D and E)
turned out to be internally inconsistent with their own per-file tables —
batch D's header said "7 high-risk," its table shows 6; batch E's header
double-counted one file into both LOW and UNCERTAIN. The table below is
recomputed directly from all 66 individual per-file verdicts, not from any
batch's summary arithmetic.

| Classification | Count |
|---|---|
| REAL_VIOLATION_HIGH_RISK | 21 |
| REAL_VIOLATION_LOW_RISK | 16 |
| LEGITIMATE_EXEMPTION | 28 |
| UNCERTAIN | 1 |

## The 21 HIGH_RISK files — confirmed live, confirmed rendered, core surfaces

Grouped by the surface they actually hit (a file can hit more than one):

**Play with Coach (`/play-with-coach`) — 14 files, by far the worst-affected surface:**
`coach_play/coach_commentary.py` (chat bubble text), `coach_play/punishment_puzzle.py`
(deliberate second engine — needs a product decision, not a migration
ticket), `mistake_classifier.py` (the postgame lesson card's "Key errors"
list), `move_intent_analyzer.py` (coach's own move commentary + curriculum
feedback), `opening_assessment_service.py` (the session-start welcome
message), `opening_curriculum_engine.py` (same function legitimately gated
in one call path, ungated in another — the guard's textbook disease case),
`pattern_learning/pattern_learner.py` (a full second LLM engine, triggered on
user "this was wrong" feedback — also reaches Lab and Reflect via the same
feedback modal), `pedagogical_opportunity_service.py` (**default-on** for
every new session), `postgame_analysis.py` (`coach_summary`/`encouragement`
on every postgame card, unconditionally alongside `pattern_verdict`),
`realtime_coaching_feedback.py` (CLAUDE.md's own "★" engine — headline
message IS centralized in prod via `PWC_USE_CENTRAL_CAPTION_PIPELINE=true`,
but `consequence`/`candidate_moves[].idea` are not), `shared_coaching_v5.py`
(the actual main entry point per its own docstring; **100% of opponent-move
commentary** bypasses the center entirely), `socratic_engine.py` (via
`human_coach_service.py`, fires whenever a separate "wisdom" rule engine
doesn't match), `meta_patterns.py` (the fallback path when
`PWC_USE_CENTRAL_CAPTION_PIPELINE` is off — largely superseded in prod today
since that flag is `true` there, but not in local/dev), `routes/coach_play.py`
itself (3 separate sites: impulse-warning chat message, `theory_applied`
field, and the `pattern_verdict` postgame message-building — this last one is
the exact mechanism Sprint 1's `pwc_insight_shown` instrumentation now times,
see the residency notes).

**Game Review (`/game/:gameId`) — 4 files:**
`decryption_voice/concept_templates.py` (a full 19-template engine that
**outranks** the central caption by explicit priority order in
`orchestrator.py`), `plan_analysis_service.py` ("what was your plan?"
feature), `turning_point_explainer.py` (the "story of the game" headline),
`routes/lab.py` (a full independent, from-scratch, non-Stockfish
move-quality classifier for the practice-move widget).

**Reflect (`/reflect`) — 3 files:**
`cognitive_gap_service.py` (the *only* source of prose for the cognitive-gap
card — 11 hand-written explanation branches), `position_analysis_service.py`
(a second, fully independent LLM coaching call, own `call_llm` with its own
system prompt), `position_strategy_analyzer.py` (unguarded on `/reflect`;
also reachable via Game Review with a central-first pattern there, and via a
dead code path in `coach_commentary.py`).

## The 16 LOW_RISK files

Real, live, reachable — but scoped to secondary surfaces (Training/puzzle
pages, Opening Walkthrough, Plateau Breaker) or a single short string sitting
next to an otherwise-correct central narrative: `coaching_puzzle_service.py`,
`community_training_service.py`, `fundamentals_checklist_service.py`,
`line_parser.py`, `move_by_move_coach.py`, `blunder_intelligence_service.py`,
`coach_play/pattern_indexer.py`, `coaching_classifier_service.py`,
`community_learning_service.py`, `interactive_training_service.py`,
`opening_service.py`, `routes/games.py`, `opening_walkthrough_service.py`,
`puzzle_move_evaluator.py`, `pv_tactical_analyzer.py`, `trick_library_service.py`.

## The 1 UNCERTAIN file

`game_decryption_service.py` — the pre-V5 decryption service, still written
by `analysis_worker.py` Phase 9 for every analyzed game. Could not determine
from static reading whether any live page still reads the legacy
`decryption_data`/`decryption_summary` fields it writes, vs. `decryption_v5_data`.
**Needs Mohit or a frontend-wide grep to resolve** — not attempted tonight to
avoid a guess standing in for evidence.

## The 28 LEGITIMATE_EXEMPTION files

Two real sub-categories, handled differently below:

**Genuine data suppliers to `caption_pipeline.py` / docstring false positives
(11 files, get `# allow-noncentral-caption` on the specific lines — see
"Allowlisting applied" below):** `decryption_voice/opening_book.py`,
`decryption_voice/per_move_caption.py`, `distilled_caption_service.py`,
`best_move_tactic_detector.py`, `opening_deviation.py`,
`opening_theory_lookup.py`, `opp_quiet_threat_detector.py`,
`pattern_catalog.py`, `principle_blocked_pawn.py`, `shape_detectors.py`,
`opening_trainer_service.py` (static opening-theory reference content, same
category as `data/traps.json`).

**The verifier-allowlist gap (1 file, whole-file `ALLOWLIST` addition):**
`caption_claim_verifier.py` — the direct sibling of the already-allowlisted
`narrator_claim_verifier.py`; omission looks accidental, not a real gap.

**Dead code — zero importers repo-wide, left UNALLOWLISTED on purpose (10
files):** `deterministic_principle_caption_generator.py`, `pdr_service.py`,
`coach_play/teaching_coach.py`, `coach_play/pre_move_guardian.py` (its
`EnforcementLadder` class specifically — the file's *other*, actually-live
class, `PreMoveGuardian`, is a different code path entirely and isn't part of
this finding), `pattern_learning/pattern_rule_extractor.py`,
`position_explainer.py`, `principle_based_caption_generator.py`,
`simple_endgame_caption_builder.py`, `badge_service.py` (route live, only
frontend caller is an orphaned unimported component),
`mistake_explanation_service.py` (same shape — LLM fallback path, zero live
UI callers). Recommend an actual deletion ticket for these, not silencing —
allowlisting a file that produces zero player value just to quiet the guard
would hide that it's dead weight worth removing.

**Retired/kill-switched subsystems, left UNALLOWLISTED on purpose (2 files):**
`active_teaching_engine.py` (permanently routed around by
`ENABLE_DECISION_ENGINE=True`), `chess_brain/chess_brain.py` (explicitly
disabled 2026-05-10 per its own code comment: "wrong teaching is worse than
no teaching"). Kept visible rather than silenced in case either is ever
accidentally re-enabled — a re-enable should immediately retrip the guard.

**Mixed docstring-FP + dead-endpoint files, left UNALLOWLISTED on purpose (2
files):** `routes/coach.py`, `routes/interactive.py`, `routes/training_advanced.py`
(3, not 2 — correcting inline). All three have some genuinely dead/orphaned
endpoints alongside docstring false positives; several agents flagged these
explicitly as "one wiring change away from becoming a live bypass" — the
guard should keep watching them, not go quiet.

**`game_decryption_v5_service.py` (17 lines, left UNALLOWLISTED on purpose):**
confirmed non-risk today (output is explicitly discarded, central pipeline is
the real live source), but the agent who traced it called the ~1,700 lines of
dead plan-building code behind it a real cleanup opportunity. Leaving the
guard noisy here is a deliberate reminder, not an oversight.

## Allowlisting applied tonight

- `backend/services/caption_claim_verifier.py` added to the guard's
  `ALLOWLIST` set (alongside `narrator_claim_verifier.py`).
- `# allow-noncentral-caption` appended to the specific confirmed-safe lines
  in the 10 other data-supplier/docstring files listed above (21 lines
  total). Every line was re-read and verified against its batch doc's quoted
  text before the marker was added — not applied blind by line number alone,
  since line numbers can drift between when a batch was scanned and now.
- Re-ran `check_caption_sources.py --strict` after applying these to confirm
  the finding count dropped by exactly the number of lines allowlisted, and
  that no unrelated finding count changed (a regression would mean a marker
  landed on the wrong line).

## Recommended next steps (not done tonight — real migration work, out of
Sprint 1's scope which was triage, not fixes)

1. **Play with Coach needs the actual migration**, not just triage — it has
   14 of the 24 HIGH_RISK files, more than Game Review and Reflect combined.
   `shared_coaching_v5.py`'s opponent-move commentary (100% bypass) and
   `pedagogical_opportunity_service.py` (default-on for every session) are
   the two highest-leverage single fixes.
2. **`opening_curriculum_engine.py`'s dual-use split** (gated via
   `caption_pipeline.py`'s A11 logic in one call path, ungated via direct
   `routes/coach_play.py` calls in another) is the guard's textbook disease
   case and probably the cleanest, most illustrative first migration — same
   function, same data, just route the second call site through the gate too.
3. **Resolve the one UNCERTAIN file** (`game_decryption_service.py`) with a
   full-frontend grep or a direct question to Mohit.
4. **File a deletion ticket** for the 9 confirmed-dead files plus the ~1,700
   dead lines inside `game_decryption_v5_service.py` — separate from caption
   architecture, just repo hygiene.
5. Only after (1)-(2) meaningfully shrink the HIGH_RISK list should flipping
   `--strict` on in CI be reconsidered.
