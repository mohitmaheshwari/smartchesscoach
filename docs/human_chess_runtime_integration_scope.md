# Human Chess Runtime Integration — Scope

**Status:** LOCKED — Mohit approved completion on 2026-09-01 with “go ahead and complete it then, with 100% accuracy.”
**Parent:** Human Chess Intelligence research and the merged Personalized Game Review Quality V2.

## 0. Existing surfaces audit

Game Review already has one central caption decision, one typed review-event adapter, one consistency gate and one validator-facing comparison surface. Play with Coach already has a Stockfish opponent and a deterministic blunder guard. Training already has one admitted puzzle pool and a prospective first-attempt evidence contract. Endgame lessons already read one canonical theory tree and use committed Syzygy evidence for content admission. A provider-neutral Maia-2/Otter adapter already exists, but no production call site uses it.

The overlap is therefore nearly complete. The missing value is governed runtime evidence: exact endgame truth attached to eligible real-game decisions, and human-move likelihood attached to already-verified choices. The implementation will **EXTEND** these existing authorities. It will not create a new coach, caption system, endgame catalog, puzzle pool, mastery store or human-model truth source.

## 1. What it is

ChessGuru will use an exact endgame source to recognize when a move preserves or changes a forced win or draw, and will use Otter or Maia to estimate which legal moves a player is likely to consider. Exact tablebase evidence may explain chess truth. Human-model evidence may make safe coaching choices more understandable and human-like, but it can never decide whether a move is correct or invent a weakness.

## 2. What the user sees

### Game Review

```text
YOU LET THE DRAW SLIP

This king-and-pawn ending was still a draw before Kf4. After Kf4, every reply
loses. Kf2 kept the draw because it stopped their king from getting in front
of the pawn.

Remember: in a pawn ending, check the result after every king move.
```

If exact evidence is unavailable, the review keeps the existing verified Stockfish explanation and makes no tablebase claim.

### Endgame lesson

```text
Your move keeps the position won. It is not the shortest route, but it is
still correct. Two other moves also preserve the win.
```

### Play with Coach

```text
The opponent chooses a move players around this level genuinely consider,
but only after the normal chess-safety guard accepts it.
```

The player is not shown model percentages or technical model names.

### Puzzle training

There is no new visible difficulty label in this release. The system records a shadow findability estimate and later compares it with real first, unassisted attempts before changing puzzle order.

## 3. In scope (V1)

- One canonical exact-endgame service with strict legal-position, complete-move-partition, WDL and provenance validation.
- Local Fathom/Syzygy configuration that fails closed when its binary, tables, coverage or response is unavailable.
- Exact endgame evidence attached during review generation and persisted with the move decision, never inferred from prose.
- Exact result-preserving alternative grading for covered endgame lessons and puzzles.
- One canonical human-policy evidence contract built on the existing provider-neutral engine.
- Otter with verified move history as the preferred provider; Maia-2 as the measured no-history fallback.
- Analysis-time storage of provider, version, input fingerprint, legal probabilities, entropy, played-move rank, coverage and warnings.
- No database or API request failure when either model is absent; absence is stored as an explicit reason.
- Human-policy selection in Play with Coach only inside a Stockfish/tablebase-approved candidate set, behind a separate default-off flag, with the existing opponent as fallback.
- Maia puzzle findability and verified distractor candidates stored in shadow only; no public ordering or grading change.
- Independent flags, structured observability, deterministic cache keys and rollback without rewriting mastery.
- Tests for illegal moves, incomplete tablebase partitions, stale model versions, absent weights, model exceptions, unsafe candidates, unsupported endgame claims and legacy-response parity.

## 4. Explicitly out of scope (V1)

- Maia, Otter or an LLM deciding chess correctness, detector identity, mastery or a psychological cause.
- “You rushed” or “you knew this” language; the clock ablation rejected that inference.
- Player-visible Maia puzzle difficulty before prospective first-attempt calibration.
- Using the 25cp sound-and-findable band for player-facing teaching before the required blinded coach review.
- Replacing Stockfish outside tablebase-covered positions.
- Downloading model weights or tablebase files during a user request.
- A second endgame catalog, caption renderer, player profile or progress vocabulary.
- Bulk historical Stockfish analysis.

## 5. Success criteria

- Zero false tablebase-result claims across every covered regression and corpus position; incomplete evidence always abstains.
- Every human-model move is legal, versioned and subordinate to a verified candidate set; an unsafe model preference never reaches the board.
- Model absence, timeout, corrupt output or unavailable tables preserve the current production behavior.
- Game Review, lesson grading and puzzle feedback agree on the exact result-preserving move set for the same covered position.
- Play with Coach validation shows no free-piece/queen hang introduced by the human-policy selector and no increase in guard failures.
- Shadow puzzle evidence joins cleanly to real first, unassisted, measured-rating attempts without changing public difficulty.
- The player sees plain coaching language and never model scores, centipawns or unsupported intent claims.

## 6. Open questions

- **Question:** When may the 25cp same-WDL alternative policy become visible? **Why unresolved:** its engine evidence passed, but blinded coach preference is external. **Unblocking step:** complete the approved blind packet and lock the winning policy.
- **Question:** When may Maia replace current puzzle difficulty? **Why unresolved:** historical attempts lack attempt-time rating and assistance. **Unblocking step:** deploy the prospective attempt contract, accumulate the clean cohort and calibrate on held-out outcomes.
- **Question:** How much local tablebase coverage is operationally affordable? **Why unresolved:** deployment storage is an infrastructure choice. **Unblocking step:** report eligible-position coverage for installed 5/6/7-piece tables; code remains coverage-neutral.

## 7. Pre-code requirements

- Start from the latest merged `origin/working-code` in a clean isolated worktree.
- Preserve the dirty main tree and import no whole stale files.
- Use the existing central caption, review-event, puzzle-attempt, endgame-content and opponent-guard authorities.
- Lock provider roles from the completed Stage 1–4 measurements; introduce no unmeasured numeric threshold.
- Keep every new feature default-off or shadow, except exact fully verified tablebase explanations under the enrolled Quality V2 review gate.
- Keep user-facing chess truth behind deterministic Stockfish/tablebase verification.
- Pass the six-point pre-code audit before editing runtime code.
