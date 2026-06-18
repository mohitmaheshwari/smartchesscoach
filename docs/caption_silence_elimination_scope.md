# Caption Silence Elimination — Scope (DRAFT, awaiting sign-off)

*Created 2026-06-18, rewritten 2026-06-19 against a fresh re-render (was
`opponent_move_guidance_scope.md` — broadened from opponent-only once the real
numbers came in). Scope-Driven Development: no detector code until Mohit signs off.*

Parent design: [why_now_coach_layer_scope.md](why_now_coach_layer_scope.md).
Substrate: 100-game whole-game gold corpus (`_gold_records_wg.jsonl`, 6216 verified
captions) + the **fresh re-render** comparison (`scripts/fresh_render_compare.py`).

## The gap — LOCKED on a fresh re-render (not stale stored data)

Measured by re-rendering the **current** V5 pipeline in-memory on all 100 corpus
games (no DB writes) and tiering each served caption vs gold with the locked
`caption_classifier` (teaching = HIGH/MID):

| | value |
|---|---|
| moves | 6216 |
| system TEACHES (fresh served caption) | **69%** |
| gold teaches | 90% |
| **TRUE MISS (system silent/filler, gold teaches)** | **1612 = 25%** |
| of which empty `R_FALLBACK_no_primary` (pure silence) | **788 = 12%** |
| miss split | **1060 opp (66%) / 552 user (34%)** |

Three measurements were taken; only this one is trusted. `primary_reason` alone
(674, "100% opp") was the wrong layer — it's one input, not the served caption.
Stored captions read 63% teach / 32% miss but were **stale** (older pipeline);
fresh reads 69%, confirming the staleness and the decision to re-render.

### The principle (Mohit, 2026-06-19)
There are almost **no truly "quiet" moves**. c5 = Sicilian (name it), c4 = English
(name it), Ne2 = development (if the back rank is clear, *you can castle* — say so),
h4 = it chases your queen / storms your king (derive the real point). **Every silence
gets real, board-derived content, or stays silent only when there is genuinely
nothing. No "calm / keep developing" filler** (memory `feedback_principle_bank_is_filler`).

## Where the silence lives (rule paths, to confirm with rule_name dump in build step 0)

The miss-by-type maps onto specific silent rule paths in the existing engine:

| Miss type (n) | Likely silent path | Derived content to add |
|---|---|---|
| opp_other 257, good_other 189 | `R_FALLBACK_no_primary` (788 empty) | opening name · what-move-attacks · castling cue · the plan |
| opp_develop 129, good_develop 55 | `R11_development` (**"silent, no JSON variant"**) | the plan behind the developing move + castling-available cue |
| opp_trade 180 | A3 opp-narration gap | the recapture / reply (`user_best_reply_san`) |
| opp_pawn 89, opp_space 83 | opp-narration / fallback | what the push attacks; pawn-storm awareness; the reply |
| good_space 61, good_centralize 56, good_rook_* 88 | `R15_good_move` quiet | what the good move accomplishes (the plan) |

## Proposed build — EXTEND the existing engine, no new surface

Single-source-of-truth (memories `feedback_single_source_of_truth`,
`feedback_one_source_of_truth`, `project_pwc_runs_second_coaching_engine`): all of
this routes through the existing `caption_facts` → `extract_primary_reason` → rule
paths → `build_move_teaching_decision`. **No second engine, no parallel detector
file.** Each item below is a derived-fact clause feeding an *existing* silent path.

### Derived-content building blocks (each board-derived + independently verifiable)
1. **Opening name (both sides)** — route through the canonical
   `opening_book.recognize_opening_from_history` (memory `project_opening_recognizer_canonical`).
   It's not firing on all opening moves (c5/c4). Extend firing/coverage; do NOT add a 5th recognizer.
   *Verify:* recognizer returns a name for the move-history prefix.
2. **Castling-available cue** — student can legally castle *now* (rights intact, squares
   between king/rook empty, not in/through check). *Verify:* `board.has_castling_rights` + legal `O-O`.
3. **What-the-move-attacks (opp moves)** — the opponent's move (or its threatened next push,
   e.g. h4→h5) attacks a student piece → "move it / defend it." *Verify:* target square in
   `board_after.attacks(...)` or engine PV shows the capture; never claim a threat the line doesn't show.
4. **Pawn-storm awareness** — ≥2 opponent pawns advancing toward the student king file-zone →
   one awareness clause. *Verify:* pawn ranks + proximity to king; gate hard against false alarms.
5. **The reply / opportunity (opp moves)** — extend the EXISTING `user_best_reply_san` /
   `opponent_opportunity` beyond forcing/material to positional replies: recapture, grab-loose-pawn,
   centralize, trade-into-winning-ending, blockade-passer. *Verify:* named reply = engine PV[0]
   on the post-opp position; "free pawn" SEE-verified; "winning ending" eval-verified.
6. **Plan-behind-a-good-move (user moves)** — on a good move that fires no primary_reason
   (R11/R15 quiet), state what it accomplishes (develops + eyes X / centralizes / gains space /
   opens the file for the rook). Much is already in `caption_facts` (best_purpose, develops,
   open-file) — the fix is *rendering* it on good moves, not new detection. *Verify:* the moved
   piece actually does what's claimed (strict attribution, as in the distill skill).

### Fill the two designed silences
- **`R11_development`** — give it a real clause (block 6 + castling cue) instead of staying mute.
- **`R_FALLBACK_no_primary`** — when it fires, run blocks 1–6 in priority order; emit the first
  that verifies. Emit nothing only if all abstain (should be rare). Replaces the 788 empty captions.

### Truth bar (`right-or-silent`) — unchanged from the locked distillation arch
Every claim re-derived independently at render; any clause that fails to verify abstains;
whole caption abstains rather than guess; no runtime LLM (offline-distilled templates,
deterministic render + verify). Run `pwc_coaching_lint.py` after any coaching-surface change
(memory `feedback_dont_make_mohit_qa`) — catches empty/snake_case/grammar/jargon/pawn-called-piece
(the live pipeline already ships "it dose not give the tempo"-class bugs; lint must gate them).

## Acceptance (measured on `fresh_render_compare.py`, the locked harness)
- **System-teaches 69% → target ≥ 85%**; **empty `R_FALLBACK_no_primary` 788 → ~0**.
- Per derived-content block: **verified-truth = 100%** on a held-out slice (the shippable gate).
- No regression: existing fired captions don't lose tier; `pwc_coaching_lint` clean.
- `log()` whatever stays silent after the pass (no silent caps — memory `feedback_three_detection_principles`).

## Build order (cleanest/most-verifiable first)
0. **Confirm the silent-path mapping** — dump `rule_name` for the 1612 misses (one fresh-render
   pass with rule_name capture) so we build for the paths that actually fire, not the table's guess.
1. Opening-name coverage (block 1) — pure reuse, highest certainty.
2. Castling-available (2) + plan-behind-good-move (6) — board-checkable, no engine dependency.
3. What-move-attacks (3) + the reply (5) — engine-PV-verified.
4. Pawn-storm (4) — gate hardest (false-alarm risk).
5. Re-render, re-measure, iterate to ≥85%.

## Open questions for Mohit (sign-off)
1. **Target** — is ≥85% system-teaches the right bar, or push for ~90% (gold parity)? Some moves
   may legitimately abstain (irreducibly positional) — I expect a small honest residual, not 0%.
2. **Build-order** — agree with starting on opening-name + castling + good-move-plan (no-engine,
   fastest, highest certainty) before the engine-verified opp-reply blocks?
3. **calm residual** — confirmed NO generic filler; a move with nothing board-derivable stays
   silent. Agreed?
