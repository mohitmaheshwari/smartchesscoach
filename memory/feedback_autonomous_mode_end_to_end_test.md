---
name: autonomous-mode-end-to-end-test
description: When Mohit goes away and tells me to build autonomously, I do not ping him until I am 100% satisfied. End-to-end developer testing is the bar — unit + integration + real-corpus simulation + edge cases + self-audit per design_clean_code_leaky. No exceptions.
metadata:
  type: feedback
---

When Mohit goes away and tells me to build autonomously, **I do not ping him until I am 100% satisfied with end-to-end developer testing.**

**Why:** Locked 2026-05-19 by Mohit before Phase 2 build: "I am going to be away. When you develop all this, I want you to proper do end to end test, your developer based testing before assigning it to me. Until you're not 100% satisfied, don't assign — keep working and fixing." This is the developer-first quality bar. Tests-first → ship-first → user-validate-last is the right order; pinging too early wastes a senior person's attention on bugs I should have caught.

**How to apply:** Before any "ready to playtest" handoff in autonomous mode:

1. **Unit-level verification** — every helper function does what it claims (decay math, ELO weighting, suppression keys). Print numerical proofs in smoke tests; don't just "the imports work."
2. **Integration testing** — exercise the full path from DB query → service call → API response → frontend render. Catch wiring bugs that pass per-function tests.
3. **Real-corpus simulation** — pull a real user/game from prod, walk through it end-to-end against my new code. The Walloo21 fixture caught 3 bugs before playtest in Phase 1 — that approach generalizes.
4. **Edge cases enumerated upfront** per [[design-clean-code-leaky]]:
   - Empty state (user with no history, fresh game, no prior fires)
   - Boundary conditions (1 entry, exactly threshold, 1 above threshold)
   - Failure modes (DB unreachable, malformed data, version mismatch)
   - Latency edges (slowest expected query)
5. **Self-audit before handoff** — re-read my own code as a stranger would. Look for: claims I haven't verified, error branches I haven't tested, downstream effects on other surfaces, regressions in adjacent features.
6. **Voice check** — every user-visible string passes [[1200-test]] AND the relevant voice rules ([[coach-voice]], [[teaching-not-reading]], etc.).
7. **Latency check** — if it touches the live-move path, verify <700ms total budget per [[play-with-coach-phase1-design]].

**The "100% satisfied" gate:** before pinging Mohit, ask myself:
- Did I run the new code against real prod data?
- Would I bet money this works on his next playtest without him finding a bug?
- Have I written down what I verified vs what I left untested?

If any answer is "no" or "I'm not sure," KEEP WORKING. Don't ship to him.

**The opposite failure mode:** over-engineering or analysis paralysis. The bar is "I'm confident this works for the use cases I shipped it for," not "I have solved every theoretical edge case." Ship the surface that addresses the user's actual ask, with rigorous tests for THAT surface. Don't gold-plate beyond the contract.

Companion: [[design-clean-code-leaky]] (audit before merge), [[vision-match-before-ship]] (verify end-to-end vision elements present), [[no-yes-man]] (don't tell Mohit it works without proof), [[surface-teaching-gold-proactively]] (research output must be product-ready, not just analytical).
