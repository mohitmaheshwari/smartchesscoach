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
as `{narrative, plan, question, hint}`. **Original finding (2026-08-01):
0 of 12,328 analyzed games had a non-null `socratic_coaching` value.
Root-caused and fixed 2026-08-03 — see §9.1.**

Separately, **the frontend never read this field at all** — grepped the
entire `frontend/` tree for `socratic_coaching` / `socraticCoaching`,
zero references, in the one live game-review component
(`GameDecryptionV5.jsx`, confirmed as the only page-imported decryption
component — the sibling `GameDecryption.jsx` exists but is imported by no
page). A frontend render block for this field was added 2026-08-01 and
adjusted 2026-08-03 (see §10).

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

## 9. LLM usage — where, the "hang" that wasn't, and the real bug

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
`AsyncAnthropic(...)` / `AsyncOpenAI(...)`. **Fixed 2026-08-03**: neither
constructor passed an explicit `timeout=`, so a slow upstream response had
no ceiling — both now pass `timeout=30.0`, generous for the ~50-200 token
completions this codebase actually asks for.

### 9.0.1 Both LLM providers are non-functional in production — not a bug to fix

Found while spot-checking the timeout fix (2026-08-03), verified directly
against the running production container: `ANTHROPIC_API_KEY` is unset
everywhere (every `"claude*"` call fails immediately, before any network
request), and `OPENAI_API_KEY` is set but has zero credit balance (fails
with `insufficient_quota`). Every LLM call in this codebase currently
fails, for two independent, pre-existing reasons.

**Explicitly not an action item.** Mohit has confirmed the product does
not need LLM calls to function — the real, live coaching surfaces
(severity classification, R08-R12 templates, the distilled/verified
caption layers, the whole per-move caption pipeline) are deterministic,
not LLM-dependent, and were verified end-to-end this session without
touching either provider. The two LLM call sites that do exist
(`v5_llm_polish.py`, `v5_llm_narrator.py`) are legacy/parallel paths, not
load-bearing. Recorded here as an architectural fact, not a problem —
don't re-flag this as urgent or in need of fixing.

### 9.1 The "reproducible hang" — corrected finding

An earlier pass through this audit (2026-08-01/02) found what looked like
a genuine multi-hour production hang: a full-game live-render attempt
(86-move real game) hung for 1h49m, and a follow-up single-move test —
bypassing both LLM call sites entirely — also hung with the same
signature (`futex_wait_queue`, 0% CPU). That second result was wrongly
taken as evidence the hang lived somewhere deeper in the pipeline than the
LLM calls.

**Root cause, found 2026-08-03 with `faulthandler.dump_traceback_later`:**
the test script's own process never exited, but the function it called
had already **returned a correct, real result** before the "hang" began.
The actual stack trace showed a background thread stuck in
`chess.engine.py`'s own `asyncio.run()`, waiting on a live Stockfish
subprocess via `_do_waitpid` — this is `services/engine_pool.py`'s warm
engine, which is *designed* to never quit (`"Do NOT call engine.quit()
inside the scope — the engine is meant to stay warm"`, `engine_pool.py:
19`) because it's meant to live for the lifetime of a long-running server
process. A one-shot `docker exec python3 -c "..."` test script is not a
long-running server process — it spawns the same warm-forever engine and
then never exits, because nothing was ever supposed to tell it to.

**This was never a production bug.** The real, continuously-running
`analysis_worker.py` process has successfully written `decryption_v5_data`
for all 12,328 analyzed games in production — direct proof the real code
path completes normally. The "hang" was entirely an artifact of testing a
warm-engine-pool design with a test harness that doesn't match its
lifetime assumption. The LLM timeout fix above is still good, independent
hygiene — it just isn't what this specific mystery turned out to be.

### 9.2 The real bug behind 0/12,328 `socratic_coaching` — found and fixed

Once the hang was ruled out, a clean single-move call to
`build_move_teaching_decision` for a real, confirmed 431cp blunder
(`game_ef9f422a062d`, move 15 black `Qxf3`) **worked and returned a real
result** — narrative and plan populated correctly. So the underlying
mechanism was never broken. The actual bug: `game_decryption_v5_service
.py` computes its own `severity` value and passes it as `severity_
override` into the central pipeline (a documented, intentional split —
line 111-114: *"V5 applies its own book-move / best-equals / rating-band
downgrades to `severity` BEFORE the central call"*). One of those
downgrades — the "forced recapture" check in `compute_severity_for_move`
(`caption_pipeline.py:620-636`) — set `severity = "good"` whenever a
player recaptured on the immediately-preceding move's square with their
only legal recapturing piece, **regardless of the resulting cp_loss**.
For the confirmed real case above, that's exactly wrong: `Qxf3` was the
only legal recapture, but it immediately hung the queen to a further
capture (431cp loss) — a genuine blunder, silently relabeled "good" for
`severity_override` purposes even though the separately-computed
`severity_practical` field (used for the visible caption) correctly said
"blunder" the whole time. That's also why the caption text itself was
never wrong — only the narrower `severity_override` path feeding the
Socratic auto-derive gate (`_eff_sev in ("mistake", "blunder")`,
`caption_pipeline.py:3924`) was affected.

**Fixed 2026-08-03**: the forced-recapture downgrade now only applies when
`severity_canonical` (computed two lines earlier in the same function,
unaffected by this bug) isn't already `blunder`/`mistake`/`serious`.
Separately, `"serious"` — a real, distinct severity tier between
`"mistake"` and `"blunder"` (`services/severity.py:137`) — was missing
from the Socratic gate's tuple entirely; added.

**Verified end-to-end after the fix**: re-ran `build_move_teaching_
decision` for the same confirmed blunder — `socratic_coaching` now
populates correctly, and the real production `/api/analysis/{id}/
enriched` endpoint (the exact one `GameDecryptionV5.jsx` calls) was
confirmed to return the populated `narrative`/`plan` fields for this
move via a temporary, read-only, safely-cleaned-up verification session
scoped to the game's real owner.

**Corpus-wide, not just one hand-picked case** (2026-08-03, requested
follow-up after "did you verify against all our users?"): a read-only
scan of all 12,506 analyzed games / 384,342 user moves found 10,487
moves matching the old bug's exact trigger condition, of which **733
across 712 distinct games** were genuine blunder/mistake/serious moves
previously mislabeled "good" — confirmed via the same canonical
`classify_severity()` the app itself uses, not a re-derived guess. This
was never a one-off (`Qxf3`) — it was a real, widespread pattern across
many different real users.

A stratified 15-case sample was then independently re-analysed with a
**fresh, standalone Stockfish process** (not the stored cp_loss, not the
app's engine pool) to check the classification itself, not just whether
the field was populated. Initial depth-16 spot check disagreed with the
stored cp_loss on 5/15 — investigating the two clearest disagreements at
production's actual depth (18, per `config.py: STOCKFISH_DEPTH = 18`)
and deeper (20/22) resolved both: the stored data was correct, and
depth-16 was simply too shallow to see the tactics. A third case stayed
genuinely unstable across depths (best-move kept changing), consistent
with it being an already near-decided position where different lines
are close to equally (ir)relevant — a property of the position, not a
data-quality bug.

---

## 10. Frontend wiring — `socratic_coaching`

`GameDecryptionV5.jsx` is the only page-imported game-review component
(`Lab.jsx:14`, `LabV2.jsx:68`). Its per-move mapping (`...m` spread,
around line 359/372/386) already carries `move.socratic_coaching`
through to the rendered move object with no backend change needed — the
gap was purely that nothing read it.

A render block was added on 2026-08-01, then rewritten on 2026-08-03 once
the actual field shapes in production were confirmed. `R18_socratic_
user_mistake.json`'s 19 narrative variants all ship with hardcoded empty
`"question": ""` / `"hint": ""` — those two fields are a content-
authoring gap, not something the frontend can render around. The block
now gates on `move.socratic_coaching && (move.socratic_coaching.narrative
|| move.socratic_coaching.plan)` and renders `.narrative` (primary) and
`.plan` (secondary) as plain paragraphs — no click-to-reveal mechanic,
since there's no hint text to reveal. With the §9.2 severity fix, this is
no longer a no-op: qualifying real mistakes now populate `narrative`/
`plan` and the block renders. Filling in `question`/`hint` with real
per-variant content remains open, separate work (content authoring, not
a code bug).

---

## 11. Known bugs / gaps — summary, severity-tagged

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | `trap_detection` / `opening_play` concept detectors never fire | Medium — silent data loss, no crash | **FIXED 2026-08-03 (second pass, real redesign, verified end-to-end).** The first pass only fixed the arg-passing bug — end-to-end testing then found two deeper bugs the arg fix didn't touch (see prior entries, kept below for history): `opening_play.py` imported 3 functions that don't exist in `opening_curriculum_engine.py`; `trap_detection.py` called `detect_trap_setup()` with the wrong argument type and read return keys that don't exist. Both rewritten for real: `trap_detection.py` now re-derives victim/setter status statelessly from the full move history on every call (no session state needed — reuses the exact `trap_color`-vs-mover-color logic already proven correct in `caption_pipeline.py`'s live trap state machine), verified against a real trap (Blackburne Shilling Gambit) through its full line — victim's bad moves correctly grade "missed", setter's punishing moves correctly grade "applied", an unrelated move correctly grades `None`. `opening_play.py` now calls the real `get_opening_guidance()` and grades "applied" for confirmed in-book moves, verified against a real Italian Game sequence. Both detectors' original "grade a bad/losing deviation" ambition was dropped — neither `traps.json` nor `opening_curriculum.json` has data to distinguish a sound deviation from a losing one (confirmed by reading `_off_book_guidance()`, which treats every deviation identically), so deviations correctly return `None` rather than a guessed grade. `coach_memory.py` and `_runner.py` extended to thread the full SAN history through (needed since `board_before` is built from a stored FEN with no move_stack). |
| 2 | `socratic_coaching` never populated for game review (0/12,328) | Medium — orphaned feature, real UX upside if fixed | **FIXED 2026-08-03** — root cause was NOT a missing `socratic_context` wiring (that guess was wrong); it was the forced-recapture severity downgrade in `compute_severity_for_move` silently feeding "good" into `severity_override` regardless of real cp_loss. See §9.2. Frontend render updated to match (§10) |
| 3 | `player_identities.pattern_history` — opponent always "unknown", description always empty | Low-Medium — degrades a "remember this" retrieval feature that isn't built yet anyway | **FIXED 2026-08-03, in two passes.** Pass 1: `data_freshness.py`'s `$project` was dropping the `$lookup`-joined `white_player`/`black_player` fields before the per-game loop could read them — added to the projection. Pass 2 (found during independent deep verification, not by inspection): the description fallback read `move_eval.get("caption")` off `stockfish_analysis.move_evaluations`, but that field **never exists there** (confirmed 0/14,992 sampled moves) — real captions live only on the separate `decryption_v5_data` array, which isn't index-aligned (different length, both colors vs user-only). My first-pass claim that it "reuses the real, already-verified caption text" was false; it was always the generic fallback sentence. Fixed by joining on `fen_before` (near-unique per position) into `decryption_v5_data`. **Re-verified across all 63 real users after the second fix**: 5,047 pattern_history entries, 0% "unknown" opponent, 0% empty description, 97.6% real position-specific captions (2.4% honest generic fallback for positions with no V5 data). Two sampled captions independently hand-verified against the raw FEN (piece placement, legal moves, tactical geometry) — both checked out as chess-accurate. |
| 4 | `/coach/deep-memory/pattern-history` route referenced by frontend does not exist | Low — panel degrades to blank via `DeepMemoryPanel.jsx`'s `if (error \|\| !memory) return null`, not a visible crash | **Deferred, not in this pass** — building the route family requires matching an undocumented response shape across two endpoints; bigger and riskier than the other items here, needs its own scoping |
| 5 | `AsyncAnthropic`/`AsyncOpenAI` clients constructed with no timeout anywhere in `llm_service.py` | High — real hang risk on any call | **FIXED 2026-08-03** — both clients now pass `timeout=30.0` |
| 6 | ~~Reproducible multi-hour hang on a single move's caption generation~~ | ~~High~~ | **RETRACTED 2026-08-03** — not a real bug. Conclusively identified as a test-harness artifact: `engine_pool.py`'s warm engine is designed to never quit for a long-running server process, and a one-shot test script that imports it never exits either, for the same reason. See §9.1. The 12,328 successfully-analyzed production games are direct proof the real code path never hung |
| 7 | Legacy dual narrative system (`v5_llm_narrator`, `ChessPlan`, `golden_rule_service`) still writes text in parallel with the central pipeline, contradicting the file's own "single source of truth" comment | Medium — real sprawl/consistency risk, plus §9's LLM calls live here | Open — requires confirming nothing else depends on the legacy fields before removal |
| 8 | Four independent mastery/progress systems (§6) use incompatible vocabularies with no reconciliation | Medium-High — blocks any future "has the user mastered X" feature from getting one honest answer | Open — consolidation project, not a quick fix |
| 9 | No coverage-gap signal anywhere in training/puzzle selection (§8) | N/A — confirmed absent, not a bug, a scoping fact for future work | Open — net-new work |

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
- The previously-reported "reproducible hang" in the live-caption-
  generation path was investigated to ground truth on 2026-08-03 and is
  **not a real bug** — it was a test-harness artifact of `engine_pool
  .py`'s intentional warm-engine design (see §9.1). Don't re-open it
  without first checking whether a new repro actually differs from that
  known artifact.
- `socratic_coaching` population, the `pattern_history` data-loss bug,
  and the `trap_detection`/`opening_play` concept detectors (§11, items
  1, 2-3, 5) were all root-caused and fixed 2026-08-03, each verified
  against real production data or a real, known trap/opening line — not
  just code review. The `/coach/deep-memory` route gap (item 4) remains
  open and deliberately deferred.
