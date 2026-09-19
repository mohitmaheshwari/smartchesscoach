# First Coaching Session — Implementation Specification

**Status:** approved product scope; implementation planning and existing-flow repairs in progress. New first-lesson exposure remains blocked.
**Version:** v1, 2026-09-18. Base: `8c6685c1`.
**Approved correction, 2026-09-19:** retain adaptive puzzles as discovery before assigning any lesson. A correct move does not establish understanding. Existing difficulty/consistency rules stay unchanged; no fixed lesson is assigned to everyone.
**Scope:** multi-stage extension, not a replacement grader. Scope approved by Mohit in the current conversation on 2026-09-18.

## 1. The problem

A reported new player waited almost an hour for useful content. That account's timeline has not been inspected; no engine/queue root cause is asserted. Code independently confirms that the connection path can send a player to a game before analysis finishes, and the diagnostic removes feedback after two seconds. Intermediate V2 successes have `step_verdict` but no final `verdict`, which the renderer incorrectly treats as a failed answer. Legacy replies use `is_correct`, also not understood by the current feedback renderer.

## 2. The shape — outcomes

- Move awaiting a response: hold the played board and prevent duplicate submission.
- Verified successful move: acknowledge the move, preserve feedback, deliberate continuation.
- Verified non-solution/partial move: preserve its actual feedback without pretending a concept diagnosis.
- Intermediate calculation step: acknowledge that step, then let the player continue with the stored opponent reply; do not count the puzzle completed yet.
- Request failed or response ambiguous: preserve context, do not claim the move is wrong or blindly resubmit an attempt that might already have saved.
- Full future first lesson: unaided decision -> explanation/demo -> assisted practice if needed -> changed-position check -> provisional next lesson. The latter requires reviewed teaching content, not just frozen move grades.

## 3. Schema / files touched

Existing-flow repair first: `frontend/src/pages/DiagnosticPuzzles.jsx` and behavior tests. Reuse existing API response shapes, route, board, grading and analytics constants. No new store, grading formula or account access decision in this repair.

Later integration boundaries: `ActivationHub.jsx`, `Onboarding.jsx`, diagnostic routes/service, existing caption proof path, `learning_evidence_ledger.py`, Home provisional-focus read. Future durable feedback requires server-owned pending feedback plus explicit acknowledgement and a session/revision token; account+session scoping, atomic advancement and idempotency must be designed and tested before that change. Browser-local storage is not an adequate substitute.

## 4. New facts / data the system needs

Current offline pool builder stores legal-move grades and the solution continuation. It does not store a verified causal explanation for each candidate or an independently reviewed changed-position pairing. Do not infer a fork/pin/transfer relationship merely from a theme, nor call a capture a net win. Audit the existing live pool read-only with operator cooperation; derive proposed teaching through canonical facts/captions, retaining provenance. No live engine fallback or fabricated starter dataset is authorized here.

## 5. Gating — preventing another silent feature

No new first-lesson label/CTA until the complete corresponding interaction exists. Future rollout flag proposal: `FIRST_COACHING_SESSION_ENABLED=false`, combined with explicit per-account enrollment on every route. Missing content is a measured delivery failure, not a fake lesson completion. Existing diagnostic repairs do not enable this new experience. Session continuity, atomic feedback persistence, authored teaching and changed-position suitability remain gates.

## 6. Test strategy

Repair: actual React rendering with mocked API boundaries; V2 exact/alternative/partial/missing replies, legacy correct/incorrect replies, intermediate calculation, final feedback, index progression, double events and network/HTTP failure. Time advancement must NOT dismiss feedback. Existing partial-exit tests must remain green.

New lesson: API integration with real session persistence, adversarial chess claims, stale/missing proof, account isolation, two tabs/retries, refresh during feedback, assisted vs unaided evidence, slow/empty/failed import and non-admin browser cold start. Existing backend all-flows suite is mandatory after backend changes. An API mock test is not evidence of a production round trip.

## 7. Risk + rollback

The first repair changed feedback presentation. The 2026-09-19 extension adds opt-in `explicit_v1` receipts in existing diagnostic session documents, atomic with attempt advancement, plus an authenticated acknowledgement route. No bulk migration is required. Preserve backend/frontend compatibility while unread receipts exist; do not silently remove them on rollback. Local tests cover resume and duplicate/stale submissions; Mongo-backed and real-browser validation remain required. This is not the complete teaching state machine.

New experience stays default-off pending all gates. If a pilot is rolled back, retain evidence, explain the interruption and offer the existing flow without swapping an active controller mid-step. False claims, hidden sound alternatives, cross-account leakage, contaminated independent evidence or broken resume stop exposure immediately. Never roll back evidence schemas by deleting attempts.

## 8. What this spec does NOT cover

New detectors, grading thresholds, rating models, PWC rebuild, fresh Stockfish analysis, production writes, pricing or guaranteed retention. No claim that the whole approved onboarding scope is delivered by the first repairs.

## 9. Implementation order

1. Repair known diagnostic interaction defects and run discriminating regressions; preserve existing routes and grading.
2. Obtain read-only content coverage and affected-user timeline evidence; review complete example encounters. Resolve numeric/session-limit decisions from data, not a guessed puzzle count.
3. Implement the server-owned first-session state and reviewed content integration behind the default-off account-scoped gate. Add import detachment only with a durable server job, never a fire-and-forget browser request.
4. Verify the complete local/non-admin journey, then hand off for independent review and operator deployment. No production exposure at this stage.
5. After explicit rollout approval: internal Mohit/Parth A/B for one week; approved 10% eligible cohort for one week; broader release only on measured acceptance. Delete legacy only after two clean weeks at full rollout and explicit approval. Those periods are process conventions, not statistical evidence of retention.

## 10. Decisions / open questions

Reuse existing diagnostic/board/grader: yes. Long assessment stays optional in the final product. No numerical acceptance threshold is being changed by the repair.

Still blocking the new teaching integration: which existing proof-backed content and changed-position pairs qualify; assistance/retry state; exact first cohort; measured latency and behavioral targets. Feedback/acknowledgement is implemented locally, not production-verified. Claude owns the independent import-delay trace; it does not block local interaction repairs. User authorized implementation, not bypassing the content gates. Claude retains push/production deployment responsibility. The next audit must name interaction suppliers and example chess evidence rather than mark these questions resolved by assumption.
