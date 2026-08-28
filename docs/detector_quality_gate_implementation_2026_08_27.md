# Detector Quality Gate — implementation report (2026-08-27)

Status: IMPLEMENTED, DEFAULT-OFF ROLLOUT

## Runtime result

- Canonical authority: `services/detector_quality.py`.
- Rollout flag: `DETECTOR_QUALITY_GATE_ENFORCED=false` by default.
- Unknown IDs are strictly Shadow when enforcement is enabled.
- Explicitly Disabled IDs are blocked even while rollout is off.
- One current Plan-grade ID: `gap:piece_safety:simple_hang`.
- Current strict inventory: 116 IDs — 1 Plan, 112 Shadow, 3 Disabled.
- Read-only report:
  `python backend/scripts/report_detector_quality.py`.

The default-off flag is deliberate. Turning strict enforcement on before the
caption and shape packets are promoted would silence most existing principle
and shape teaching. The implementation records grades now, quarantines known
unsafe claims, and makes strict rollout testable without an accidental global
coaching outage.

## Enforced chokepoints

- concept mastery grades: `concept_detectors/_runner.py`;
- Chess Brain tactical/strategic/behavioral results:
  `chess_brain/detector_registry.py`;
- caption shape selection: `shape_layer.py` and the post-move fallback in
  `caption_pipeline.py`;
- caption principles: `caption_pipeline.py`, with Shadow evidence retained
  under `detector_quality_shadow`;
- weakness and tactical-strength aggregation:
  `primary_weakness_picker._get_cohort_signals`;
- active focus reads, Lab preference, Daily Fix, focus game, prescribed
  training resolution and focus email selection;
- legacy coach-memory fallback is bypassed when strict enforcement is on.

New focus documents are stamped with `detector_quality_id` and
`detector_quality_grade`. Existing versioned PIC simple-hang focuses have a
compatibility mapping; unversioned legacy focuses fail closed in strict mode.

## Quarantined now

- `concept:endgame_rule_of_square`;
- `brain:trapped_piece_detector`;
- `brain:king_safety_detector`.

Rule-of-square no longer writes mastery outcomes. The old tests that expected
those writes were updated to assert quarantine; the direct detector's clean
positive example remains tested.

## Lichess evidence work

- Fixed the fork validator to replay all player plies in a solution.
- Added a non-fork-tag negative-control arm.
- Corrected positive coverage: 997/1,000 (99.7%).
- Untagged control fires: 304/1,000 (30.4%).

Fork is not promoted: positive coverage is excellent, but tag absence is not
valid negative truth and incidental check/mate geometry still needs blinded
semantic adjudication.

## Exchange-truth remediation

The first promotion candidates exposed two verifier blind spots rather than a
clean promotion:

- `shape:free_piece` passed the old 200/200 geometry audit, but a full-corpus
  post-capture replay found 7 x-ray recaptures among 1,849 stored fires. The
  detector and independent verifier now reject any advertised capture with a
  legal immediate recapture.
- `principle:TAC_HANGING_PIECE` also appeared 200/200 under a verifier that
  reused its static SEE. Independent legal replay found 3,571 concerning
  claims among 24,793 fires (14.4%). Hanging attribution now uses the exact
  board-mutating exchange evaluator selected in
  `docs/detector_exchange_truth_lock_2026_08_27.md`.
- V5 coaching version was bumped from 136 to 137 so stored pre-fix captions
  become stale and can lazily regenerate after deployment.

Neither ID was promoted. The corrected implementation still needs the blinded
fire and near-negative packets required for Caption-grade.

## Verification

- quality authority + Lichess validator: 14 passed;
- quality + existing concept/Chess Brain integration: 33 passed, 7 skipped;
- focus/PIC/instruction suites: 67 passed;
- compile check: all modified backend modules passed;
- whitespace check: passed;
- caption boundary suite: 146 passed, 6 unrelated existing assertions failed
  (forced-recapture and missing text-field expectations while rollout is off);
- mandated full E2E script: dependencies were restored in `.test-deps`, then
  the run stopped because no local backend is listening. It was not pointed at
  production because that suite contains state-changing flows.

## Rollout gate

Do not enable `DETECTOR_QUALITY_GATE_ENFORCED=true` globally yet. First:

1. promote enough Caption-grade principles/shapes to preserve teaching value;
2. run the full E2E suite against a local/staging backend;
3. run the authorization report and review every Plan/Caption promotion;
4. enable in staging, then an explicitly scoped cohort, then globally.
