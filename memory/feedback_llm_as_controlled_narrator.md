---
name: llm-as-controlled-narrator
description: "HARD architectural law (2026-05-15). LLM is a controlled narrator, not a reasoning system. Facts → semantic IR (resolver) → verbalization (LLM) → repair (verifier). Never return to fat-prompt LLM-as-reasoner."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---

The V5 LLM caption pipeline is built on this architectural law:

  facts → semantic IR (resolver) → verbalization (LLM) → repair (verifier)

NOT:

  facts → giant mystical transformer soup

This means the LLM is demoted from REASONING SYSTEM to CONTROLLED NARRATOR.
All chess decisions (which focus, which anchor, which entities may be named)
happen in Python BEFORE the LLM is called. The LLM only verbalizes a
pre-resolved decision in coach voice.

**Why:** The fat-prompt approach (21K chars, 9 branches, full catalog exposure)
gave us:
  - Hallucinated moves (alt-suggestions outside whitelist)
  - Hallucinated openings (Italian Game on c5)
  - Hallucinated shapes (Free Piece when no shape fired)
  - Selective rule-dropping at scale on gpt-4o-mini
  - Non-reproducible captions, model-version sensitive

The new pipeline gives us DETERMINISTIC FAILURE MODES — failures are
inspectable, attributable, reproducible, testable. That is the real win,
bigger than cost reduction.

**How to apply:**
1. Never expose the LLM to "all signals, pick the right one" prompts —
   that's the resolver's job, in code.
2. Never add chess analysis (FEN parsing, PV walking, engine calls) to
   the LLM prompt — keep [[renderer-never-computes-chess-meaning]] intact.
3. If captions need richer voice, add layered prompting (style-layer
   modularization) — NOT bigger prompts.
4. If captions feel templated, fix by adding [[persistent-coaching-memory]]
   context — NOT by expanding the system prompt.
5. Hidden LLM recovery is FAKE RELIABILITY — if the resolver is wrong but
   the LLM "rescues" it, you can't debug, benchmark, or improve. Resolver
   bugs MUST surface as caption bugs; that's how we know to fix them.

Recovery escape hatch: if a class of moves genuinely needs LLM-level
reasoning that the resolver can't pre-compute, the answer is to extract
the missing fact upstream (in caption_facts or a new detector), not to
re-empower the LLM as a reasoner.

Locked 2026-05-15 with user sign-off after the bounded-improvisation
evolution (commit 886457bb). See [[v5-caption-rewrite-no-patches]],
[[renderer-never-computes-chess-meaning]], [[design-clean-code-leaky]].
