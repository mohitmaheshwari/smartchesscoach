# Caption-Source Guard Triage — Batch B (13 files)

Investigated with `docker exec chess-coach-backend python3 scripts/check_caption_sources.py --strict <file>`
(container code is a slightly older snapshot than the working tree — line numbers below are given for
**both** the guard's reported line and the current working-tree line where they differ; content matches).

Legend: LEGITIMATE_EXEMPTION / REAL_VIOLATION_LOW_RISK / REAL_VIOLATION_HIGH_RISK / UNCERTAIN

---

## 1. backend/opening_trainer_service.py

**Classification: LEGITIMATE_EXEMPTION** (static curated reference data, not a per-move caption engine)

Flagged lines 109, 180, 217, 279, 432 are all string literals inside `OPENINGS_DATABASE`, a hand-authored
dict of opening names/traps/variation ideas (e.g. `"idea": "Black pins the knight. Very sharp and
double-edged."`). This is fixed reference/theory content — analogous to `data/traps.json` /
`data/endgames.json` — not text generated from a specific user's board state or mistake.

**Reachability (real, but a secondary surface):** `OPENINGS_DATABASE` and `get_opening_training_content` /
`get_opening_quiz` are imported live in `backend/routes/training_advanced.py:2653-2924` behind
`GET /training/openings/{key}`, `GET /training/openings/{key}/quiz`, `GET /training/openings-database`.
Frontend callers: `frontend/src/components/OpeningTrainer.jsx` (mounted inside `TrainingNew.jsx`, which is
routed live at `/coach` and `/focus` in `App.js:223-232`) and `frontend/src/components/OpeningQuiz.jsx`
(routed at `/training/quiz/:openingKey` via `OpeningQuizPage.jsx`, `App.js:334-338`).

**Player-facing impact:** Static opening-theory copy shown on the Opening Trainer widget and opening quiz —
not per-move mistake coaching, doesn't compete with or bypass `build_move_teaching_decision`. Recommend
`# allow-noncentral-caption` on the 5 flagged lines (or add the file to the guard's data-supplier
allowlist) rather than rewriting it through the pipeline.

---

## 2. backend/pdr_service.py

**Classification: LEGITIMATE_EXEMPTION — fully dead code**

`grep -r "pdr_service"` across the **entire repo** (content search, not just filename) returns zero hits
outside the file itself — no route, service, or test imports `get_refutation`, `generate_idea_chain_explanation`,
or `get_simple_refutation_fallback`. The module (an LLM-based "Personalized Decision Reconstruction"
explainer, flagged lines 192/205/209) is orphaned: written, never wired to any endpoint.

**Player-facing impact:** None — unreachable code.

---

## 3. backend/position_analysis_service.py

**Classification: REAL_VIOLATION_HIGH_RISK**

Flagged lines 407/409 (`"However, this is a serious mistake."` / `"...a mistake."`) live inside
`generate_verified_insight()`, called from:
- `backend/routes/reflect.py:206-282` — `POST /api/reflect/explain-moment` (mounted, `server.py:340,448`)
- also from `reflect_service.py:374/406` and `plan_interpretation_service.py`

`explain-moment` is a **second, fully independent LLM coaching engine**, entirely outside
`caption_pipeline.py`: it builds `generate_verified_insight()` facts, then calls its own
`call_llm(system_message="You are a supportive chess coach...", model="gpt-4o-mini")`
(`reflect.py:230-236`), and falls back to the raw `verified_impact`/`verified_better_plan` strings
(containing the flagged lines) whenever the LLM output fails validation or errors
(`reflect.py:255-277`).

**Reachability:** Confirmed live. `frontend/src/pages/Reflect.jsx:506` calls
`POST /reflect/explain-moment` directly; `Reflect.jsx` is routed at `/reflect` (`App.js:404`), a primary
nav page (post-game reflection flow), not a dead component.

**Player-facing impact:** Users on the Reflect page get an LLM-generated (or verified-insight-fallback)
"impact"/"better_plan" explanation of their move that never passes through
`build_move_teaching_decision` or the verifier stack — exactly the "second coaching engine" anti-pattern
called out in repo memory (`project_pwc_runs_second_coaching_engine`, `feedback_one_source_of_truth`).
Classified HIGH_RISK despite Reflect not being one of the 3 explicitly-named core surfaces, because it is
a complete standalone LLM caption path with real hallucination exposure, not just a decorative string.

---

## 4. backend/routes/coach.py

**Classification: LEGITIMATE_EXEMPTION** (docstring false-positive + two dead/unwired endpoints)

- **Line 3467** (`"best_move": "Bxh7+",  # What was better`) is inside a request-body **docstring example**
  for `POST /human-coach/mistake-response` — never executed as prose. That endpoint itself (delegates to
  `services/human_coach_service.get_socratic_response`, not one of our 13 files) has **zero frontend
  callers** (`grep` across `frontend/src` for `human-coach/mistake-response` — no matches) — dead in
  practice regardless.
- **Lines 3999-4023** (`"Arre {first_name}, remember {time_ref}..."` etc.) live inside
  `GET /coach/memory-lane` (`coach.py:3926-4034`).
- **Lines 4152-4155** (`"Dekho {first_name}, this is where you played..."`) live inside
  `GET /coach/habit-challenge` (`coach.py:4084+`).

Both `memory-lane` and `habit-challenge` are mounted, real routes, but `grep -r "memory-lane\|habit-challenge"
frontend/src` returns **no matches** — no page or component ever fetches them. They are backend-only,
unreferenced by the live UI.

**Player-facing impact:** None currently — orphaned endpoints. Flag for cleanup risk: if either endpoint
is wired to a UI later, the Indian-English "memory"/"challenge" templates would become a live bypass and
should be migrated to the central pipeline first.

---

## 5. backend/routes/coach_play.py

**Classification: REAL_VIOLATION_HIGH_RISK** — this is the file with the clearest, most damaging findings.

All three live sites are inside `POST /coach/play/v5/interactive-feedback` (`get_interactive_coaching`,
`coach_play.py:2823-4162`), the endpoint `frontend/src/pages/CoachPlay.jsx` calls directly at lines
1564/1634/1716 — the real-time move-feedback loop for **Play with Coach**, one of the three explicitly
named core surfaces.

1. **Impulse-warning chat message** (guard lines 3036/3041, current ~3036/3041): hand-built f-string
   (`f"You played {move_san} in {_tspent_disp}s — that turned into a {_grade} ({cp_loss}cp lost)..."`)
   inserted directly into `db.coach_messages` with `"type": "impulse_warning"`. Confirmed rendered:
   `frontend/src/components/coach/CoachPlaySidebar.jsx:529,625` special-cases
   `msg.type === "impulse_warning"` and displays the message text verbatim in the PWC chat feed.

2. **`theory_applied` field** (guard/current line ~3714): `coaching_dict["theory_applied"] = f"You played
   the book move in the {opening_name}. The theory is sticking."` — appended directly onto the
   otherwise centrally-generated `coaching_dict` payload (built via `shared_coaching_v5.generate_move_coaching`).
   Confirmed rendered: `frontend/src/components/shared/V5CoachingCard.jsx:333,342-343` renders
   `coaching.theory_applied` as an inline span, and `CoachPlay.jsx:3414` reads it to color the last-move
   square "book" vs severity.

3. **Post-game `pattern_verdict`** (guard lines 9845/9921 → current 9953/9921, inside
   `GET /coach/play/postgame/{session_id}`, `coach_play.py:9817+`): hand-built messages such as
   `f"This time, no {pattern_label.lower()} mistakes."`, `f"Again, {diag.get('short', ...)}."`, and
   `f" On move {worst_move.move_number}, you played {worst_move.user_move} instead of
   {worst_move.best_move}."`. Confirmed rendered: `frontend/src/pages/CoachPlay.jsx:671,3009,3446` fetches
   this endpoint and passes the response into `CoachPlaySidebar` → `PostGameReflection.jsx`, which reads
   `data.pattern_verdict` (lines 45,48,64) and `data.coach_summary` (line 172) directly into the DOM. This
   is the **Post-Game Reflection card shown at the end of every PWC game**.

**Dead sub-finding (for completeness):** `_transform_to_fun_language()` (guard lines 4182/4184) has
**zero callers** anywhere in the codebase — dead code, no action needed.

**Player-facing impact:** Real, high-frequency, core-surface bypass. Three independent hand-built prose
generators feed the live PWC chat feed, the coaching card, and the post-game reflection card — none of
them route through `build_move_teaching_decision`. This is the single clearest violation in the batch.

---

## 6. backend/routes/games.py

**Classification: REAL_VIOLATION_LOW_RISK** (one live sub-feature confirmed rendered; two others computed but currently dead in the frontend)

All three flagged spots are inside `GET /games/{game_id}/coach-review` (`games.py:513+`), fetched live by
`frontend/src/pages/LabV2.jsx:476` — the **/game/:gameId core Game Review page**.

- **Trap "story" text** (lines 679-687, e.g. `f"You played the {trap.name} and it worked!"`): **confirmed
  rendered** — `LabV2.jsx:2004` displays `{t.story || t.explanation}` inside the opening/traps panel. This
  is a small supplementary blurb (trap-recognition note), separate from the main narrative.
- **Key-moment `summary` fallback** (lines 783/785, `f"You played {user_move}; the engine's pick was
  {best_move}."`): part of `result["key_moments"][i]["summary"]`. Grepped `key_moments` usage across
  `LabV2.jsx` — the only reference is a code comment (line 1001); the actual "Try yourself" interactive
  button sources its FEN/moves from a different, principle-based object (`p.fen_before` /
  `p.san_played`, `LabV2.jsx:1814-1819`), not `coachReview.key_moments`. This field is returned by the API
  but **not currently rendered**.
- **`phase_story`** (lines 981-987, e.g. `"You played well until the endgame, then it collapsed."`): part
  of `result["session"]`. `grep "coachReview\." frontend/src/pages/LabV2.jsx` shows no reference to
  `coachReview.session` anywhere — dead in the current frontend.

Notably, the file's **primary** narrative panel (`result["story"]`, opener/principles/summary_table/
good_moves/homework/closing, `games.py:867-884`) is built by `services/game_coach_review.compose_story`,
which explicitly **prefers `decryption_data` (the central-pipeline V5/R12_blunder captions)** — that part
is correctly central-pipeline-sourced. The violation is scoped to the separate, smaller trap-story
sub-feature that sits next to it.

**Player-facing impact:** A short trap-recognition sentence on the core Game Review page bypasses the
central pipeline; the other two computed strings are effectively dead weight (no current UI reads them),
but recommend deleting or gating them rather than leaving orphaned bespoke-prose code paths live.

---

## 7. backend/routes/interactive.py

**Classification: LEGITIMATE_EXEMPTION** (docstring + effectively-dead endpoint)

- **Line 114** — pure docstring example (`- "You played 8 moves under time pressure"`) inside
  `get_game_time_analysis`'s docstring, never executed as a string literal returned to a client.
- **Line 700** — `answer = mistake_analysis.get("template", f"The best move was {best_move_for_user}.")`,
  a fallback inside `POST /game/{game_id}/ask` (`ask_about_move`, `interactive.py:440+`), which also
  independently calls an LLM (`system_message="You are a chess coach who ONLY verbalizes pre-analyzed
  facts..."`, line 691).

**Reachability:** The route is mounted (`server.py` includes `interactive_routes.router`), and its only
frontend caller is `frontend/src/components/BadgeDetailModal.jsx:484`. `BadgeDetailModal` is defined and
exported but **never imported by any other frontend file** — it is an orphaned component, not mounted in
the live app (confirmed via repo-wide grep for `BadgeDetailModal`).

**Player-facing impact:** None currently — the endpoint is live on the backend but has no live caller in
the shipped UI. Same latent-risk caveat as `routes/coach.py`'s dead endpoints: if `BadgeDetailModal` (or a
new caller) is ever wired up, this becomes a second independent LLM Q&A engine on a real surface.

---

## 8. backend/routes/lab.py

**Classification: REAL_VIOLATION_HIGH_RISK**

Two distinct sites, both on the core Game Review page (`/game/:gameId` → `LabV2.jsx`):

1. **Lines 1109/1112** (`f"You played {user_move}; the engine's pick was {best_move}."`) — inside
   `GET /lab/{game_id}/deep-strategy` (`lab.py:955+`), building `critical_moments[0]["coach_explanation"]`.
   Reachable (`LabV2.jsx:511` fetches it into `deepStrategy` state), but `deepStrategy` is **never read
   again** anywhere else in `LabV2.jsx` after the fetch effect (confirmed via full-file grep) — the data
   is fetched and discarded. Its other caller, `LabClassic.jsx`, is **not routed** in `App.js` at all
   (dead page). → this specific sub-finding is effectively dead-in-practice, not rendered today.

2. **Lines 1323/1403/1426/1435** (`f"{user_move_san} is playable, but {request.best_move} was stronger
   here."`, `"...loses a pawn..."`, `"...You played the same move again..."`) — inside
   `POST /lab/evaluate-move` (`evaluate_practice_move`, `lab.py:1245+`). This is a **complete, independent,
   heuristic-based move-quality classifier** (piece-value tables, `is_capture`/`is_piece_hanging`/`gives_check`
   checks via python-chess, no Stockfish/no central pipeline) that assigns `quality`/`cp_loss`/`feedback`
   from scratch.

**Reachability confirmed for (2):** `LabV2.jsx:993` POSTs to `/lab/evaluate-move` for the "try the best
move yourself" interactive-solve feature on Game Review; the response's `.feedback` string is shown via
`toast.success/info/error(evalResult.feedback)` (`LabV2.jsx:1045,1047,1178,1180`) — directly surfaced to
the user.

**Player-facing impact:** The interactive-solve move-quality feedback on the core Game Review page is
generated by a second, from-scratch heuristic engine (not even a database-of-fact-driven one — genuinely
reasons about the board itself and invents severity/cp_loss numbers independently of Stockfish), fully
bypassing `build_move_teaching_decision`. This is a real second engine, not just leftover prose.

---

## 9. backend/routes/training_advanced.py

**Classification: LEGITIMATE_EXEMPTION** (all 4 sites resolve to dead code or currently-unrendered fields on a live endpoint — flagged as a latent-risk watch item, not a clean pass)

- **Line 298** (`BEHAVIOR_SENTENCE` dict, `"missed_tactic": "You missed a tactic that was there."`) is
  inside `_generate_game_story()`, called from `_build_lab_coaching()` (`training_advanced.py:777`), which
  IS invoked by the live `GET /lab-coach-pick` endpoint (`training_advanced.py:1642`, `CLAUDE.md`'s
  documented "Lab page with decay-model Coach's Pick"). Its output lands in `problem_games[].behavior`.
  Grepped all 3 live frontend consumers of `/lab-coach-pick` (`Dashboard.jsx`, `AllGames.jsx`,
  `CoachPlay.jsx`) for `.behavior` — **zero references**. `Dashboard.jsx`'s verdict/subline instead reads
  `root_cause`/`subline` from a **different**, newer function (`services/game_coach_summary.compute_game_summary`,
  `training_advanced.py:1461-1465`) — `behavior` is a superseded/legacy field still computed but no
  longer displayed.
- **Line 1101** (`STRENGTH_DATA["solid_play"]`) — same function family, feeds `coaching["strengths"]`.
  Grepped all `/lab-coach-pick` consumers for `.strengths` — zero references. (A same-named `strengths`
  array exists on the unrelated `/progress/narrative` endpoint used by `UnifiedProgress.jsx`, not this one.)
- **Lines 1188-1194** (`_describe_critical_moment()`) — **zero callers anywhere** in the codebase; dead code.
- **Line 2275** (inside `describe_plan_moves`'s neighbor, actually `POST /training/milestone/explain`,
  `training_advanced.py:2235+`) — `grep` for `milestone/explain` across `frontend/src` → **no matches**;
  dead endpoint.

**Player-facing impact:** None today. Caveat: `behavior`/`strengths` sit unused inside the live
`/lab-coach-pick` payload — an easy accidental resurrection path (a future frontend change could start
reading them without anyone noticing they bypass the pipeline). Recommend deleting the dead fields/functions
rather than leaving them as loaded guns, even though today's classification is exemption.

---

## 10. backend/services/active_teaching_engine.py

**Classification: LEGITIMATE_EXEMPTION — retired code path, both callers currently inert**

Flagged lines (542/582/601, e.g. `f"Okay, you played {move_san}. Let's continue."`) live inside
`ActiveTeachingEngine`'s socratic-dialogue templates. Two real call sites:

1. `backend/routes/coach_play.py:9571` (`generate_teaching_feedback`, inside the "Fall back to Active
   Teaching Engine for middlegame+" branch) is gated by `if not engine_handled and not coach_game_over:`.
   `engine_handled` defaults from `services.message_decision_engine.ENABLE_DECISION_ENGINE`, which is
   hard-set to **`True`** (`message_decision_engine.py:30`) — so in the current codebase this whole legacy
   block is always skipped (`pass  # Silent — evaluate-pending handles opponent awareness`,
   `coach_play.py:9516-9517`).
2. `backend/routes/coach.py:2535`, inside `POST /coach/teaching/feedback` — `grep` for `teaching/feedback`
   across `frontend/src` → **no matches**; no frontend caller.

**Player-facing impact:** None currently — both entry points are inert (one behind a permanently-True kill
switch that routes around it, one with zero UI callers). Matches the "retired code path that no longer
executes" exemption category exactly.

---

## 11. backend/services/best_move_tactic_detector.py

**Classification: LEGITIMATE_EXEMPTION — clean data-supplier case, docstring false positive**

Both flagged lines (5, 58) are inside the module/function **docstring**, not string literals returned to
users (e.g. `Closes Mohit-flagged gap (2026-05-20): captions said "{best_move} was better" without
explaining WHY...`). The module's own docstring states its actual output is structured data
(`{"kind": "mate"/"piece_capture"/..., ...}`) and explicitly: *"The result feeds R12_blunder.json
`why_clauses_user` predicates so the phrasing lives in JSON. Python only extracts chess data here."*

**Confirmed data-supplier relationship:** imported directly by `backend/services/caption_rules.py:468`
(which **is** on the guard's own `ALLOWLIST`) and by `services/pattern_catalog.py:321,546`.

**Recommendation:** Add `# allow-noncentral-caption` to lines 5 and 58 (docstring text triggering the
regex), or better, tighten the guard's docstring-detection to not scan inside triple-quoted module
docstrings.

---

## 12. backend/services/caption_claim_verifier.py

**Classification: LEGITIMATE_EXEMPTION — the verifier itself, guard allowlist gap**

Both flagged lines (45, 164) are docstring/comment text describing what the verifier checks (e.g. *"This
is the check that rejects 'Re1 threatens the bishop on e3' when the e1 rook does not attack e3."*) — not
generated prose. The module's actual functions (`_verify_threats`, `_verify_blunder`, etc.) return
`(bool, note)` tuples, never player-facing text.

**Confirmed role:** imported by `backend/services/game_decryption_v5_service.py:3798` as the gate that
approves/rejects a detector's claim before it ships in a V5 caption — i.e., part of the verification layer
for the **central** pipeline. It is the explicit sibling of `narrator_claim_verifier.py`, which **is**
already on the guard's `ALLOWLIST` (`check_caption_sources.py` ALLOWLIST set) — this looks like an
oversight/omission in the allowlist rather than a real gap.

**Recommendation:** Add `backend/services/caption_claim_verifier.py` to the guard's `ALLOWLIST` alongside
`narrator_claim_verifier.py`, rather than annotating individual lines.

---

## 13. backend/services/chess_brain/chess_brain.py

**Classification: LEGITIMATE_EXEMPTION — retired/disabled subsystem**

Flagged line 364 (`main_insight=f"You played {user_move}"`) is inside `ChessBrain._create_fallback_output`,
part of a full alternative "deterministic coaching engine" (`ChessBrain` class, `chess_brain/integration.py`).

**Confirmed disabled:** its one production call site,
`backend/services/realtime_coaching_feedback.py:1002-1171` (`generate_move_feedback`), gates it behind
`use_chess_brain: bool = False,  # DISABLED: see comment below` (line 1007) with an explicit docstring
explanation: *"DISABLED 2026-05-10. ChessBrain's lesson library was firing canned snippets ... matched at
random to moves where they didn't apply ... For live coaching, wrong teaching is worse than no teaching."*
`grep -r "use_chess_brain=True"` across the backend → **zero matches** — nothing ever re-enables it. All
other references to `ChessBrain`/`chess_brain` are in `backend/tests/test_chess_brain*.py` (test-only,
already excluded by the guard's own `SKIP_FRAGMENTS`).

**Player-facing impact:** None — dead/disabled subsystem, kept around (per the comment) presumably for a
future retry, not currently reachable from any live coaching flow.

---

## Summary table

| # | File | Classification |
|---|------|----------------|
| 1 | opening_trainer_service.py | LEGITIMATE_EXEMPTION |
| 2 | pdr_service.py | LEGITIMATE_EXEMPTION (dead code) |
| 3 | position_analysis_service.py | **REAL_VIOLATION_HIGH_RISK** |
| 4 | routes/coach.py | LEGITIMATE_EXEMPTION (docstring + dead endpoints) |
| 5 | routes/coach_play.py | **REAL_VIOLATION_HIGH_RISK** |
| 6 | routes/games.py | REAL_VIOLATION_LOW_RISK |
| 7 | routes/interactive.py | LEGITIMATE_EXEMPTION (docstring + dead caller) |
| 8 | routes/lab.py | **REAL_VIOLATION_HIGH_RISK** |
| 9 | routes/training_advanced.py | LEGITIMATE_EXEMPTION (dead/unrendered, latent-risk watch) |
| 10 | services/active_teaching_engine.py | LEGITIMATE_EXEMPTION (retired, kill-switched) |
| 11 | services/best_move_tactic_detector.py | LEGITIMATE_EXEMPTION (data supplier) |
| 12 | services/caption_claim_verifier.py | LEGITIMATE_EXEMPTION (verifier, allowlist gap) |
| 13 | services/chess_brain/chess_brain.py | LEGITIMATE_EXEMPTION (retired, disabled) |

**3 real violations, all confirmed rendered to players, on core surfaces:**
- `position_analysis_service.py` via `/reflect/explain-moment` (Reflect page) — independent LLM engine.
- `routes/coach_play.py` via `/v5/interactive-feedback` and `/postgame/{session_id}` (Play with Coach) —
  three separate hand-built prose sites feeding the live chat feed, coaching card, and post-game card.
- `routes/lab.py` via `/lab/evaluate-move` (Game Review interactive-solve) — a full independent
  heuristic move-quality/caption engine.

`routes/games.py` is a smaller, scoped violation (a trap-recognition blurb) sitting next to an otherwise
correctly central-pipeline-sourced narrative on the same page.
