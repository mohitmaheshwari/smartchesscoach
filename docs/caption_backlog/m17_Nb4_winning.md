# m17 Nb4 — winning position (+465cp), captioned "is a mistake"

**Game:** `f4125049` move 17
**FEN:** `r4rk1/ppp2ppp/2n5/P2p3Q/8/4B3/2PN2P1/qN2KB2 b - - 0 17`
**Played:** `Nb4` (cp_loss = 125)
**Current caption:** *"Nb4 is a mistake. Rae8 was better. Opponent's strongest reply: Kf2."*

## Engine analysis (Stockfish depth 18)

| Move | eval (user POV) | Comment |
|---|---|---|
| Before move | **+570cp** | Black winning by ~5.7 pawns |
| After Nb4 (played) | **+465cp** | Still winning by ~4.65 |
| After Rae8 (best) | +559cp | Slightly preferred |

Best PV (after Rae8): `Rae8 Kf2 Rxe3 Kxe3 Qxa5 Ke2 g6 Qh4 Re8+ Kd1`

## Diagnosis

Black is winning by 4-5 pawns. Above our `user_is_winning` threshold (+200cp). Same `why_user_reply` issue as m28/m29 — opp_reply_san is "Kf2", so the engine-speak why-clause fires and blocks `user_losing_position`/`user_winning_position`.

Note: this is borderline. eval_after_played = +465cp, well above +200cp threshold; eval_before = +570cp. The cp_loss is 125 (just over R12's 100cp threshold).

## Suggested fix

Same as [m28_Bd4_winning.md](m28_Bd4_winning.md). After the fix:

> *"Nb4 is fine — you're still winning. Rae8 would have kept the pressure on."*

## Category

`pattern_a_eval_reframing_blocked_by_engine_speak`
