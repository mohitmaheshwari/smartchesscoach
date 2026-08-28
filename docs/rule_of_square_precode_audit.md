# Rule-of-Square Source Consolidation - pre-code audit

Status: PASS - 2026-08-27

1. **Literal UI contract - PASS.** The signed scope contains exact correct-play,
   missed-play and abstention copy; no new UI is added.
2. **Pattern-led narrative - PASS.** The lesson is the king entering the pawn's
   square. Move notation is supporting evidence.
3. **Thresholds from data - PASS.** No new numeric heuristic survived. The
   formula bake-off and mutual-race boundary are locked in
   `docs/rule_of_square_data_lock_2026_08_27.md`.
4. **Behavior-changing success - PASS.** All adapters must agree and Disabled
   authorization must prevent player-facing output.
5. **Deferred work remains deferred - PASS.** No runtime network, Stockfish,
   LLM, multi-piece ending, UI, backfill or authorization promotion enters V1.
6. **Explicit signoff - PASS.** Mohit replied: "locked, go code."

Additional hard gates:

- canonical source: `services/concept_detectors/rule_of_the_square.py`;
- tablebase source/provenance: locked;
- mutual races: excluded from V1;
- gold format and held-out policy: recorded;
- current player-facing paths remain Disabled.

Proceeding to implementation.

