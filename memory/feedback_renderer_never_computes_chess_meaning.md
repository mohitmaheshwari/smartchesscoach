---
name: Renderer never computes chess meaning — extractor is the only source of truth
description: HARD architectural law for the V5 caption pipeline and any future coaching renderer built on top of the fact extractor. Locked 2026-05-11 on user sign-off of design doc v2. The instant the renderer starts "figuring things out," the old V5 hallucination disease returns.
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
**The rule:** In the caption pipeline (and every future renderer that uses `caption_facts.extract_facts()`):

  - **Extractor computes chess meaning.** It reads the FEN, the engine PV, the eval, and produces a deterministic dict of FACTS. Every fact is a function of board state — no opinions, no narration, no "intent" guessing.
  - **Renderer NEVER computes chess meaning.** It only SELECTS a rule whose trigger matches the facts dict, and COMPRESSES the matched facts into ≤25 words by filling a template. It cannot introduce a fact the extractor didn't return.
  - **Rule triggers** are boolean predicates over the facts dict — nothing else. A trigger MUST NOT call python-chess, MUST NOT inspect the FEN, MUST NOT walk a PV, MUST NOT consult Stockfish. Anything the trigger needs comes from the facts dict.

If a rule wants to express something the extractor didn't compute → add a fact to the extractor. **Never** make the renderer do the chess work.

**Why this is law:** The old V5 disease was multiple voices computing chess meaning independently — the king-safety voice, the opening voice, the teaching voice — and rendering onto the same card. They contradicted each other because each ran its own little chess reasoning. The new architecture only works if there's ONE place where chess meaning is computed (the extractor). The moment the renderer starts inferring, even mildly ("hmm if this is a knight on the edge it's probably bad"), we recreate the old failure mode in a new file.

**How to apply during implementation:**
  - Write the extractor first. ALL facts get computed there. No `getattr(facts, "guess_something_clever")` in rules.
  - Rule triggers should be boilerplate-simple: `facts["tactic"] == "fork"`, `facts["is_exchange_losing"]`, `facts["played_is_best"] and facts["primary_reason"] is not None`. Each trigger fits in one line.
  - Templates fill `{variables}` from the facts dict. The variable names in templates must match key names in facts. No string-manipulation logic inside templates.
  - If you're tempted to write `if facts["played_san"].startswith("N"):` in a rule — STOP. Add `facts["played_is_knight_move"]` to the extractor.
  - Code review checklist for any new rule: "Could this rule run if I deleted python-chess from the codebase?" If yes, the rule is correct. If no, it's reaching past the facts dict into chess logic.

**The verification:** the test for this rule is mechanical. Once the renderer is built, grep for these inside `caption_rules.py` and `caption_renderer.py`:
  - `import chess` — banned
  - `chess.Board` — banned
  - `board.parse_san` / `board.attacks` / `board.piece_at` — banned
  - `engine.analyse` / `engine.play` — banned
  - Any function call other than dict lookups + string formatting — suspicious; review

If any of those appear in the renderer or rule files, the rule is being broken. Move the logic to the extractor.

**Extended scope:** this law applies to every renderer built on top of the fact extractor, including future:
  - Play with Coach commentary
  - Postgame review
  - Puzzle explanations
  - Plateau Breaker captions
  - "Why not this move?" tutor responses
  - Tactical quiz feedback
  - Adaptive lesson narration

The user (2026-05-11) observed: *"You accidentally created something bigger than captions: facts → reasoning → compressed teaching. The extractor layer becomes the canonical chess understanding layer. That's the real leverage."* This rule protects that leverage by keeping the extractor as the single chokepoint for chess truth.
