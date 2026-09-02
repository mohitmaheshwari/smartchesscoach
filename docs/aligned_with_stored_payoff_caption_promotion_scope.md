# Aligned With Stored Payoff Caption Promotion — Scope

## 0. Existing surfaces audit

- `shape_detectors.py` and `_aligned_pieces_evidence()` already provide the canonical before/after pin and skewer proposals.
- `aligned_tactic_puzzle_proof.py` already owns independent two-blocker ray reconstruction and stored-line payoff verification.
- `verified_puzzle_builder.py` is the shared admission path for both stored puzzle pools.
- `verified_puzzle_feedback.py` already owns the deterministic player-facing pin/skewer explanation.
- `detector_quality.py` is the only authority that can permit the exact caption.
- The Caption-only admission boundary already separates post-answer explanation from Prompt/Plan-grade drill identity.
- `shape:pin` and `shape:skewer` are separate research detectors. They are not the proof-backed quality family being promoted here and remain Shadow.
- There is no canonical pin/skewer learner skill, reviewed opportunity denominator, or mastery contract in `skill_tree.json`.

The overlap is complete at the detector, proof, admission, and rendering layers. The genuine new value is independent promotion evidence, correct separation of pin versus skewer language, and correct narration of direct versus discovered alignments.

**Overlap decision: EXTEND.** Do not create another recognizer, renderer, quality ID, skill, puzzle grader, or progress model.

## 1. What it is

This promotion lets ChessGuru explain one narrow line tactic after a puzzle attempt. For a pin, it shows that one opponent piece is shielding a more valuable piece behind it. For a skewer, it shows that the more valuable front piece moves in the stored line and leaves the rear piece available. The coach describes the exact pieces and squares in plain language. It does not call this a recurring personal weakness or claim the player has learned it.

## 2. What the user sees

Direct pin:

```text
Not this time. Compare your move with Bb5.

Bb5 puts your bishop on b5, lining it up with the rook on c6 and the queen on d7. If the rook moves, the queen on d7 is exposed behind it.
When one piece shields something more valuable, look for a rook, bishop or queen move that attacks them along the same line.
```

Direct skewer:

```text
Not this time. Compare your move with Bb5.

Bb5 puts your bishop on b5, lining it up with the queen on c6 and the rook on d7. When the queen moves off that line, the rook on d7 is left available to your bishop.
When a valuable piece stands in front of another piece, look along the same line to see what becomes available after the front piece moves.
```

If the best move uncovers an existing attacker rather than moving that attacker, the first sentence says, for example, `Nf6 clears a line for your rook on d1` instead of claiming that Nf6 put the rook there.

The move, creation mode, attacker, front piece, rear piece, and all squares come from independently verified board facts. The explanation teaches the geometry without requiring the player to know the words “pin” or “skewer.”

## 3. In scope (V1)

- Reproduce the stored `tactic:aligned_with_stored_payoff` population across both puzzle pools without rerunning Stockfish.
- Independently distinguish pin from skewer by piece ordering and exact values on a legal ray.
- Independently distinguish direct from discovered creation based on whether the best move lands on the attacking piece's square or clears its line.
- Independently replay the complete stored continuation and verify the exact front/rear payoff contract.
- Version a privacy-safe packet with 25 distinct-source pins, 25 distinct-source skewers, and 50 stratified negative controls.
- Include both pools, bishop/rook/queen attackers, and direct/discovered creation in the positive packet.
- Recheck every currently stored aligned candidate as a full-population safety gate.
- Promote only `tactic:aligned_with_stored_payoff` from Shadow to Caption if every combined and subtype gate passes.
- Extend the existing centralized renderer with exact piece names, squares, creation mode, and separate pin/skewer teaching language.
- Keep Prompt, Plan, Mastery, focus selection, and recovery identity unchanged.

## 4. Explicitly out of scope (V1)

- Promoting the separate `shape:pin` or `shape:skewer` research detectors.
- Prompt, Plan, or Mastery authorization.
- Adding pin/skewer nodes or aliases to `skill_tree.json` or persistent learner state.
- Claiming every legal defence loses material or that the tactic is forced.
- Claiming the line tactic caused the player's mistake, is recurring, or has been learned.
- Alignments without a complete stored payoff, equal-value alignments, or quiet pressure without a captured target.
- New puzzle UI, accepted answers, runtime engine/model calls, or a parallel caption path.
- Admission backfill, production writes, feature flags, pushing, or deployment.

## 5. Success criteria

- Every stored candidate and selected fire independently satisfies the locked geometry, semantic label, consequence, and payoff contract.
- Pin and skewer each separately clear the existing Caption precision and Wilson-bound bars; neither may borrow confidence from the other.
- Every control remains silent across all ten measured failure modes.
- Every rendered positive names the move, creation mode, attacker, front/rear pieces and their squares, then ends with the correct reusable line-search habit.
- Prompt, Plan, Mastery, skill identity, and exact-concept recovery remain absent.
- Product learning success is not declared by this release. A later prospective transfer study must show improved unassisted recognition on unseen aligned positions before ChessGuru says the player improved at pins or skewers.

## 6. Open questions

- **Question:** Can pins and skewers become persistent learner skills?
  - **Why unresolved:** no canonical skill nodes, opportunity/recall packet, or real-game transfer evidence exists.
  - **Unblocking step:** define one opportunity contract per semantic family and meet Plan/Mastery recall and prospective-transfer bars.
- **Question:** When may the coach say the tactic “wins a piece” or is forced?
  - **Why unresolved:** one stored principal variation proves one legal payoff line, not every meaningful defence.
  - **Unblocking step:** validate an all-defence or stored multi-candidate proof whose wording matches that stronger claim.
- **Question:** Should the words “pin” and “skewer” appear in the caption?
  - **Why unresolved:** the geometry is teachable without jargon, and no comprehension comparison exists.
  - **Unblocking step:** keep V1 geometry-first; test optional concept naming later without changing proof authority.

## 7. Pre-code requirements

- The existing-surface audit is locked as EXTEND.
- The full read-only census provides enough distinct pin, skewer, direct, discovered, pool, and attacker-type cases.
- The balanced 25/25 positive packet and ten negative strata are locked from measured supply.
- Independent gold does not import the canonical detector, proof, ray helper, stored-line replay helper, or stored verdict.
- Literal pin, skewer, and discovered-creation wording is fixed before runtime edits.
- The Complete Coaching Phase 3 order is already approved, and Mohit's “go ahead” explicitly starts this third selected family.
