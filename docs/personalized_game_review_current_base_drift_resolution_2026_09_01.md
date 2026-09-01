# Personalized Game Review — current-base drift resolution

Date: 2026-09-01

## Outcome

The Phase 0–6 implementation has been adapted to the current
`origin/working-code` architecture without weakening detector authorization.

The failing baseline on Claude's integration worktree was **33 failed / 138
passed** across the available review boundary. After the changes below, the
same boundary plus the restored Stage 4 caption contract is **175 passed**.

The Phase 6 validation panel and its test had also been omitted during the
hunk-level integration. They are restored, the three affected frontend suites
are **14 passed**, and the current-base production frontend build completes.

## LessonResult v2

`LessonResult.content_version` is required evidence identity, not a schema
label. The canonical PIC identity now owns `PIC_CONTENT_VERSION = "1"` beside:

- `PIC_CONTENT_ID = "piece_safety.simple_hang"`;
- `PIC_CANONICAL_SOURCE = "personal_curriculum.piece_safety.v1"`.

Review reflection, guided practice, and organic-game observation adapters use
that shared version. Organic observations explicitly carry
`EvidenceSourceType.ORGANIC_GAME`.

`LessonResult.from_event_dict` now rehydrates the complete v2 event rather
than dropping content version, skill identity, assistance, reasoning,
provenance, source type, detector version, clock context, and grader fields.

## Detector authorization lock

DECISION LOCKED: `gap:piece_safety:simple_hang` remains Caption-grade.

EVIDENCE:

- reviewed semantic precision: **96.9% over 260 fires**;
- D_live miss recall: **16.09%**;
- Plan-grade recall floor: **at least 60%**.

REJECTED: promoting or special-casing `simple_hang` as Plan-grade. That would
undo the evidence-backed authorization registered in
`services/detector_quality.py`.

## Allowed behavior

A current-schema, final-verified `simple_hang` may:

- explain the observed move;
- enter a single-game turning-point chapter;
- ask one event-scoped reflection.

It may not:

- claim that the weakness recurs across games;
- prescribe a next lesson or training action;
- award `used_in_games` or any mastery state.

The generic planner still supports future Plan-grade evidence. Its positive
recurrence/prescription test uses an explicit test-only Plan authorization,
never a production detector.

## Verification

- Corrected architecture boundary: **149 passed**.
- Complete available Phase backend boundary plus restored caption contract:
  **175 passed**.
- Phase 6 validation UI, personalized review coach, and analytics suites:
  **14 passed**.
- Current-base production frontend build: **passed**.
- Changed production modules compile successfully.
- Detector quality thresholds and the production authorization registry were
  not modified.

The integration worktree still has unresolved Git index entries owned by
Claude's hunk-level merge. These source fixes must be preserved when those
conflicts are marked resolved.
