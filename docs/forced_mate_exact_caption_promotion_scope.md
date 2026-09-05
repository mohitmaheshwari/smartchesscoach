# Forced-Mate Exact Caption Promotion — Scope

## 0. Existing surfaces audit

- `missed_mate_detector.py` already proposes a missed-mate candidate from the stored best line.
- `forced_mate_puzzle_proof.py` already owns legal replay of that stored line and rejects lines that do not terminate in checkmate for the player.
- `verified_puzzle_builder.py` already routes the proof through the shared admission boundary.
- `verified_puzzle_feedback.py` already owns the only verified-puzzle explanation surface.
- `detector_quality.py` is the sole authorization source and currently keeps `tactic:forced_mate_exact` at Shadow.
- `caption_facts.py`, `distilled_caption_service.py`, Game Review, and the decryption voice contain older mate wording, but none is a second authority for this proof-backed puzzle family.
- `skill_tree.json` does not provide a reviewed forced-mate opportunity, transfer, or mastery contract that this promotion may invent.

The overlap is complete. The new value is an independent promotion packet and wording whose strength exactly matches what stored analysis plus legal replay can prove.

**Overlap decision: EXTEND.** Do not add a mate recognizer, caption pipeline, learner skill, focus calculation, grader, or progress state.

## 1. What it is

This promotion lets ChessGuru explain a missed mating opportunity after a puzzle attempt when the stored engine evidence identifies the best move and an independent legal replay reaches checkmate for the player. The explanation shows the first move and the verified finish in plain language. It does not call the idea forced unless the stored evidence and promotion audit independently support that stronger statement, and it does not diagnose a recurring weakness.

## 2. What the user sees

Mate in one:

```text
Not this time. Compare your move with Qg7#.

Qg7# puts your queen on g7 with checkmate. The king on h8 has no legal reply.
Before playing a quiet move, examine every check and count the king's escape squares.
```

Longer verified stored continuation:

```text
Not this time. Compare your move with Kg1.

Kg1 starts the mating continuation recorded for this position. The verified line ends with Ra8#, when your rook reaches a8 and Black has no legal reply.
Before playing a quiet move, examine every check, capture and direct threat first.
```

If the available facts prove only one legal stored continuation and not every defence, the caption says `the verified line` or `the stored continuation`; it does not say `forced`, `unavoidable`, or `mate in N`.

## 3. In scope (V1)

- Reproduce the complete stored `tactic:forced_mate_exact` candidate population across both verified puzzle pools without rerunning game analysis.
- Independently parse the initial position, played move, best move, and full stored continuation.
- Verify legal move order, mating side, terminal checkmate, first move, final mating move, mating piece and square, king square, and legal-reply count.
- Measure which stored fields, if any, independently establish forcedness or mate distance rather than merely one mating continuation.
- Create a privacy-safe positive packet with enough distinct sources to clear the existing Caption Wilson-bound bar and negative controls covering every measured failure family.
- Recheck the full candidate population for illegal, truncated, wrong-side, non-terminal, low-consequence, and fact-mismatch cases.
- Promote only the exact quality ID from Shadow to Caption if the locked packet passes with zero critical errors.
- Extend the existing proof facts and centralized renderer only as required for the verified wording above.
- Keep Prompt, Plan, Mastery, focus selection, puzzle identity, accepted moves, and recovery identity unchanged.

## 4. Explicitly out of scope (V1)

- Claiming `forced`, `mate in N`, or `only move` from a single principal variation.
- Proving all defensive branches with a new runtime chess engine or exhaustive search.
- Promoting `missed_mate`, `allowed_mate`, back-rank mate, or any older caption rule by association.
- Prompt, Plan, Mastery, recurrence, focus, recovery, or learner-skill authorization.
- Reanalysis of existing games, production writes, backfills, deployment, or visible progress changes.
- A new mate lesson, puzzle UI, runtime LLM call, or parallel caption path.

## 5. Success criteria

- Every selected positive and every stored candidate satisfies the locked legal-replay, terminal-state, actor, consequence, and distinct-source contract.
- Every selected negative abstains for the intended independent reason.
- Every rendered caption names only board facts the independent verifier proves: first move, final mating move, mating piece and square, king square, and zero legal replies at the terminal position.
- No player-facing caption says `forced`, `unavoidable`, `mate in N`, or `only move` unless the data lock establishes an independent all-defence proof for that exact claim.
- The family remains absent from Prompt, Plan, Mastery, persistent focus, and exact-concept recovery.
- Product learning success remains unclaimed until a later prospective transfer study measures unassisted mate recognition in unseen positions.

## 6. Open questions

- **Question:** Do stored analysis fields prove forced mate or only preserve one checkmating principal variation?
  - **Why unresolved:** legal replay proves the shown line, not that every opponent defence loses.
  - **Unblocking step:** census the stored mate score/distance/provenance fields and compare them with an independent engine audit on the locked packet if the stronger wording is desired.
- **Question:** Can forced mate become a persistent learner focus?
  - **Why unresolved:** there is no reviewed comparable-opportunity denominator, recall packet, or transfer contract.
  - **Unblocking step:** separately scope an opportunity detector and prospective unseen-position study after Caption truth is established.
- **Question:** How long a line should be displayed?
  - **Why unresolved:** correctness does not determine comprehension for 600–1500 players.
  - **Unblocking step:** V1 shows the first move and verified finish; later comprehension testing may add a short replay without altering proof authority.

## 7. Pre-code requirements

- The full read-only census establishes distinct-source supply, line lengths, source-pool coverage, stored mate fields, and every measurable rejection family.
- Packet size is derived from the existing Wilson lower-bound gate, not selected from preference.
- Independent gold does not import the canonical missed-mate detector, forced-mate proof builder, stored-line verifier, admission verdict, or stored quality verdict.
- Literal mate-in-one and longer-line wording is fixed before runtime edits.
- A pre-code audit confirms that every visible phrase is covered by an independent verifier fact.
- The approved Complete Coaching System Phase 3 sequence selects forced mate fourth, and Mohit's current instruction to proceed starts this packet.
