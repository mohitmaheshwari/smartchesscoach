---
name: v5-qg2-data-corruption
description: One V5 move record (game a50ddf30, move 10 black "Qg2") has fen_before showing the black queen ALREADY on g2 — impossible if Qg2 is the actual move. Stockfish crashed analyzing this position. Suggests fen_before was stored as fen_after OR the move_san is misrecorded. Single-move; root cause not yet traced.
metadata:
  type: project
---

Surfaced 2026-05-17 while triaging Parth fb_49f1b336b497. The bug entry
has:
- `fen`: `r1b1k1nr/pppp1Npp/8/8/1bBPP3/3P4/PPP2PqP/RNBQK2R b KQkq - 0 10`
  (rank 2 = `PPP2PqP` → black queen on g2)
- `move_san`: `Qg2`
- `cp_loss`: 182, `eval_before`: -9, `eval_after`: 173
- Follow-up caption referenced *"Opponent plays Nxh8 winning your rook"*

If the queen is already on g2, the move `Qg2` is meaningless. Either:
1. fen_before was stored as fen_after (the queen JUST moved to g2, so
   the system captured post-move state by mistake), OR
2. move_san is wrong — the actual move was something else from g2
   (e.g., `Qxh1+`) and the SAN got truncated/garbled.

The Nxh8 follow-up is consistent with white's f7 knight capturing
black's h8 rook — that move is available regardless of which black
move preceded, but supports the position-context being roughly right.

## Stockfish behaviour

Engine crashed when asked to analyse this FEN at d22 (exit code -11).
The position may be technically legal but unusual enough to trip
something in Stockfish's setup, OR the FEN is illegal in some subtle
way (counter mismatch, half-move clock, etc.).

## What to investigate when Docker is back

1. **Compare adjacent moves' fen_before vs fen_after.** If move 9's
   `fen_after` matches move 10's `fen_before` literally, then the V5
   pipeline is consistent and Parth's reported FEN may have a separate
   widget-side bug. If they diverge, the pipeline writes inconsistent
   FENs somewhere.

2. **Check the PGN.** What did black actually play on move 10?
   `db.games.find_one({"game_id": "a50ddf30-..."}, {"pgn": 1})` — read
   the SAN directly from the source PGN. Compare to V5's stored
   move_san.

3. **Check if `Qg2` is a parsing artifact.** Sometimes ambiguous SANs
   (e.g., when two queens could move to the same square) get
   abbreviated. But the position only has one black queen, so this
   shouldn't apply here. Worth verifying anyway.

4. **Stockfish crash repro.** Run `stockfish` interactively with
   `position fen <FEN> / go depth 22` to see if the engine errors
   out cleanly or genuinely crashes. If crash, the FEN is malformed
   in a way python-chess accepts but Stockfish rejects — likely the
   `pppp1Npp` (rank 7) has a white knight in the middle of black
   pawns, which is fine, but could be a half-move-clock or
   en-passant-target issue.

## Why this isn't a code-fix priority

- Single-move occurrence noticed so far. May be isolated bug.
- The user-facing caption *"Qg2 loses about 2 pawns. Qxh2 was better.
  Opponent plays Nxh8 winning your rook."* — if "Qg2" in the caption
  is wrong, that's user-visible. But cp_loss=182 and the strategic
  framing are accurate to the game.
- Mostly the caption reads odd ("Qg2" when there's a queen on g2 the
  user might be confused about) but isn't catastrophically wrong.

## Related

- `[[feedback-chess-content-verification]]` — audit at the rendered
  string layer. The "Qg2" string is wrong if the actual move was
  Qxh1+; a more thorough scan of V5 records for FEN/SAN consistency
  would find any other corrupted moves.
