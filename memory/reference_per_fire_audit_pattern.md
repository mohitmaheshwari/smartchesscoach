---
name: per-fire-audit-pattern
description: Five-step pattern for proving detector-layer accuracy — frequency audit + independent per-fire geometric verifier + targeted scrub script. Result on 2026-05-12 — TIER 3 and TIER 2 hit 100% per-fire geometric accuracy across production corpus.
metadata: 
  node_type: memory
  type: reference
  originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---

The pattern that made `feedback_chess_content_verification` mechanically enforceable:

1. **Data catalog first** — `backend/services/shape_patterns.py` and `caption_principles.py` are pure data with locked names/descriptions before any detector code ships.
2. **Detector module** — `shape_detectors.py` and the `_p_*` functions in `caption_facts.py`. Emit evidence dicts with claimed squares + executing move.
3. **Frequency audit** on a benchmark corpus — catches spam patterns. (`audit_caption_v5_corpus.py`, the inline corpus tests in `_self_check()`)
4. **Per-fire geometric audit** — independent re-derivation of the geometric claim from the FEN. Crucially, the verifier code is SEPARATE from the detector code; same geometry, different implementation. When they disagree, one of them has a bug.
   - `scripts/audit_shape_patterns_per_fire.py` (23 patterns)
   - `scripts/audit_caption_principles_per_fire.py` (28 principles; 20 GEOMETRIC, 8 STRUCTURAL-only)
   - Verifier scope: GEOMETRIC re-derives the claim. STRUCTURAL only checks evidence shape. Subjective principles (king safety, walk king, king activity) get STRUCTURAL — be honest about that, don't fake-verify.
5. **Targeted scrub** — when a detector bug is fixed, existing data still carries pre-fix FPs. `scripts/scrub_principle_fps.py` runs the same audit verifier per-fire and drops mismatches. Much lighter than full V5 re-extraction.

**Bugs this caught on 2026-05-12 (would have shipped to users otherwise):**
- `open_long_line` parity swap — 80% FP rate (2276 FP fires of 2845 total).
- `TAC_BACK_RANK` missing king-on-back-rank gate — 24% FP rate on a strict-gated principle.

**Verifier bugs this caught in MY OWN AUDIT CODE:**
- 5 of 6 initial V5 failures were bugs in the verifiers, not the detectors. Independent implementation works — you find bugs in BOTH directions.

**Final state after this round:** 100% per-fire geometric accuracy on both TIER 2 (390 fires) and TIER 3 (643 fires).

Use this pattern for any new detector layer. Build per-fire verifier BEFORE claiming the layer is accurate.
