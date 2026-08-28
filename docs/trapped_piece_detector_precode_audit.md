# Trapped-Piece Detector - Pre-Code Audit

**Date:** 2026-08-27
**Result:** PASS

- **Scope:** covered by the signed
  docs/detector_quality_gate_scope.md, which explicitly includes repairing or
  quarantining trapped_piece in place.
- **UI contract:** not applicable; this is a deterministic bug fix with no new
  surface, schema, route, or copy family.
- **Narrative:** the existing headline remains the board pattern ("trapped
  piece"), not move notation.
- **Thresholds:** the formula and consequence gate are locked in
  docs/trapped_piece_detector_data_lock_2026_08_27.md from read-only
  production measurements.
- **Success measure:** false causal fires and semantic precision, not activation
  or click-through rate.
- **Scope control:** no detector promotion, UI, LLM judge, backfill, deployment,
  or unrelated detector work.
- **Sign-off:** Mohit explicitly requested the next planned detector repair:
  "go for next please."
- **Dirty tree:** detector_registry.py contains the already-scoped quality-gate
  edits. The patch will be surgical and preserve them. Other production targets
  are clean.

Proceeding to implementation.
