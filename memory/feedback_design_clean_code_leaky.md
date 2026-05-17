---
name: My design is bang on; my code leaks bugs — apply 7-rule discipline
description: HARD self-discipline. User's repeated observation that my architecture is correct but implementation introduces bugs I should have caught. Specific rules to apply on every coding task.
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
HARD self-discipline rule locked 2026-05-12.

User feedback verbatim: *"when you present your design, architecture you're
bang on, 100% correct, but then when you code, you really start sucking up
and start leaking bugs, so please be mindful, we have to value our time and
efforts."*

The pattern that triggered this: every recent shipped pipeline (V5 bends 1–8,
the retire+frontend isolation, the discovered-attack ray fix) had bugs that
only surfaced when the user ran the code on real corpus / real games, not in
my own pre-commit verification. Synthetic test cases passed; reality didn't.

**Why:** My pre-commit testing has been optimistic — I build test cases that
exercise the path I just wrote, not the edge cases the design didn't model.
Each bend was caused by corpus realities the architecture didn't anticipate.

**How to apply** — these seven rules ride on every implementation task:

1. **Ship the text/data layer BEFORE the code layer.** Catalogs, configs,
   tables, schemas ship as pure data files for user review. No detectors,
   no functions, no behavior. The user signs off on the contract first.
   Then I write detectors against the locked contract.

2. **Calibrate audit cadence to risk surface, NOT to a fixed cadence.**
   For chess-geometry code (SEE walks, ray-clearance, mutual-line gates,
   pin/skewer/fork detectors with complex state) — corpus audit BEFORE
   next change. That class is where I leak bugs.
   For simple wrappers / one-condition detectors / table lookups, batch
   and audit collectively (Mohit 2026-05-12: "it's a waste of time to
   audit with one detector"). Per-detector audit ≠ free; corpus regen
   costs ~20 min each, so 27 small wrappers would burn 9+ hours for
   isolation value the per-principle audit aggregation already gives.
   Real-corpus INLINE tests (5 positive + 5 negative) still ship per
   detector before commit. The audit-batch only changes WHEN the
   3,549-game corpus pass runs, not whether each detector got
   verification. Don't drop the inline discipline.

2b. **"Defer until corpus data" is ALSO over-caution.** Same anti-pattern
    as audit-each-one — caught 2026-05-12 when I shipped 24/28 detectors
    and rationalized the gap as "these 4 need corpus calibration."
    Mohit caught it: "we decided total 28, right?" Reframe:
       - If the catalog text is locked, ship a v1 detector that may
         need tuning. Audit + tune is cheaper than deferred-forever.
       - "Hard to detect cleanly" is not the same as "impossible." If
         a simple proxy fires on the obvious cases and misses subtle
         ones, ship it; the corpus audit shows what to refine.
       - Deferring entries leaves catalog-vs-code drift, which compounds.
         A documented-but-unimplemented entry is debt, not safety.
    The rule: hit the committed scope. Tune from audit data, don't
    pre-emptively narrow it to "what I can prove correct in advance."

3. **Real-corpus tests, not synthetic.** Every detector PR includes
   ≥5 positive examples pulled from real corpus games (with game_id /
   move_number / FEN) and ≥5 negatives where the detector should NOT
   fire. Synthetic hand-built FENs miss the edge cases real games hit.

4. **Edge case enumeration at the top of every function.** Before the
   body, list: promotion, en passant, castling, empty PV, missing eval,
   pinned pieces, mate sentinel, edge ranks/files, all the boundary
   conditions. If I can't enumerate them, I haven't thought hard enough.

5. **No "verified locally" claims without naming scope.** Per
   `feedback_chess_content_verification.md` — explicitly state what was
   tested, what wasn't, what could still break. Bend #4 was claimed
   verified before #11 OPP Qxe2+ surfaced; that should not repeat.

6. **Pre-commit self-audit with the "Parth's tester" hat.** Re-read the
   diff before pushing. For each conditional, ask: what's the case where
   this returns the wrong answer? If I can't articulate why a specific
   edge is handled, I haven't handled it. Slow down before commit.

7. **Bug rate calibrated honestly.** First-pass detectors WILL have
   false positives. Up-front estimate: "~1–2 cases per detector at first
   audit." That's calibrated honesty, not a promise of perfection. We
   work from a known baseline, not a fictional clean one.

**Specifically forbidden:**
- Claiming a detector "works" after passing only my own constructed test
- Shipping multiple detectors at once and auditing collectively
- "Should be fine" reasoning without an edge-case list
- Optimistic refactors that change behavior alongside bug fixes
- Skipping the corpus audit because the change "looks small"
