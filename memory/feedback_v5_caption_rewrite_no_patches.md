---
name: V5 caption rewrite — no patches until the new pipeline lands
description: HARD RULE against patching templates or filters in V5 caption code until the full fact-extractor + rule-library + renderer pipeline ships and is approved on game d7ce40cf. Locked 2026-05-11 to break the loop where I keep proposing rewrites then ship band-aid template patches instead.
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
**The rule:** Until the new caption pipeline lands and produces user-approved output for game `d7ce40cf-2856-4f1f-b61b-29167deef219`, DO NOT:
  - Patch any existing template (`recognize_good_move`, `_generate_generic_plan` piece branches, `_explain_opponent_move_with_context`, `extract_plan_from_pv` variants in `services/game_decryption_v5_service.py`)
  - Add any new filter rule (`vacuous_text_detector`, `coaching_text_guard`, sentence-stripper, etc.)
  - Ship any caption-related code change outside the new pipeline

The new pipeline ships FIRST. Everything else waits.

**Why:** The loop has been — user points at bad captions → I propose "rewrite the dispatcher properly" → I hit friction (backfill takes 30 min, regen-diff is unclear, container rebuild) → I peel off a smaller "fix this one template" win because it ships in 20 min → big rewrite never happens → next session same bugs reappear. User explicitly called this pattern out (2026-05-11): *"you said this exact thing multiple times and then we lose and develop shit, why this happens?"* This rule binds future-me to push through even when the friction kicks in.

**How to apply:**
  - On session start, check if `services/caption_facts.py` (or equivalent) exists. If not, this rule is active.
  - Any urge to "just fix this one template real quick" is exactly the failure mode this rule exists to prevent. Push through to the new pipeline instead.
  - If the user asks for a small template patch while the rule is active, point at this memory and propose folding the fix into the new pipeline instead.

**Architecture the rewrite must produce:**
  - `services/caption_facts.py` — fact extractor. Inputs: `(board_before, move, board_after, eval_before, eval_after, cp_loss, best_move, pv_after_played, pv_after_best, move_history_san, full_move_number)`. Returns a deterministic dict of facts (attackers/defenders count per square, tactic detected via existing pattern_analyzer, material delta walked from PV, opening match, hanging pieces, etc.). NO claim in the output goes anywhere except a fact this function returned.
  - `data/caption_rules.json` (or .py module) — the ~20 canonical 1200-level rules. Each entry: trigger condition (which fact pattern matches) + template string with named `{variables}` + priority for tie-breaking.
  - `services/caption_renderer.py` — picks the rule whose trigger matches the facts, fills the template, returns ≤25 words. Returns "" when no rule fires (silence preferred over filler).
  - Wired into V5 main loop, REPLACING `recognize_good_move` / `_explain_opponent_move_with_context` / `_generate_generic_plan`. Old code paths get deleted, not gated.

**Voice spec the renderer enforces:**
  - ≤25 words total
  - Structure when applicable: `{Rule}. {Mistake instance}. {Better move + reason}.`
  - Very simple English (1200-level vocabulary)
  - Memorable rule first when possible — e.g. "Only capture when defenders match attackers."
  - No jargon (outpost, fianchetto, controls, minority attack, luft, repositions — see `feedback_1200_test.md`)
  - Every claim traces to a fact returned by the extractor (hallucination = bug)

**Proof gate before the rule unlocks:** Run new pipeline on game `d7ce40cf-2856-4f1f-b61b-29167deef219`. Show captions for all 24 moves. User approves them. Only then does this rule retire and normal work resumes. If captions for that game are still wrong, iterate on the pipeline — DO NOT fall back to patching old templates.
