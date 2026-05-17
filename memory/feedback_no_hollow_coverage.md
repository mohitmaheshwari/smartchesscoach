---
name: Don't pad coverage with hollow captions
description: When coverage metrics improve but caption text doesn't actually explain why a move is better, that's an accounting trick — not a real fix
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
When templating chess captions (or any "explanation" text), generic descriptive text counts as a coverage win in audits but **does not satisfy the product vision**. Examples of what failed:

  - "Engine prefers c6 over h5 — different pawn, different idea." ← says nothing
  - "Knight to e5 — engine prefers Nd4, a stronger square for that knight." ← player still has no idea why
  - "...switches to a pawn move instead of the bishop." ← describes the swap, not the reason

These produced a 12-point coverage jump but the player learns nothing from them.

**Why:** The product vision (CLAUDE.md / project_product_vision memory) is "teach thinking process, not moves — fundamentals checklist, guided discovery, make players feel better." A real coach explains *why* the engine's square is better (attacks more material? defends a vulnerable piece? leads to a tactical sequence in the PV?), not just *that* the engine prefers it.

**How to apply:**
  - When a caption template lacks a concrete *why* (material gain, king safety, threat, tactical sequence, piece activity diff), prefer honest silence or a generic "engine line is better — see the moves" over fluffy template text.
  - Coverage % is a leading indicator, not a quality indicator. Always read sample captions for any new bucket and ask: "would a 1200-rated player learn anything from this?"
  - Use available signals (pv_after_best, attack/defense maps, piece activity diff) to derive WHY before defaulting to descriptive shape comparisons.
  - "The engine prefers X here" is bad. "Engine prefers Nxe5 — wins the bishop" is good. The middle ground (long descriptive sentence with no concrete payoff) is *worse* than the original because it pretends to explain.
