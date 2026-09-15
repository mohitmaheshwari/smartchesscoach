# Community Game Coherent Walkthrough — Pre-code Audit

**Status:** PASS
**Date:** 2026-09-15
**Scope decision:** EXTEND EXISTING
**Approval:** Mohit explicitly approved the corrected scope and extension.

## Gate 1 — Schema and interaction before JSX: PASS

The approved scope contains the literal player experience and the data lock names the required interactive fields before implementation: question, position-relevant choices, bounded hint, legal demonstration and replay target. Empty authored content makes a chapter ineligible; the client cannot fill it with generic text.

Ownership is explicit:

- new `frontend/src/components/review/GuidedReviewMoment.jsx`: predict, hint and reveal state;
- existing `frontend/src/components/GameDecryptionV5.jsx`: canonical board, watch-line animation and learner replay;
- existing `frontend/src/pages/LabV2.jsx`: fetches and persists the active prescription/study state;
- prototype `InteractiveMoment.jsx`: unchanged and not mounted into the canonical path.

## Gate 2 — Move-led narrative: PASS

The v2 regression is forbidden. Every headline begins with a pattern, geometry or human chess idea. SAN is supporting evidence only. The acceptance gate is 100%, so a single move-led headline blocks visibility.

## Gate 3 — Numeric choices locked from data: PASS

The frozen 60-game measurement selected a variable two-to-three-chapter budget and `coherent_role_then_quality.v1`. Cap four and cap five add no coverage while nearly doubling or tripling repetition. The visible admission floor is two distinct authorized principles/families. No fitted severity weight or guessed game-length cutoff is introduced.

## Gate 4 — Behavior-changing metric instrumented: PASS WITH ROLLOUT BLOCK

The primary behavior chain is start → predict → watch → replay → complete → linked next action. It will be recorded server-side. The current production history is too small to set a defensible percentage, so the three-admin cohort is operability validation only. Ordinary-user expansion remains mechanically blocked until a post-instrumentation baseline and threshold are separately frozen. This is not a vanity-metric substitution.

## Gate 5 — Deferred work remains deferred: PASS

No runtime model call, Stockfish rerun, Maia inference, new knowledge registry, opening-name promotion, named-endgame inference, human matchmaking, community reputation or transfer claim enters this phase. Terminal checkmate requires its own exact Caption promotion; it is not smuggled through another quality ID.

## Gate 6 — Existing authorities and exact files: PASS

Backend extensions:

- `backend/services/caption_facts.py`: typed, board-exact terminal fact and family-specific teaching slots; no copied knowledge table.
- `backend/services/caption_pipeline.py`: central authored interactive projection for admitted facts.
- `backend/services/game_review_shadow_runtime.py`: adapt authorized proof families into the existing `TeachableEvent` contract.
- `backend/services/game_review_planner.py`: add `coherent_role_then_quality.v1`, two-to-three budget and role/principle deduplication.
- `backend/services/community_game_study_service.py`: extend the neutral schema and fail-closed projection; it remains the community-source authority.
- `backend/services/coach_selected_review_service.py`: extend the existing recommendation lifecycle to a licensed anonymous community source, while preserving personal fallback.
- `backend/routes/training_advanced.py`: extend existing review lifecycle endpoints with chapter actions; no second route family.
- `backend/services/review_learning_adapter.py` and `backend/services/learning_evidence_ledger.py`: record assisted study without changing transfer.
- `backend/scripts/build_community_game_study_review_packet.py`: produce the v3 blinded review packet.

Frontend extensions:

- new `frontend/src/components/review/GuidedReviewMoment.jsx`;
- existing `frontend/src/components/GameDecryptionV5.jsx`;
- existing `frontend/src/pages/LabV2.jsx`;
- existing `frontend/src/pages/AllGames.jsx`;
- existing `frontend/src/lib/analytics.js`, only if the same events also need client diagnostics; server records remain authoritative.

Tests required before visibility:

- planner formula, cap, chronological order and no-repeat tests;
- community admission, source anonymity and Shadow/Disabled exclusion tests;
- exact terminal-fact and promotion-packet adversarial tests;
- interaction schema, legal demonstration and empty-content fail-closed tests;
- personal fallback byte-equivalence tests with flags off;
- chapter lifecycle idempotency and server event tests;
- learning-ledger tests proving assisted completion cannot alter transfer;
- `GuidedReviewMoment` predict/hint/reveal tests;
- canonical-board watch and learner-replay tests;
- Game Review selection/resume/fallback tests;
- the mandatory core backend suite and relevant frontend production build.

## Forecasted bottleneck

The bottleneck is not detector incidence. Forty of sixty sampled games already have at least two distinct candidate principles. The load-bearing blockers are terminal-checkmate Caption promotion, authored interaction completeness and player-path reach. Implementation must solve and test those wires before broadening any chess family.

## Stop conditions

Stop and return to Shadow on any incorrect claim, illegal replay, unauthorized family, identity leak, incomplete interaction, changed personal fallback with flags off, assisted-to-transfer mutation or missing server event. A clean test suite without a real isolated-account journey is insufficient for visibility.
