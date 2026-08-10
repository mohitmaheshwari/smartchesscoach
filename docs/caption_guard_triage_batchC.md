# Caption-Source Guard Triage — Batch C (13 files)

Guard: `backend/scripts/check_caption_sources.py --strict`. Central layer:
`backend/services/caption_pipeline.py` (`build_move_teaching_decision`) + the
`caption_*` modules on its `ALLOWLIST`.

**Correction on allow-marker**: the task brief guessed `# allow-caption-source-guard`.
The guard script's actual opt-out marker (see its docstring, line 19) is:

```
# allow-noncentral-caption
```

Use that exact string, not the guessed one.

Exact flagged lines were reproduced locally with://
`python backend/scripts/check_caption_sources.py <the 13 files>` (docker not
required — same code, same result).

---

## Summary of verdicts

| # | File | Verdict |
|---|------|---------|
| 1 | move_intent_analyzer.py | REAL_VIOLATION_HIGH_RISK |
| 2 | opening_assessment_service.py | REAL_VIOLATION_HIGH_RISK |
| 3 | opening_curriculum_engine.py | REAL_VIOLATION_HIGH_RISK |
| 4 | opening_deviation.py | LEGITIMATE_EXEMPTION |
| 5 | opening_theory_lookup.py | LEGITIMATE_EXEMPTION |
| 6 | opening_walkthrough_service.py | REAL_VIOLATION_LOW_RISK |
| 7 | opp_quiet_threat_detector.py | LEGITIMATE_EXEMPTION |
| 8 | pattern_catalog.py | LEGITIMATE_EXEMPTION |
| 9 | pattern_learning/pattern_learner.py | REAL_VIOLATION_HIGH_RISK |
| 10 | pattern_learning/pattern_rule_extractor.py | LEGITIMATE_EXEMPTION (dead code) |
| 11 | pedagogical_opportunity_service.py | REAL_VIOLATION_HIGH_RISK |
| 12 | plan_analysis_service.py | REAL_VIOLATION_HIGH_RISK |
| 13 | position_explainer.py | LEGITIMATE_EXEMPTION (dead code) |

6 high-risk real violations, 1 low-risk real violation, 6 legitimate
exemptions (2 of those dead code, 4 genuine data suppliers to the central
pipeline that just need the opt-out comment on their docstring lines).

---

## 1. `backend/services/move_intent_analyzer.py`

**Verdict: REAL_VIOLATION_HIGH_RISK**

Flagged lines 37/41 are just the `unclear`-intent fallback strings inside
`analyze_move_intent()` — not even the interesting part.

Caller chain (both live, both on the core PWC surface):
- `backend/routes/coach_play.py:4550-4554` — inside the per-move guidance
  endpoint, when curriculum guidance has no `opponent_commentary`, calls
  `analyze_move_intent(last_fen, last_san)` on the **coach's own last move**
  and uses `intent.description` (with "You"→"Opponent" substitution) as
  `coach_move_commentary`, which flows straight into the JSON response the
  frontend sidebar renders.
- `backend/routes/coach_play.py:7127-7136` — when the user is off an opening
  curriculum's book, falls back to `analyze_move_intent(fen_before, move)` and
  uses `intent.feedback` / `intent.description` directly as
  `curriculum_feedback`, shown to the user as the coach's reaction to their
  move.

Both call sites hand-assemble player-facing sentences ("You castled to get
your king safe." / "Opponent {verb} ...") entirely inside
`move_intent_analyzer.py`, with no pass through `build_move_teaching_decision`.
Per repo memory ("One source of truth for coaching" — every caption surface,
including coach-own-move, is supposed to route through the central function),
this is exactly the parallel-engine pattern that rule exists to prevent, and
it's live on `/play-with-coach`, a core surface.

**Player-facing impact**: directly shown as the coach's move commentary and
as reaction-to-your-move feedback in Play with Coach.

---

## 2. `backend/services/opening_assessment_service.py`

**Verdict: REAL_VIOLATION_HIGH_RISK**

Flagged line 424 is inside `get_pregame_intro`'s `knows_basics` branch:
`f"You keep getting {w['position']} wrong. You played {...} but should play
{...}."`

Caller chain:
- `backend/routes/coach_play.py:6913-6916` — inside the `POST
  /coach/play/start` handler (structured-curriculum branch), calls
  `get_pregame_intro(db, user.user_id, opening_key)` and uses
  `pregame.get("intro", personalized_greeting)` **directly as
  `welcome_message`** — the coach's opening greeting shown the instant a
  curriculum-based PWC session starts.
- Also reachable via mounted endpoints `GET /coach/play/assess-opening` and
  `GET /coach/play/pregame-intro` (`coach_play.py:4709`, `4729`), though no
  frontend caller of those two exact routes was found — the `/start` path is
  the one confirmed live.

This is entirely hand-built prose (repetition-count callouts, "you played X
but should play Y") generated with zero involvement from
`caption_pipeline.py`, and it is the very first thing the user reads when
starting a structured-opening PWC session — a core surface.

**Player-facing impact**: becomes the coach's welcome message at PWC session
start for curriculum-based openings.

---

## 3. `backend/services/opening_curriculum_engine.py`

**Verdict: REAL_VIOLATION_HIGH_RISK** (dual-use file — legitimate as a data
supplier in one call path, a live bypass in another)

Flagged lines 275-276 are inside `get_opening_guidance()`'s "weak spot"
branch: personalized `hint` / `wrong_feedback` strings ("You played this
wrong {n} times before...").

Two distinct call chains:
- **Legitimate supplier path**: `caption_pipeline.py:3595-3632` (function
  `_apply_a11_curriculum_deviation`, gated on `is_user AND cp_loss>=30 AND
  full_move_number<=20`) imports `get_opening_guidance` and
  `_load_curriculum`, and places the tree's `wrong_feedback` verbatim into
  `caption_facts["curriculum_deviation_clause"]`. Here the central layer
  decides whether/how to surface it — this part is fine.
- **Live bypass path**: `backend/routes/coach_play.py:7102-7136` calls
  `get_opening_guidance(teaching_opening, move_history_san, user_color,
  assessment=assessment)` **directly** inside the per-move handler, with its
  own separate logic (not the A11 gate) to pick `right_feedback` /
  `wrong_feedback` / the personalized "weak spot" hint, and assigns the
  result straight to `curriculum_feedback` which is returned to the frontend.
  Also `coach_play.py:4546-4547` reads `guidance["opponent_commentary"]`
  from the same function for narrating the coach's own move.

So the same hand-authored prose source is consumed once through the central
gate and once completely outside it, on the same live PWC surface — the
"second engine" pattern for opening curriculum specifically.

**Player-facing impact**: PWC opening-teaching hints/right-wrong feedback and
opponent-move commentary, independent of and unguarded by the central
caption gates.

---

## 4. `backend/services/opening_deviation.py`

**Verdict: LEGITIMATE_EXEMPTION** — data supplier / docstring, needs the
opt-out comment.

`detect_opening_deviation()` returns a pure structured dict per its own
documented schema (`user_color`, `in_book_through_user_move`, `deviation:
{user_move_number, ply, played_san, expected_san, last_opening_name}`,
`version`) — no free-text sentence field anywhere in the module.

Caller: `backend/analysis_worker.py:1401` stores the dict verbatim as
`analysis_doc["opening_deviation"]`. The actual displayed sentence is built
**in the frontend**: `frontend/src/components/GameDecryptionV5.jsx:1865-1869`
composes `"Played {played} — book continues with {expected} — {idea}"` from
the structured fields.

Flagged line 6 (`Surfaces in Lab game review as "you played the Italian Game
through`) is inside the module's top-of-file docstring, describing what the
frontend later renders — not code that emits that string.

**Action**: append `# allow-noncentral-caption` to line 6 (and check line 7
if the pattern spans it) since it's documentation quoting example UI text.

**Player-facing impact**: none directly from this file — it supplies facts,
Game Review's frontend builds the sentence.

---

## 5. `backend/services/opening_theory_lookup.py`

**Verdict: LEGITIMATE_EXEMPTION** — data supplier, needs the opt-out comment.

`match_position()`, `classify_played_move()`, `top_best_move()` all return
dicts/tuples/enums (`"best"`/`"mistake"`/`"critical_only"`), never a
composed sentence.

Caller: `caption_pipeline.py:2655-2679` imports all three functions directly
and populates `caption_facts["opening_theory_*"]` keys from the returned
dicts — a textbook data-supplier-to-the-central-layer pattern (same shape as
the already-allowlisted `caption_facts.py`).

Flagged line 233 (`'best' / 'mistake' are precise teaching moments: "you
played the`) is inside `classify_played_move`'s docstring, explaining the
return-value semantics with example phrasing — not runtime output.

**Action**: append `# allow-noncentral-caption` to line 233.

**Player-facing impact**: none directly — pure fact supplier to the central
layer.

---

## 6. `backend/services/opening_walkthrough_service.py`

**Verdict: REAL_VIOLATION_LOW_RISK**

Flagged lines: 192 (`f"You played {move_san} but {best_move} was better."`)
inside `key_lessons` construction, and 291 (`return f"Not the best. {best}
was stronger."`) inside `_get_mistake_idea()`.

Confirmed live and mounted:
- `backend/routes/lab.py:852-864` — `GET /api/opening-walkthrough` →
  `generate_walkthrough(db, user_id, opening_name, call_llm_func)`.
- `frontend/src/App.js:31,349-351` routes `/opening-walkthrough` →
  `frontend/src/pages/OpeningWalkthrough.jsx`, which calls exactly that
  endpoint (`OpeningWalkthrough.jsx:53-54`).

The service builds substantial bespoke prose independent of
`caption_pipeline.py`: per-move `idea` strings for good/opponent/mistake/
inaccuracy moves (`_get_good_move_idea`, `_get_opponent_idea`,
`_get_mistake_idea`, `_get_inaccuracy_idea`), `key_lessons` "what_happened"/
"why" text, `remember` lines, and it even runs its **own separate LLM call**
(`_generate_walkthrough_narrative`) cached in a dedicated
`opening_walkthroughs` collection.

Scoped as LOW risk rather than HIGH because `/opening-walkthrough` is a
distinct, secondary page — not Game Review (`/game/:gameId`), not
`/play-with-coach`, not the main Lab review — even though the prose volume
here is substantial and it duplicates a lot of what the central layer already
does for mistakes elsewhere.

**Player-facing impact**: the entire content of the dedicated Opening
Walkthrough page (a guided lesson built from the user's own games).

---

## 7. `backend/services/opp_quiet_threat_detector.py`

**Verdict: LEGITIMATE_EXEMPTION** — data supplier, needs the opt-out comment.

`detect_quiet_when_threatened()` returns `{"piece": ..., "square": ...,
"best_san": ...} | None` — a fact dict, not prose.

Caller: `caption_pipeline.py:5531` imports and calls it inside a
`try/except`, consuming the returned dict as more caption_facts material —
same supplier pattern as #5 above, and reuses
`played_hangs_detector._winnable_squares` (an existing validated primitive).

Flagged line 7 (`you just take it. The bare caption was "Opponent's X is a
mistake."; this`) is inside the module's top docstring, quoting the OLD
(pre-this-detector) caption text for historical context on why the detector
was built — not code producing that string.

**Action**: append `# allow-noncentral-caption` to line 7.

**Note for the person scoping the allowlist**: the file's own docstring
says `STATUS: v0.1, NEEDS REVIEW (do not wire yet)` but it IS wired
(caption_pipeline.py:5531) — that comment is stale and should probably be
updated or removed separately from this triage.

**Player-facing impact**: none directly — pure fact supplier.

---

## 8. `backend/services/pattern_catalog.py`

**Verdict: LEGITIMATE_EXEMPTION** — data supplier, needs the opt-out comment.

`detect_opp_move_punishments()` and `detect_opp_positional_mistake()` both
return `Dict` of fact keys (confirmed by reading `detect_opp_positional_mistake`'s
own docstring: "Returns a dict of fact keys (opp_played_*) that
R12_blunder.json's why_clauses_opp section reads").

Caller: `caption_pipeline.py:1241` (`detect_opp_move_punishments`) and
`:1260` (`detect_opp_positional_mistake`) — both inside the central layer,
feeding `R12_blunder.json`'s template system. Other callers
(`game_decryption_v5_service.py`, `routes/games.py:1035`,
`pattern_progress_aggregator.py`, `pattern_event_logger.py`) use
`resolve_pattern_ids` / `detect_position_patterns` / `get_pattern` — all
lookups/metadata, not prose emission.

Flagged line 395 (`"""v80 (2026-05-25) — Mohit: "Opponent's a3 is a
mistake. Your`) is inside `detect_opp_positional_mistake`'s function
docstring, quoting Mohit's original bug-report feedback verbatim as the
rationale for the detector — not runtime output.

**Action**: append `# allow-noncentral-caption` to line 395.

**Player-facing impact**: none directly — pure fact supplier to the central
layer.

---

## 9. `backend/services/pattern_learning/pattern_learner.py`

**Verdict: REAL_VIOLATION_HIGH_RISK**

Flagged lines 212/220 are actually in `pattern_rule_extractor.py` per the
guard output — for *this* file the flagged lines are 348
(`5. Speak directly to the student ("You played X instead of Y
because...")`), a bullet inside an LLM prompt template
(`_build_correction_prompt`, lines 319-356) that instructs GPT to generate a
`corrected_explanation` and return it as JSON.

Caller chain (confirmed live end-to-end):
- `pattern_learning/auto_correction_service.py:39,66` — `AutoCorrectionService.__init__`
  instantiates `PatternLearner(api_key)` as `self.learner`.
- `backend/routes/coach_advanced.py:2326-2389` — `POST
  /api/coach/pattern-learning/feedback` (mounted at `server.py:479`) calls
  `service.submit_feedback_and_correct(...)`, which uses the learner to
  generate `corrected_explanation`, returned directly in the response.
- `frontend/src/components/FeedbackModal.jsx:80,107-110` — used with
  `source="lab"`, `"reflect"`, and `"coach_play"` — posts to that exact
  endpoint and shows `result.corrected_explanation` in a toast.
- `frontend/src/pages/CoachPlay.jsx:2048,2070-2075` — the **Play with
  Coach page itself** also posts to the same endpoint when a user marks a
  coach message "wrong", and shows the LLM-generated
  `corrected_explanation` in a toast.

This is a full parallel LLM caption-generation path — user flags a caption
as wrong, and an entirely separate LLM prompt (not `build_move_teaching_decision`)
regenerates a new explanation that gets shown to the user, on core surfaces
(PWC, Lab, Reflect).

**Player-facing impact**: the "corrected" coaching explanation shown via
toast whenever a user submits "this was wrong" feedback anywhere in the app.

---

## 10. `backend/services/pattern_learning/pattern_rule_extractor.py`

**Verdict: LEGITIMATE_EXEMPTION — dead code**

Flagged lines 212/220 are hardcoded `"explanation_template"` string values
inside example/default pattern dicts (e.g. `"The move {best_move} was better
because it gives your king breathing room (luft)..."`, "You missed a back
rank mate threat...").

Repo-wide grep (not just `backend/`) for `pattern_rule_extractor`,
`PatternRuleExtractor`, and `PositionFeatures` (this file's own dataclass,
distinct from the same-named class in `coach_play/teaching/types.py`) finds
**zero importers** anywhere — not in `pattern_learning/__init__.py`'s
exports (which list `FeedbackCollector`, `PatternLearner`, `RuleValidator`,
`RuleExecutor`, `LearningDB`, `AutoCorrectionService` — `PatternRuleExtractor`
is conspicuously absent), not in `auto_correction_service.py`, not in any
route, script, or test. The one internal match (`self.extractor =
PatternRuleExtractor()` at line 418) is the class referencing itself within
the same file.

This reads as an earlier, superseded design (feature-extraction +
templated-rule generation) that was replaced by `pattern_learner.py`'s
direct-LLM-prompt approach and left orphaned.

**Action**: no code executes this module; either delete it or leave it
unallowlisted since the guard already only scans files with `import chess`
and it will keep flagging until removed — no `# allow-noncentral-caption`
needed since dead code doesn't need a runtime opt-out, but worth a follow-up
cleanup ticket.

**Player-facing impact**: none — never imported.

---

## 11. `backend/services/pedagogical_opportunity_service.py`

**Verdict: REAL_VIOLATION_HIGH_RISK**

Flagged lines 762/770 are inside `evaluate_user_response()`'s
`missed_messages` dict: `f"You missed a fork! {best_exploit} attacks two
pieces at once. Tip: ..."` / `f"You missed a pin! {best_exploit} pins a
piece to a more valuable one behind. Tip: ..."` (FORK/HANGING_PIECE/PIN/
SKEWER all have their own hardcoded templates, lines 747-785).

Caller chain — confirmed live and **default-on**:
- `backend/coach_play/coach_game_session.py:376` — `start_coach_session`
  sets `pedagogical_mode_active=True` with the comment "Enable pedagogical
  opponent by default" for every new PWC session.
- `coach_game_session.py:822-880` (`_make_coach_move`) — when
  `game_phase in non_opening_phases and session.pedagogical_mode_active`,
  instantiates `PedagogicalOpportunityService` and calls
  `should_create_opportunity` to have the coach deliberately play a
  "good-but-not-best" move as bait.
- `coach_game_session.py:486-510` — on the user's next move, if
  `session.pending_opportunity` was set, calls
  `ped_service.evaluate_user_response(...)`, which returns the hardcoded
  "found"/"missed" message shown to the user as `consequence_feedback`.

This is a fully independent, template-based coaching-prose engine, wired
into the default game-play loop of Play with Coach — the core surface —
completely bypassing `caption_pipeline.py`.

**Player-facing impact**: the "You missed a fork!" / "Excellent! You found
the fork!" style consequence messages that appear after nearly every
non-opening move in a default PWC game (since the feature is on by default).

---

## 12. `backend/services/plan_analysis_service.py`

**Verdict: REAL_VIOLATION_HIGH_RISK**

Flagged line 387 (`f"This is the move you missed."`) is the tail of
`_build_explanation()`'s `missed_tactic` branch (lines 361-402), which
hand-assembles full sentences for `missed_tactic` / `calculation_depth` /
generic gap types, e.g.: `"Your calculation stopped at move {n}. You
expected {x}, but {y} is a {tactic} that changes everything (+N.N pawns
swing). This is the move you missed."`

Caller chain — confirmed live and mounted:
- `backend/routes/analysis.py:1233-1265` — `POST /analyze-plan` (mounted via
  `server.py:364,472`) calls `analyze_user_plan(fen, user_move, plan_moves,
  plan_reasoning)` from this module and returns `asdict(analysis)` directly.
- `frontend/src/components/GameDecryptionV5.jsx:610-627` — the core Game
  Review page (`/game/:gameId`) posts to `/analyze-plan` (the "what was your
  plan?" feature: user enters their intended continuation, backend explains
  where it broke down) and stores the result in `planAnalysis` state,
  rendered in the UI.

This is a second, independent explanation-builder living on the single most
central review surface in the product, entirely outside
`caption_pipeline.py`.

**Player-facing impact**: the explanation text shown when a user uses the
"What was your plan?" feature on Game Review.

---

## 13. `backend/services/position_explainer.py`

**Verdict: LEGITIMATE_EXEMPTION — dead code**

Flagged lines 401-414 are hardcoded headline/explanation string values in
what looks like a lookup table for missed-capture / missed-check messages
("You missed a winning capture" / "The best move was capturing material...").
The module's own docstring explicitly frames it as rule-based ("This is NOT
an LLM - it's rule-based chess pattern recognition").

Repo-wide grep for `position_explainer` (not scoped to `backend/`) finds
**zero references anywhere** — no route, service, script, or test imports
it.

**Action**: no opt-out comment needed (nothing executes it); candidate for
deletion in a follow-up cleanup, same as #10.

**Player-facing impact**: none — never imported.

---

## Cross-cutting notes for whoever scopes the blocking allowlist

- Four of the six exemptions (`opening_deviation.py`, `opening_theory_lookup.py`,
  `opp_quiet_threat_detector.py`, `pattern_catalog.py`) are genuine data
  suppliers already consumed by `caption_pipeline.py` — they just need
  `# allow-noncentral-caption` on the specific docstring lines the guard's
  regex matches (it doesn't skip docstrings, only `#`-comments and blank
  lines), rather than being added to the file-level `ALLOWLIST`. Adding them
  to `ALLOWLIST` wholesale would be too broad since these files could grow
  real prose-building code later without the guard catching it.
- Two files (`pattern_rule_extractor.py`, `position_explainer.py`) are dead
  code with zero importers repo-wide — worth a deletion ticket independent of
  this triage; until deleted they'll keep tripping the guard on every scan.
- The six HIGH_RISK violations (`move_intent_analyzer.py`,
  `opening_assessment_service.py`, `opening_curriculum_engine.py`,
  `pattern_learning/pattern_learner.py`, `pedagogical_opportunity_service.py`,
  `plan_analysis_service.py`) all sit on confirmed-live, confirmed-mounted,
  confirmed-frontend-wired code paths reaching Play with Coach and/or Game
  Review — these are not stale/theoretical findings.
- `opening_curriculum_engine.py` is the clearest case of the exact disease
  the guard docstring describes ("a new surface growing its OWN caption
  engine that bypasses the central layer") because the SAME function
  (`get_opening_guidance`) is legitimately gated when called from
  `caption_pipeline.py`'s A11 logic, and ungated when called directly from
  `routes/coach_play.py`.
