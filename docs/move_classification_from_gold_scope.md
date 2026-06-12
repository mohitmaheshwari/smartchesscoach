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

## 8b. LOCKED TAXONOMY (Mohit 2026-06-11) — fundamentals-first, depth as the spine

Derived from the **existing** `mistake_classifier` types (hangs/forks/pins/walked-into)
+ 4 new engine-decidable detectors. `cognitive_gap` is rewired to THIS set (one
taxonomy — no third layer). `time_pressure` is a modifier flag, not a category.

**Precedence (single-label; highest confirmed wins). Phase gates apply first
(endgame/opening eligibility), then this severity order:**

| # | Category | Engine signal | Tier |
|---|----------|---------------|------|
| 1 | `allowed_mate` ⭐NEW | opponent has forced mate after the move (eval≈mate vs user) | fund |
| 2 | `one_move_blunder` | hung material, taken in 1 (HANGING_PIECE/MATERIAL_BLUNDER) | fund |
| 3 | `walked_into_tactic` | material lost to a 2–3 move tactic (WALKED_INTO_*) | fund |
| 4 | `bad_trade` ⭐NEW | voluntary unequal exchange (material delta) | fund |
| 5 | `missed_mate` ⭐NEW | had forced mate, lost it (eval≈mate before → gone) | fund |
| 6 | `missed_tactic` | missed a 1–3 move fork/pin/skewer (MISSED_*) | fund |
| 7 | `missed_free_material` ⭐NEW | best move takes free/hanging material, played didn't | fund |
| 8 | `conversion` | was winning (eval≥~+200 for user) → slipped to ≤0 | fund |
| 9 | `king_safety` | real attack on exposed king, queens/pieces ON | concept |
| 10 | `endgame_technique` | queens-off endgame conversion / king activity | concept |
| 11 | `calculation_depth` | genuinely deep (>3) miscalc | concept |
| 12 | `ignore_threat` | ignored a non-material threat (already in code) | concept |
| 13 | `pawn_structure` | lasting pawn weakness — **judgment (LLM)** | concept |
| 14 | `piece_activity` | passive piece, no material/tactic — **judgment (LLM)** | concept |
| 15 | `opening_knowledge` | opening-phase departure from theory | concept |

Folded (not separate): `missed_defense` → `missed_tactic`; `tactical_oversight`
RETIRED (was the vague bucket → splits into walked_into_tactic / missed_tactic);
`piece_safety` RETIRED as a surfaced label → umbrella only (rolls up 2–4).

**Engine-decidable (hard gold, no LLM): 1–12, 15.** LLM only needed for **13–14**.
**Rating-tier surfacing:** <1300 sees the fundamentals (1–8); >1300 leans concept (9–15).

### 8b-update (Mohit 2026-06-12) — PHASE categories are fundamentals too

`opening_knowledge` and `endgame_technique` moved from concept → **FUNDAMENTALS
tier**. Rationale: for <1300 the *phase* skills (develop/castle/centre; king
activity/promote/basic mates) are core fundamentals — it's inconsistent to call
the tactical fundamentals "fundamental" but not the phase ones. So the
**fundamentals tier = 10**: one_move_blunder, walked_into_tactic, bad_trade,
allowed_mate, missed_mate, missed_tactic, missed_free_material, conversion,
**opening_knowledge, endgame_technique**. Concept tier (now 5): king_safety,
calculation_depth, ignore_threat, pawn_structure, piece_activity.

**`opening_knowledge` detection (the move<=8 heuristic was garbage, 0/12):** sits
**below** material/mate/tactic in precedence (an opening hang is one_move_blunder,
not opening_knowledge). "Real" opening_knowledge = a non-blunder opening error —
**early queen, same piece moved twice, no castle by ~move 12, off-book vs the
opening DB** (reuse `EARLY_QUEEN` + `detect_opening_from_moves` + opening
curriculum). Engine/rule-based, not the cp-only heuristic.

### 8b-correction (2026-06-12) — material detection must be PV-grounded, NOT geometry

VERIFIED against the engine: the geometry hang-checker
(`_played_move_hangs_piece`) false-positives **~37%** ("attacked+undefended" but
the engine doesn't actually win it — pinned/overloaded defender, capture
walks-into-a-tactic, x-ray) AND misses material losses not on the moved piece.
`one_move_blunder`/`walked_into_tactic` (and the shipped `_precedence_adjust`
rule A) must classify from the **engine PV**: walk `pv_after_played`, net material
lost at ply ≤2 → one_move_blunder; ply 3+ → walked_into_tactic; never lost → defer.
Corrected fundamentals on the 3 users: one_move_blunder fell 41→28% (shobhit),
32→19% (mohit) once FPs were removed.

## 9. Open questions for Mohit
1. **Precedence (§1) — sign off or reorder?** Specifically: does `king_safety`
   outrank `missed_tactic` when a king is both exposed AND there's a missed fork?
   (Proposed: missed_tactic first — the concrete forced win is the lesson.)
2. **Distinct `king_activity` tag** vs folding into `endgame_technique`? Proposed:
   fold (no taxonomy growth; the teaching prompt already fits). Revisit if the
   confusion matrix shows endgame_technique is too broad.
