# m29 g6 — winning position, captioned "is a mistake"

**Game:** `db4ea92d` move 29
**FEN:** `6k1/5ppp/pp6/3p4/PP1bq1b1/5NP1/6KP/3Q4 b - - 0 29`
**Played:** `g6` (cp_loss = 223)
**Current caption:** *"g6 is a mistake. h5 was better. Opponent's strongest reply: a5."*

## Engine analysis (Stockfish depth 18)

| Move | eval (user POV) | Comment |
|---|---|---|
| Before move | **+712cp** | Black is winning by ~7.1 pawns |
| After g6 (played) | **+730cp** | Still winning by ~7.3 |
| After h5 (best) | +731cp | Tiny preference |

Best PV (after h5): `h5 h3 Bxf3+ Qxf3 g6 b5 axb5 axb5 Bc5 Qxe4`

## Diagnosis

Same root cause as [m28_Bd4_winning.md](m28_Bd4_winning.md). Black is up 7+ pawns. The cp_loss of 223 reflects engine preference, not a real mistake. `why_user_reply` fires ("Opponent's strongest reply: a5"), blocking the `user_winning_position` variant.

Note: this is the SAME GAME as m28 (`db4ea92d`), one move later. Both positions show the same failure mode.

## Suggested fix

Same as [m28_Bd4_winning.md](m28_Bd4_winning.md) — gate `why_user_reply` on `user_is_winning: false`.

After fix, caption would read:

> *"g6 is fine — you're still winning. h5 would have kept the pressure on."*

## Category

`pattern_a_eval_reframing_blocked_by_engine_speak`
