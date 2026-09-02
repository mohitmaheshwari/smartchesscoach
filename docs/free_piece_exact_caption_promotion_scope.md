# Free-Piece Exact Caption Promotion — Scope

**Status:** LOCKED — covered by Mohit's approved Complete Coaching System scope and explicit “go” for Phase 3 on 2026-09-02

## 0. Existing surfaces audit

The requested capability already exists in pieces:

- `free_piece_puzzle_proof.py` proposes the exact stored-best capture using the canonical shape detector.
- Its independent verifier rebuilds the post-capture board and rejects every legal immediate recapture.
- `verified_puzzle_builder.py` is the shared admission path for both puzzle pools.
- `verified_puzzle_feedback.py` already owns the deterministic player-facing explanation.
- `detector_quality.py` is the only authority that can permit the specific caption.
- Phase 2's puzzle-attempt v2 path already records the player's answer without trusting the browser.

Today the proof is Shadow, so an otherwise verified free-piece position is deliberately reduced to a broad puzzle. There is no canonical free-piece learner skill or opportunity contract in `skill_tree.json`, so it cannot honestly become a plan or mastery claim.

**Overlap decision: EXTEND.** Build the missing promotion evidence around the existing proof, renderer and quality authority. Do not create another detector, caption path, content entry, skill identity, puzzle grader or progress calculation.

## 1. What it is

This promotion lets ChessGuru explain one narrow, objective tactical fact: the stored best move captures an opponent knight, bishop, rook or queen, and the opponent has no legal move that immediately captures back on that square. It teaches the player to scan legal captures before beginning a quieter plan. It does not claim that free-piece recognition is the player's main weakness or that the skill has been learned.

## 2. What the user sees

There is no new page or component. On an admitted puzzle, the existing centralized feedback can become specific:

```text
Not this time. Compare your move with Nxd5.

Nxd5 takes the knight on d5, and the opponent has no legal recapture.
Before choosing a plan, scan every legal capture and count the recaptures.
```

The move, piece and square come from verified board facts. If those facts are absent or conflict, the specific explanation remains unavailable.

## 3. In scope

- Reproduce the current candidate population across both admitted puzzle pools without rerunning Stockfish.
- Build an independent semantic verifier that does not call the canonical free-piece detector or reuse its result.
- Version a privacy-safe Caption promotion packet with 50 distinct-source fires and 20 near-negative/adversarial controls.
- Include both puzzle pools and every claimed target type: knight, bishop, rook and queen.
- Verify all currently stored candidates as a full-corpus safety check in addition to the promotion sample.
- Promote only `tactic:free_piece_exact` from Shadow to Caption if every locked gate passes.
- Keep the existing centralized deterministic feedback and add only guard tests required by the promotion.

## 4. Explicitly out of scope

- Plan, Prompt or Mastery authorization.
- Adding a free-piece node to `skill_tree.json` or calling it a persistent personal weakness.
- A recall claim, recurrence rule, lesson-completion rule or improvement verdict.
- Pawns, favorable exchanges, multi-move combinations, trapped capturing pieces or a general claim that material remains won beyond the immediate legal reply.
- New caption prose, a parallel renderer, runtime LLM use or fresh Stockfish analysis.
- Backfilling stored admissions, changing production data, enabling flags, pushing or deploying.
- Fork, pin/skewer, forced-mate or later Phase 3 families.

## 5. Success criteria

- Every selected fire and every current stored candidate satisfies the exact player-facing claim under independent legal replay.
- All 20 near-negative controls correctly abstain, including the historical x-ray-recapture failure mode.
- The versioned packet meets the existing Caption precision, Wilson-bound, sample and zero-critical-error gates.
- The centralized explanation names the move, captured piece and square and ends with a reusable action.
- When a later rollout is authorized, Phase 2 records first-answer behavior so future work can measure whether players begin spotting the same clue unassisted. No behavior-change claim is made in this phase.

## 6. Open questions

- **Question:** Can free-piece recognition become a persistent focus?
  - **Why unresolved:** there is no canonical learner skill, independently sampled opportunity denominator, recall packet or teaching-to-transfer evidence.
  - **Unblocking step:** a later family-specific Plan/Mastery scope must add those pieces and earn the stronger authorization independently.

- **Question:** When may the coach say the player “wins material” rather than “there is no immediate recapture”?
  - **Why unresolved:** the present proof certifies the immediate reply, not every later tactical consequence.
  - **Unblocking step:** define and validate a stored-line or exact-exchange proof whose visible claim matches that stronger wording.

## 7. Pre-code requirements

- The Complete Coaching System scope and Phase 3 implementation order are approved.
- The Phase 0 bake-off selects `tactic:free_piece_exact` first.
- The live read-only census confirms enough distinct positive sources and near-negative controls.
- Caption promotion thresholds are inherited unchanged from the detector-quality threshold lock.
- The semantic claim is narrower than the available proof and has literal player-facing copy.
- The implementation extends the canonical proof/admission/feedback/authorization owners only.
- No runtime edit begins until the accompanying data lock and pre-code audit pass.
