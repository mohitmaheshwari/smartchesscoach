# m8 b6 — "wins material" engine-speak fires when the win is positional

**Game:** `db4ea92d` move 8
**FEN:** `r2qkb1r/pp3ppp/2n1bn2/2Ppp3/1P6/P3P3/5PPP/RNBQKBNR b KQkq - 0 8`
**Played:** `b6` (cp_loss = 116)
**Current caption:** *"b6 is a mistake. a5 was better. a5 wins material in the resulting line."*

## Engine analysis (Stockfish depth 18)

| Move | eval (user POV) | Comment |
|---|---|---|
| Before move | **+137cp** | Black slightly better (Black to move) |
| After b6 (played) | **+25cp** | Black gave up most of the edge |
| After a5 (best) | +140cp | Keeps the advantage |

Best PV (after a5): `a5 b5 Na7 Nf3 e4 Nd4 Bxc5 Nc3 Nc8 Na4 Bd6`

## Diagnosis

The caption claims "a5 wins material in the resulting line" — this fires when `missed_tactic_kind = "material"` (the LOW engine-speak variant in R12). The detector saw user-side captures in the PV that net some material gain, but the eval guard (require eval >= +400cp from user POV) failed.

Looking at the PV: `a5 b5 Na7 Nf3 e4 Nd4 Bxc5 ...` — the user gets Bxc5 (winning a pawn? checking the position, c5 has a white pawn). So a5 b5 → user retreats knight to Na7. Then Nf3 e4 (kicking knight), Nd4 (white centralizes), and user plays Bxc5 winning the c-pawn.

But +140cp is below our piece_capture eval guard (+400cp). So we don't claim "wins the pawn on c5"; we just say the engine-speak "wins material."

The cp_loss is 116 — barely above R12 threshold. And we don't have user_is_winning (eval +137cp is below the +200 threshold).

## Suggested fix

Two possible directions:

1. **Improve the "material" framing.** Instead of "wins material in the resulting line," say something like "a5 keeps your queenside under control" or describe the positional gain. This would require the detector to recognize positional vs material outcomes.

2. **Add an opening-curriculum entry for this Benoni-like setup.** The position arose from 1.d4 d5 2.c4 e6 3.Nc3 Nf6 4.Nf3 c5 5.cxd5 exd5 6.dxc5 d4 (?) — actually unclear without PGN. If this is a known opening (Benoni or Albin reversed), a curriculum tree could teach the principle.

For now, accept that this is a LOW caption with no clean fix.

## Category

`pattern_b_material_engine_speak_low_eval_guard`
