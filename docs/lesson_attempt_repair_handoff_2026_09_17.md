# Personalized lesson attempt repair — 2026-09-17

## Status and scope

Local implementation on `codex/lesson-attempt-repair-v1`, based on
`09e235bc`. No push, deployment, flag change, production migration or user
data mutation. This repairs existing lesson paths; it does not add a new
teaching engine or promote a detector.

## Findings and repairs

1. The workspace immediately replaced `current_item` after grading, even on
   the final question. It now retains the attempted board, verdict and
   explanation until Next position / Try again / Finish lesson. Continue is
   a local presentation action, not another attempt submission.
2. A successful move gets a checkmark when there is no unverified or serious
   soundness caveat. Move feedback and reasoning feedback remain separately
   visible, so correcting a reason does not erase the explanation of the move.
3. Next-item responses used the plain formatter, dropping account-gated
   position-relative question settings. They now use the same public projection
   as session start/resume.
4. Concept sessions without available exact questions no longer require a
   generic attitude quiz. They submit the move for grading directly. Missing
   reason evidence cannot earn an independent-understanding state.
5. Serialized older concept items now consume the existing `lesson_question_spec`
   acceptance contract for new attempts. Piece safety uses the already-present
   any-safe rule rather than its frozen single-best puzzle rule. Historical
   evidence remains unchanged. Other categories retain their existing grading.
6. A landing-square pass with a verified serious other problem does not advance
   ordinary practice. Blind diagnostics still expose the two judgments separately.
7. The async puzzle evaluator ran blocking engine code, defeating its caller's
   timeout, and searched the starting position twice. Engine work now runs off
   the event loop. A scored root PV provides move and evaluation together;
   another move receives one restricted search from the same root. The best
   move needs no second search. Incomplete/bounded results fail closed. Existing
   quality thresholds are unchanged; stored best-move text cannot override
   fresh evidence. Best-move UCI is now returned alongside SAN.
8. Timeout feedback no longer asserts that an unmeasured move has another
   chess problem. A transient reason-submission error keeps the staged move.

## Explicit limits

- Exact reasoning remains gated by `CANDIDATE_LESSON_REASONS_ENABLED`, account
  eligibility, the current detector version and Plan authorization. None was
  relaxed. Verify these for the intended account before promising exact questions.
- This does not make every tactical/opening/endgame move acceptable. Those
  families retain their own proof and authored-move contracts.
- No production timing measurement was made. A cold local synthetic opening
  call took 6423ms; the next took 1307ms while a frontend build was running.
  These are smoke measurements, not an SLA or a before/after benchmark.
- An async timeout can return without blocking the server; it does not cancel
  an already-running synchronous engine search. Engine startup/search resource
  lifecycle under sustained concurrency remains a load-test requirement.
- Feedback persistence is within the current page. Refreshing follows the
  server's already-persisted session position; this change adds no durable
  feedback-acknowledgment workflow.

## Verification

- Focused backend: **52 passed**, covering adapter, teaching engine, lesson
  contracts, routes, search counts, incomplete results, stale best-move labels,
  event-loop responsiveness, resumed acceptance rules, and next-item questions.
- Full frontend: **68 suites / 318 tests passed**. Added delayed-response board
  retention and explicit next-position behavior; final-feedback and retry
  expectations updated. Tests use mocked API responses, not production sessions.
- Real local Stockfish on standard opening positions only: `d4` accepted as
  excellent while `e4` was preferred (20cp); Black's `e5` accepted as best.
  No stored/user game was reanalysed.
- Required `tests/test_all_flows.py`: **blocked**, HTTP connection failed before
  the first assertion. No authenticated live E2E claim.
- Strict CI build: **failed** on existing `GameDecryptionV5.jsx:430`
  `react-hooks/exhaustive-deps` warning for `applyCaptionArrows`. That file is
  unchanged from the baseline. Do not report a strict build pass.
- Normal production build (`CI=false`): **exit 0**, with the existing lint
  warning retained. This is not a strict-CI pass.

## Before deployment / acceptance

Claude retains push/deploy ownership. Integrate scoped commits/hunks onto the
current production lineage; do not copy entire shared backend files over newer work.

On an isolated test account, record request timing and payloads for move staging
and reason submission separately. Verify an acceptable alternative, an unsafe
move, a safe destination with another serious problem, an unavailable engine,
a correct move with a wrong reason, the second puzzle, and the final puzzle.
The board must remain on the attempt and its feedback until clicked forward.
Check the response's actual question/proof eligibility; flag-off should skip a
generic quiz, not silently present it. Do not count skipped questions as mastery.

No production writes, flag changes or live testing have been performed here.
