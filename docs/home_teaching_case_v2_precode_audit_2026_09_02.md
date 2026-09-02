# Home Teaching Case V2 — Pre-code Audit

**Result:** PASS
**Scope:** `docs/home_teaching_case_v2_scope.md`
**Data lock:** `docs/home_teaching_case_v2_data_lock_2026_09_02.md`

1. **Literal UI mockup — PASS.** Section 2 contains literal Home, move-first, component-question, coach-response, transfer and later-visit states.
2. **Pattern/geometry headline — PASS.** The product leads with “hit back without hanging the piece”; move notation is supporting position evidence only.
3. **Data-derived decisions — PASS.** Existing Plan authorization, pair cadence and detector thresholds are reused. Reason completeness, alternatives and optional components were locked from a read-only 5,760-move replay. No new numeric rollout threshold was guessed.
4. **Behavior-changing success — PASS.** The flow measures controlled transfer, routes the missed component to an existing teaching action, and waits for an authorized real-game opportunity before claiming application.
5. **Deferred scope preserved — PASS.** No new detector families, learner profile, mastery store, community explanation system, Maia/Otter/Fathom runtime dependency, or all-user rollout enters V1.
6. **Explicit Mohit signoff — PASS.** Mohit approved the completed scope with “go ahead” on 2026-09-02.

## Single-source audit

- Destination truth and counterfactual grading remain in `destination_safety_detector.py`.
- Independent exchange verification remains in `legal_exchange_verifier.py`.
- The typed reason bundle extends the canonical per-move teaching decision contract; it is not a Home-only classifier.
- Personal Curriculum remains the decision/state owner.
- `learning_sessions`/`LessonResult` remain the evidence owner.
- `HomeReplayDiagnostic.jsx` remains a renderer of server-authored questions.
- The gold JSON is test-only adjudication evidence and is never a runtime content source.
- The existing `_reason_choices("concept")` + `_expected_reason` path is the duplicate being retired for blind diagnostic V2 only; ordinary lesson kinds remain backward compatible.

**PRE-CODE AUDIT: PASS. Proceeding to implementation in the clean `codex/home-teaching-case-v2` worktree.**
