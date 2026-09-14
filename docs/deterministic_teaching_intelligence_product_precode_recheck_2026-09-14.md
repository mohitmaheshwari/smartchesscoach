# Deterministic Teaching Intelligence — Product Pre-Code Recheck

**Date:** 2026-09-14
**Scope:** \`docs/deterministic_teaching_intelligence_scope.md\`
**Second data lock:** \`docs/deterministic_teaching_intelligence_second_data_lock_2026-09-14.md\`
**Status:** PASS — FOUR LOCKED FAMILIES ONLY

## 1. Literal player contract — PASS

The approved scope contains literal player-facing examples for the coach-picked game, connected game story, position-relative question, short answer, line replay, opponent chance, queen-exchange decision, good play, exact endgame and honest learning state. Product code must realize those interactions through the existing Game Review journey. A schema, internal fact or stored caption is not a substitute for that experience.

## 2. Teaching begins with an idea — PASS

The approved examples lead with ideas such as “Attack two pieces at once” and “The exchange you should pause over.” SAN and engine lines remain evidence inside the explanation and replay. They may not become the headline or the lesson by themselves.

## 3. Scope and thresholds come from frozen data — PASS

The selected first bundle is exactly:

1. \`forced_mate_story\`;
2. \`multi_move_material_accounting\`;
3. \`queen_safety_or_greedy_capture\`;
4. \`unpunished_opponent_opportunity\`.

The bundle was selected from the frozen 100-game development comparison: 73 uncovered opportunities in 61 games across 30 of 34 players, with 72 confirmed high-consequence opportunities. No new family or threshold is inferred during implementation.

Each family remains Shadow until its own packet contains at least 50 independently reviewed visible claims, at least 95% semantic precision, a Wilson 95% lower bound of at least 85%, and zero critical false chess claims. One family may not borrow another family’s authorization.

## 4. Canonical ownership — PASS

The implementation extends the existing owners only:

- \`caption_facts.py\` owns typed, legally replayed chess causes;
- \`stored_line_verifier.py\` owns line legality and settled payoff;
- \`caption_pipeline.MoveTeachingDecision\` owns the complete move decision and candidate contrast;
- \`game_review_event_adapter.py\` owns authorized event projection;
- \`game_review_planner.py\` owns selection and the inherited three-moment cap;
- \`whole_game_review_composer.py\` owns connected presentation without redetecting chess;
- \`detector_quality.py\` owns surface authorization.

No new general fact table, classifier, caption bank, principle bank, phase detector, concept taxonomy or review ranker is authorized.

## 5. Shadow/visible last wire — PASS WITH REQUIRED DESIGN

The current broad \`review:verified_single_game_cause\` authorization predates these four semantic families. A newly generated family must never inherit that authorization merely because its low-level cause uses the same legal replay machinery.

Therefore implementation must:

- give each selected family its own detector-quality identity, initially Shadow;
- derive that identity once at the canonical decision boundary;
- store measurable Shadow candidate output separately from player-visible output;
- project only a comparison whose own quality identity is Caption-authorized;
- fail closed when family identity, actor, proof version or evidence fingerprint is absent or inconsistent;
- test that legacy, disabled, unenrolled and Shadow paths cannot leak candidate text.

This separation is a release invariant, not an operator procedure.

## 6. Proof and voice — PASS

Every rendered clause must come from strict typed slots that an independent verifier can replay:

- mate reaches a legal terminal mate;
- material is counted from one root side through the settled boundary;
- queen advice names the position-specific consequence and never teaches “avoid queen trades” as a universal rule;
- an opponent chance starts before the opponent’s choice and is worded counterfactually.

Copy targets the 600–1500 player: short first, concrete pieces and squares, no centipawn language, no unsupported intention or mental-state claim, and one transferable memory cue. Deeper evidence belongs behind replay, comparison or hint controls.

## 7. Success and deferred work — PASS

Implementation success is increased independently verified causal teaching coverage against the current rendered review, not more stored captions. Practice or recognition does not prove later-game transfer.

The other fifteen frozen opportunity families remain deferred. The sealed holdout stays unopened until development logic and decisions are frozen. This work does not authorize regeneration, migration, production flags, rollout, push or deployment.

## 8. Approval — PASS

Mohit approved the second data lock and implementation with “okay, go ahead for more opportunities” on 2026-09-14. Product implementation may now begin within this document’s boundaries.
