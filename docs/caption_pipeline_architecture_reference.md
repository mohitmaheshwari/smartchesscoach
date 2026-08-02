# ChessGuru Caption & Teaching Pipeline — Architecture Reference

**Purpose of this document:** a factual, as-built reference for third-party
technical review. Every claim below was verified directly against the
codebase (file:line citations throughout) on 2026-08-01 — this is not a
design proposal or an aspirational spec. Where something is broken,
orphaned, or unconfirmed, that is stated explicitly rather than smoothed
over, because the review this document is feeding into is only useful if
it's working from the real state of the system.

Codebase root: `backend/` and `frontend/` under the ChessGuru monorepo.

---

## 1. What this system does

ChessGuru analyzes a user's chess games (imported from Chess.com/Lichess,
or played live against the in-app engine) and generates a natural-language
coaching caption for every move. Captions appear in two surfaces:

- **Game Review** — `frontend/src/components/GameDecryptionV5.jsx`,
  rendered on the Lab page (`Lab.jsx`, `LabV2.jsx`) after a game has been
  fully analyzed by Stockfish.
- **Play with Coach (PWC)** — live, move-by-move coaching during an
  in-app game against the engine, via `routes/coach_play.py` and
  `services/live_v5_teaching.py`.

Both surfaces are intended to share one caption-generation engine (see
§2), though as documented in §9 this convergence is not yet complete.

---

## 2. The central pipeline

The core entry point is `build_move_teaching_decision()` in
`backend/services/caption_pipeline.py` (~4,800 lines). It is a pure,
synchronous function — confirmed to have **zero LLM imports and zero
network/Stockfish-subprocess calls directly in this file** (grepped for
`call_llm`, `llm_service`, `AsyncAnthropic`, `AsyncOpenAI`, `httpx`,
`requests`, `subprocess` — no matches). Any LLM or engine usage happens in
caller code or in specific imported helper modules, not in the orchestration
layer itself.

It takes a `MoveInputs` dataclass (fen, played move, best move, eval
before/after, cp_loss, rating, move history, optional PWC-only context
objects) and a `CrossMoveState` object (carries state across moves within
one game — e.g. which shape patterns have already fired, to avoid
repeating the same pattern-callout every move), and returns a
`MoveTeachingDecision` (the caption text plus structured metadata).

### 2.1 Call order (as implemented, `caption_pipeline.py:3708-4803`)

1. `extract_facts_verified` / `extract_facts` — base position facts
   (`caption_facts_verified.py`, Stockfish-backed verification layer)
2. Severity classification — `classify_severity_practical`,
   `classify_severity` (lines 3792-3802) — **runs before any concept/
   principle facts exist.** This is the single most consequential
   ordering decision in the pipeline; see §5.
3. `inject_opp_side_narration_facts` (line 3860) — gated
   `opp_cp_loss >= 30`
4. `inject_opening_context_facts` (line 3960)
5. `inject_good_move_reason_facts` (line 3977) — gated `cp_loss == 0`
6. Pre-move shape-opportunity pass — `shape_layer.select_shape_for_position`
   (line 3996)
7. `inject_user_blunder_detector_facts` (line 4011) — gated
   `is_user AND best_move AND best_move != move_san AND cp_loss >= 100`
   (exact condition, line 694: `if not (is_user and best_move and
   best_move != move_san and (cp_loss or 0) >= 100): return`)
8. `inject_em_dash_and_trap_context_facts` (line 4023) — same `cp_loss
   >= 100` gate (line 1067)
9. `inject_eval_trajectory_facts` / `inject_curriculum_deviation_facts` /
   `inject_blocked_pawn_facts` (lines 4034-4063) — all gated on cp_loss
   thresholds
10. `inject_board_state_describer_clause` (line 4066)
11. Render — `caption_renderer.render_caption_dict` (line 4133)
12. Principle suppression/cue-selection block (lines 4193-4292), reads
    `services/caption_principles.py`
13. `select_shape_pattern_record` (A6, line 4310)
14. `update_trap_recognition_state` (A5, line 4326)
15. `apply_promotion_ladder_dispatch` (A9, line 4339)
16. Board-grounding verifier — `_verify_and_recover_caption` (line 4371)
17. Floor-principle append — `_maybe_append_floor_principle` (line 4404)
    — see §11.7 for the known critique of this step
18. Why-bad / why-better splice-ins (lines 4413-4495)
19. `narrator_claim_verifier.verify_caption` — final ship gate (line 4508).
    Confirmed deterministic — no LLM call in this module
    (`narrator_claim_verifier.py`, grepped for LLM/network calls, none
    found).
20. King-pin prepend (line 4538)
21. `classify_caption_tier` (A8, line 4558)
22. Optional distilled-caption swap (line 4568)
23. Coach Conductor player-model thread override (lines 4585-4715) —
    requires a live `db` connection; see §7.2 for what this reads

### 2.2 Which surface calls this function

- **PWC** (`routes/coach_play.py`, `services/live_v5_teaching.py`) has
  called `build_move_teaching_decision` directly since the "phase B"
  migration (code comment, `caption_pipeline.py:3722`: *"PWC calls this
  instead of the six individual helpers it has today"*).
- **Game Review** (`game_decryption_v5_service.py`) was migrated to the
  same function in "v100" (code comment, line 108: *"v100 FINAL: V5
  service now calls build_move_teaching_decision()"*), gated behind
  `CAPTION_V5_PIPELINE_ENABLED` (line 106, defaults to `True` unless the
  import fails or the env var explicitly disables it; line 3486 is the
  call site).
- **However**, an older code comment at line 3722-3726 says *"V5 service
  keeps its per-block call points for now (it has additional inline
  logic interleaved with the A-helpers — curriculum detection, blocked-
  own-pawn, eval trajectory — that isn't part of the A-set)."* This
  comment appears to predate the v100 migration and may be stale; the
  live import/call-site evidence (line 108, 3486) says the migration
  happened. Worth a direct line-by-line confirmation by whoever reviews
  this, since the two comments in the same file disagree.

---

## 3. Classification / knowledge layer

This is the layer that decides *what's educationally relevant* about a
position — the closest thing in this codebase to "concept detection."

### 3.1 Strategic principles — `services/caption_principles.py`

**33 hand-authored entries**, each with `phase_in_scope`, `priority`,
`match_kind`, `aligned_moves`, `gate_policy` (endorsement required /
preferred / forbidden, cp_loss-strict), a `suppress` policy, and 3-tier
cue text (`cue_best` / `cue_top_n` / `cue_absent`). Full id list (lines
117-902):

```
OP_FINISH_DEVELOPMENT, OP_LOOSE_KING_PAWNS, OP_QUEEN_OUT_EARLY,
OP_SAME_PIECE_TWICE, OP_PAWN_HEAVY, OP_CLAIM_CENTER, OP_KNIGHT_ON_RIM,
OP_BISHOP_BLOCKED, OP_NOT_CASTLED, TAC_CHECKS_CAPTURES_THREATS,
TAC_BACK_RANK, TAC_HANGING_PIECE, TAC_DEFENDER_COUNT, TAC_FORK_PATTERN,
TAC_PIN_PATTERN, TAC_SKEWER_PATTERN, TAC_DISCOVERED_PATTERN,
DEF_MOST_ATTACKED, TAC_CHANGED_AFTER_MOVE, MID_KING_SAFETY,
MID_KEEP_ATTACKERS, MID_ROOK_OPEN_FILE, DEF_TRADE_ATTACKERS,
MID_BAD_BISHOP, MID_PAWN_BREAK, DEF_WALK_KING, END_PASSED_PAWN,
END_KING_ACTIVE, END_RULE_OF_SQUARE, END_OPPOSITION,
END_ROOK_BEHIND_PASSER, PAWN_PUSH_TRAPS_OWN_ROOK,
OP_BISHOP_TRADE_DOUBLES_PAWN, OP_TRAPPED_KNIGHT
```

The catalog's own header (lines 21-23) documents a locked product rule:
**no jargon** — words like "outpost," "fianchetto," "minority attack,"
"luft" are deliberately excluded from the vocabulary. This is a product
decision, not an oversight (target audience: 600-1500 rated players).

### 3.2 Tactical shape patterns — `services/shape_patterns.py`

**26 entries** (`assert len(SHAPE_PATTERNS) == 26`, line 372), each with
`name`, `description`, `phase_in_scope`, `priority`, `geometry_hint`,
`verifier_policy` (`engine_confirms_target` / `engine_in_top_3` /
`heuristic_only`), some with a `dynamic_policy`. Ids:

```
knight_fork, bishop_fork, rook_fork, pawn_fork, hidden_attack, pin,
skewer, double_attack_line, back_rank_trap, h7_attack, queen_knight_mate,
strong_knight_square, weak_squares, free_pawn, open_long_line,
no_safe_square, tired_defender, free_piece, long_diagonal_bishop,
remove_the_guard, force_the_king, in_between_move, knight_mate,
pawn_hole_fianchetto, king_pawn_lifted, clearance_for_attack
```

Three entries (`double_attack_line`, `weak_squares`, `tired_defender`)
have `"description": ""` and are documented in-code (lines 138-147,
193-204, 254-259) as **deliberately silenced** after a 2026-05-30 audit
found them firing as generic filler on 2.5%+ of moves.

### 3.3 Trap library — `services/trap_library.py` + `data/traps.json`

Traps are matched by **exact SAN move-sequence comparison** (`find_
relevant_trap`, `get_trap_for_position`, `detect_trap_in_position`, lines
121-311: `normalized_history == normalized_setup[:history_len]`). There is
no structured precondition data (no "king castled AND knight can reach g5
AND queen can reach h5" type modeling) — a transposition or slightly
different move order will not match. Representative entry (Fried Liver
Attack):

```json
{"name": "Fried Liver Attack",
 "setup_moves": ["e4","e5","Nf3","Nc6","Bc4","Nf6","Ng5"],
 "trap_line": [{"move":"d5","explanation":"..."}, ...],
 "result_type": "wins_material", "difficulty": "intermediate",
 "trap_color": "white"}
```

### 3.4 Opening curriculum — `services/opening_curriculum_engine.py` +
`data/opening_curriculum.json`

A real tree structure with per-node `idea`, `hint`, `plan`, `right_
feedback`, `wrong_feedback`, `golden_rules`, `trap_reference` — richer
than the trap library, but navigation is still literal move-matching
(`get_opening_guidance`, lines 77-420, walks `tree[move]` /
`node["responses"][move]`), not board-condition matching.

### 3.5 Endgame lessons — `services/endgame_teaching.py` +
`data/endgames.json`

**6 total lessons**: `queen_checkmate, rook_checkmate, opposition,
rule_of_square, lucena_position, philidor_position`. Each is one fixed
`setup_fen` + a fixed `solution_moves` list (not adaptive to the user's
actual position) + sparse `explanations` keyed by move index +
`key_concepts` / `common_mistakes` arrays. `detect_endgame_type` (lines
101-142) picks a lesson *type* from the user's material, but the lesson
content itself is one canned position, not the user's real game.

**Separately**, real condition-based endgame *detection* on the user's
actual position does exist: `services/concept_detectors/endgame_
opposition.py` (and siblings `endgame_lucena.py`, `endgame_philidor.py`)
use structured preconditions (e.g. `_is_kp_endgame`, `_in_direct_
opposition` — kings not in opposition pre-move, in opposition post-move,
and it's a king move) to grade a move `applied`/`missed`/`None` on any
real position. This is not connected to `endgame_teaching.py`'s lesson
library — see §7.1.

---

## 4. Severity / gating (the "engine-first" question)

Direct evidence that the pipeline is **engine-score-first**, not
concept-first:

- Severity is computed at lines 3792-3802, before `caption_facts` is
  even created (line 3804) — i.e. before any concept/pattern facts exist.
- The richest detector suite (`inject_user_blunder_detector_facts` — 14
  detectors: clearance attacks, queen forks, knight outposts, discovered
  attacks, etc.) is hard-gated: `cp_loss >= 100` (line 694). **It does
  not run at all below 100cp loss** — i.e. never on "good" moves.
- `inject_em_dash_and_trap_context_facts`: same `cp_loss >= 100` gate
  (line 1067).
- `inject_eval_trajectory_facts` / `inject_curriculum_deviation_facts` /
  `inject_blocked_pawn_facts`: gated `cp_loss >= 100` / `>= 30`
  respectively.
- The principle-selection block explicitly suppresses a *corrective*
  principle (one recommending a different move) on any move where
  `cp_loss_cue < 30`, unless the played move itself is that principle's
  aligned move (lines 4275-4279) — i.e. principles only teach "what's
  wrong" when the engine says something's wrong.
- `select_shape_pattern_record`'s post-move "you walked into this"
  fallback pass is gated to `severity in ("mistake", "serious",
  "blunder", "opp_mistake", "opp_serious", "opp_blunder")` (lines
  2914-2923). The *pre-move* opportunity-spotting pass (e.g. "you have a
  fork available") does run independent of severity — but the
  "you fell into this pattern" retrospective teaching does not.
- Severity tiers themselves are fixed cp_loss cutoffs
  (`services/severity.py:126-143`) — a pure engine-score ladder with a
  mate-walked-into override, nothing else.
- Good/best moves get a comparatively thin path:
  `inject_good_move_reason_facts` (gated `cp_loss == 0 and move ==
  best`) plus whichever affirming (non-corrective) principle/pre-move-
  shape happens to apply.
- **Opponent-side moves are narrated on the same logic**, just mirrored:
  `inject_opp_side_narration_facts` is gated `opp_cp_loss >= 30` — so an
  opponent's brilliant, instructive move (a good prophylactic idea, a
  nice combination) is not narrated on its own educational merit either,
  only when the opponent makes a mistake.

**Net effect:** concept/pattern/principle teaching content is largely
*rationed by cp_loss*, for both the user and the opponent. The system
narrates every move to some degree (the pre-move shape pass and opening
context run regardless of eval), but the depth of teaching is fundamentally
tied to whether the engine flagged the move as an error.

---

## 5. Rating-awareness

Two genuinely different mechanisms exist under this label, with very
different real-world status.

### 5.1 Suppression (real, live, in production)

`caption_pipeline.py:4097-4126` — `rating_resolver.caption_suppress_
threshold_cp(rating)` gates *whether* a critique caption renders at all,
scaled by rating band. This changes presence, not content, and is
confirmed live in both Review and PWC.

### 5.2 Depth-branched content (real, but never reaches a user)

`inject_socratic_user_facts` (`caption_pipeline.py:2150-2171`) genuinely
branches *content* by rating band (`<1000`, `<1400`, `>=1400`) — e.g. a
sub-1000 player gets `"Look for pieces you can take safely"`, a 1400+
player gets richer capture-target-named phrasing. This is real,
differentiated text.

This gets written to `caption_facts["socratic_coaching"]` and persisted
on the move record (`game_decryption_v5_service.py:3607-3614, 4196-4200`)
as `{narrative, plan, question, hint}`. **Verified against production data:
0 of 12,328 analyzed games have a non-null `socratic_coaching` value.**
See §9 for why.

Separately, **the frontend never reads this field at all** — grepped the
entire `frontend/` tree for `socratic_coaching` / `socraticCoaching`,
zero references, in the one live game-review component
(`GameDecryptionV5.jsx`, confirmed as the only page-imported decryption
component — the sibling `GameDecryption.jsx` exists but is imported by no
page). A frontend render block for this field was added on 2026-08-01
(see §10) but has not yet displayed real data, per §9.

---

## 6. Mastery / progress tracking — four overlapping systems

Four separate systems each partially answer "has this user seen/mastered
concept X." They do not share a vocabulary and do not reconcile with each
other.

### 6.1 `coach_memory.py` — `SkillProgress` ("Engine 2")

- Write primitive: `record_skill_attempt` (`coach_memory.py:759`), called
  from `update_memory_after_game` (line 555), `record_engine2_skills_
  from_game` (line 862, openings only), `record_concept_applications_
  from_game` (line 925).
- **Confirmed wired to real games**: `analysis_worker.py:1929-1948` calls
  `update_memory_after_game(...)` for every imported game, threading
  `move_evaluations` / `user_color` / `game_id` so concept detectors can
  grade in-game application.
- **Scope is narrow by design**: `record_concept_applications_from_game`
  runs every move through 10 registered detectors (`concept_
  detectors/registry.py:71-83`): `endgame_rule_of_square, defend_
  scholars_mate, mate_kq_vs_k, mate_kr_vs_k, defend_fried_liver, endgame_
  opposition, endgame_lucena, endgame_philidor, trap_detection, opening_
  play`. **No fork/pin/skewer/hanging-piece detector exists in this
  system.** Code comment (`coach_memory.py:676-683`): *"Engine 2 is about
  CHESS KNOWLEDGE... not tactical mistakes (Engine 1 owns those)."*
- **Confirmed dead-code bug**: `trap_detection.detect_trap_application`
  (`concept_detectors/trap_detection.py:27-32`) and `opening_play.detect_
  opening_play_application` (`opening_play.py:27-33`) both declare a 4th
  parameter (`move_number`, and `opening_play` also needs `opening_name`)
  that the runner never supplies (`concept_detectors/_runner.py:47`:
  `detector(board_before, move, user_color)` — 3 args only). Both
  functions' first line is `if move_number is None: return None`. **These
  two detectors have never fired once in production.**

### 6.2 `concept_mastery_tracker.py` (`user_concept_understanding`)

- Write: `update_user_mastery_for_game` (lines 197-311), called from
  `analysis_worker.py:1522-1545` for every analyzed game.
- Keys off the **central-pipeline principle-id namespace**
  (`TAC_FORK_PATTERN` etc.), auto-creating rows to bridge what the file's
  own docstring (lines 2-8, 162-165) calls a "namespace mismatch" fix.
- **Confirmed read in two real places**:
  - `pwc_skill_gate.py:278-343` → `coach_play.py:8420-8454`, suppresses/
    downgrades live PWC coaching for mastered concepts. Gated behind
    `PWC_SKILL_GATE_ENABLED`, confirmed `true` in both
    `docker-compose.yml:114` and `docker-compose.prod.yml:46`.
  - `coach_conductor.player_concept_threads` (`coach_conductor.py:
    126-179`) feeds `caption_pipeline.MoveInputs.player_concept_threads`.
- **Confirmed NOT reaching game review**: `game_decryption_v5_service
  .py`'s own construction of `MoveInputs` (lines 3520-3543) never sets
  `player_concept_threads`, `player_motif_threads`, `player_opening_
  threads`, `strong_openings`, `player_identity`, or `session_focus` —
  they default to `None`. The "coach knows what you've mastered" signal
  reaches **live PWC only**, never post-game review.

### 6.3 `pattern_decay_service.py` (`user_pattern_decay`)

Confirmed real and wired for **Home page and Lab only**:
`refresh_user_pattern_decay` (lines 217-243) called from `analysis_
worker.py:1427-1428`, `training.py:286-287`, `home_intelligence_
service.py:524-525`, `coach_memory.py:450,1327-1328`. Read at
`digest_email_service.py:67`, `home_coach_conversation.py:309`, `puzzle_
extraction_service.py:326-327`. **Grepped `caption_pipeline.py` and
`game_decryption_v5_service.py` for any reference — zero matches.**
Decay state never informs caption generation.

### 6.4 `trap_mastery_tracker.py` — a 4th, independent record

Writes `user_opening_mastery.traps_encountered/traps_handled/traps_
fallen_for` (own docstring, lines 3-13, admits this was *"declared but
never populated"* before this tracker existed), wired at `analysis_
worker.py:1551-1575`. Entirely separate from `SkillProgress.traps_
learned` (§6.1).

### 6.5 Vocabulary mismatch, concretely

Using "fork" as the test case:

| System | Fork vocabulary | Real answer for a given user |
|---|---|---|
| `pattern_decay_service` | `missed_fork` (`cognitive_gap_service.py:40`) | Independent recency-weighted score, own ACTIVE/DECLINING/FADING state |
| `concept_mastery_tracker` | `TAC_FORK_PATTERN` (`caption_principles.py:412`) | Real streak-based mastery answer |
| `coach_memory.SkillProgress` | *(no id exists)* | No data at all — structurally can't answer |

Grepped `TAC_FORK_PATTERN` (8 files, all within the caption/principle
stack) against `missed_fork` (50 files, the legacy cognitive-gap stack) —
**no mapping table anywhere joins the two.**

---

## 7. Retrieval data — `player_identities.pattern_history`

Real, continuously-running write path (not the PWC-only one):
`analysis_worker.py:2016-2017` → `data_freshness.refresh_player_
identity` (`data_freshness.py:71-289`) — fully rebuilds `player_
identities` after every analyzed game.

**Root cause of the "opponent: unknown" / empty-description bug,
confirmed in the code, not inferred:**

The MongoDB aggregation (`data_freshness.py:93-111`) does a `$lookup`
that joins the full `games` document (including `white_player`/
`black_player` — real opponent name) — then a `$project` two lines later
(103-110) keeps only `game_id, result, user_color, stockfish_analysis,
analyzed_at`, **discarding the opponent name it just joined in**, before
the per-game loop (line 154) ever sees it. The pattern-entry builder
(lines 219-229) never reads or writes a description field at all.
`PatternHistoryEntry.from_dict` (`player_identity.py:467-476`) then
defaults the missing keys to `opponent="unknown"` / `description=""`.
**This is a fixable data-plumbing bug (extend the `$project`, add a
description-builder) — not a data-availability limitation.**

Side finding: `DeepMemoryPanel.jsx:63` fetches `${'{API}'}/coach/deep-
memory/pattern-history?limit=30` — grepped the entire backend for that
route string, **zero matches**. That specific frontend call appears to
404 in production.

---

## 8. Curriculum-gap awareness in training/puzzle selection

**Confirmed not built.** Checked every selection path:

- `routes/training.py:162-244` (`/training/prescribed/{weakness}`) —
  defaults to `"piece_safety"` or resolves via `focus_resolver.get_
  active_focus` — never "whatever the user has never attempted."
- `focus_resolver.get_active_focus` (`focus_resolver.py:117-197`) —
  priority order is entirely frequency-driven (coach_memory's current
  focus, then top-problems-by-count). No coverage/novelty term.
- `coaching_puzzle_service.get_prescribed_training` (lines 166-266) —
  all three puzzle sources (own mistakes, community puzzles, Lichess
  puzzles) are conditioned on a pattern **already selected** by the
  above; none scan for absent concepts.
- `puzzle_extraction_service.get_pattern_training_puzzles` (lines
  296-493) — ranks by recency/solve-rate on an already-chosen pattern.
- `/training/data-driven` and `/training/weekly-plan`
  (`routes/training.py:452-556`) — both sort by mistake frequency
  descending. **A concept with zero occurrences cannot appear in these
  lists at all** — the structural opposite of a coverage-gap signal.

---

## 9. LLM usage — where, and the current risk

**The central pipeline (`caption_pipeline.py`) makes no LLM calls.**
Confirmed by direct grep — the classification/knowledge/severity/
verification layers (§§2-7 above) are entirely deterministic.

**Two real LLM call sites exist**, both inside `game_decryption_v5_
service.py`'s older, partially-parallel narrative system (not the
central pipeline):

1. `services.v5_llm_polish.polish_caption_async` (called at
   `game_decryption_v5_service.py:850-851`) — takes an already-written
   deterministic caption and varies its phrasing.
2. `services.v5_llm_narrator.generate_concise_narrative` (called at
   lines 1355, 1394) — writes to the legacy `narrative`/`plan` fields
   that a code comment at lines 4061-4070 says are *"retired... no
   longer emitted"* — contradicted by this still-running pass.

Both route through `llm_service.call_llm` → `_call_claude` /
`_call_openai` (`llm_service.py:144-165`), which construct
`AsyncAnthropic(...)` (line 53) / `AsyncOpenAI(...)` (line 114) with
**no explicit `timeout=` parameter anywhere** — confirmed by reading both
constructors and every call site.

### 9.1 Confirmed and unconfirmed hang findings

- A full-game live-render attempt (86-move real game, via `generate_
  game_decryption_v5`) hung for 1h49m (0% CPU, `futex_wait_queue`) before
  being killed. This function path does include both LLM call sites
  above.
- A follow-up test calling the pure, LLM-free `build_move_teaching_
  decision` **directly** on a single real move (bypassing both LLM call
  sites entirely) **also hung**, with the same signature. This means the
  first hang cannot be attributed to the LLM calls alone — there is at
  least one other blocking call in the dependency chain. The most likely
  untested candidate is `caption_facts_verified.py`'s synchronous
  Stockfish-verification layer (own docstring: *"Extract facts with
  Stockfish verification (synchronous)"*), which may hang if the test
  script's ad-hoc process doesn't have the engine pool that `analysis_
  worker.py`'s normal execution context sets up. **This is not yet
  confirmed** — it is the leading hypothesis, not a verified root cause.
- **Net assessment**: the missing LLM client timeout is a real,
  independently-confirmed bug worth fixing regardless. Whether it is
  *the* cause of the specific hangs reproduced this session is not yet
  settled — a proper repro with a correctly-initialized Stockfish engine
  context is the next diagnostic step.

---

## 10. Frontend wiring — `socratic_coaching`

`GameDecryptionV5.jsx` is the only page-imported game-review component
(`Lab.jsx:14`, `LabV2.jsx:68`). Its per-move mapping (`...m` spread,
around line 359/372/386) already carries `move.socratic_coaching`
through to the rendered move object with no backend change needed — the
gap was purely that nothing read it.

A render block was added on 2026-08-01 (`GameDecryptionV5.jsx`, after the
existing narrative block): shows `move.socratic_coaching.question`
immediately, and `.hint` behind a "Show hint" click-to-reveal, gated on
`move.socratic_coaching && move.socratic_coaching.question` being
non-null. **This code is deployed but currently a no-op**, since (per §5
and §9) no production game has a non-null `socratic_coaching` value yet.

---

## 11. Known bugs / gaps — summary, severity-tagged

| # | Finding | Severity | Fix scope |
|---|---|---|---|
| 1 | `trap_detection` / `opening_play` concept detectors never fire (arg-count mismatch, `_runner.py:47` vs the detectors' own signatures) | Medium — silent data loss, no crash | Small — align call signature |
| 2 | `socratic_coaching` never populated for game review (0/12,328); designed as PWC-only, review's `MoveInputs.socratic_context` is never set | Medium — orphaned feature, real UX upside if fixed | Medium — needs `socratic_context` assembled in the review per-move loop, plus the hang in §9 resolved |
| 3 | `player_identities.pattern_history` — opponent always "unknown", description always empty | Low-Medium — degrades a "remember this" retrieval feature that isn't built yet anyway | Small — fix the `$project` + add a description-builder |
| 4 | `/coach/deep-memory/pattern-history` route referenced by frontend does not exist | Low — likely a silent 404 on one panel | Small |
| 5 | `AsyncAnthropic`/`AsyncOpenAI` clients constructed with no timeout anywhere in `llm_service.py` | High — real hang risk on any call | Small — add explicit timeout |
| 6 | Reproducible multi-hour hang on a single move's caption generation for a real user mistake, root cause not fully isolated | High — blocks §5.2 and any future work in this path | Needs isolated repro with correct Stockfish engine setup |
| 7 | Legacy dual narrative system (`v5_llm_narrator`, `ChessPlan`, `golden_rule_service`) still writes text in parallel with the central pipeline, contradicting the file's own "single source of truth" comment | Medium — real sprawl/consistency risk, plus §9's LLM calls live here | Medium-Large — requires confirming nothing else depends on the legacy fields before removal |
| 8 | Four independent mastery/progress systems (§6) use incompatible vocabularies with no reconciliation | Medium-High — blocks any future "has the user mastered X" feature from getting one honest answer | Large — consolidation project, not a quick fix |
| 9 | No coverage-gap signal anywhere in training/puzzle selection (§8) | N/A — confirmed absent, not a bug, a scoping fact for future work | Net-new work |

---

## 12. What a third party should know going in

- The deterministic classification/knowledge layer (principles, shapes,
  traps, opening tree) is real, substantial, and already the intended
  architecture — not something that needs rebuilding.
- The system is currently **engine-score-first**: how much a move gets
  taught is gated by how wrong Stockfish thinks it was, for both sides.
  This is the most consequential single design decision to evaluate.
- Rating-aware caption *depth* (not just suppression) is built and
  currently reaches no user in game review.
- There are four different, non-reconciled answers to "has this user
  mastered concept X," depending which internal system is asked.
- There is at least one real, unresolved, reproducible hang bug in the
  live-caption-generation path, with a confirmed contributing factor
  (missing LLM timeout) and an unconfirmed leading hypothesis (synchronous
  Stockfish calls in certain contexts).
