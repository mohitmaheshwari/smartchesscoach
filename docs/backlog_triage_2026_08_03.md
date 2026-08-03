# Backlog Triage — 2026-08-03

All 109 scope/planning docs in `docs/` triaged against the live codebase (not
just their own status headers, which turned out to be unreliable — see
Pattern #1 below). Done via 6 parallel research passes, each independently
verifying claims against real code, git log, and docker-compose flags.

## Pattern #1: doc status headers are systemically wrong

Roughly 70% of docs read "DRAFT," "awaiting signoff," or "PENDING" for
features that are fully built and live in production. Work gets approved and
shipped, and nobody goes back to update the doc. Don't trust a header alone
— verify against code. Worst offenders: `piece_safety_subtype_scope.md`
(says DRAFT, code has iterated 12 schema versions past the draft),
`coach_geometry_arrows_scope.md` and `pwc_every_move_teaches_scope.md` (both
say "no code until signed off," both fully live by default in prod).

## The single biggest finding: six fully-built features sitting flag-off

No new code needed — these are working, validated, wired-into-the-live-path
features where someone just never flipped the switch (or flipped it, then
it silently reverted). Each is a go/no-go decision, not a build task.

| Flag | What it does | Where it's built | Validation evidence |
|---|---|---|---|
| `DISTILLED_CAPTIONS_ENABLED` | Claude-distilled, gold-matched caption templates replace weaker eval-only captions | `distilled_caption_service.py`, wired into `caption_pipeline.py:4585` | 91-99% truth in `caption_distillation_results.md`'s validation sweeps |
| `VERIFIED_CAPTIONS` | Board-verified "attacks"/good-move reasons (WS1/WS2) | `caption_pipeline.py` `_VERIFIED_CAPTIONS` gate | 98/98 verified on 50 games per `caption_production_rollout_scope.md` |
| `PWC_LIVE_OPENING_NUDGE_ENABLED` | Per-move in-book opening coaching nudges during live PWC play | `realtime_coaching_feedback.py:1638-1675` | Built exactly per spec, cites the doc by name in comments |
| `PWC_GAP_ENRICHMENT` | Coach-play games get the same cognitive_gap enrichment as imported games | `enrich_with_cognitive_gaps()`, shared by both import and PWC paths | Matches existing memory note, independently re-confirmed off in prod |
| `REACT_APP_CLIENT_EVAL` | Client-side (WASM) Stockfish for PWC, zero server compute cost | `useStockfishEval.js`, fully wired `CoachPlay.jsx` → `coach_play.py` | End-to-end wired, just never set `true` in `.env.production` |
| `PWC_MOVE_QUALITY_RATING` | Deterministic, EWMA move-quality rating for 600-1500 users, replaces imported Elo | `move_quality_rating.py`, called from `coach_game_session.py` with graceful fallback | Code-complete, never flipped anywhere |

**Recommendation: flip `DISTILLED_CAPTIONS_ENABLED` and `VERIFIED_CAPTIONS`
first** — these two directly improve caption quality/truth, which is the
closest existing lever to the "captions are hard to understand" complaint
that started this whole thread. The other four are real wins but orthogonal
to that complaint.

## Real, currently-broken bug (not previously known)

**Coaching pattern detector cards silently show "no gap" for every user.**
`coordination_detector.py` / `prophylaxis_detector.py` tag real per-move
facts during analysis, but nothing rolls those tags up into the
`player_profiles.coordination_gap` / `prophylaxis_gap` shape that
`routes/coaching_patterns.py` actually reads. Only 2 of the 5 shipped
pattern cards (motif, phase-accuracy) deliver real data; opening-deviation,
coordination, and prophylaxis cards are dead weight nobody would notice
without reading the code. `docs/coaching_pattern_detectors_scope.md`.

**Possible security gap, unverified further:** `admin_openings.py` routes
gate only on `get_current_user`, not an admin check — flagged in
`path_to_10_plan.md`, still appears open. Worth a direct look before
treating as confirmed.

## Dead code sitting unused (decide: wire up or delete)

- **Coaching Prescriptions system** — full backend (`routes/coaching.py`,
  `user_coaching_prescriptions` collection, `prescription_tracking_service
  .py`) and frontend (`CoachingPrescriptions.jsx`) built in one day
  (2026-07-10), then orphaned the very next day when `HomePageNew.jsx`
  shipped and removed the old recommendations grid. Found independently by
  two separate triage passes. Zero users can currently see this feature.
- **Daily Fix card** — backend fully live (`daily_fix.py`,
  `mistake_streak_service.py`, `daily_fix_reminder.py`), but the Home
  entry point was silently deleted by the same `HomePageNew.jsx` rewrite.
  `/daily-fix/drill` is now an orphaned route, reachable only by direct URL.
- **The entire "deterministic/principle caption" architecture** — 7 docs
  (`CAPTION_REGENERATION_PLAN`, `DETERMINISTIC_READY_FOR_INTEGRATION`,
  `DETERMINISTIC_SYSTEM_READY`, `DETERMINISTIC_SYSTEM_STATUS_HONEST`,
  `HYBRID_PRINCIPLE_CAPTION_SYSTEM`, `PRINCIPLE_CAPTION_INTEGRATION`,
  `PRINCIPLE_SYSTEM_COMPLETE`) describe one caption-generation approach
  that was built, found to work <30% of the time, and correctly abandoned
  in favor of the distillation approach that shipped instead. Safe to
  delete all 7 — they're internally consistent about their own death.
- **`docs/caption_backlog.md`** (lowercase, in `docs/`) — a different,
  dead file that confusingly shares its name with the real, actively-used
  root-level `CAPTION_BACKLOG.md`. None of its proposed detectors were ever
  built. Recommend deleting to remove the naming collision risk.
- **`docs/engine2_phase2_mastery_gate.md`** — describes a
  `user_mastery_gate.py` that doesn't exist; the actual feature shipped
  under a different name/design (`pwc_skill_gate.py`, per
  `pwc_mastery_gate_scope.md`). Delete or redirect.

## Stalled research initiatives (decide: resurrect or explicitly kill)

**The 20-user, 12-week behavior-validation study** (does prescribed puzzle
training reduce targeted mistakes?) — real infrastructure exists
(`routes/behavior_study.py`, opt-in/baseline/outcome endpoints,
`study_participants` collection), described across 6 separate docs
(`EXECUTION_READY.md`, `STUDY_ROSTER_2026_07_09.md`,
`WEEK4_EMAIL_CAMPAIGN.md`, `week4_8_execution_plan.md`,
`behavior_study_consent_email.md`, `behavior_validation_study_scope.md`) —
but there is no evidence anywhere (no downstream data, no results doc, no
sent-email tracking) that it was ever actually run past enrollment. One doc
uses fictional calendar dates that don't match its own commit date.

**Universal Habit Coach's core experiment** — the habit-detector
infrastructure (Tasks 1-4) shipped, but the actual pre-registered
randomized-holdout experiment that would prove "does this loop change
behavior" (not just personalization) was never run at full scope — only a
lighter 48h pilot-health monitor exists. The core product question this
whole initiative was built to answer is still unanswered.

## Genuinely open decisions needing your call

- **`player_profiles` has 3 independent writers**, never consolidated to 1.
  The specific bug this caused was patched as a side-effect of unrelated
  work, but the actual A/B/C consolidation decision from
  `player_profiles_consolidation_scope.md` was never made.
- **PWC Coach Conductor's "no-quiz purge" is half-done.** The
  memory/thread narrative engine (motif/concept/endgame/opening threads) is
  live. But the quiz-style surfaces it was meant to replace or reduce
  (escape-squares, predict-move, rate-move, habit-prompt) are all still
  present and wired. If removing those was still the intent, that hasn't
  happened.
- **Opening-service sprawl (~22 `opening_*` files) is confirmed still
  real**, not fixed. `opening_source_consolidation_scope.md` investigated a
  full merge, explicitly decided against it as low-value, and shipped only
  a scaffold (`add_opening.py`) that fixes "adding one new opening" without
  touching the underlying duplication. If this sprawl becomes a real
  problem again, know that a full consolidation was already scoped and
  deliberately rejected once — don't re-litigate without new information.

## Documentation corrections needed (not code, just accuracy)

- **CLAUDE.md's route table is stale in at least two places**: `/home` →
  documented as `HomePage.jsx`, actually `HomePageNew.jsx` (confirmed
  independently by two separate triage passes). `/training/pattern/:pattern`
  → documented as `PatternTraining.jsx`, which no longer exists; merged
  into `PrescribedTraining.jsx`.

## Confirmed DONE and live (no action needed, ~75 docs)

The large majority of the 109 docs describe features that are genuinely
built, live, and match their spec closely. Not itemized here individually —
available in the full per-agent triage output if a specific doc's status
is ever in question. Notable clean examples where the doc and code matched
closely and the doc's own status header was accurate:
`personal_concept_card_scope.md` (correctly self-declared superseded),
`motif_profile_backlog.md` (correctly self-documents its own build date and
remaining deferred items), `coach_derived_rating_scope.md` and
`coach_ladder_scope.md` (both correctly self-declare terminal status).
