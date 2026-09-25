# Trap Corpus Independent Review Protocol

**Status:** ACTIVE INDEPENDENT REVIEW
**Date:** 2026-09-04
**Purpose:** Define the chess-truth and evaluation gates for the Lichess trap-coverage measurement before seeing its results.

## Decision

Measure the existing `lichess_puzzles` corpus before acquiring more games. The measurement may nominate evidence, but it may not promote a trap, detector, caption, or player-facing claim by itself.

`backend/data/traps.json` remains the single source of authored trap content. This review must not create another trap library or copy the 54 definitions into a second table.

## Independent baseline found before the corpus result

The current workspace contains 54 trap entries across 28 opening families.

- All 54 entries contain the currently required fields.
- Only 51 of 54 complete authored sequences are legal from the initial position.
- The illegal entries are `Lolli Variation`, `Tarrasch Trap (Open Lopez)`, and `Halosar Trap`.
- `trap_scanner.py` infers the setter from the side to move after the setup. That conflicts with canonical `trap_color` for 23 of 54 traps. The scanner must use `trap_color`; whose turn follows the setup is not the same fact as who owns the trap.
- `Elephant Trap` and `Marshall Trap` encode the same complete move sequence with the checkpoint boundary shifted by one ply. They must not count as two independent coverage examples.
- `Elephant Trap` and `Cambridge Springs Trap` have the same exact setup sequence. The current first-match recognizer returns the first entry, so the latter cannot be independently identified at that checkpoint.
- Of 343 authored trap-line steps, 332 are legally reached before the three broken sequences stop; those 332 rows collapse to 311 unique board positions. Coverage and dataset splitting must operate on position/game clusters, not raw rows.

A preliminary 20,000-node Stockfish screen scored 177 setter moves and 155 victim moves from the authored lines. Fourteen setter moves were more than 100 centipawns below the engine's preferred move, including two mate-scale disagreements. This is a quarantine signal, not a final verdict: illustrative continuations and low-node instability must be separated from moves that ChessGuru tells a player are correct.

### Runtime role fragmentation

The canonical `trap_color` fact is not consumed consistently:

- `caption_pipeline.py`, `trap_recognition.py`, and the rewritten concept detector read `trap_color`.
- `trap_scanner.py` treats the side to move after setup as the setter.
- `trap_intelligence.py` guesses the setter from an opening-family allowlist.
- `trap_library.analyze_game_for_traps()` guesses the beneficiary from `_BLACK_OPENINGS`.
- `concept_detectors/trap_detection.py` assumes every even trap-line step is a victim error and every odd step is a setter punishment.

The data disproves that last convention: 31 trap lines begin with a setter move and 23 begin with a victim move. Therefore role cannot be inferred from line-step parity, and “authored continuation” cannot automatically mean “victim mistake.” These paths must converge on canonical color plus verified per-checkpoint meaning before stored fires are regenerated.

### Quarantined historical lines

- The current Lolli entry incorrectly answers `Bxf7+` with illegal `Kxf7`; the legal theoretical response is `Ke7`, followed by White's central break `d4`.
- The current Open Ruy Lopez Tarrasch entry omits the actual setup (`...Be7`, `Re1`, `...O-O`, `Nd4`, `...Qd7`) and starts its continuation from the wrong position.
- The current Halosar entry uses illegal `...Bxc3`; the known Ryder Gambit line continues `...Bg4?` and `Nb5!` after long castling.

These entries remain quarantined rather than silently edited during Claude's measurement. The corrected Tarrasch position also demonstrates a schema requirement: both `...Qxe6` and `...fxe6` can be acceptable continuations. A single mandatory move per step is not sufficient for verified trap teaching.

Line references used only to nominate corrections (Stockfish and legal replay
still adjudicate the final data):

- `https://en.wikipedia.org/wiki/Two_Knights_Defense`
- `https://en.wikipedia.org/wiki/Ruy_Lopez%2C_Tarrasch_Trap`
- `https://en.wikipedia.org/wiki/Blackmar%E2%80%93Diemer_Gambit`

## Candidate reconstruction contract

For every Lichess puzzle considered:

1. Preserve the original `puzzle_id`, `game_url`, rating, popularity, themes, opening tags, FEN, and UCI solution.
2. Start from the stored FEN and legally apply `moves[0]`, the opponent's setup move. The resulting position is the first player decision position.
3. Replay the complete solution. Inspect every player solution ply, not only the first one. A relevant tactic may appear later in the solution.
4. Match board state, not opening name alone. A legal position identity includes piece placement, side to move, castling rights, and any legally relevant en-passant square; move counters do not define a different position.
5. Treat an opening tag only as a search hint. It is neither a trap label nor negative truth when absent.
6. Record whether the match is an exact canonical checkpoint, a legal transposition to that checkpoint, a continuation checkpoint, or merely a same-family candidate.
7. Never infer setter/victim from move parity or opening family. Use canonical `trap_color` and the actual side to move at the matched checkpoint.

## Engine adjudication contract

Every candidate promoted beyond `candidate_match` must be independently adjudicated from the reconstructed board.

- Verify legality and side to move before evaluating any claim.
- Record the Stockfish version and search limit.
- Evaluate the intended move and all materially equivalent alternatives, not only a single principal variation.
- Separate the victim's decisive error from quiet or forced continuation moves. A trap line does not require every victim move to lose evaluation.
- Separate an illustrative historical line from a move ChessGuru will praise as correct. Every praised or prescribed move must be sound in that position.
- A move tagged by Lichess may nominate a case; it cannot be its own independent semantic label.
- Mate, repetition, stalemate, and forced-recapture cases require explicit outcome checks rather than centipawn arithmetic alone.

## Hard-negative contract

Hard negatives must resemble a covered trap without containing a sound punishment. They may come from:

- the same opening and nearby move order but a materially different board;
- the same apparent motif with an extra defender, escape square, intermezzo, or changed king safety;
- a transposed-looking position where castling or en-passant rights change the truth;
- a tempting trap move that Stockfish refutes;
- the canonical setup where the supposed victim chooses a sound defense.

The absence of a Lichess theme or opening tag is not a negative label.

## Leakage controls

- Normalize `game_url` to its underlying game identifier. Different puzzle URLs or ply fragments from the same game belong to one split.
- Cluster identical decision positions and canonical trap continuations before splitting.
- Report per-opening and per-trap results. A large Italian Game stratum must not hide zero evidence for a thin family.
- If any learned ranker is evaluated, add a leave-opening-family-out result. Maia2 may rank human-likely choices but may not adjudicate chess truth.
- The final reviewed sample must be blinded to Lichess theme tags and to the candidate method that nominated it.

## Promotion states

The measurement must distinguish these states rather than returning one undifferentiated count:

1. `candidate_match` — nominated by tag, position, or move sequence.
2. `legal_match` — full reconstruction and claimed checkpoint are legal.
3. `engine_verified` — decision, punishment, and acceptable alternatives are verified.
4. `human_reviewed` — chess meaning and trap identity are independently reviewed.
5. `player_authorized` — the detector-quality gate explicitly permits the evidence on player surfaces.

Invalid, duplicate, ambiguous, and shadowed canonical entries remain visible in the report but cannot enter the eligible denominator.

## Acceptance gates

- Zero illegal lines among eligible canonical traps.
- Zero wrong-side setter/victim claims.
- Zero duplicate logical traps counted as independent evidence.
- Zero same-game or same-position leakage across evaluation splits.
- At least 95% precision on the blinded, stratified human-reviewed sample before player-facing use.
- Recall reported per trap and per opening against an independently adjudicated positive set. No recall target is locked until the available-positive distribution is known.
- Every player-facing example retains enough provenance to reproduce the board and engine decision.
- A detector remains fail-closed until its registry authorization changes; corpus volume alone cannot promote it.

## Review of Claude's eventual result

The independent review will check:

- whether all 54 source entries were considered but only eligible entries entered quality denominators;
- whether the three illegal lines, duplicate sequence, and first-match collision were handled explicitly;
- whether puzzle setup and later solution plies were replayed correctly;
- whether transpositions preserved full legal-position state;
- whether game and position clusters were isolated across splits;
- whether alternatives and hard negatives were engine-verified;
- whether coverage is reported as a distribution rather than converted prematurely into arbitrary `well-covered` thresholds;
- whether thin families alone justify any later targeted raw-game mining.

## Reproduction commands

From `backend/`, run the structural gate with:

```bash
python scripts/audit_trap_library_truth.py --strict
```

Run the engine evidence pass where Stockfish is installed with:

```bash
python scripts/audit_trap_engine_truth.py \
  --stockfish /usr/games/stockfish --nodes 20000 --multipv 5 \
  --output /tmp/trap-engine-audit.json
```

The structural output includes the SHA-256 of `traps.json`. Claude's report
must name the same hash, or explicitly declare and justify a different source
snapshot, before results can be compared.
