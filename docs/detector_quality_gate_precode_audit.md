# Detector Quality Gate — pre-code audit

Status: PASS — 2026-08-27

1. **Literal UI contract — PASS.** V1 has no new UI. Section 2 defines the
   player-visible effect and literal examples for Plan-grade, Caption-grade and
   silence.
2. **Pattern-led narrative — PASS.** The contract describes weaknesses and
   lessons by chess pattern; SAN is evidence, not the headline.
3. **Thresholds from data — PASS.** Candidate floors, Wilson treatment,
   production baselines, rejected candidates and Lichess pilots are recorded in
   `docs/detector_quality_threshold_lock_2026_08_27.md`.
4. **Behavior-changing success — PASS.** This is safety infrastructure, so the
   relevant behavior is enforced end to end: Shadow/Disabled output cannot
   change captions, active focus, plans, mastery or prompts; authorized output
   can. The scope requires both proofs.
5. **Deferred work remains deferred — PASS.** No new UI, lesson modes, pricing,
   LLM truth judge, live API dependency, blanket detector rewrite, or external
   player evidence is entering V1.
6. **Explicit signoff — PASS.** Mohit replied “go” after being asked for full
   scope authorization; the scope skill explicitly recognizes “yes go” as
   signoff.

Additional hard gates:

- complete registry inventory: `docs/detector_inventory_2026_08_27.md`;
- independent gold protocol: `docs/detector_gold_adjudication_protocol.md`;
- provenance: `docs/lichess_detector_corpus_provenance.md`;
- baseline tests: 21 passed, 2 rule-of-square failures, 7 skipped. The failures
  are pre-existing evidence that rule-of-square must remain Shadow, not a waiver.

Proceeding to implementation with unknown IDs failing closed.
