# Fork With Stored Payoff Caption Promotion — Scope

**Status:** LOCKED — covered by the approved Complete Coaching System Phase 3 scope and Mohit's explicit “sure” to proceed with this named next family on 2026-09-02

## 0. Existing surfaces audit

The requested capability already exists in pieces:

- `fork_puzzle_proof.py` asks the canonical knight, bishop, rook and pawn shape detectors whether the stored best move creates a fork, then separately requires a complete legal stored line with material payoff on one original target.
- `verified_puzzle_builder.py` is the shared admission path for both stored puzzle pools.
- `verified_puzzle_feedback.py` already owns the deterministic player-facing fork explanation.
- `detector_quality.py` is the only authority that can permit the exact caption.
- The Caption-only admission field added by the first Phase 3 promotion already separates post-answer explanation from Prompt/Plan-grade drill identity.

There is no canonical fork learner skill, reviewed opportunity denominator or fork-specific mastery contract in `skill_tree.json`.

**Overlap decision: EXTEND.** Build promotion evidence around the existing proof, admission and renderer. Do not create another fork detector, caption engine, skill identity, puzzle grader or progress model.

## 1. What it is

This promotion lets ChessGuru explain one narrow tactical idea after a puzzle attempt: the stored best move places the moved knight, bishop, rook or pawn where it attacks at least two valuable opponent pieces at once, and the stored best line shows that the fork matters rather than being harmless geometry. It teaches the player to search for one move that attacks more than one piece. It does not call fork recognition a persistent personal weakness or claim the player has learned it.

## 2. What the user sees

There is no new page or component. The existing verified-puzzle feedback becomes specific only after the answer:

```text
Not this time. Compare your move with Nxc7+.

Nxc7+ puts your knight on c7, attacking the pieces on a8 and e8 at the same time.
Before choosing a move, scan every legal check and capture for one move that attacks more than one piece.
```

The move, forking piece, fork square and target squares come from independently verified board facts. The wording works for two or more targets and explains the geometry without requiring the player to know the word “fork.”

## 3. In scope

- Reproduce the stored `tactic:fork_with_stored_payoff` population across both puzzle pools without rerunning Stockfish.
- Build promotion gold that independently reconstructs the post-move attack map and legally replays the stored continuation without importing the canonical fork detectors, fork proof or stored-line replay helper.
- Version a privacy-safe packet with 50 distinct-source fires and 25 stratified near-negative/adversarial controls.
- Include both puzzle pools, knight/bishop/rook/pawn fork creators, and both observed two-target and three-target positions.
- Recheck all currently stored fork candidates as a full-population safety gate.
- Promote only `tactic:fork_with_stored_payoff` from Shadow to Caption if every gate passes.
- Improve the existing centralized fork wording so it remains true for two or more targets and teaches the idea in plain language.
- Reuse the existing Caption-only admission boundary; keep Prompt, Plan and Mastery unauthorized.

## 4. Explicitly out of scope

- Prompt, Plan or Mastery authorization.
- Adding fork nodes or aliases to `skill_tree.json`, focus selection or persistent learner state.
- A claim that every fork wins material against every legal defence.
- Queen or king as the forking piece; the canonical proof currently covers knight, bishop, rook and pawn.
- Forks whose payoff is absent from the complete stored continuation.
- New puzzle UI, accepted answers, runtime engine/model calls, fresh Stockfish analysis or a parallel caption path.
- Admission backfill, production writes, feature flags, pushing or deployment.
- Pin/skewer, forced mate, opening-plan or later Phase 3 families.

## 5. Success criteria

- Every selected fire and every currently stored candidate independently satisfies the locked geometry, consequence and payoff contract.
- All 25 controls correctly abstain across five distinct failure modes.
- The packet clears the existing Caption precision, Wilson-bound, source-count and zero-critical-error gates.
- Every rendered positive caption names the move, moved piece, fork square and all target squares, then ends with one reusable board-search habit.
- Prompt, Plan, Mastery, skill identity and exact-concept recovery remain absent.
- A later prospective study may test whether players begin spotting multi-target moves unassisted; this phase makes no improvement claim.

## 6. Open questions

- **Question:** Can fork recognition become a persistent personal focus?
  - **Why unresolved:** there is no canonical learner skill, independently sampled opportunity/recall packet or real-game transfer evidence.
  - **Unblocking step:** a later Plan/Mastery scope must define the skill and opportunity contract, then meet the stronger recall and prospective-transfer bars.

- **Question:** When may the coach say “this wins a piece” rather than only describe the fork geometry?
  - **Why unresolved:** one complete stored principal variation proves the observed payoff line, not every meaningful opponent defence.
  - **Unblocking step:** validate an all-defence or stored multi-candidate proof whose visible wording matches that stronger claim.

## 7. Pre-code requirements

- The Complete Coaching System architecture and Phase 3 implementation order are approved.
- The Phase 0 bake-off selects `tactic:fork_with_stored_payoff` second.
- The existing-surface audit is surfaced to Mohit and locked as EXTEND.
- The read-only census confirms enough distinct positive sources, all four supported forking pieces and all five negative strata.
- Promotion thresholds are inherited from the detector-quality threshold lock; the extra fifth negative stratum is justified by measured corpus supply.
- The exact visible claim and plain-language example are written before runtime code changes.
- No runtime edit starts until the accompanying data lock and pre-code audit pass.
