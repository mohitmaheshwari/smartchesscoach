# Onboarding: one concrete teaching encounter, not a generic lesson

2026-09-19. Local content review example only. No player route or enrollment added.

## Evidence and limits

Source: existing test-only adjudicated `backend/data/detector_gold/home_teaching_case_v2_v1.json`, case `approved_rook_recapture_connection`. This is NOT a record from the production diagnostic pool and must not be inserted into it as a fabricated starter puzzle.

Canonical provider: `caption_pipeline.build_reason_bundle_for_move` -> `destination_safety_detector.build_destination_safety_reason_bundle`. Detector `piece_safety.destination_safety_exact.v2`, verifier `legal_exchange_verifier.v1`; proof fingerprint `190c6de32fa2d3a6521d1d72bc8344a93f50935da2ef88ad27d12e09e703ea4d`.

Starting board: `3r1rk1/p2p1ppp/2p1p3/8/N3P3/1P1RPP2/P1q4P/3R2K1 w - - 0 1`.

White has rooks on d1 and d3. Black's queen on c2 attacks both. The candidate move is the rook from d3 to d2. Existing proof establishes that the destination capture can be answered; it does NOT establish this is Stockfish's best move, that the whole position is safe, or that a player understands rook coordination. No new engine evaluation was performed.

## What the learner should experience

### 1. Try before teaching

Board without attack arrows or explanatory caption:

> What would you play here?

The player makes a move. Acceptability must come from that move's current stored grade, including valid alternatives. The example below follows d3-d2; its local geometry proof alone cannot supply the missing global move grade.

### 2. One useful question, not four leading questions

Keep the played board. Select the existing `one_recapture_calculation` component:

> If Black plays Qxd2, what happens next?

Existing answers: “I answer Rxd2.” / “I cannot recapture on d2.” / “I saw the capture, but I did not calculate my reply.” Answer order is seeded by the existing provider, not hard-coded by this page.

Do NOT first say the rook is protected, show its defender arrow, or ask the destination-safety question: that would teach the answer before this check. The final option is a self-report; do not treat it as proof of the player's prior thought process. A reply here measures performance on this prompted question, not unaided game behavior.

### 3. Reveal what the board proves

Hold the board and feedback until the player continues. Use the canonical explanation, not a theme-based paragraph:

> After Qxd2, Rxd2 answers the capture.

Show the two-move reply on request. The animation must start from the played board (rook already on d2), demonstrate c2-d2 and d1-d2, then allow replay. It is a hypothetical capture, not a claim that Black must take the rook.

Only after the answer, show the existing supporting relationships: queen on c2 attacked d1 and d3; the rook on d2 also attacks that queen. A proposed concise connective sentence for content review is: “Your other rook can take back on d2. Before moving away from a threat, see whether your pieces can protect each other.” This is mockup copy, not a new runtime template or separately approved caption.

### 4. What happens next

Correct move + supported reply: record those two narrow observations; do not assign a remedial lesson solely because this position was tagged piece safety. Wrong/unsure reply: explain and replay; a successful repeat is now assisted practice, not a fresh independent solve.

A changed-position check must come from an independently reviewed pairing with the same board mechanism and a current frozen move map. It cannot be selected by shared category alone. No such pairing has been established by this example. Until it is, continue the existing discovery puzzles without announcing mastery, improvement, or a completed first lesson.

## Interaction suppliers and remaining implementation

| Interaction | Existing supplier | What remains |
|---|---|---|
| Legal move + accepted alternatives | `DiagnosticPuzzles.jsx`, `DiagnosticGrader` | Real-pool content inventory; no new grading rule |
| Durable move feedback | Diagnostic `explicit_v1` receipt repair | Real Mongo and non-admin browser verification |
| Position-specific question + answer binding | `TeachingReasonBundle.question/grade_component` | Onboarding session state, account gate, assistance provenance |
| Actual explanation | Central reason component success/correction text | Independent teaching review and non-leading selection |
| Demonstration/replay | Canonical capture/recapture facts | Onboarding renderer controls, legal replay and resume tests |
| Changed-position check | No qualifying pairing established | Content review before implementation/enrollment |

The reason contract and legal demonstration are tested locally in `test_diagnostic_teaching_readiness.py`. This is not a browser demo, an end-to-end product pass, or proof of production pool coverage. In particular, four serialized questions working does not make asking all four good pedagogy.
