---
name: audit-coverage-tracks-surface
description: "HARD self-discipline locked 2026-05-13. Per-fire audits must extend to cover EVERY rule/field/renderer I touch, not stay frozen at the first layer I happened to audit. \"100% verified\" without a scope clause is a lie by omission. When stating results, lead with what's NOT covered."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---

The pattern that keeps biting: I audit one layer (TIER 2 principles +
TIER 3 shapes — 28 + 23 detectors), declare 100%, and ship. Then the
user opens a real game and finds bugs in R07, R11, R12, missed_tactic
detection, cue noise, opp-blunder gaps. Every one of those was an
UNAUDITED rule or field. The 100% was correct within scope. The scope
was too narrow.

**Why:** The user asked me directly on 2026-05-13 why bugs still exist
"when we created many scripts verifying board, stockfish, pv everything
and you said 100% clear." The honest answer: my audits were narrow,
and the headline number anchored louder than the scope clause.

**How to apply:**

1. **Every time I patch a rule, renderer, or fact**, I add or extend a
   per-fire audit for THAT specific thing. R07 audit when I touch R07.
   R11 audit when I touch R11. R12 WHY-presence audit when I add the
   WHY clause. Not just unit tests — corpus per-fire.

2. **When stating audit results, lead with what's NOT covered:**
   - Bad: "100% per-fire geometric accuracy across 643 fires."
   - Good: "100% per-fire geometric accuracy on TIER 2 principles + TIER 3 shapes
     ONLY. Not audited: R01–R14 renderer rules, missed_tactic_evidence,
     cue pedagogical fitness, opp-blunder WHY presence."

3. **An audit that checks 'when X fires it's geometrically right' does
   NOT cover:**
   - Whether the right things FIRE (over-fire / under-fire)
   - Whether the rendered TEXT correctly attributes to the played move
   - Whether the cue is pedagogically useful (hollow coverage)
   - Gaps where a field SHOULD exist but doesn't (R12 opp-blunder WHY)
   - Whether "N pawns" framing is semantically right vs just numerically true

4. **My reliable lane: plumbing + spec-execution + audit-extension.**
   Authoring player-facing text and self-judging pedagogy are where my
   errors compound. The operating mode signed off 2026-05-12:
   user authors text, user specs detectors with FENs, I extend the audit.

This memory exists because the user asked "did you learn anything."
The answer being yes only counts if it's persisted.
