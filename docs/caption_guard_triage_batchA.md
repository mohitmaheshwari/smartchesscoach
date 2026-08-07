# Caption-source guard triage — Batch A (14 files)

Investigated against `backend/scripts/check_caption_sources.py --strict`, run locally via:
`backend/.venv/Scripts/python backend/scripts/check_caption_sources.py --strict <files>`
to get the exact flagged lines (43 total across these 14 files), then traced each flagged
function's caller chain to a live route and, where live, to the actual frontend consumer to
see whether the flagged string reaches the rendered page or is a dead-end value.

Central pipeline entry point: `backend/services/caption_pipeline.py` → `build_move_teaching_decision`.
Checked `caption_pipeline.py`'s own import list — **none of these 14 files are imported by
`caption_pipeline.py` or any other allowlisted `caption_*` module**, so none qualify as a
literal "data supplier to the central pipeline" exemption.

---

## 1. backend/badge_service.py

**Classification: LEGITIMATE_EXEMPTION (dead-from-UI)**

Flagged lines 1746–1884 sit in `_generate_opening_explanation` / `_generate_tactical_explanation`
/ `_generate_positional_explanation` / `_generate_endgame_explanation` / `_generate_focus_explanation`
/ `_generate_why_score`, all called from `get_badge_details()`.

- Caller chain: `routes/player.py:774` (`GET /api/player/badges`) and
  `routes/player.py:791-803` (`GET /api/player/badges/{badge_key}/details`) — both routes are
  registered (`player_routes` mounted at `/api`, `server.py:477`).
- Frontend: the only component that calls `/badges/{badge_key}/details` is
  `frontend/src/components/BadgeDetailModal.jsx:882`. `grep -rn "BadgeDetailModal"
  frontend/src` finds **only its own definition/export** — it is never imported by any page
  or component. The summary endpoint `/api/player/badges` also has zero frontend callers.
- Player-facing impact: **none today.** The backend route is live and would return this
  prose if hit directly, but no UI path renders it — `BadgeDetailModal` is an orphaned
  component. Recommend either wiring it up for real or deleting it; until then this is dead
  weight, not an active violation.

---

## 2. backend/blunder_intelligence_service.py

**Classification: REAL_VIOLATION_LOW_RISK**

Flagged lines: 3017 (`_analyze_opening_strategy` → `critical_deviation.explanation`), 3507
(`_generate_future_advice` → `advice`).

- Caller chain: both feed `get_lab_data()` / `get_lab_data_async()` (line 3523, 3712), called
  from `routes/lab.py:216-219`, endpoint `GET /api/lab/{game_id}`.
- This endpoint **is** live and called by the current game-review page:
  `frontend/src/pages/LabV2.jsx:469` (`GET /api/lab/${gameId}`) — LabV2 is the routed
  `/game/:gameId` page per `App.js:281,286`.
- However, `grep -n "labData" LabV2.jsx` shows the page only reads
  `labData?.accuracy` and `labData?.core_lesson` — it never reads `labData.strategic_analysis`
  or `labData.future_advice`. The only consumer of those fields is
  `frontend/src/pages/LabClassic.jsx` (`strategic_analysis`, `future_advice`,
  `critical_deviation`), which is **not imported/routed in `App.js`** (dead page).
- Player-facing impact: the prose is computed and shipped in the `/api/lab/{game_id}` JSON
  payload (so it's inspectable over the network / one UI change from being rendered) but the
  live page does not currently display it. Low risk today, but it sits inside the response of
  a core Game Review endpoint, so any future dev wiring up these fields would silently
  reintroduce a parallel caption source.

---

## 3. backend/coach_play/coach_commentary.py

**Classification: REAL_VIOLATION_HIGH_RISK**

Flagged lines: 328 (`_analyze_missed_opportunity`), 900/925 (`generate_coach_chat_message`),
1041 (false positive — a keyword list, not prose), 1271 (`generate_response_to_user`).

- `generate_coach_chat_message` (lines 800-929, containing lines 900/925) has **zero callers**
  anywhere in the backend (`grep -rn "generate_coach_chat_message" backend` finds only its own
  `def`) — that half of the finding is dead code.
- `generate_response_to_user` (932+, containing line 1271) **is live**: called from
  `routes/coach_play.py:1622` inside `POST /api/coach/play/chat`, which is fetched by
  `frontend/src/components/coach-play/CoachChat.jsx:53` and
  `frontend/src/pages/CoachPlay.jsx:2558` — `/play-with-coach` is a core, routed surface.
  `CoachPlay.jsx:2574` (`message: data.response`) renders the exact string built by the
  `parts` list in `coach_commentary.py:1257-1301`, including line 1271's
  `f"That one was off — {bm} was stronger."`.
- Also confirmed: the file has an explicit "ZERO LLM in coaching... composed
  DETERMINISTICALLY" comment (line 1251-1256) documenting this as an intentional parallel
  engine for the *chat* feature — it classifies move quality and names the better move itself
  (via `CoachCommentary._classify_move_quality`/`analyze_move`), independent of
  `build_move_teaching_decision`.
- `_analyze_missed_opportunity` (line 328) is reachable via `coach.analyze_move()`, called
  both directly in `routes/coach_play.py:1595` and again inside `generate_response_to_user`
  (line 1118) — but its `missed_tactic` output is stored in `result["missed_tactic"]` and
  returned in the `/chat` JSON without being appended into `result["response"]` (verified: the
  `parts` list never references `result["missed_tactic"]`). So line 328's specific text is a
  same-response dead-end (present in payload, not rendered) — the concrete rendered violation
  is line 1271.
- Player-facing impact: **direct** — the "Ask the coach a question" chat bubble text on
  `/play-with-coach` is generated by this file, not the central pipeline.

---

## 4. backend/coach_play/pattern_indexer.py

**Classification: REAL_VIOLATION_LOW_RISK**

Flagged lines 317/320 (`_describe_mistake`, inside `PatternIndexer.index_user_patterns`).

- Caller chain: `_describe_mistake` output becomes `IndexedPattern.what_happened` (line 131-142),
  surfaced by `get_pattern_retrieval()` (line 395), called from
  `coach_play/personalized_coach.py:465` inside `get_personalized_coaching()`, which is called
  live from `routes/coach_play.py:1612` — the same `/coach/play/chat` handler as file 3.
- `personalized_coach.py:487-494` copies `what_happened` into
  `personal_context["similar_mistake"]["what_happened"]`.
- Traced into `coach_commentary.py`: the only place `personal_context["similar_mistake"]` is
  read in the code path that actually reaches `result["response"]` is the fallback branch at
  `coach_commentary.py:1288-1292`, which uses **only** `sm.get('opponent')` — `what_happened`
  is never appended there. It IS interpolated into an LLM `prompt` string at
  `coach_commentary.py:1076-1082`, but that `prompt` variable (built at line 1240) is **never
  passed to `call_llm`** anywhere in the function (confirmed no `call_llm(` call exists in
  `generate_response_to_user`) — it's leftover pre-refactor dead code, discarded before
  reaching the player.
- Also dead: `get_full_pattern_context` and `CrossGamePatternIndex`/`CrossGameIndex` in the
  same file have no callers outside the file itself and tests.
- Player-facing impact: computed and passed through a live core-surface call chain, but the
  specific flagged string currently dead-ends before rendering. One accidental edit to the
  fallback branch (adding `what_happened` to the message) would surface it directly — flagged
  as low-but-real risk rather than a clean exemption.

---

## 5. backend/coach_play/pre_move_guardian.py

**Classification: LEGITIMATE_EXEMPTION (dead code)**

Flagged line 845: `"tactical_blunder": "You missed a tactic before. Look harder."` inside
`EnforcementLadder.MESSAGES` (class defined at line 806, used by `evaluate_with_enforcement`
at line 971).

- `grep -rn "evaluate_with_enforcement|EnforcementLadder" backend` outside this file: **only
  hits in `backend/tests/test_enforcement_checkbox_improvement.py` and
  `test_streak_behavioral_enforcement.py`.** No production route imports `EnforcementLadder`.
- The live "are you sure?" guardian used by `routes/coach_play.py:1738-1740` is the
  **different** class `PreMoveGuardian` (line 108) / `evaluate_move_for_guardian` (line 746),
  which is not where the flagged line lives.
- Recommend `# allow-noncentral-caption` on line 845 (and the rest of `MESSAGES`), or delete
  `EnforcementLadder` if it's confirmed superseded by `PreMoveGuardian`.
- Player-facing impact: none — exercised only by tests.

---

## 6. backend/coach_play/punishment_puzzle.py

**Classification: REAL_VIOLATION_HIGH_RISK**

Flagged lines: file docstring example (line 10, arguably exempt as a comment/example — see
note) and line 447 (`f"{best_user_san} wins the pawn — your {cap_name} takes on ..."`, inside
the function building `PuzzleSpec.reveal`).

- Caller chain: `evaluate_for_puzzle` arms the puzzle at `routes/coach_play.py:9381`, and
  `evaluate_user_response` evaluates it at `routes/coach_play.py:7151`, both inside the core
  `POST /api/coach/play/move` handler (the move-submission endpoint for `/play-with-coach`).
- Frontend: `frontend/src/components/coach/PunishmentPuzzleCard.jsx` renders
  `puzzle.observation` (line 85), `puzzle.challenge` (line 88), and `feedback.feedback_text`
  (line 63) verbatim — `feedback_text` is built from `reveal` (the flagged f-string at line
  447). This card is imported by `CoachPlaySidebar.jsx` and `CoachPlay.jsx`, i.e. it renders
  directly inside the live `/play-with-coach` page.
- Player-facing impact: **direct** — this is a fully independent, deliberately-designed
  bespoke prose engine (the file's own docstring frames it as an alternative to "narrating"
  the normal way) producing observation/challenge/reveal text entirely outside
  `caption_pipeline.py`. This is the clearest "second engine" in the batch: live, core
  surface, definitely player-facing, definitely bypasses the central layer's classifier and
  templates. Worth a product conversation — it's a distinct interaction pattern (Socratic
  puzzle-on-blunder), not a per-move caption, so migrating it into
  `build_move_teaching_decision` may not be a clean fit; either way it needs an explicit,
  documented decision (scoped allowlist entry with a design rationale, or migrate), not silent
  drift.

---

## 7. backend/coach_play/teaching_coach.py

**Classification: LEGITIMATE_EXEMPTION (dead code)**

Flagged lines 316/318 inside `TeachingCoach._explain_why_move_was_weak`.

- `grep -rn "teaching_coach|TeachingCoach" backend` outside this file: **zero hits**, including
  no test coverage. The `TeachingCoach` class is not imported anywhere — fully orphaned file.
- Player-facing impact: none.

---

## 8. backend/coaching_classifier_service.py

**Classification: REAL_VIOLATION_LOW_RISK**

Flagged line 439: `f"This move gives up significant ground. {best_move} was stronger."`
inside `classify_move_for_coaching`.

- Caller chain: only caller is `interactive_training_service.py:209`
  (`classify_move_for_coaching(...)`), inside `get_user_puzzles()`, called from
  `routes/player.py:1479` → `GET /api/training/puzzles`, fetched live by
  `frontend/src/pages/TrainingNew.jsx:164` (`TrainingNew` is routed at `/coach` and `/focus`
  in `App.js:225,230`).
- BUT: `interactive_training_service.py:248-249` only pulls `classification.get('category')`
  and `classification.get('priority')` into the puzzle object sent to the frontend —
  `coaching_message` (the flagged field) is **never included** in the returned `puzzle` dict.
- Player-facing impact: live call chain, real player-facing endpoint, but this specific
  flagged string is computed and discarded before the response is built — a dead-end value,
  not currently visible to users.

---

## 9. backend/cognitive_gap_service.py

**Classification: REAL_VIOLATION_HIGH_RISK**

Flagged lines 760/761, 827/829, 875, 917, 949 — all inside `analyze_cognitive_gap`'s
per-case `explanation` / `evidence` fields.

- Caller chain: `analyze_cognitive_gap` + `get_coaching_message` are called from
  `routes/interactive.py:332,347`, endpoint `POST /api/games/{game_id}/move/{move_number}/analyze-gap`.
- Frontend: `frontend/src/pages/Reflect.jsx:361` calls this endpoint. `Reflect.jsx` is
  routed at `/reflect` (`App.js:404`) — CLAUDE.md lists it as a real page ("Game reflection").
  Confirmed rendering: `Reflect.jsx:1204` — `{awarenessGap.cognitive_gap.explanation}` — and
  `Reflect.jsx:1254` — `{awarenessGap.cognitive_gap?.coaching_focus || awarenessGap.coaching_message}`
  — both render the flagged strings **verbatim** to the player.
- Player-facing impact: **direct.** This is a fully independent explanation-generation engine
  (11 hand-written `Case N` branches producing `explanation` strings) that is the *only*
  source of prose for the `/reflect` page's cognitive-gap card — it does not call
  `build_move_teaching_decision` at all. Not one of the three surfaces named in the brief
  (Game Review / PWC / Lab), but it is a core, actively-routed, prose-heavy coaching page —
  functionally a fourth core surface the central-pipeline migration hasn't reached.

---

## 10. backend/community_learning_service.py

**Classification: REAL_VIOLATION_LOW_RISK**

Flagged line 242: `f"Incorrect. The best move was {puzzle['best_move_san']}"` inside
`attempt_community_puzzle`.

- Caller chain: `routes/training_advanced.py:3375` → `POST /api/community/puzzles/{puzzle_id}/attempt`,
  called live from `frontend/src/pages/TrainingNew.jsx:479` (routed page, see file 8).
- `TrainingNew.jsx` sets `feedback` to the raw response and renders `{feedback.message}` at
  lines 1075/1137/1205 — the flagged string **is rendered**.
- Player-facing impact: real, but narrow — a single factual sentence naming the correct move
  (no engine reasoning, no "why"), on the Training/puzzle surface rather than one of the three
  named core surfaces. Still a genuine bypass of the central layer for a real player-facing
  string.

---

## 11. backend/interactive_training_service.py

**Classification: REAL_VIOLATION_LOW_RISK**

Flagged line 407: `quality_text = "Acceptable, but you missed the best."` inside
`validate_puzzle_answer`.

- Caller chain: `routes/training_advanced.py:2528` → `POST /api/training/puzzle/validate`,
  called live from `frontend/src/pages/TrainingNew.jsx:486` (the "own puzzle" branch, sibling
  to file 10's community-puzzle branch).
- `interactive_training_service.py:480` sets `"message": quality_text` — this is the exact
  field `TrainingNew.jsx` renders at lines 1075/1137/1205 (`{feedback.message}`).
- Player-facing impact: real, but these are six generic templated quality labels ("Perfect!",
  "Good move, but there's a better one.", etc.) with no position-specific reasoning — same
  narrow scope as file 10, same Training surface, same secondary (non-core) classification.

---

## 12. backend/mistake_classifier.py

**Classification: REAL_VIOLATION_HIGH_RISK**

Flagged lines 897 (comment quoting a bug report — not itself emitted, see note), 1128, 1488,
1495, 1663-1685ish (`get_verbalization_template` — one branch per `MistakeType`).

- This file is imported by ~13 other backend files. Traced the highest-confidence live path:
  `services/postgame_analysis.py:941` imports `classify_mistake` inside `_analyze_mistakes()`.
  Line 952-954: `pattern_reason = classified.pattern_details.get("reason")` (the flagged
  `.reason` prose from `classify_mistake`'s internal rules, e.g. line 1495's
  `"You missed exploiting the overloaded {defender_piece}"`) **overwrites** the generic
  `explanation` variable when present.
- `_analyze_mistakes` feeds `analyze_postgame()`, called from `routes/coach_play.py:1279`
  inside `POST /api/coach/play/analysis`.
- Frontend: `frontend/src/components/PostGameLesson.jsx:174` — `{d.explanation}` — renders
  each mistake's explanation directly. `PostGameLesson` is imported by
  `CoachPlaySidebar.jsx`, the main sidebar of the live `/play-with-coach` page (per CLAUDE.md:
  "Main coaching sidebar, 1163 lines").
- Also confirmed live (not separately traced to render, but same classifier + same `.reason`
  field, additional exposure): `routes/interactive.py:600` (a Socratic-dialogue endpoint) and
  `coach_play/teaching/pattern_detectors.py:263` / `teaching_evaluator.py:460-585` (teaching
  mode detectors) also import from this file.
- Player-facing impact: **direct and high-confidence** — the "Key errors" list on the
  post-game lesson card in Play with Coach is populated by this classifier's own
  hand-authored English (`get_verbalization_template` / `pattern_details["reason"]`), not by
  `build_move_teaching_decision`. Given the breadth of import sites, this is effectively a
  second general-purpose "mistake explainer" living in parallel with the whole central layer.

---

## 13. backend/mistake_explanation_service.py

**Classification: LEGITIMATE_EXEMPTION (dead-from-UI, fallback-only)**

Flagged lines 411, 971 (inside `analyze_mistake_position` and `get_quick_explanation` /
`MISTAKE_TEMPLATES` lookup) — these are the **fallback** path, only reached when the primary
LLM call (`generate_mistake_explanation`) throws.

- Caller chain: `routes/lab.py:672-687`, endpoint `POST /api/explain-mistake` (note: this is a
  *different* route from `routes/coach.py`'s `POST /api/coach/explain-mistake`, which uses
  `services/line_parser.explain_line` and is unrelated to this file).
- Frontend: the only component calling `/explain-mistake` (no `/coach` prefix) is
  `frontend/src/components/Lab/GameSummary.jsx:67`. `GameSummary` is imported by
  `GameDecryption.jsx` (not `GameDecryptionV5.jsx` — the old file, unrouted anywhere in
  `App.js`) and by `LabV2.jsx`, but **`LabV2.jsx:57` has the `GameSummary` import
  commented out** (`// import GameSummary from "@/components/lab/GameSummary";`). No live page
  renders it.
- Player-facing impact: none currently — both the primary (LLM) and fallback (flagged)
  explanation paths in this file are unreachable from any active UI route today.

---

## 14. backend/opening_service.py

**Classification: REAL_VIOLATION_LOW_RISK**

Flagged line 119: `{"mistake": "Forgetting Bg5", "fix": "Bg5 pins the knight and creates
pressure. Essential move!"}` inside the hardcoded `OPENING_COACHING` dict.

- Sole importer: `blunder_intelligence_service.py:2890` — `from opening_service import
  OPENING_COACHING`, used inside `_analyze_opening_strategy` (the same function investigated
  in file 2).
- Same conclusion as file 2 applies directly: reachable via the live `GET /api/lab/{game_id}`
  endpoint, included in the JSON response's `strategic_analysis` block, but the current live
  page (`LabV2.jsx`) does not read `strategic_analysis` — only the dead `LabClassic.jsx` does.
- Player-facing impact: computed, shipped in a core-surface API response, not currently
  rendered. Low risk today, same "one wiring change away" caveat as file 2.

---

## Summary counts

| Classification | Files |
|---|---|
| REAL_VIOLATION_HIGH_RISK | 3 (coach_commentary.py, punishment_puzzle.py, mistake_classifier.py) + cognitive_gap_service.py = **4** |
| REAL_VIOLATION_LOW_RISK | blunder_intelligence_service.py, pattern_indexer.py, coaching_classifier_service.py, community_learning_service.py, interactive_training_service.py, opening_service.py = **6** |
| LEGITIMATE_EXEMPTION | badge_service.py, pre_move_guardian.py, teaching_coach.py, mistake_explanation_service.py = **4** |
| UNCERTAIN | 0 |

**Total: 14/14 classified**, none required the UNCERTAIN bucket — every file's liveness and
render-reach was resolvable by tracing the actual call chain and grepping the frontend for the
response field names.

### Headline findings

1. **`mistake_classifier.py` and `cognitive_gap_service.py` are the two highest-priority real
   violations.** Both are full independent "mistake explainer" engines (11+ hand-written
   English branches each) that render directly onto live pages —
   `mistake_classifier.py`'s `.reason`/`get_verbalization_template` text onto the Play with
   Coach post-game lesson card, `cognitive_gap_service.py`'s `explanation` onto `/reflect`.
   Neither calls `build_move_teaching_decision`; both are the *only* source of prose for their
   surface, not a duplicate of an already-central caption.

2. **`punishment_puzzle.py` is a deliberate, documented second engine** (its own docstring
   frames it as an alternative to normal narration) rendering directly in
   `PunishmentPuzzleCard.jsx` on `/play-with-coach`. Unlike the other findings, this looks like
   an intentional product decision to build a distinct Socratic-puzzle interaction rather than
   an accidental parallel caption path — it needs an explicit scoping decision, not just a
   migration ticket.

3. **A recurring "computed but not rendered" pattern** shows up in 4 of the 6 LOW_RISK files
   (`blunder_intelligence_service.py`, `pattern_indexer.py`, `coaching_classifier_service.py`,
   `opening_service.py`): the bespoke prose is built by live code reachable from a real
   endpoint, but the current frontend either dropped the field or never wired it up. These are
   real violations of the letter of the rule (bespoke prose exists outside the central layer,
   on a live path) but not of its player-facing spirit yet — they're one small frontend change
   away from becoming HIGH_RISK, so they shouldn't be waved through as clean exemptions.

4. **2 of the 4 exemptions are "dead-from-UI, not dead-from-backend"**
   (`badge_service.py`, `mistake_explanation_service.py`): the API route is registered and
   would serve the flagged prose if called directly, but the only frontend component that ever
   called it is unused or commented out. Recommend deleting the orphaned frontend components
   (or actually wiring them up) rather than leaving live backend routes with zero UI reach.
