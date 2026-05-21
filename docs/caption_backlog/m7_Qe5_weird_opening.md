# m7 Qe5 — same weird game as m5, black missed Qxb2

**Game:** `f4125049` move 7
**FEN:** `rnb1k1nr/pppp1ppp/5q2/8/P5QP/4B3/1PP3P1/RN2KBNR b KQkq - 0 7`
**Played:** `Qe5` (cp_loss = 185)
**Current caption:** *"Qe5 is a mistake. Qxb2 was better. Opponent's strongest reply: Qe2."*

## Engine analysis (Stockfish depth 18)

| Move | eval (user POV) | Comment |
|---|---|---|
| Before move | **-252cp** | Black is now LOSING by ~2.5 pawns |
| After Qe5 (played) | **-452cp** | Black falls further |
| After Qxb2 (best) | -267cp | Limits damage |

Best PV (after Qxb2): `Qxb2 Qd4 Qxd4 Bxd4 f6 Nc3 Nc6 Nf3 Nge7 h5 h6`

## Diagnosis

This is the same game as [m5_Qf6_weird_opening.md](m5_Qf6_weird_opening.md), two moves later. Black went from winning by 3 pawns to losing by 2.5 pawns in two moves of strange play.

**Position-eval analysis:**
- Black is losing (eval_after_played = -452cp, below our -200cp threshold)
- `user_is_losing` is TRUE
- cp_loss = 185 (mistake tier)
- `user_losing_position` SHOULD fire... but doesn't, because `why_user_reply` fires first (Opponent's strongest reply: Qe2) and blocks the position-eval reframing.

## Suggested fix

Same as [m28_Bd4_winning.md](m28_Bd4_winning.md) — gate `why_user_reply` and `why_user_missed_material` on `user_is_winning: false, user_is_losing: false`. After fix:

> *"Qe5 doesn't change much — you were already losing. Qxb2 would have made the loss slower."*

Caveat: per [m20_Qe6_losing.md](m20_Qe6_losing.md), `user_is_losing` should also consider eval_before. Here eval_before = -252cp (already losing), so the framing is accurate — black WAS already losing before Qe5.

## Category

`pattern_a_eval_reframing_blocked_by_engine_speak`
