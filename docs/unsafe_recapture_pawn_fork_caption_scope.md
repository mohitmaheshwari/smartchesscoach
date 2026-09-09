# Unsafe Recapture Pawn-Fork Caption — Scope

**Status:** LOCKED — Mohit approved the exact deterministic direction on 2026-09-09 and said “go for it please.”

## 0. Existing surfaces audit

ChessGuru already has one central Game Review caption path. `caption_pipeline.py` gathers facts for an opponent mistake, `pattern_catalog.py` describes the user's immediate reply, and `R12_blunder.json` chooses the sentence the player reads. `GameDecryptionV5.jsx` displays that sentence and already lets the player step through moves mentioned in it.

The same backend also has one trusted legal-replay path, `stored_line_verifier.py`, which replays stored continuations and preserves the identity, square, captures, checks, and relationships of every piece. `caption_facts.py` already uses that replay evidence for other verified explanations.

The overlap is deliberate: the current caption can already say `Play Nxe4`, and the generic immediate-move helper can say that the move takes a pawn. The genuine missing value is the reason the move works after the obvious recapture: `Rxe4 d5` attacks the rook and bishop together. No current opponent-caption fact proves that capture → recapture → pawn-fork chain, so the generic sentence wins.

**Decision: EXTEND existing.** Add one reusable proof family to the central stored-line facts and let the existing opponent-caption selector prefer it. Do not create another caption engine, renderer, move replayer, or teaching surface.

## 1. What it is

When the strongest move looks impossible because the opponent can immediately take the attacking piece, ChessGuru checks the continuation before speaking. If a pawn push then attacks the recapturing piece and another target together, the review explains that hidden idea in ordinary language and shows the exact moves that prove it.

## 2. What the user sees

For the reported position:

> Opponent's Re1 is an inaccuracy. Play Nxe4. If Rxe4, d5 attacks their rook at e4 and bishop at c4 together. After Bxd5 Qxd5, your knight and their bishop both come off the board. Before recapturing, check whether a pawn push can attack two pieces.

For the second real stored example:

> Opponent's Nf6 is a major mistake. Play Nxc4. If Qxc4, d5 attacks their queen at c4 and pawn at e4 together. After Qe2 dxe4, you also take their pawn. Before recapturing, check whether a pawn push can attack two pieces.

If the stored line does not legally prove every named move, piece, square, and payoff, the player sees the existing safe fallback instead. There is no guessed explanation.

## 3. In scope (V1)

- Recognize a legal stored line shaped as capture → exact recapture → pawn move attacking the recapturing piece and at least one other enemy target.
- Require the stored continuation to prove one of two concrete endings: the pawn takes the second target after the first target moves, or the pawn is captured and that capturing piece is recaptured.
- Preserve the identity of the initially captured attacker and every later target; square coincidence alone is not proof.
- Produce typed, board-derived facts for every move, piece, square, and ending used in the caption.
- Prefer this verified explanation over the current immediate `trades his pawn` fallback on opponent mistakes.
- Cover both approved real examples and adversarial near-misses with deterministic tests.
- Bump the stored V5 caption version so existing reviewed games can regenerate through the normal path after deployment.
- Keep the strict caption-source CI gate mergeable when that version file is
  touched: scan only added or modified lines, while continuing to block every
  new noncentral caption. Unchanged legacy findings remain visible in the
  whole-backend audit and are not silently exempted.

## 4. Explicitly out of scope (V1)

- New Stockfish, Maia, Otter, tablebase, or LLM calls.
- Guessing beyond the stored continuation or extending its search horizon.
- Calling every pawn double attack a fork worth teaching; this version requires the exact capture-and-recapture setup.
- User-side mistake captions; V1 corrects the reported opponent-move learning opportunity first.
- A new Game Review component, animation, lesson, detector registry, or database collection.
- Naming the idea “center-fork trick” in player copy; V1 teaches the visible geometry first.
- Claiming a material win when the line proves only a fair exchange or a positional improvement.

## 5. Success criteria

- In both real examples, a player is told what the pawn push attacks and can follow every named move on the existing board.
- A player can state the reusable lesson after the line: before recapturing, check whether a pawn push attacks two pieces.
- The reported `Re1` caption no longer says only `Nxe4 — it trades his pawn`.
- Every positive caption field is reconstructed from legal board replay; illegal, incomplete, identity-mismatched, one-target, or unresolved lines produce no new claim.
- Existing opponent captions remain unchanged when this exact mechanism is absent.

## 6. Open questions

- **Question:** Should a later version name this the “center-fork trick” after explaining it?
- **Why unresolved:** The name can aid memory, but it may be jargon for a 600–1000 player and not every qualifying position is literally in the center.
- **Unblocking step:** Keep V1 geometric and compare player recognition later; naming is not required for correctness.

## 7. Pre-code requirements

- The central caption and legal-replay owners are identified; no parallel source will be added. **Met.**
- At least two real stored examples demonstrate the mechanism. **Met:** `Re1 Nxe4 Rxe4 d5 Bxd5 Qxd5` and the anonymized stored line `Nf6 / Nxc4 Qxc4 d5 Qe2 dxe4`.
- No new numeric threshold or ranking formula is introduced. **Met.**
- Literal player copy is approved as the product target. **Met by Mohit's 2026-09-09 “go for it please” after the exact caption direction.**
- The pre-code audit passes before implementation begins. **Met:** `docs/unsafe_recapture_pawn_fork_caption_precode_audit_2026_09_09.md`.
