# m20 Qe6 — clearly losing, deserves "you were already losing" framing

**Game:** `c25fea91` move 20
**FEN:** `4rk2/p1p2ppp/2p3q1/8/5B2/2PP2P1/P1P1bPQP/4R1K1 b - - 7 20`
**Played:** `Qe6` (cp_loss = 321)
**Current caption:** *"Qe6 is a serious mistake. Bg4 was better. Opponent's strongest reply: Be3."*

## Engine analysis (Stockfish depth 18)

| Move | eval (user POV) | Comment |
|---|---|---|
| Before move | **-104cp** | Black slightly worse but close to balance |
| After Qe6 (played) | **-395cp** | Black now clearly losing |
| After Bg4 (best) | -122cp | Limits damage |

Best PV (after Bg4): `Bg4 Rxe8+ Kxe8 f3 Be6 Qf2 Qh5 Bxc7 Qb5 c4`

## Diagnosis

This is a real mistake — cp_loss = 321 (well into "serious" tier). Black went from slightly worse (-104) to clearly losing (-395) with Qe6.

`user_is_losing` is TRUE after the played move (-395 < -200). So the `user_losing_position` variant SHOULD fire... but it doesn't, for the same reason as Pattern A: `why_user_reply` fires first, sets why_clause, blocks the position-eval reframing.

If the fix from [m28_Bd4_winning.md](m28_Bd4_winning.md) ships, this caption becomes:

> *"Qe6 doesn't change much — you were already losing. Bg4 would have made the loss slower."*

Honestly this is debatable — Black WAS only slightly worse (-104) before Qe6, and Qe6 turned it into a real loss. So "you were already losing" is too soft. The current caption ("is a serious mistake") is actually more accurate.

Maybe `user_losing_position` should require user_is_losing BEFORE the played move (eval_before_user ≤ -200), not just eval_after_played. Otherwise we're confusing "you made the position lose" with "you were already losing."

## Suggested fix

Refine `user_is_losing` semantics: fire only when eval_before_user (not just after) was already losing. For this position, eval_before_user = -104cp, so user_is_losing should be FALSE. Then the caption stays as "is a serious mistake" — which is the right framing because Qe6 IS what made it serious.

## Category

`pattern_b_position_eval_threshold_uses_wrong_eval`
