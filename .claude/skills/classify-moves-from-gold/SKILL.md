---
name: classify-moves-from-gold
description: Audit and fix the CATEGORY each mistake move is mapped to (king activity, king safety, tactics, piece safety, endgame, …) across a batch of games, against a verified gold, using a single-label precedence. Sibling to teach-detectors-from-gold — that grades the caption WHY; this grades the gap CATEGORY (which is upstream of the caption). Builds a per-move category gold (engine-hard deterministic first, Claude terminal fallback for the positional residue, engine-verified), scores the classifier via a confusion matrix against a two-bar metric, and fixes mislabels at the shared chokepoint. Trigger when the user says "classify the moves correctly", "are moves mapped to the right category", "king activity not king safety", "fix the gap labels", "audit move classification across N games", or any category-correctness (not caption-text) intent.
---

# Classify moves from gold — category-correctness audit & fix

Built 2026-06-11 after `king_safety` was found firing on queens-off endgame king
moves that are really endgame king-activity (right mistake, WRONG category → wrong
teaching prompt). The category is **upstream** of the caption: mis-categorize and
the whole card is wrong. This skill grades and fixes the CATEGORY; the caption-WHY
loop is `teach-detectors-from-gold`. Scope + precedence: [[move_classification_from_gold_scope]].

## The precedence (single-label tie-break — the whole point)

A move is often several things at once. Assign the **highest-priority category whose
claim the verifier CONFIRMS**; fall to a positional category only when no engine-hard
one fires. Gold and detector MUST use the same order or the match-rate can't converge.

**Engine-hard (outrank positional):** 1 `piece_safety` (material hangs) · 2
`missed_tactic` (engine PV is a missed forced win) · 3 `king_safety` (real attack on
an exposed king, **queens/pieces ON**) · 4 `endgame_technique` incl. king-activity
(queens-off endgame) · 5 `opening_knowledge` (opening phase, off-book).
**Positional (softer, Claude-assisted):** 6 `calculation_depth` · 7
`tactical_oversight` · 8 `pawn_structure` · 9 `piece_activity`.
**Phase gates:** king_safety needs queens on (else a queens-off king move ≤6 non-pawn
pieces, not in check → endgame_technique); endgame_technique needs endgame; opening_knowledge
needs opening. `time_pressure` is a modifier flag, never competes.

## The metric — TWO bars (never blend them)

- **Engine-hard categories:** gold is engine-verified → **≥85% category-match**, hard gate.
- **Positional categories:** gold is Claude judgment → measure + improve worst
  confusions, but do NOT block on 85% (inherent ambiguity; report separately, no silent blend).

## When to invoke

- "classify the moves correctly / map each move to the right category", "king
  activity not king safety", "fix the gap labels across N games".
- Do NOT invoke for caption-WHY quality (→ `teach-detectors-from-gold`), a single
  flagged caption (→ /audit-flagged-caption), or voice rewrites (→ /rewrite-for-1200).

## The ordered pipeline — DO NOT REORDER (each step is a gate)

### 0. Confirm the sample
- Last-N-games' **mistake moves** (cp_loss over the rating-aware bar), **user moves
  only** — derive mover from FEN side-to-move vs `user_color`, never trust a flag alone.
- Respect the requested N exactly ([[feedback_respect_specified_sample_sizes]]).

### 1. Current category — fresh, never stored blindly
- Run the shared classifier (`analysis_interpreter.enrich_with_cognitive_gaps` /
  `interpret_game_analysis`) over the batch's `move_evaluations`. Stub Stockfish —
  engine truth is already stored (~150ms/move). Container: `sys.path.insert(0,"/app/backend")`.

### 2. Build the category GOLD — cheapest-trustworthy first
- **Engine-hard deterministic** via `services/caption_claim_verifier.py` + features
  (queens, non-pawn count, phase, is-king-move, hanging detection, engine PV
  fork/pin/mate). This PINS categories 1–5 without an LLM. Apply the precedence here.
- **Claude terminal gateway** (`host.docker.internal:8000`) ONLY for the ambiguous
  positional residue (6–9): feed FEN + stored engine data + candidate list + the
  precedence; ask for one category + one-line why. Engine-hard moves skip the LLM.
- **Verify-or-redo:** engine-confirm Claude's pick where checkable (don't accept
  "missed fork" unless the PV forks). A confabulated category is an automatic gold-reject.

### 3. Validate the gold-builder on a hand-labeled sample (~15) BEFORE trusting the batch
- Hand-label 15 moves; confirm the engine-hard pinner + Claude fallback agree with
  your read. If they don't, fix the pinner/prompt before grading anything.

### 4. Confusion matrix — current vs gold, across the batch
- Build the full NxN matrix. Read the systematic confusions (king_safety↔endgame,
  piece_activity↔piece_safety, calculation_depth as catch-all). Root-cause from the
  WHOLE confusion cell, not one example ([[feedback_three_detection_principles]]).

### 5. Fire-rate / distribution before any classifier change
- For the rule you'll change: how often does it fire and on what feature
  distribution? Pick the gate threshold from the histogram, never from gut
  ([[feedback_threshold_before_distribution_is_sin]] / /lock-via-data). (The king
  fix: ≤6 non-pawn pieces captured 95% of the suspect bucket.)

### 6. Fix at the ONE chokepoint — fix framing, never delete detection
- All surfaces route through the shared interpreter — add the phase gate / feature
  guard THERE so import + PWC both get it ([[feedback_one_source_of_truth]],
  [[feedback_fix_framing_not_detection]]). Reclassify, don't drop. Reuse an existing
  category + its teaching prompt where one fits (king-activity → endgame_technique,
  whose prompt already says "the king is a fighter — walk it to the centre").

### 7. SCORE → iterate or redo until the bar (the gate)
- Re-render, rebuild gold-comparison, report the confusion matrix + **engine-hard
  category-match %**. <85% engine-hard → cluster residual confusions, back to step 4/6.
- Spot-check MATCHes are engine-truthful (a "right for the wrong reason" hit is a fail).

### 8. Prove + lock + expand
- Lock the batch as a **category regression set** (move → gold category). A future
  classifier change must not flip a locked MATCH to MISS. King_safety→endgame is the
  first locked case. Expand 500 → 2k → all, bar holds at each scale.

## What NOT to do
- Do NOT blend the engine-hard and positional bars into one number.
- Do NOT call the LLM for engine-hard categories (they're deterministically pinnable).
- Do NOT change the classifier before the gold is verified, the gold-builder is
  validated on a sample, and the fire-rate distribution is known.
- Do NOT generalize a confusion's cause from one example — read the whole cell.
- Do NOT re-run Stockfish during re-render; truth is stored. Do NOT shrink N silently.

## Notes
- Gateway, verifier, re-render harness, traps: shared with [[teach-detectors-from-gold]].
- Categories/taxonomy: CLAUDE.md "Cognitive Gap Types". Backfill existing games via
  `backend/scripts/backfill_cognitive_gaps.py` after a classifier change.
