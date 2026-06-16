# Caption Distillation Rollout — Scope

*Plain-English scope (per scope-driven-development). Drafted 2026-06-16. Author: Lane-takeover agent, founder-directed.*

## What this WILL be at the end
Every flagged user (and notable opponent) move on chessguru gets a coaching caption that is **(a) true on
the board** and, where the situation is engine-decidable, **(b) gold-grade in what/why/principle** — produced
**deterministically at $0 runtime LLM cost**, with **Claude used only offline** to distill the templates.
Moves whose "why" is irreducibly positional **abstain** (right-or-silent) rather than ship filler.

## Why (the problem we proved)
- The legacy R12 cascade scores **~16% match-to-gold** and **hand-editing it REGRESSES** (41→36%, whack-a-mole
  fillers, gates that don't obey their docs). Dead end.
- **Distillation** (Claude writes+distills one template per CLEAN situation; strict engine slots; independent
  verifier) ships **truthful** captions at $0 runtime and reaches gold-grade on clean tactical situations
  (piece_safety 72%, missed_tactic 54%). Proven on 4 situations.

## The model
- **Engine = truth** (PV/eval). **Claude = meaning** (offline distillation, once/situation). **Verifier = safety**
  (board-checks every claim; unverifiable → abstain). Recipe lives in the `distill-caption-template` skill.
- **Bars:** verified-TRUTH = the shippable gate (0 lies). gold-match = a quality tracker (noisy < n≈50; gate
  the gold itself; principle-bank per sub-case).

## Two prerequisites (systemic — do once, up front)
1. **Clean-taxonomy reclassification.** Re-label gold + live moves into the clean 15-cat taxonomy
   (`classify_fundamentals.classify`). Vague buckets (tactical_oversight) must be split or they cap ~33%.
2. **PV depth.** Shallow situations work on stored data; DEEP ones (missed_mate, multi-move combos) need
   deeper stored `pv_after_best` (re-analyze with longer PV storage, or Stockfish-at-distill-time) to name
   the specific tactic. Until then, deep situations ship the verifiable-but-vaguer "a winning line exists."

## Phased plan
- **Phase 1 — shallow clean tactical (NOW, no infra blocker):** `one_move_blunder` (39 gold),
  `walked_into_tactic` (37), `missed_free_material` (8). Each: reclassify-filter → distill → strict slots +
  verifier + gold-verify → judge → iterate slots to verified-truth=100% + best clean-gold match. These name
  the hung/captured piece from the immediate position — no deeper PV needed.
- **Phase 2 — deep clean tactical (after PV-deepening):** `missed_mate` (17), multi-move combinations.
  Requires the PV-depth prerequisite; until then ship the verifiable-vaguer form.
- **Phase 3 — positional:** `king_safety` / `pawn_structure` / `piece_activity` (~45% defer) →
  **abstain by design** (right-or-silent). No template; optional offline-Claude cache for high-frequency repeats.
- **Phase 4 — wire to prod:** the distilled templates feed `build_move_teaching_decision` (the central layer);
  served via the existing path; **no runtime Claude**. Flag-gated rollout (default off → 10% → 100%).

## Cost (measured, not estimated)
- ~40-60 verified gold/situation (mostly already collected) + ~1-4 slot passes (~2-4 hrs eng/situation,
  variety-dependent). Claude: one cheap distillation pass/situation. Runtime Claude: $0.
- ~40-60 engine-decidable situations; positional residue abstains.

## Done when
Each shipped situation: **0 false claims (verified-truth 100%)** + best-achievable clean-gold match; positional
abstains cleanly; the whole path runs with **zero runtime LLM**; flag-gated rollout complete.

## Non-negotiables
- Never hand-edit the R12 cascade to chase a category (proven to regress).
- Every claim type a template emits has a board-verifier checker authored FIRST.
- Verify the gold before grading against it.
- Ship truth; let match be a tracker; abstain over filler.
