# m5 Qf6 — bizarre opening, no curriculum applies

**Game:** `f4125049` move 5
**FEN:** `rnbqk1nr/pppp1ppp/8/2b5/P6P/4P3/1PP3P1/RNBQKBNR b KQkq - 0 5`
**Played:** `Qf6` (cp_loss = 144)
**Current caption:** *"Qf6 is a mistake. d5 was better. Opponent's strongest reply: Nc3."*

## Engine analysis (Stockfish depth 18)

| Move | eval (user POV) | Comment |
|---|---|---|
| Before move | **+306cp** | Black is already winning by ~3 pawns |
| After Qf6 (played) | **+184cp** | Still winning |
| After d5 (best) | +316cp | Keeps the bigger advantage |

Best PV (after d5): `d5 c4 Nf6 Nc3 Bd6 Be2 dxc4 Bxc4 Nc6 Nf3 Bg3+`

## Diagnosis

This is from a bizarre game — white opened with 1.h4 (?) e5 2.a4 (?) followed by some kind of exchange that left black up 3 pawns by move 5. The opening is totally off-book; no curriculum applies.

**Position-eval analysis:**
- Black is winning by 3 pawns (eval_before = +306, eval_after_played = +184)
- After Qf6, still winning by ~1.8 pawns
- `user_is_winning` is TRUE (above +200cp threshold... wait, +184 is below threshold)
- cp_loss = 144 (R12 fires at "mistake" tier)

Hmm — eval_after_played = +184cp is JUST below our +200cp threshold for `user_is_winning`. So the reframing doesn't fire. Caption falls to `user_with_best_and_why` with the engine-speak why.

If we lowered the threshold slightly (to +150cp), this position would get reframed. But that creates noise in other balanced positions.

## Suggested fix

This is the "borderline winning" edge case. Options:

1. **Lower the user_is_winning threshold to +150cp.** Tradeoff: more positions get "you're still winning" reframing including ones that aren't really winning.

2. **Use a continuous "advantage magnitude" framing.** Three tiers instead of binary:
   - clearly_winning (>= +500cp): "you're winning easily"
   - slightly_winning (+150 to +500cp): "you have the advantage"
   - balanced (-150 to +150): no reframing

3. **Accept this as engine-speak.** The position is so weird (1.h4 e5 2.a4 ...) that no real teaching applies anyway.

## Category

`pattern_c_borderline_winning_threshold`
