# Canonical Teaching History Bridge — Pre-code Audit (2026-09-05)

## Schema before mockup

The canonical schema already exists: `LessonResult v2` in
`services/personal_curriculum.py`, stored in `learning_sessions.events` and
validated by `services/concept_mastery_service.py`. No new store or public
mastery schema is introduced.

## Move-led narrative

The bridge changes only delivery memory. Board truth, expected moves, graders,
concept identity, and lesson content remain immutable inputs owned elsewhere.

## Instrument before validate

The reducer already exposes accepted/rejected event counts. This change adds
fact-only outcome, assistance, latest-event, and next-evidence fields so paired
histories can be compared without interpreting UI prose.

## Forecasted bottleneck

The forecasted bottleneck is alias and content-identity contamination: a raw
session lookup can accidentally mix old identifiers or unrelated content. The
test gate therefore requires canonical alias lookup plus exact content identity
validation before any history affects delivery.

## Deferred remains deferred

Public mastery, retention timing, detector Plan/Mastery promotion, focus
resolution, and legacy UI retirement remain deferred. No numeric decision is
being locked, so a separate threshold data lock is not applicable.

## Gate verdict

PASS. Extend `concept_mastery_service` and `personal_teaching_profile`; do not
create a parallel learner model or teaching path.
