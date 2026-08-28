# Detector exchange-truth formula lock (2026-08-27)

Status: LOCKED FROM READ-ONLY PRODUCTION MEASUREMENT

## Decision locked

Use a board-mutating legal exchange search for player-facing claims that a
piece is hanging. Keep the older static swap-list only for explicitly
hypothetical shape research where the evaluating side may not be the side to
move.

For the `free_piece` label, require that the advertised capture has no legal
immediate recapture on the post-capture board.

## Evidence

Production snapshot on 2026-08-27:

- `TAC_HANGING_PIECE`: 24,793 stored fires.
- Current static SEE: retained 24,793, but independent legal replay found
  3,571 non-winning/non-legal exchange claims (14.4%). The primary
  `moved_into_hanging_square` branch had 2,681 concerns in 15,555 fires
  (17.2%).
- Legal-capture-only gate: retained 23,782 (95.9%) but still retained 2,560
  exchanges where taking the claimed piece did not win material.
- Board-mutating optimal legal exchange: retained 21,222 (85.6%) and removed
  all 3,571 measured non-winning cases by construction. It also respects check,
  pins, king captures and x-rays because every candidate capture is pushed on
  a real board.
- `free_piece`: 1,849 stored fires; 7 had a legal post-capture recapture hidden
  by an x-ray, including 2 non-winning captures. The strict no-recapture rule
  retains 1,842 (99.62%).
- Runtime bake-off on 1,999 random production moves: exact legal exchange
  averaged 0.1505 ms/move versus 0.0115 ms/move for static SEE; 257/1,999
  results differed. The additional ~0.14 ms/move is acceptable for postgame
  analysis and avoids a separate fast-but-unsafe player-facing truth path.

## Rejected candidates

- Keep current static SEE: rejected because its verifier shared the same
  approximation and reported 200/200 while the independent full-corpus replay
  found thousands of concerns.
- Add only an immediate-legality gate: rejected for hanging-piece attribution
  because it still calls equal or losing exchanges “hanging.”
- Use Stockfish centipawn loss or first PV move as the truth label: rejected
  because those indicate move cost/engine choice, not the causal material
  claim.

## Measurement method

Read-only aggregation over production `game_analyses.decryption_v5_data`.
Each claimed move was replayed from `fen_before`; legal captures on the claimed
square were recursively pushed with optimal stop/recapture decisions. Related
records were not written back to production.

This lock does not promote either detector. Blinded semantic review and the
negative-case floors in `docs/detector_quality_threshold_lock_2026_08_27.md`
still apply.
