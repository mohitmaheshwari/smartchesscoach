# Move Classification From Gold — Scope (plain English)

> Status: **DRAFT — Mohit agreed to approach + "you propose the precedence" (2026-06-11).**
> Awaiting sign-off on §1 (precedence) before the classifier is changed. The skill
> (`classify-moves-from-gold`) and this scope are tooling/process — they ship no
> user-facing change; the actual detector edits the skill produces still pass the
> in-skill gates. Sibling to [[project_user_games_gold_detector_loop]] /
> `teach-detectors-from-gold` (that grades the caption WHY; this grades the CATEGORY).

## 0. Why this exists

`king_safety` was firing on queens-off endgame king moves that are really **king
activity / endgame technique** — right mistake, wrong category, wrong teaching
prompt (engine-verified: 12% of all king_safety fires, 95% of those ≤6 non-pawn
pieces). King is just instance #1. The goal: **every mistake move in the last 500
games mapped to the correct cognitive-gap category**, measured against a verified
gold, fixed at the classifier chokepoint, locked.

## 1. THE DECISION — category precedence (single-label tie-break)

Each move gets **one** `cognitive_gap`, but a move is often several things at once
(a hang that's also "passive", a missed fork that's also "shallow calculation").
"Correct" is undefined without a precedence. **Rule: assign the highest-priority
category whose claim the engine/verifier CONFIRMS; only fall to a positional
(judgment) category when no engine-hard category fires.** Gold and detector use
the SAME order — otherwise the match-rate can't converge.

**Engine-hard tier (objectively checkable → outrank positional):**
1. `piece_safety` — material hangs with no compensation (verifier: material check / engine PV).
2. `missed_tactic` — engine PV is a forced win the player missed (fork/pin/skewer/mate).
3. `king_safety` — engine shows a real attack on an exposed king **WITH queens/pieces on the board** (not endgame).
4. `endgame_technique` (incl. **king activity**) — queens-off endgame conversion/king error.
5. `opening_knowledge` — opening phase, deviation from theory (opening-book checkable).

**Positional tier (judgment, softer gold, Claude-assisted):**
6. `calculation_depth` — right idea, missed the deeper line.
7. `tactical_oversight` — saw move 1, missed the reply.
8. `pawn_structure` — weak pawns / bad break.
9. `piece_activity` — passive pieces.

**Phase gates (the structural fix that kills the king bug class):**
- `king_safety` requires queens/attack present → else, on a king move in a
  queens-off endgame (≤6 non-pawn pieces, not in check), it is `endgame_technique`.
- `endgame_technique` requires endgame phase; `opening_knowledge` requires opening phase.

**Orthogonal modifier (NOT in the precedence):** `time_pressure` is a *cause* (the
clock), not a *what*. Treat as a flag alongside the category, never competing with it.

## 2. What it is (the loop)

Pull last-500-games' mistake moves → current detector category → build a VERIFIED
category gold per move → confusion matrix (current vs gold) → fix the classifier at
the one chokepoint → score → iterate to bar → regression-lock. Mechanically the
same gold→verify→score→iterate discipline as `teach-detectors-from-gold`.

## 3. The metric — TWO bars (not one blended number)

- **Engine-hard categories** (1–5): gold is engine-verified, so this is a hard
  accuracy bar — **≥85% category-match**, below which we are not done.
- **Positional categories** (6–9): gold is Claude judgment, inherently fuzzier —
  **measure + report agreement, improve the worst confusions, but do NOT block** on
  the same 85% (acknowledged ambiguity; no silent blending of the two).

## 4. In scope
- Last-500-games mistake moves (cp_loss over the rating-aware bar), user moves only.
- A verified per-move category gold; a confusion matrix; classifier fixes at the
  chokepoint (phase gates / feature guards in the shared interpreter).
- King_safety→endgame as the **first fix + first locked regression case**.

## 5. Out of scope
- Caption WHY-text quality (that's `teach-detectors-from-gold`).
- New gap categories beyond the existing taxonomy (king-activity folds into
  `endgame_technique`; revisit a distinct `king_activity` tag only if the data demands).
- Changing engine analysis depth.

## 6. Reused infrastructure (build nothing new here)
- **Claude terminal gateway** `host.docker.internal:8000` — fallback gold for the
  positional residue only (engine-hard categories don't need it).
- **Verifier** `services/caption_claim_verifier.py` — per-category engine checks
  (already has material/king_safety/tactic/threat/check/recapture). Used to (a) pin
  engine-hard gold deterministically and (b) verify Claude's gold before trusting it.
- **Re-render harness** (stub Stockfish, reuse stored evals; ~150ms/move).
- `caption_facts.extract_primary_reason() → {category}`.

## 7. Gold construction order (cheapest-trustworthy first)
1. Engine-deterministic: verifier + features (queens/material/phase/king-move/
   hanging/PV fork-pin-mate) pin the engine-hard categories.
2. Claude terminal: ONLY the ambiguous positional residue, fed FEN + engine data +
   candidate list + the precedence; asked to pick one + one-line why.
3. Verify-or-redo: engine-confirm Claude's pick where checkable; never teach toward
   an unverified gold ([[feedback_query_engine_before_authoring]]).

## 8. Rollout
- Classifier change is at the shared chokepoint → new analyses get it immediately;
  existing 500 propagate via `backfill_cognitive_gaps.py`. Flag-gate only if a fix is
  riskier than the king phase-gate (which is a clear correctness win, 95% precision).
- Server-side per [[project_local_container_not_prod]].

## 9. Open questions for Mohit
1. **Precedence (§1) — sign off or reorder?** Specifically: does `king_safety`
   outrank `missed_tactic` when a king is both exposed AND there's a missed fork?
   (Proposed: missed_tactic first — the concrete forced win is the lesson.)
2. **Distinct `king_activity` tag** vs folding into `endgame_technique`? Proposed:
   fold (no taxonomy growth; the teaching prompt already fits). Revisit if the
   confusion matrix shows endgame_technique is too broad.
