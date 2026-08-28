# Hanging-Piece Detector - Pre-Code Audit

**Date:** 2026-08-28
**Result:** PASS - existing detector repair, not a new feature.

- The signed detector-quality scope requires preserving and improving
  canonical `simple_hang` and exchange machinery in place.
- Mohit approved the selected next repair with "sure".
- There is no new UI, route, schema, collection, LLM path or player-facing
  copy.
- The single-source audit selected `caption_facts.legal_exchange_gain`; Chess
  Brain will become an adapter instead of adding a recognizer.
- The 150cp material floor and strict counterfactual formula are locked from
  the production measurements in
  `docs/hanging_piece_detector_data_lock_2026_08_28.md`.
- The existing shared 100cp causal-mistake floor is reused.
- Success is fewer false causal claims and reproducible evidence, not fire
  volume.
- No promotion, rollout, deployment, backfill or production mutation is in
  scope.

Proceeding to implementation.
