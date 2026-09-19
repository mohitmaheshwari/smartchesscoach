# First Coaching Session — Pre-code Audit

2026-09-18; base `8c6685c1`.

Scope approved in conversation. Product mockups exist in `first_coaching_session_onboarding_scope.md` in the parent workspace; companion implementation spec is in this worktree. Worktree isolation preserves existing user changes.

## Existing-flow repair

This is a bug-fix slice: stop automatic disappearance of feedback, honor intermediate and legacy verdict contracts, preserve board context and prevent duplicate local submissions. Existing grader, thresholds, storage and authorizations remain unchanged. It does not add a teaching family or claim onboarding completion.

- Literal UI contract: approved scope's persistent feedback and explicit continue.
- Pattern-led copy: no SAN-led diagnosis added; feedback acknowledges a move, not inferred mastery.
- Numeric decisions: none added; two-second auto-advance removed rather than replaced with another duration.
- Behavioral check: learner can read feedback and deliberately proceed; intermediate success cannot look like failure.
- Deferred scope: no PWC/new detectors/LLM/engine runs/promotion introduced.
- Authorization: user's explicit implementation approval in current turn.

Proceed with these confirmed bug repairs and their regression tests.

## New first-session feature: BLOCKED pending evidence

2026-09-19 approved clarification: discovery through adaptive puzzles precedes teaching. No fixed lesson is assigned to all players. Existing adaptive thresholds remain unchanged. The next existing-flow repair is recoverable feedback: store the answered board and response with the attempt transition in the same session document; use compare-and-set and explicit acknowledgement so reloads, lost responses and duplicate submissions cannot skip feedback or double-count an answer. This persistence repair does not certify any new teaching content. The literal feedback screen and deliberate continuation are already approved. No chess authority, new scoring threshold or production migration is introduced.

The full scope's content-readiness, reviewed example encounter, data-lock and durable session-contract gates are not yet satisfied. A frozen grade map is not an explanation or a transfer pairing. The current pool builder discards candidate PVs after deriving scores; stored solution moves alone cannot explain every alternative causally. Do not treat a corrected diagnostic screen as the completed first lesson, change its label to promise one, or enable new exposure.

Single-source-of-truth audit: reuse `DiagnosticGrader` for frozen move acceptance, the central caption/fact path for causal claims, existing learning ledger for assistance provenance and diagnostic memory fallback for provisional focus. No parallel theme-to-explanation table or separate notion of mastery.

Next evidence task is content inventory and a complete example encounter review, alongside a read-only timeline of the reported onboarding delay. Production access and those results have not been claimed. No new thresholds are locked; `lock-via-data` remains required when choosing them.

## 2026-09-19: evidence preparation completed locally

Added a read-only diagnostic-pool audit, not a player-facing feature or a new fact source. It uses `frozen_diagnostic_grades_are_current`, `DiagnosticGrader`, `caption_pipeline.build_reason_bundle_for_move`, and the existing authorization registry. It validates the stored line and solver-step binding, counts missing legal-move grades, distinguishes duplicate positions, and reports narrow piece-safety proof availability separately from whole-move verdicts. No teaching family, selection threshold, mastery rule or production write is added.

`first_coaching_session_teaching_example.md` describes one existing adjudicated local position through question, reveal and replay. The test verifies all choice outcomes, private/public boundaries, restore, and legal capture/recapture. It explicitly does NOT establish a production pool row or a changed-position pairing. The four-question bundle is not prescribed wholesale: earlier questions can reveal later answers.

This satisfies preparation for the content review, not the outstanding full-feature gates. Live pool coverage, independently reviewed pairing, non-admin browser experience and real-Mongo persistence remain open. The skill therefore still blocks enabling the new teaching experience. User approval is not being substituted for missing chess evidence.
